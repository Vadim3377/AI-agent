"""
Debugging benchmark with visible failing tests and held-out grading.

Each task is a function with several interacting bugs, plus a bug report: a
few failing tests that pin down the intended behaviour. Both blueprints see the
same tests. The base blueprint answers single-shot; the mutated blueprint's
feedback loop can run the tests on its fix and revise. Final fixes are graded
on held-out checks (different inputs, same behaviours) that the model never
sees, with expected outputs computed from the ground-truth fix.

The question this answers: when the loop has a real test signal, does it
produce more correct fixes than single-shot?
"""

import argparse
import json
import os
import textwrap
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

import held_out
import llm_backend

load_dotenv()


def _code(src: str) -> str:
    return textwrap.dedent(src).strip() + "\n"


# Tasks: buggy code, ground-truth fix, visible test assertions (shown to the
# model), held-out expressions (hidden; expected values come from "fixed").
HARD_TASKS: List[Dict[str, Any]] = [
    {
        "id": "merge_intervals",
        "buggy": _code("""
            def merge_intervals(intervals):
                merged = []
                for start, end in intervals:
                    if merged and start < merged[-1][1]:
                        merged[-1][1] = end
                    else:
                        merged.append([start, end])
                return merged
        """),
        "fixed": _code("""
            def merge_intervals(intervals):
                merged = []
                for start, end in sorted(intervals):
                    if merged and start <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], end)
                    else:
                        merged.append([start, end])
                return merged
        """),
        "visible": [
            "merge_intervals([[1, 3], [2, 6], [8, 10]]) == [[1, 6], [8, 10]]",
            "merge_intervals([[1, 4], [4, 5]]) == [[1, 5]]",
            "merge_intervals([[1, 10], [2, 3]]) == [[1, 10]]",
            "merge_intervals([[5, 6], [1, 2]]) == [[1, 2], [5, 6]]",
        ],
        "held_out": [
            "merge_intervals([[2, 3], [1, 10], [11, 12]])",
            "merge_intervals([])",
            "merge_intervals([[1, 2], [2, 3], [3, 4]])",
            "merge_intervals([[6, 8], [1, 9], [2, 4], [4, 7]])",
        ],
    },
    {
        "id": "roman_to_int",
        "buggy": _code("""
            def roman_to_int(s):
                values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
                total = 0
                for i in range(len(s) - 1):
                    if values[s[i]] <= values[s[i + 1]]:
                        total -= values[s[i]]
                    else:
                        total += values[s[i]]
                return total
        """),
        "fixed": _code("""
            def roman_to_int(s):
                values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
                total = 0
                for i in range(len(s) - 1):
                    if values[s[i]] < values[s[i + 1]]:
                        total -= values[s[i]]
                    else:
                        total += values[s[i]]
                return total + values[s[-1]]
        """),
        "visible": [
            "roman_to_int('III') == 3",
            "roman_to_int('IV') == 4",
            "roman_to_int('MCMXCIV') == 1994",
        ],
        "held_out": [
            "roman_to_int('LVIII')", "roman_to_int('XLII')", "roman_to_int('MMXXIV')",
            "roman_to_int('CDXLIV')", "roman_to_int('I')", "roman_to_int('XX')",
        ],
    },
    {
        "id": "rle_encode",
        "buggy": _code("""
            def rle_encode(s):
                out = []
                count = 1
                for i in range(1, len(s)):
                    if s[i] == s[i - 1]:
                        count += 1
                    else:
                        out.append(s[i] + str(count))
                        count = 1
                return ''.join(out)
        """),
        "fixed": _code("""
            def rle_encode(s):
                if not s:
                    return ''
                out = []
                count = 1
                for i in range(1, len(s)):
                    if s[i] == s[i - 1]:
                        count += 1
                    else:
                        out.append(s[i - 1] + str(count))
                        count = 1
                out.append(s[-1] + str(count))
                return ''.join(out)
        """),
        "visible": [
            "rle_encode('aaabcc') == 'a3b1c2'",
            "rle_encode('a') == 'a1'",
            "rle_encode('') == ''",
        ],
        "held_out": [
            "rle_encode('zzzzzzzzzzzz')", "rle_encode('abab')", "rle_encode('  x')",
            "rle_encode('xyyzzz')",
        ],
    },
    {
        "id": "parse_duration",
        "buggy": _code("""
            def parse_duration(text):
                units = {'h': 3600, 'm': 60, 's': 1}
                total = 0
                number = ''
                for ch in text:
                    if ch.isdigit():
                        number = ch
                    else:
                        total += int(number) * units[ch]
                return total
        """),
        "fixed": _code("""
            def parse_duration(text):
                units = {'h': 3600, 'm': 60, 's': 1}
                total = 0
                number = ''
                for ch in text:
                    if ch.isdigit():
                        number += ch
                    else:
                        total += int(number) * units[ch]
                        number = ''
                return total
        """),
        "visible": [
            "parse_duration('1h30m') == 5400",
            "parse_duration('45s') == 45",
            "parse_duration('2m5s') == 125",
        ],
        "held_out": [
            "parse_duration('12h')", "parse_duration('1h1m1s')", "parse_duration('100s')",
            "parse_duration('10m10s')",
        ],
    },
    {
        "id": "top_k_frequent",
        "buggy": _code("""
            def top_k_frequent(words, k):
                counts = {}
                for w in words:
                    counts[w] = counts.get(w, 0) + 1
                ranked = sorted(counts, key=lambda w: counts[w])
                return ranked[:k]
        """),
        "fixed": _code("""
            def top_k_frequent(words, k):
                counts = {}
                for w in words:
                    counts[w] = counts.get(w, 0) + 1
                ranked = sorted(counts, key=lambda w: (-counts[w], w))
                return ranked[:k]
        """),
        "visible": [
            "top_k_frequent(['a', 'b', 'a', 'c', 'b', 'a'], 2) == ['a', 'b']",
            "top_k_frequent(['x', 'y', 'z'], 2) == ['x', 'y']",
            "top_k_frequent(['b', 'a', 'b', 'a', 'c'], 2) == ['a', 'b']",
        ],
        "held_out": [
            "top_k_frequent(['the', 'day', 'is', 'sunny', 'the', 'the', 'the', 'sunny', 'is', 'is'], 4)",
            "top_k_frequent(['q'], 1)",
            "top_k_frequent(['b', 'c', 'a'], 3)",
            "top_k_frequent(['d', 'd', 'c', 'c', 'b'], 1)",
        ],
    },
    {
        "id": "spiral_order",
        "buggy": _code("""
            def spiral_order(matrix):
                result = []
                top, bottom, left, right = 0, len(matrix) - 1, 0, len(matrix[0]) - 1
                while top <= bottom and left <= right:
                    for c in range(left, right + 1):
                        result.append(matrix[top][c])
                    top += 1
                    for r in range(top, bottom + 1):
                        result.append(matrix[r][right])
                    right -= 1
                    for c in range(right, left - 1, -1):
                        result.append(matrix[bottom][c])
                    bottom -= 1
                    for r in range(bottom, top - 1, -1):
                        result.append(matrix[r][left])
                    left += 1
                return result
        """),
        "fixed": _code("""
            def spiral_order(matrix):
                if not matrix:
                    return []
                result = []
                top, bottom, left, right = 0, len(matrix) - 1, 0, len(matrix[0]) - 1
                while top <= bottom and left <= right:
                    for c in range(left, right + 1):
                        result.append(matrix[top][c])
                    top += 1
                    for r in range(top, bottom + 1):
                        result.append(matrix[r][right])
                    right -= 1
                    if top <= bottom:
                        for c in range(right, left - 1, -1):
                            result.append(matrix[bottom][c])
                        bottom -= 1
                    if left <= right:
                        for r in range(bottom, top - 1, -1):
                            result.append(matrix[r][left])
                        left += 1
                return result
        """),
        "visible": [
            "spiral_order([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == [1, 2, 3, 6, 9, 8, 7, 4, 5]",
            "spiral_order([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]) == [1, 2, 3, 4, 8, 12, 11, 10, 9, 5, 6, 7]",
            "spiral_order([[1, 2, 3]]) == [1, 2, 3]",
            "spiral_order([]) == []",
        ],
        "held_out": [
            "spiral_order([[1], [2], [3]])",
            "spiral_order([[1, 2], [3, 4]])",
            "spiral_order([[1, 2], [3, 4], [5, 6]])",
            "spiral_order([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]])",
            "spiral_order([[7]])",
        ],
    },
    {
        "id": "semver_compare",
        "buggy": _code("""
            def semver_compare(a, b):
                if a == b:
                    return 0
                return 1 if a > b else -1
        """),
        "fixed": _code("""
            def semver_compare(a, b):
                pa = [int(p) for p in a.split('.')]
                pb = [int(p) for p in b.split('.')]
                n = max(len(pa), len(pb))
                pa += [0] * (n - len(pa))
                pb += [0] * (n - len(pb))
                if pa == pb:
                    return 0
                return 1 if pa > pb else -1
        """),
        "visible": [
            "semver_compare('1.10.0', '1.9.0') == 1",
            "semver_compare('1.0', '1.0.0') == 0",
            "semver_compare('2.0.1', '2.0.10') == -1",
        ],
        "held_out": [
            "semver_compare('0.0.1', '0.1')", "semver_compare('3', '2.9.9')",
            "semver_compare('1.2.3', '1.2.3')", "semver_compare('1.0.0.0', '1')",
            "semver_compare('10.0', '9.99')",
        ],
    },
    {
        "id": "rotate_list",
        "buggy": _code("""
            def rotate_list(lst, k):
                k = k % len(lst)
                return lst[k:] + lst[:k]
        """),
        "fixed": _code("""
            def rotate_list(lst, k):
                if not lst:
                    return []
                k = k % len(lst)
                return lst[-k:] + lst[:-k] if k else list(lst)
        """),
        "visible": [
            "rotate_list([1, 2, 3, 4, 5], 2) == [4, 5, 1, 2, 3]",
            "rotate_list([1, 2, 3], 0) == [1, 2, 3]",
            "rotate_list([], 3) == []",
        ],
        "held_out": [
            "rotate_list([1, 2, 3], 4)", "rotate_list([1, 2, 3], -1)",
            "rotate_list(['a'], 7)", "rotate_list([1, 2], 2)",
        ],
    },
    {
        "id": "flatten_dict",
        "buggy": _code("""
            def flatten_dict(d, parent='', sep='.'):
                items = {}
                for key, value in d.items():
                    new_key = parent + sep + key
                    if isinstance(value, dict):
                        items.update(flatten_dict(value, key, sep))
                    else:
                        items[new_key] = value
                return items
        """),
        "fixed": _code("""
            def flatten_dict(d, parent='', sep='.'):
                items = {}
                for key, value in d.items():
                    new_key = parent + sep + key if parent else key
                    if isinstance(value, dict):
                        items.update(flatten_dict(value, new_key, sep))
                    else:
                        items[new_key] = value
                return items
        """),
        "visible": [
            "flatten_dict({'a': 1, 'b': {'c': 2}}) == {'a': 1, 'b.c': 2}",
            "flatten_dict({'a': {'b': {'c': 3}}}) == {'a.b.c': 3}",
            "flatten_dict({'x': {'y': 1}}, sep='/') == {'x/y': 1}",
        ],
        "held_out": [
            "flatten_dict({})",
            "flatten_dict({'a': {'b': 1, 'c': {'d': 2}}, 'e': 3})",
            "flatten_dict({'k': [1, 2]})",
            "flatten_dict({'p': {'q': {'r': {'s': 0}}}}, sep='_')",
        ],
    },
    {
        "id": "int_to_base",
        "buggy": _code("""
            def int_to_base(n, base):
                digits = '0123456789ABCDEF'
                result = ''
                while n > 0:
                    result += digits[n % base]
                    n //= base
                return result
        """),
        "fixed": _code("""
            def int_to_base(n, base):
                digits = '0123456789ABCDEF'
                if n == 0:
                    return '0'
                sign = '-' if n < 0 else ''
                n = abs(n)
                result = ''
                while n > 0:
                    result = digits[n % base] + result
                    n //= base
                return sign + result
        """),
        "visible": [
            "int_to_base(10, 2) == '1010'",
            "int_to_base(255, 16) == 'FF'",
            "int_to_base(0, 8) == '0'",
            "int_to_base(-5, 2) == '-101'",
        ],
        "held_out": [
            "int_to_base(31, 16)", "int_to_base(7, 8)", "int_to_base(-255, 16)",
            "int_to_base(100, 10)", "int_to_base(1, 2)",
        ],
    },
    {
        "id": "balanced_brackets",
        "buggy": _code("""
            def balanced_brackets(s):
                pairs = {')': '(', ']': '[', '}': '{'}
                stack = []
                for ch in s:
                    if ch in '([{':
                        stack.append(ch)
                    elif ch in pairs:
                        if stack.pop() != pairs[ch]:
                            return False
                return True
        """),
        "fixed": _code("""
            def balanced_brackets(s):
                pairs = {')': '(', ']': '[', '}': '{'}
                stack = []
                for ch in s:
                    if ch in '([{':
                        stack.append(ch)
                    elif ch in pairs:
                        if not stack or stack.pop() != pairs[ch]:
                            return False
                return not stack
        """),
        "visible": [
            "balanced_brackets('([]{})') is True",
            "balanced_brackets('(]') is False",
            "balanced_brackets(')(') is False",
            "balanced_brackets('((') is False",
        ],
        "held_out": [
            "balanced_brackets('')", "balanced_brackets('a(b)c')", "balanced_brackets('{[()()]}')",
            "balanced_brackets(']')", "balanced_brackets('([)]')", "balanced_brackets('{{}')",
        ],
    },
    {
        "id": "moving_average",
        "buggy": _code("""
            def moving_average(values, window):
                result = []
                for i in range(len(values) - window):
                    result.append(sum(values[i:i + window]) // window)
                return result
        """),
        "fixed": _code("""
            def moving_average(values, window):
                result = []
                for i in range(len(values) - window + 1):
                    result.append(sum(values[i:i + window]) / window)
                return result
        """),
        "visible": [
            "moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]",
            "moving_average([5], 1) == [5.0]",
            "moving_average([1, 2], 3) == []",
        ],
        "held_out": [
            "moving_average([2, 4, 6, 8, 10], 3)", "moving_average([1, 1, 1], 3)",
            "moving_average([0, 3], 1)", "moving_average([1, 2, 4], 2)",
        ],
    },
]


