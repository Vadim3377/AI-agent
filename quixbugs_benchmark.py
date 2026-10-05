"""
Run external debugging validation on a QuixBugs subset.

The benchmark embeds ten Python programs from QuixBugs (buggy version and
ground-truth fix) and compares a base single-shot blueprint against a mutated
feedback-loop blueprint.

Each blueprint's final fix is graded on held-out test cases: the expected
outputs come from running the ground-truth fix, and neither the cases nor the
fix are shown to the model. The agent's own in-loop pytest result is reported
separately as a self-check, because pytest_runner only generates generic
smoke tests and cannot judge correctness for these programs.
"""

import argparse
import json
import os
import textwrap
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

import held_out
import llm_backend

load_dotenv()
# 10 QuixBugs Python tasks: buggy version, ground-truth fix, held-out test inputs.
# Source: https://github.com/jkoppel/QuixBugs (MIT licence). The buggy code is
# sent to the model without hints; expected outputs are computed from "fixed".
QUIXBUGS_TASKS = [
    {
        "id": "bitcount",
        "description": "Count set bits using Brian Kernighan's method",
        "buggy": textwrap.dedent("""\
            def bitcount(n):
                count = 0
                while n:
                    n ^= n - 1
                    count += 1
                return count
        """),
        "fixed": textwrap.dedent("""\
            def bitcount(n):
                count = 0
                while n:
                    n &= n - 1
                    count += 1
                return count
        """),
        "cases": [[127], [128], [3005], [13], [14], [27], [834], [254], [256]],
    },
    {
        "id": "find_first_in_sorted",
        "description": "Binary search for first occurrence of x",
        "buggy": textwrap.dedent("""\
            def find_first_in_sorted(arr, x):
                lo = 0
                hi = len(arr)
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if x == arr[mid] and (mid == 0 or x != arr[mid - 1]):
                        return mid
                    elif x <= arr[mid]:
                        hi = mid
                    else:
                        lo = mid + 1
                return -1
        """),
        "fixed": textwrap.dedent("""\
            def find_first_in_sorted(arr, x):
                lo = 0
                hi = len(arr)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if x == arr[mid] and (mid == 0 or x != arr[mid - 1]):
                        return mid
                    elif x <= arr[mid]:
                        hi = mid
                    else:
                        lo = mid + 1
                return -1
        """),
        "cases": [
            [[3, 4, 5, 5, 5, 5, 6], 5], [[3, 4, 5, 5, 5, 5, 6], 7],
            [[3, 4, 5, 5, 5, 5, 6], 2], [[3, 6, 7, 9, 9, 10, 14, 27], 14],
            [[0, 1, 6, 8, 13, 14, 67, 128], 80], [[0, 1, 6, 8, 13, 14, 67, 128], 67],
            [[0, 1, 6, 8, 13, 14, 67, 128], 128],
        ],
    },
    {
        "id": "flatten",
        "description": "Flatten a nested list",
        "buggy": textwrap.dedent("""\
            def flatten(arr):
                for x in arr:
                    if isinstance(x, list):
                        for y in flatten(x):
                            yield y
                    else:
                        yield flatten(x)
        """),
        "fixed": textwrap.dedent("""\
            def flatten(arr):
                for x in arr:
                    if isinstance(x, list):
                        for y in flatten(x):
                            yield y
                    else:
                        yield x
        """),
        "cases": [
            [[[1, [], [2, 3]], [[4]], 5]], [[[], [], [], [], []]],
            [[[], [], 1, [], 1, [], []]], [[1, 2, 3, [[4]]]], [[1, 4, 6]],
            [["moe", "curly", "larry"]], [["a", "b", ["c"], ["d"], [["e"]]]],
        ],
    },
    {
        "id": "gcd",
        "description": "Euclidean GCD",
        "buggy": textwrap.dedent("""\
            def gcd(a, b):
                if b == 0:
                    return a
                else:
                    return gcd(a % b, b)
        """),
        "fixed": textwrap.dedent("""\
            def gcd(a, b):
                if b == 0:
                    return a
                else:
                    return gcd(b, a % b)
        """),
        "cases": [[17, 0], [13, 13], [37, 600], [20, 100], [624129, 2061517], [3, 12]],
    },
    {
        "id": "is_valid_parenthesization",
        "description": "Check balanced parentheses",
        "buggy": textwrap.dedent("""\
            def is_valid_parenthesization(parens):
                depth = 0
                for paren in parens:
                    if paren == '(':
                        depth += 1
                    else:
                        depth -= 1
                        if depth < 0:
                            return False
                return True
        """),
        "fixed": textwrap.dedent("""\
            def is_valid_parenthesization(parens):
                depth = 0
                for paren in parens:
                    if paren == '(':
                        depth += 1
                    else:
                        depth -= 1
                        if depth < 0:
                            return False
                return depth == 0
        """),
        "cases": [["((()()))()"], [")()("], ["(("], ["()"], ["(()"], ["()()(())"]],
    },
    {
        "id": "max_sublist_sum",
        "description": "Kadane's algorithm for maximum subarray sum",
        "buggy": textwrap.dedent("""\
            def max_sublist_sum(arr):
                max_ending_here = 0
                max_so_far = 0
                for x in arr:
                    max_ending_here = max_ending_here + x
                    max_so_far = max(max_so_far, max_ending_here)
                return max_so_far
        """),
        "fixed": textwrap.dedent("""\
            def max_sublist_sum(arr):
                max_ending_here = 0
                max_so_far = 0
                for x in arr:
                    max_ending_here = max(0, max_ending_here + x)
                    max_so_far = max(max_so_far, max_ending_here)
                return max_so_far
        """),
        "cases": [
            [[4, -5, 2, 1, -1, 3]], [[0, -1, 2, -1, 3, -1, 0]], [[3, 4, 5]],
            [[4, -2, -8, 5, -2, 7, 7, 2, -6, 5]], [[-4, -4, -5]], [[-2, 1, -3, 4, -1, 2, 1, -5, 4]],
        ],
    },
    {
        "id": "next_palindrome",
        "description": "Find the next palindrome greater than a number given as a digit list",
        "buggy": textwrap.dedent("""\
            def next_palindrome(digit_list):
                high_mid = len(digit_list) // 2
                low_mid = (len(digit_list) - 1) // 2
                while high_mid < len(digit_list) and low_mid >= 0:
                    if digit_list[high_mid] == 9:
                        digit_list[high_mid] = 0
                        digit_list[low_mid] = 0
                        high_mid += 1
                        low_mid -= 1
                    else:
                        digit_list[high_mid] += 1
                        if low_mid != high_mid:
                            digit_list[low_mid] += 1
                        return digit_list
                return [1] + (len(digit_list)) * [0] + [1]
        """),
        "fixed": textwrap.dedent("""\
            def next_palindrome(digit_list):
                high_mid = len(digit_list) // 2
                low_mid = (len(digit_list) - 1) // 2
                while high_mid < len(digit_list) and low_mid >= 0:
                    if digit_list[high_mid] == 9:
                        digit_list[high_mid] = 0
                        digit_list[low_mid] = 0
                        high_mid += 1
                        low_mid -= 1
                    else:
                        digit_list[high_mid] += 1
                        if low_mid != high_mid:
                            digit_list[low_mid] += 1
                        return digit_list
                return [1] + (len(digit_list) - 1) * [0] + [1]
        """),
        "cases": [
            [[1, 4, 9, 4, 1]], [[1, 3, 1]], [[4, 7, 2, 5, 5, 2, 7, 4]],
            [[4, 7, 2, 5, 2, 7, 4]], [[9, 9, 9]], [[9, 9]],
        ],
    },
    {
        "id": "pascal",
        "description": "Generate the first n rows of Pascal's triangle",
        "buggy": textwrap.dedent("""\
            def pascal(n):
                rows = [[1]]
                for r in range(1, n):
                    row = []
                    for c in range(0, r):
                        upleft = rows[r - 1][c - 1] if c > 0 else 0
                        upright = rows[r - 1][c] if c < r else 0
                        row.append(upleft + upright)
                    rows.append(row)
                return rows
        """),
        "fixed": textwrap.dedent("""\
            def pascal(n):
                rows = [[1]]
                for r in range(1, n):
                    row = []
                    for c in range(0, r + 1):
                        upleft = rows[r - 1][c - 1] if c > 0 else 0
                        upright = rows[r - 1][c] if c < r else 0
                        row.append(upleft + upright)
                    rows.append(row)
                return rows
        """),
        "cases": [[1], [2], [3], [4], [5]],
    },
    {
        "id": "possible_change",
        "description": "Count the ways to make change for a total from given coin denominations",
        "buggy": textwrap.dedent("""\
            def possible_change(coins, total):
                if total == 0:
                    return 1
                if total < 0:
                    return 0
                first, *rest = coins
                return possible_change(coins, total - first) + possible_change(rest, total)
        """),
        "fixed": textwrap.dedent("""\
            def possible_change(coins, total):
                if total == 0:
                    return 1
                if total < 0 or not coins:
                    return 0
                first, *rest = coins
                return possible_change(coins, total - first) + possible_change(rest, total)
        """),
        "cases": [
            [[1, 4, 2], -7], [[1, 5, 10, 25], 11], [[1, 5, 10, 25], 75],
            [[1, 5, 10, 25], 34], [[1, 5, 10], 34], [[1, 5, 10, 25], 140], [[1, 3], 0],
        ],
    },
    {
        "id": "wrap",
        "description": "Word-wrap text to a given column width",
        "buggy": textwrap.dedent("""\
            def wrap(text, cols):
                lines = []
                while len(text) > cols:
                    end = text.rfind(' ', 0, cols + 1)
                    if end == -1:
                        end = cols
                    line, text = text[:end], text[end:]
                    lines.append(line)
                return lines
        """),
        "fixed": textwrap.dedent("""\
            def wrap(text, cols):
                lines = []
                while len(text) > cols:
                    end = text.rfind(' ', 0, cols + 1)
                    if end == -1:
                        end = cols
                    line, text = text[:end], text[end:]
                    lines.append(line)
                lines.append(text)
                return lines
        """),
        "cases": [
            ["The quick brown fox jumps over the lazy dog.", 10],
            ["Lorem ipsum dolor sit amet, consectetur adipiscing elit.", 20],
            ["short", 50], ["abcdefghijklmnop", 5], ["a b c d e f g", 3],
        ],
    },
]

