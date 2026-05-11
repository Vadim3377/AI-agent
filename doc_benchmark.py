"""
doc_benchmark.py — Documentation feedback loop benchmark.

Root cause of previous 100% flat results
-----------------------------------------
The base blueprint runs _run_single_shot(), which returns a JSON string in
`raw_output` (the documentation schema asks for fields like `docstrings_added`).
The mutated blueprint runs _run_documentation_loop(), which returns actual
Python code in `final_code`.

The benchmark was passing the JSON string to the AST checker, which found
zero Python symbols (total=0), defaulting coverage to 1.0 = 100%. Both
paths appeared identical because neither was being measured correctly.

Fix (two parts)
---------------
1. The base blueprint is run via a DIRECT prompt that explicitly asks for
   Python code back, not JSON. This is done by temporarily overriding the
   blueprint subdomain to force _run_documentation_loop even for the base,
   OR by using a separate direct LLM call for the base that returns code.

   Simpler: use a dedicated _run_doc_single_shot() call that bypasses the
   JSON schema entirely and asks directly for code.

2. The code extractor now tries (in order):
   a. final_code key (mutated loop path)
   b. Largest ```python ... ``` block in raw_output
   c. Largest ``` ... ``` block in raw_output
   d. raw_output itself if it parses as valid Python

Quality-aware scoring
----------------------
A docstring is COMPLETE only if it has:
- Args: section   for functions that take parameters
- Returns: section for functions that return a value
One-liner docstrings like '''Return the mean.''' score 0 on quality coverage.
This is where the LLM predictably falls short on helper functions,
giving the feedback loop something real to improve.
"""

import ast
import json
import os
import re
import textwrap
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# 10 multi-function modules
# ---------------------------------------------------------------------------