def visible_tests(task: Dict[str, Any]) -> str:
    """Pytest source for the task's visible tests."""
    return "\n\n".join(
        f"def test_{task['id']}_{i}():\n    assert {assertion}"
        for i, assertion in enumerate(task["visible"], 1)
    )


def validate_tasks() -> Dict[str, List[List[Any]]]:
    """
    Check every task: the fix passes the visible tests, the buggy code fails at
    least one visible test, and the buggy code fails at least one held-out check.
    Returns held-out expected outputs per task.
    """
    expected_by_task = {}
    for task in HARD_TASKS:
        visible_ok = [["ok", True]] * len(task["visible"])
        if held_out.evaluate(task["fixed"], task["visible"]) != visible_ok:
            raise ValueError(f"{task['id']}: fix fails its visible tests")
        if held_out.evaluate(task["buggy"], task["visible"]) == visible_ok:
            raise ValueError(f"{task['id']}: buggy code passes every visible test")
        check = held_out.check_task(task["buggy"], task["fixed"], task["held_out"])
        if not check["bug_observable"]:
            raise ValueError(f"{task['id']}: buggy code passes every held-out check")
        expected_by_task[task["id"]] = check["expected"]
    return expected_by_task


def run_hard_benchmark(
    expected_by_task: Dict[str, List[List[Any]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    from architecture_generator import ArchitectureGenerator
    from blueprint_mutator import BlueprintMutator
    from domain_profiler import DomainProfiler
    from llm_agent_runner import LLMAgentRunner

    profile = DomainProfiler().profile(
        "Debug this Python function. It gives the wrong output and the test fails."
    )
    base_blueprint = ArchitectureGenerator().generate(profile)
    mutated_blueprint = BlueprintMutator().mutate(base_blueprint)
    runner = LLMAgentRunner()

    results = []
    usage_logs: Dict[str, List[Dict[str, Any]]] = {"base": [], "mutated": []}

    for task in HARD_TASKS:
        print(f"  [{task['id']}]", end="", flush=True)
        tests = visible_tests(task)
        n_checks = len(task["held_out"])
        row: Dict[str, Any] = {"task_id": task["id"], "checks": n_checks}

        for name, blueprint in (("base", base_blueprint), ("mutated", mutated_blueprint)):
            result = runner.run(blueprint, task["buggy"], tests=tests)
            fix = result.get("final_fix") or runner._extract_fix(
                result.get("parsed_output"), result.get("raw_output", "")
            ) or ""
            passed = held_out.grade(fix, task["held_out"], expected_by_task[task["id"]])
            usage_logs[name].append(result["usage"])
            row.update({
                f"{name}_checks_passed": passed,
                f"{name}_passed": passed == n_checks,
                f"{name}_fix": fix,
                f"{name}_latency_s": result["usage"]["latency_s"],
            })
            if name == "mutated":
                row["rounds_taken"] = result.get("rounds_taken", 0)
                row["first_attempt_visible_passed"] = bool(result.get("first_attempt_passed"))
                row["final_visible_passed"] = bool(result.get("final_pytest_passed"))

        print(f"  base={row['base_checks_passed']}/{n_checks}"
              f"  mutated={row['mutated_checks_passed']}/{n_checks}"
              f"  rounds={row['rounds_taken']}")
        results.append(row)

    usage = {name: llm_backend.summarise_runs(log) for name, log in usage_logs.items()}
    return results, usage


def save_markdown(results: List[Dict[str, Any]], usage: Dict[str, Dict[str, Any]], path: str) -> None:
    n = len(results)
    base_pass = sum(r["base_passed"] for r in results)
    mut_pass = sum(r["mutated_passed"] for r in results)
    first_vis = sum(r["first_attempt_visible_passed"] for r in results)
    total_checks = sum(r["checks"] for r in results)
    base_checks = sum(r["base_checks_passed"] for r in results)
    mut_checks = sum(r["mutated_checks_passed"] for r in results)
    avg_rounds = sum(r["rounds_taken"] for r in results) / n

    lines = [
        "# Visible-Test Debugging Benchmark",
        "",
        f"{n} multi-bug functions. Both blueprints see the same failing tests; only the",
        "mutated blueprint can run them and revise. Fixes are graded on hidden held-out checks.",
        "",
        "| Metric | Base (single-shot) | Mutated (test loop) |",
        "|---|---|---|",
        f"| **Held-out pass rate** | **{base_pass}/{n} ({base_pass/n:.0%})** "
        f"| **{mut_pass}/{n} ({mut_pass/n:.0%})** |",
        f"| Held-out checks passed | {base_checks}/{total_checks} | {mut_checks}/{total_checks} |",
        f"| First attempt passes visible tests | - | {first_vis}/{n} |",
        f"| Avg revision rounds | 0.00 | {avg_rounds:.2f} |",
        "",
        "| Task | Base | Mutated | Rounds |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['task_id']} | {r['base_checks_passed']}/{r['checks']}"
            f" | {r['mutated_checks_passed']}/{r['checks']} | {r['rounds_taken']} |"
        )
    for name in ("base", "mutated"):
        lines += ["", f"## LLM Usage: {name}", "", "```", llm_backend.format_usage(usage[name]), "```"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Visible-test debugging benchmark")
    parser.add_argument("--validate-only", action="store_true",
                        help="Check the task set and exit; no API calls.")
    llm_backend.add_cli_args(parser)
    args = parser.parse_args()
    llm_backend.apply_cli_args(args)

    print("Validating tasks...")
    expected_by_task = validate_tasks()
    print(f"  {len(HARD_TASKS)} tasks OK")
    if args.validate_only:
        return
    if not llm_backend.is_configured(args.provider):
        print(f"ERROR: provider {args.provider!r} is not configured.")
        return

    os.makedirs("results", exist_ok=True)
    json_path = llm_backend.results_path("results/hard_benchmark.json", args.provider)
    md_path = llm_backend.results_path("results/hard_benchmark.md", args.provider)

    results, usage = run_hard_benchmark(expected_by_task)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "llm_usage": usage}, f, indent=2)
    save_markdown(results, usage, md_path)

    n = len(results)
    print()
    print(f"Base held-out pass rate   : {sum(r['base_passed'] for r in results)}/{n}")
    print(f"Mutated held-out pass rate: {sum(r['mutated_passed'] for r in results)}/{n}")
    for name in ("base", "mutated"):
        print(f"\n[{name}]\n{llm_backend.format_usage(usage[name])}")
    print(f"Saved -> {json_path}\nSaved -> {md_path}")


if __name__ == "__main__":
    main()