# Held-out grading

def _case_exprs(task: Dict[str, Any]) -> List[str]:
    return [f"{task['id']}(*{args!r})" for args in task["cases"]]


def grade_fix(fix: str, task: Dict[str, Any], expected: List[List[Any]]) -> int:
    """Number of held-out cases the fix gets right (0 if there is no fix)."""
    return held_out.grade(fix, _case_exprs(task), expected)


def validate_tasks() -> Dict[str, List[List[Any]]]:
    """
    Compute expected outputs and check every task is a real bug: the fixed
    version must pass all cases and the buggy version must fail at least one.
    """
    expected_by_task = {}
    for task in QUIXBUGS_TASKS:
        check = held_out.check_task(task["buggy"], task["fixed"], _case_exprs(task))
        if not check["bug_observable"]:
            raise ValueError(f"{task['id']}: buggy version passes every case")
        expected_by_task[task["id"]] = check["expected"]
    return expected_by_task


# Benchmark runner

def run_quixbugs_benchmark(
    expected_by_task: Dict[str, List[List[Any]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Run every task on both blueprints; return per-task results and per-blueprint usage."""
    from architecture_generator import ArchitectureGenerator
    from blueprint_mutator import BlueprintMutator
    from domain_profiler import DomainProfiler
    from llm_agent_runner import LLMAgentRunner

    profiler = DomainProfiler()
    generator = ArchitectureGenerator()
    mutator = BlueprintMutator()
    runner = LLMAgentRunner()

    debug_prompt = "Debug this Python function. It gives the wrong output and the test fails."
    profile = profiler.profile(debug_prompt)
    base_blueprint = generator.generate(profile)
    mutated_blueprint = mutator.mutate(base_blueprint)

    results = []
    base_usage, mutated_usage = [], []

    for task in QUIXBUGS_TASKS:
        print(f"  [{task['id']}] {task['description']}", end="", flush=True)
        expected = expected_by_task[task["id"]]
        n_cases = len(task["cases"])

        # Base blueprint - single-shot; extract the fix the same way the loop does.
        base_result = runner.run(base_blueprint, task["buggy"])
        base_fix = runner._extract_fix(
            base_result.get("parsed_output"), base_result.get("raw_output", "")
        ) or ""
        base_cases = grade_fix(base_fix, task, expected)

        # Mutated blueprint - with pytest feedback loop
        mutated_result = runner.run(mutated_blueprint, task["buggy"])
        mutated_fix = mutated_result.get("final_fix") or ""
        mutated_cases = grade_fix(mutated_fix, task, expected)

        base_usage.append(base_result["usage"])
        mutated_usage.append(mutated_result["usage"])

        print(
            f"  base={base_cases}/{n_cases}"
            f"  mutated={mutated_cases}/{n_cases}"
            f"  rounds={mutated_result.get('rounds_taken', 0)}"
        )

        results.append({
            "task_id": task["id"],
            "description": task["description"],
            "cases": n_cases,
            "base_cases_passed": base_cases,
            "mutated_cases_passed": mutated_cases,
            "base_passed": base_cases == n_cases,
            "mutated_passed": mutated_cases == n_cases,
            "mutated_self_check_passed": bool(mutated_result.get("final_pytest_passed")),
            "mutated_first_attempt_self_check": bool(mutated_result.get("first_attempt_passed")),
            "rounds_taken": mutated_result.get("rounds_taken", 0),
            "base_latency_s": base_result["usage"]["latency_s"],
            "mutated_latency_s": mutated_result["usage"]["latency_s"],
            "base_fix": base_fix,
            "mutated_fix": mutated_fix,
        })

    usage = {
        "base": llm_backend.summarise_runs(base_usage),
        "mutated": llm_backend.summarise_runs(mutated_usage),
    }
    return results, usage


# Reporting

def save_json(results: List[Dict[str, Any]], usage: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "llm_usage": usage}, f, indent=2)


def save_markdown(
    results: List[Dict[str, Any]], path: str, usage: Optional[Dict[str, Dict[str, Any]]] = None
) -> None:
    n = len(results)
    base_pass = sum(1 for r in results if r["base_passed"])
    mutated_pass = sum(1 for r in results if r["mutated_passed"])
    self_check = sum(1 for r in results if r["mutated_self_check_passed"])
    total_cases = sum(r["cases"] for r in results)
    base_case_pass = sum(r["base_cases_passed"] for r in results)
    mutated_case_pass = sum(r["mutated_cases_passed"] for r in results)
    avg_rounds = sum(r["rounds_taken"] for r in results) / n if n else 0

    lines = [
        "# QuixBugs External Validation Benchmark",
        "",
        "Validates the debugging agent on 10 real Python bugs from the QuixBugs dataset",
        "(https://github.com/jkoppel/QuixBugs). Bugs were not seen during development.",
        "",
        "A fix counts as passed only if it is correct on every held-out test case.",
        "",
        "| Metric | Base blueprint | Mutated blueprint |",
        "|---|---|---|",
        f"| Held-out pass rate (all cases) | {base_pass}/{n} ({base_pass/n:.0%}) "
        f"| {mutated_pass}/{n} ({mutated_pass/n:.0%}) |",
        f"| Held-out cases passed | {base_case_pass}/{total_cases} "
        f"| {mutated_case_pass}/{total_cases} |",
        f"| Agent self-check (pytest_runner) | - | {self_check}/{n} |",
        f"| Avg revision rounds | 0.00 | {avg_rounds:.2f} |",
        "",
        "| Task | Description | Base cases | Mutated cases | Self-check | Rounds |",
        "|---|---|---|---|---|---|",
    ]

    for r in results:
        lines.append(
            f"| {r['task_id']} | {r['description']}"
            f" | {r['base_cases_passed']}/{r['cases']}"
            f" | {r['mutated_cases_passed']}/{r['cases']}"
            f" | {'yes' if r['mutated_self_check_passed'] else 'no'}"
            f" | {r['rounds_taken']} |"
        )

    if usage:
        for name in ("base", "mutated"):
            lines += [
                "",
                f"## LLM Usage: {name} blueprint (per task = one runner.run, incl. revision rounds)",
                "",
                "```",
                llm_backend.format_usage(usage[name]),
                "```",
            ]

    lines += [
        "",
        "## Notes",
        "",
        "- These are real bugs from an independent external dataset, not tasks",
        "  designed by the author. The buggy code is sent without hints.",
        "- Held-out grading runs each final fix on test inputs whose expected outputs",
        "  come from the ground-truth fix; the model never sees them.",
        "- Self-check is the agent's own pytest_runner result inside the feedback loop.",
        "  It uses generic smoke tests, so it can pass on fixes that are still wrong.",
        "- The mutated blueprint's feedback loop gives it additional revision",
        "  opportunities not available to the base blueprint.",
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="QuixBugs external validation benchmark")
    llm_backend.add_cli_args(parser)
    args = parser.parse_args()
    llm_backend.apply_cli_args(args)

    if not llm_backend.is_configured(args.provider):
        print(f"ERROR: provider {args.provider!r} is not configured "
              "(set OPENAI_API_KEY, or GOOGLE_CLOUD_PROJECT for gemini).")
        return

    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    json_path = llm_backend.results_path(os.path.join(results_dir, "quixbugs_benchmark.json"), args.provider)
    md_path = llm_backend.results_path(os.path.join(results_dir, "quixbugs_benchmark.md"), args.provider)

    print("Validating tasks against ground truth...")
    expected_by_task = validate_tasks()

    print("Running QuixBugs external validation benchmark...")
    print(f"Tasks: {len(QUIXBUGS_TASKS)}")
    print()

    results, usage = run_quixbugs_benchmark(expected_by_task)

    save_json(results, usage, json_path)
    save_markdown(results, md_path, usage)

    n = len(results)
    base_pass = sum(1 for r in results if r["base_passed"])
    mutated_pass = sum(1 for r in results if r["mutated_passed"])

    print()
    print("=" * 50)
    print(f"Base blueprint held-out pass rate   : {base_pass}/{n} ({base_pass/n:.0%})")
    print(f"Mutated blueprint held-out pass rate: {mutated_pass}/{n} ({mutated_pass/n:.0%})")
    for name in ("base", "mutated"):
        print()
        print(f"[{name}]")
        print(llm_backend.format_usage(usage[name]))
    print(f"Saved -> {json_path}")
    print(f"Saved -> {md_path}")


if __name__ == "__main__":
    main()