DOC_TASKS = [
    {
        "id": "stats_module",
        "code": textwrap.dedent("""\
            def mean(values):
                return sum(values) / len(values)

            def variance(values):
                m = mean(values)
                return sum((v - m) ** 2 for v in values) / len(values)

            def std_dev(values):
                return variance(values) ** 0.5

            def z_score(value, values):
                m = mean(values)
                s = std_dev(values)
                if s == 0:
                    return 0.0
                return (value - m) / s

            def normalise(values):
                if not values:
                    return []
                s = std_dev(values)
                if s == 0:
                    return [0.0] * len(values)
                return [z_score(v, values) for v in values]
        """),
    },
    {
        "id": "cache_module",
        "code": textwrap.dedent("""\
            class LRUCache:
                def __init__(self, capacity):
                    self.capacity = capacity
                    self.cache = {}
                    self.order = []

                def get(self, key):
                    if key not in self.cache:
                        return -1
                    self.order.remove(key)
                    self.order.append(key)
                    return self.cache[key]

                def put(self, key, value):
                    if key in self.cache:
                        self.order.remove(key)
                    elif len(self.cache) >= self.capacity:
                        oldest = self.order.pop(0)
                        del self.cache[oldest]
                    self.cache[key] = value
                    self.order.append(key)

                def evict_all(self):
                    self.cache.clear()
                    self.order.clear()

                def size(self):
                    return len(self.cache)
        """),
    },
    {
        "id": "graph_module",
        "code": textwrap.dedent("""\
            def build_adjacency_list(edges, directed=False):
                graph = {}
                for u, v in edges:
                    graph.setdefault(u, []).append(v)
                    if not directed:
                        graph.setdefault(v, []).append(u)
                return graph

            def bfs(graph, start):
                visited = set()
                queue = [start]
                order = []
                while queue:
                    node = queue.pop(0)
                    if node in visited:
                        continue
                    visited.add(node)
                    order.append(node)
                    queue.extend(graph.get(node, []))
                return order

            def dfs(graph, start, visited=None):
                if visited is None:
                    visited = set()
                visited.add(start)
                result = [start]
                for neighbour in graph.get(start, []):
                    if neighbour not in visited:
                        result.extend(dfs(graph, neighbour, visited))
                return result

            def shortest_path_length(graph, start, end):
                if start == end:
                    return 0
                visited = {start}
                queue = [(start, 0)]
                while queue:
                    node, dist = queue.pop(0)
                    for neighbour in graph.get(node, []):
                        if neighbour == end:
                            return dist + 1
                        if neighbour not in visited:
                            visited.add(neighbour)
                            queue.append((neighbour, dist + 1))
                return -1
        """),
    },
    {
        "id": "text_processing_module",
        "code": textwrap.dedent("""\
            def tokenise(text):
                return text.lower().split()

            def remove_stopwords(tokens, stopwords):
                return [t for t in tokens if t not in stopwords]

            def word_frequency(tokens):
                freq = {}
                for token in tokens:
                    freq[token] = freq.get(token, 0) + 1
                return freq

            def top_n_words(text, stopwords, n=10):
                tokens = tokenise(text)
                tokens = remove_stopwords(tokens, stopwords)
                freq = word_frequency(tokens)
                return sorted(freq.items(), key=lambda x: x[1], reverse=True)[:n]

            def avg_word_length(tokens):
                if not tokens:
                    return 0.0
                return sum(len(t) for t in tokens) / len(tokens)

            def sentence_count(text):
                return len([s for s in text.split('.') if s.strip()])
        """),
    },
    {
        "id": "pagination_module",
        "code": textwrap.dedent("""\
            def paginate(items, page, page_size):
                start = (page - 1) * page_size
                end = start + page_size
                return items[start:end]

            def total_pages(total_items, page_size):
                if page_size <= 0:
                    raise ValueError("page_size must be positive")
                return (total_items + page_size - 1) // page_size

            def page_info(total_items, page, page_size):
                pages = total_pages(total_items, page_size)
                return {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": pages,
                    "has_next": page < pages,
                    "has_prev": page > 1,
                }

            def validate_page(page, total_pages_count):
                if page < 1 or page > total_pages_count:
                    raise ValueError(f"Page {page} out of range 1-{total_pages_count}")
                return page
        """),
    },
    {
        "id": "retry_module",
        "code": textwrap.dedent("""\
            import time

            def retry(func, attempts, delay=0.0, exceptions=(Exception,)):
                last_error = None
                for attempt in range(attempts):
                    try:
                        return func()
                    except exceptions as exc:
                        last_error = exc
                        if delay > 0:
                            time.sleep(delay)
                raise last_error

            def retry_with_backoff(func, attempts, base_delay=1.0, factor=2.0):
                delay = base_delay
                last_error = None
                for attempt in range(attempts):
                    try:
                        return func()
                    except Exception as exc:
                        last_error = exc
                        time.sleep(delay)
                        delay *= factor
                raise last_error

            def is_retryable(exc, retryable_types):
                return isinstance(exc, tuple(retryable_types))

            def call_with_timeout(func, seconds, default=None):
                import threading
                result = [default]
                exc_holder = [None]
                def target():
                    try:
                        result[0] = func()
                    except Exception as e:
                        exc_holder[0] = e
                t = threading.Thread(target=target)
                t.start()
                t.join(timeout=seconds)
                if exc_holder[0]:
                    raise exc_holder[0]
                return result[0]
        """),
    },
    {
        "id": "validation_module",
        "code": textwrap.dedent("""\
            import re

            def is_email(value):
                pattern = r'^[\\w.+-]+@[\\w-]+\\.[\\w.]+$'
                return bool(re.match(pattern, value))

            def is_url(value):
                pattern = r'^https?://[^\\s/$.?#].[^\\s]*$'
                return bool(re.match(pattern, value))

            def clamp(value, lo, hi):
                return max(lo, min(hi, value))

            def validate_range(value, lo, hi, name="value"):
                if not lo <= value <= hi:
                    raise ValueError(f"{name} must be between {lo} and {hi}")
                return value

            def validate_required(data, required_keys):
                missing = [k for k in required_keys if k not in data]
                if missing:
                    raise ValueError(f"Missing required fields: {missing}")
                return data

            def coerce_int(value, default=0):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return default
        """),
    },
    {
        "id": "config_module",
        "code": textwrap.dedent("""\
            import json
            import os

            def load_json_config(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)

            def load_env_config(prefix):
                result = {}
                for key, value in os.environ.items():
                    if key.startswith(prefix):
                        clean_key = key[len(prefix):].lower()
                        result[clean_key] = value
                return result

            def merge_configs(*configs):
                merged = {}
                for config in configs:
                    merged.update(config)
                return merged

            def get_with_default(config, key, default=None):
                return config.get(key, default)

            def require_key(config, key):
                if key not in config:
                    raise KeyError(f"Required config key missing: {key!r}")
                return config[key]
        """),
    },
    {
        "id": "event_module",
        "code": textwrap.dedent("""\
            class EventBus:
                def __init__(self, name="default"):
                    self.name = name
                    self.listeners = {}

                def subscribe(self, event, callback):
                    self.listeners.setdefault(event, []).append(callback)

                def unsubscribe(self, event, callback):
                    if event in self.listeners:
                        self.listeners[event] = [
                            cb for cb in self.listeners[event] if cb != callback
                        ]

                def publish(self, event, *args, **kwargs):
                    for callback in self.listeners.get(event, []):
                        callback(*args, **kwargs)

                def clear(self, event=None):
                    if event:
                        self.listeners.pop(event, None)
                    else:
                        self.listeners.clear()

                def listener_count(self, event):
                    return len(self.listeners.get(event, []))
        """),
    },
    {
        "id": "data_pipeline_module",
        "code": textwrap.dedent("""\
            def extract(source, fields):
                return [{f: row.get(f) for f in fields} for row in source]

            def transform(records, transformers):
                result = []
                for record in records:
                    transformed = dict(record)
                    for key, fn in transformers.items():
                        if key in transformed:
                            transformed[key] = fn(transformed[key])
                    result.append(transformed)
                return result

            def filter_records(records, predicate):
                return [r for r in records if predicate(r)]

            def load(records, destination):
                destination.extend(records)
                return len(records)

            def run_pipeline(source, fields, transformers, predicate, destination):
                records = extract(source, fields)
                records = transform(records, transformers)
                records = filter_records(records, predicate)
                return load(records, destination)
        """),
    },
]

# ---------------------------------------------------------------------------
# Direct LLM call for base blueprint — returns code, not JSON
# ---------------------------------------------------------------------------

_BASE_DOC_PROMPT = """\
Add Google-style docstrings to every public function and class in the code below.

Requirements:
- Every public function must have a docstring.
- Functions with parameters must include an Args: section listing each parameter.
- Functions that return a value must include a Returns: section.
- Keep the code otherwise unchanged.

Return ONLY the documented Python code inside a ```python ... ``` block.
No explanation, no JSON, no other text.

Code to document:
{code}
"""


def _call_llm_for_code(client, model: str, code: str) -> str:
    """Direct LLM call that asks for Python code back, not JSON."""
    response = client.responses.create(
        model=model,
        input=_BASE_DOC_PROMPT.format(code=code),
    )
    return response.output_text


# ---------------------------------------------------------------------------
# Code extraction from LLM response
# ---------------------------------------------------------------------------

def _extract_python_code(raw: str) -> str:
    """
    Extract Python code from an LLM response.

    Tries in order:
    1. Largest ```python ... ``` fenced block
    2. Largest ``` ... ``` fenced block
    3. raw text itself if it parses as valid Python
    4. Empty string (signals extraction failure)
    """
    # Try python-fenced block
    blocks = re.findall(r"```python\s*\n(.*?)```", raw, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()

    # Try any fenced block
    blocks = re.findall(r"```\s*\n(.*?)```", raw, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()

    # Try raw text
    try:
        ast.parse(raw.strip())
        return raw.strip()
    except SyntaxError:
        pass

    return ""


# ---------------------------------------------------------------------------
# Quality-aware docstring coverage checker
# ---------------------------------------------------------------------------

def _has_args_section(doc: str) -> bool:
    return bool(re.search(r"(Args|Arguments|Parameters)\s*:", doc, re.IGNORECASE))


def _has_returns_section(doc: str) -> bool:
    return bool(re.search(r"(Returns|Yields|Return)\s*:", doc, re.IGNORECASE))


def _node_has_params(node: ast.FunctionDef) -> bool:
    all_args = node.args.args + node.args.posonlyargs + node.args.kwonlyargs
    meaningful = [a for a in all_args if a.arg not in ("self", "cls")]
    return bool(meaningful) or bool(node.args.vararg) or bool(node.args.kwarg)


def _node_has_return(node: ast.FunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return True
    return False


def _get_public_nodes(tree: ast.Module) -> List[Any]:
    """
    Return module-level and class-level nodes only — no nested functions.
    Mirrors the runner's checker exactly so both measure the same symbols.
    """
    nodes: List[Any] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            nodes.append(node)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nodes.append(child)
    return nodes


def _measure_quality_coverage(code: str) -> Dict[str, Any]:
    """
    Quality-aware docstring coverage — identical standard to the runner.
    A symbol is complete only if it has Args/Returns sections where required.
    Only top-level and class-level symbols are counted (no nested functions).
    """
    if not code.strip():
        return {
            "coverage": 0.0, "total": 0, "complete": 0,
            "present": 0, "incomplete": [], "missing": [],
            "error": "empty input",
        }

    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError as exc:
        return {
            "coverage": 0.0, "total": 0, "complete": 0,
            "present": 0, "incomplete": [], "missing": [], "error": str(exc),
        }

    total = 0
    complete = 0
    present_count = 0
    incomplete: List[str] = []
    missing: List[str] = []

    for node in _get_public_nodes(tree):
        if node.name.startswith("_"):
            continue

        total += 1

        has_any = (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        if not has_any:
            missing.append(node.name)
            continue

        present_count += 1
        doc = node.body[0].value.value

        if isinstance(node, ast.ClassDef):
            complete += 1
            continue

        needs_args = _node_has_params(node)
        needs_returns = _node_has_return(node)

        ok = True
        if needs_args and not _has_args_section(doc):
            ok = False
        if needs_returns and not _has_returns_section(doc):
            ok = False

        if ok:
            complete += 1
        else:
            incomplete.append(node.name)

    coverage = round(complete / total, 3) if total > 0 else 0.0
    return {
        "coverage": coverage,
        "total": total,
        "complete": complete,
        "present": present_count,
        "incomplete": incomplete,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_doc_benchmark() -> List[Dict[str, Any]]:
    import os
    from openai import OpenAI
    from architecture_generator import ArchitectureGenerator
    from blueprint_mutator import BlueprintMutator
    from domain_profiler import DomainProfiler
    from llm_agent_runner import LLMAgentRunner

    model = "gpt-4.1-mini"
    client = OpenAI()

    profiler = DomainProfiler()
    generator = ArchitectureGenerator()
    mutator = BlueprintMutator()
    llm_runner = LLMAgentRunner(model=model)

    doc_prompt = "Add useful comments and docstrings to explain the code."
    profile = profiler.profile(doc_prompt)
    base_blueprint = generator.generate(profile)
    mutated_blueprint = mutator.mutate(base_blueprint)

    results = []

    for task in DOC_TASKS:
        code = task["code"]
        initial = _measure_quality_coverage(code)

        print(
            f"  [{task['id']}]  symbols={initial['total']}"
            f"  initial={initial['coverage']:.0%}",
            end="",
            flush=True,
        )

        # --- Base: direct LLM call asking for code, not JSON ---
        # The base blueprint's single-shot path returns JSON because the
        # documentation schema asks for structured fields. To measure base
        # quality fairly we use a direct prompt that returns Python code.
        base_raw = _call_llm_for_code(client, model, code)
        base_code = _extract_python_code(base_raw)
        base_stats = _measure_quality_coverage(base_code) if base_code else {
            "coverage": 0.0, "total": 0, "complete": 0,
            "present": 0, "incomplete": [], "missing": ["extraction_failed"],
        }

        # --- Mutated: uses the documentation feedback loop ---
        mutated_result = llm_runner.run(mutated_blueprint, code)
        mutated_raw = mutated_result.get("final_code") or mutated_result.get("raw_output", "")
        mutated_code = _extract_python_code(mutated_raw) if mutated_raw else ""
        mutated_stats = _measure_quality_coverage(mutated_code) if mutated_code else {
            "coverage": 0.0, "total": 0, "complete": 0,
            "present": 0, "incomplete": [], "missing": ["extraction_failed"],
        }
        doc_rounds = mutated_result.get("doc_rounds_taken", 0)

        print(
            f"  base={base_stats['coverage']:.0%}"
            f" ({base_stats['complete']}/{base_stats['total']} complete)"
            f"  mutated={mutated_stats['coverage']:.0%}"
            f" ({mutated_stats['complete']}/{mutated_stats['total']} complete)"
            f"  rounds={doc_rounds}"
        )

        results.append({
            "task_id": task["id"],
            "total_symbols": initial["total"],
            "initial_coverage": initial["coverage"],
            "base_present": base_stats["present"],
            "base_complete": base_stats["complete"],
            "base_coverage": base_stats["coverage"],
            "base_incomplete": base_stats["incomplete"],
            "mutated_present": mutated_stats["present"],
            "mutated_complete": mutated_stats["complete"],
            "mutated_coverage": mutated_stats["coverage"],
            "mutated_incomplete": mutated_stats["incomplete"],
            "doc_rounds_taken": doc_rounds,
            "coverage_improved": mutated_stats["coverage"] > base_stats["coverage"],
        })

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _avg(results: List[Dict], key: str) -> float:
    vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def save_json(results: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def save_markdown(results: List[Dict[str, Any]], path: str) -> None:
    avg_base = _avg(results, "base_coverage")
    avg_mutated = _avg(results, "mutated_coverage")
    avg_rounds = _avg(results, "doc_rounds_taken")
    n_improved = sum(1 for r in results if r["coverage_improved"])
    n = len(results)
    avg_symbols = _avg(results, "total_symbols")

    lines = [
        "# Documentation Feedback Loop Benchmark",
        "",
        "## Scoring: quality-aware coverage",
        "",
        "A docstring is **complete** only if it contains an `Args:` section "
        "(for functions with parameters) and a `Returns:` section (for functions "
        "that return a value). One-liner docstrings score 0.",
        "",
        "**Base blueprint**: single direct LLM call asking for documented code.  ",
        "**Mutated blueprint**: `verify_docstring_coverage` step triggers an "
        "AST-based checker; incomplete symbols are sent back for revision.",
        "",
        "| Task | Symbols | Base complete | Mutated complete | Rounds | Improved |",
        "|---|---:|---:|---:|---:|---|",
    ]

    for r in results:
        improved = "✓" if r["coverage_improved"] else "—"
        lines.append(
            f"| {r['task_id']}"
            f" | {r['total_symbols']}"
            f" | {r['base_complete']}/{r['total_symbols']} ({r['base_coverage']:.0%})"
            f" | {r['mutated_complete']}/{r['total_symbols']} ({r['mutated_coverage']:.0%})"
            f" | {r['doc_rounds_taken']}"
            f" | {improved} |"
        )

    lines += [
        f"| **Average** | **{avg_symbols:.1f}** "
        f"| **{avg_base:.0%}** | **{avg_mutated:.0%}**"
        f" | **{avg_rounds:.2f}** | **{n_improved}/{n}** |",
        "",
        "## Key observations",
        "",
        f"- Base blueprint (single-shot) average quality coverage: **{avg_base:.0%}**",
        f"- Mutated blueprint (feedback loop) average quality coverage: **{avg_mutated:.0%}**",
        f"- Coverage improved in **{n_improved} of {n}** tasks.",
        f"- Average revision rounds: **{avg_rounds:.2f}**",
        "",
        "The LLM reliably adds *some* docstring on the first pass, but frequently "
        "writes one-liners that omit Args/Returns sections for helper functions. "
        "The mutated blueprint's quality checker surfaces these gaps and sends "
        "back a targeted revision request.",
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.")
        return

    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    print("Running documentation feedback loop benchmark (quality-aware)...")
    print(f"Tasks: {len(DOC_TASKS)}")
    print("Base: direct code prompt (no JSON schema)")
    print("Mutated: verify_docstring_coverage feedback loop")
    print("Scoring: complete = has Args + Returns sections where required")
    print()

    results = run_doc_benchmark()

    save_json(results, os.path.join(results_dir, "doc_benchmark.json"))
    save_markdown(results, os.path.join(results_dir, "doc_benchmark.md"))

    avg_base = _avg(results, "base_coverage")
    avg_mutated = _avg(results, "mutated_coverage")
    n_improved = sum(1 for r in results if r["coverage_improved"])

    print()
    print("=" * 55)
    print(f"Base blueprint avg quality coverage   : {avg_base:.0%}")
    print(f"Mutated blueprint avg quality coverage: {avg_mutated:.0%}")
    print(f"Improved in                           : {n_improved}/{len(results)} tasks")
    print("Saved → results/doc_benchmark.json")
    print("Saved → results/doc_benchmark.md")


if __name__ == "__main__":
    main()
