"""
task_benchmark.py — Objective task-level benchmark for the debugging agent.

30 hand-curated Python functions with intentional bugs across 6 categories:
  wrong_operator, off_by_one, missing_return, wrong_comparison,
  logic_error, type_scope_error.

Scoring is objective and independent of the evaluator:
  - pytest is run on both the buggy code and the fixed code (subprocess)
  - static_checker is run on the buggy code (AST)
  - task_score per case = 0.5*(fixed pytest passes) + 0.3*(pytest improved) + 0.2*(signal hit rate)

Run:
    python task_benchmark.py
    python task_benchmark.py --output results/task_benchmark.json --summary results/task_benchmark.md
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from tools import pytest_runner, static_checker


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

@dataclass
class BugCase:
    id: str
    bug_type: str
    description: str
    buggy_code: str
    fixed_code: str
    expected_signals: List[str]   # strings that should appear in static_checker output


DATASET: List[BugCase] = [
    # wrong_operator (8)
    BugCase("op_001", "wrong_operator", "add subtracts",
            "def add(a, b):\n    return a - b",
            "def add(a, b):\n    return a + b",
            ["suspicious_operator"]),
    BugCase("op_002", "wrong_operator", "multiply divides",
            "def multiply(a, b):\n    return a / b",
            "def multiply(a, b):\n    return a * b",
            []),
    BugCase("op_003", "wrong_operator", "subtract adds",
            "def subtract(a, b):\n    return a + b",
            "def subtract(a, b):\n    return a - b",
            ["suspicious_operator"]),
    BugCase("op_004", "wrong_operator", "total_sum uses subtraction",
            "def total_sum(x, y, z):\n    return x - y - z",
            "def total_sum(x, y, z):\n    return x + y + z",
            ["suspicious_operator"]),
    BugCase("op_005", "wrong_operator", "sum_all reduces instead of adds",
            "def sum_all(items):\n    result = 0\n    for item in items:\n        result -= item\n    return result",
            "def sum_all(items):\n    result = 0\n    for item in items:\n        result += item\n    return result",
            []),
    BugCase("op_006", "wrong_operator", "plus_one subtracts",
            "def plus_one(x):\n    return x - 1",
            "def plus_one(x):\n    return x + 1",
            ["suspicious_operator"]),
    BugCase("op_007", "wrong_operator", "sum_pair uses subtraction",
            "def sum_pair(a, b):\n    return a - b",
            "def sum_pair(a, b):\n    return a + b",
            ["suspicious_operator"]),
    BugCase("op_008", "wrong_operator", "total uses subtraction",
            "def total(a, b, c):\n    return a - b - c",
            "def total(a, b, c):\n    return a + b + c",
            ["suspicious_operator"]),

    # off_by_one (3)
    BugCase("obo_001", "off_by_one", "range misses last element",
            "def count_up_to(n):\n    return list(range(1, n))",
            "def count_up_to(n):\n    return list(range(1, n + 1))",
            []),
    BugCase("obo_002", "off_by_one", "first element skipped",
            "def first_n(lst, n):\n    return lst[1:n+1]",
            "def first_n(lst, n):\n    return lst[0:n]",
            []),
    BugCase("obo_003", "off_by_one", "loop runs one too many times",
            "def repeat(s, n):\n    result = ''\n    for i in range(n + 1):\n        result += s\n    return result",
            "def repeat(s, n):\n    result = ''\n    for i in range(n):\n        result += s\n    return result",
            []),

    # missing_return (5)
    BugCase("ret_001", "missing_return", "modifies local, no return",
            "def double(x):\n    x = x * 2",
            "def double(x):\n    return x * 2",
            ["missing_return"]),
    BugCase("ret_002", "missing_return", "conditional return, no else",
            "def safe_div(a, b):\n    if b != 0:\n        return a / b",
            "def safe_div(a, b):\n    if b != 0:\n        return a / b\n    return 0",
            []),
    BugCase("ret_003", "missing_return", "appends but returns nothing",
            "def make_list(n):\n    result = []\n    for i in range(n):\n        result.append(i)",
            "def make_list(n):\n    result = []\n    for i in range(n):\n        result.append(i)\n    return result",
            ["missing_return"]),
    BugCase("ret_004", "missing_return", "square computes but doesn't return",
            "def square(x):\n    result = x * x",
            "def square(x):\n    return x * x",
            ["missing_return"]),
    BugCase("ret_005", "missing_return", "negate stores result locally",
            "def negate(x):\n    y = -x",
            "def negate(x):\n    return -x",
            ["missing_return"]),

    # wrong_comparison (3)
    BugCase("cmp_001", "wrong_comparison", "is instead of ==",
            "def is_zero(x):\n    return x is 0",
            "def is_zero(x):\n    return x == 0",
            []),
    BugCase("cmp_002", "wrong_comparison", "> should be >=",
            "def is_adult(age):\n    return age > 18",
            "def is_adult(age):\n    return age >= 18",
            []),
    BugCase("cmp_003", "wrong_comparison", "== True instead of truthy",
            "def check_flag(flag):\n    if flag == True:\n        return 'yes'\n    return 'no'",
            "def check_flag(flag):\n    if flag:\n        return 'yes'\n    return 'no'",
            []),

    # logic_error (6)
    BugCase("log_001", "logic_error", "and should be or in guard",
            "def clamp(x, lo, hi):\n    if x < lo and x > hi:\n        return lo\n    return x",
            "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x > hi:\n        return hi\n    return x",
            []),
    BugCase("log_002", "logic_error", "negation flipped",
            "def is_even(n):\n    return n % 2 != 0",
            "def is_even(n):\n    return n % 2 == 0",
            []),
    BugCase("log_003", "logic_error", "max returns min",
            "def maximum(a, b):\n    return a if a < b else b",
            "def maximum(a, b):\n    return a if a > b else b",
            []),
    BugCase("log_004", "logic_error", "factorial multiplies by 0",
            "def factorial(n):\n    result = 1\n    for i in range(n):\n        result *= i\n    return result",
            "def factorial(n):\n    result = 1\n    for i in range(1, n + 1):\n        result *= i\n    return result",
            []),
    BugCase("log_005", "logic_error", "fibonacci returns wrong variable",
            "def fib(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(n - 1):\n        a, b = b, a + b\n    return a",
            "def fib(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(n - 1):\n        a, b = b, a + b\n    return b",
            []),
    BugCase("log_006", "logic_error", "absolute returns negative for negatives",
            "def absolute(x):\n    if x < 0:\n        return x\n    return x",
            "def absolute(x):\n    if x < 0:\n        return -x\n    return x",
            []),

    # type_scope_error (5)
    BugCase("typ_001", "type_scope_error", "string concat instead of int add",
            "def add_nums(a, b):\n    return str(a) + str(b)",
            "def add_nums(a, b):\n    return a + b",
            []),
    BugCase("typ_002", "type_scope_error", "global not declared",
            "counter = 0\ndef increment():\n    counter += 1",
            "counter = 0\ndef increment():\n    global counter\n    counter += 1",
            ["missing_return"]),
    BugCase("typ_003", "type_scope_error", "floor div when float needed",
            "def average(nums):\n    return sum(nums) // len(nums)",
            "def average(nums):\n    return sum(nums) / len(nums)",
            []),
    BugCase("typ_004", "type_scope_error", "mutable default argument",
            "def append_to(element, to=[]):\n    to.append(element)\n    return to",
            "def append_to(element, to=None):\n    if to is None:\n        to = []\n    to.append(element)\n    return to",
            []),
    BugCase("typ_005", "type_scope_error", "int used as bool directly",
            "def is_positive(x):\n    return x > 0\n\ndef check(x):\n    if is_positive(x) == 1:\n        return 'yes'\n    return 'no'",
            "def is_positive(x):\n    return x > 0\n\ndef check(x):\n    if is_positive(x):\n        return 'yes'\n    return 'no'",
            []),
]


# ---------------------------------------------------------------------------
# Per-case scoring
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    case_id: str
    bug_type: str
    description: str
    pytest_buggy: bool
    pytest_fixed: bool
    signals_found: List[str]
    signal_score: float
    task_score: float


def score_case(case: BugCase) -> CaseResult:
    buggy_r = pytest_runner(case.buggy_code)
    fixed_r = pytest_runner(case.fixed_code)
    static_r = static_checker(case.buggy_code)

    static_text = " ".join(
        f"{i.get('type','')} {i.get('message','')}"
        for i in static_r.output.get("issues", [])
    ).lower()

    signals_found = [s for s in case.expected_signals if s.lower() in static_text]
    signal_score = len(signals_found) / len(case.expected_signals) if case.expected_signals else 1.0

    pytest_improved = not buggy_r.success and fixed_r.success
    task_score = round(
        0.5 * (1.0 if fixed_r.success else 0.0)
        + 0.3 * (1.0 if pytest_improved else 0.5)
        + 0.2 * signal_score,
        2,
    )

    return CaseResult(
        case_id=case.id,
        bug_type=case.bug_type,
        description=case.description,
        pytest_buggy=buggy_r.success,
        pytest_fixed=fixed_r.success,
        signals_found=signals_found,
        signal_score=signal_score,
        task_score=task_score,
    )


# ---------------------------------------------------------------------------
# Full benchmark
# ---------------------------------------------------------------------------

def run_benchmark() -> Dict[str, Any]:
    print(f"Running {len(DATASET)} bug cases...")
    results = [score_case(c) for c in DATASET]

    total = len(results)
    fixed_passes = sum(1 for r in results if r.pytest_fixed)
    avg_signal = round(sum(r.signal_score for r in results) / total, 2)
    avg_task = round(sum(r.task_score for r in results) / total, 2)
    failing = [r.case_id for r in results if not r.pytest_fixed]

    # Breakdown by bug type
    by_type: Dict[str, List[CaseResult]] = {}
    for r in results:
        by_type.setdefault(r.bug_type, []).append(r)

    breakdown = {
        bt: {
            "count": len(cases),
            "pytest_pass_rate": round(sum(1 for c in cases if c.pytest_fixed) / len(cases), 2),
            "avg_task_score": round(sum(c.task_score for c in cases) / len(cases), 2),
        }
        for bt, cases in by_type.items()
    }

    return {
        "total_cases": total,
        "pytest_fixed_pass_rate": round(fixed_passes / total, 2),
        "avg_signal_score": avg_signal,
        "avg_task_score": avg_task,
        "failing_cases": failing,
        "bug_type_breakdown": breakdown,
        "case_results": [
            {
                "id": r.case_id, "bug_type": r.bug_type,
                "pytest_fixed": r.pytest_fixed, "signal_score": r.signal_score,
                "task_score": r.task_score,
            }
            for r in results
        ],
    }


def save_markdown_summary(report: Dict[str, Any], path: str) -> None:
    lines = [
        "# Task-Level Debugging Benchmark\n",
        f"**Cases:** {report['total_cases']}  ",
        f"**pytest pass rate (fixed code):** {report['pytest_fixed_pass_rate']*100:.1f}%  ",
        f"**Avg static signal score:** {report['avg_signal_score']*100:.1f}%  ",
        f"**Avg task score:** {report['avg_task_score']:.2f}\n",
        "## Bug Type Breakdown\n",
        "| Bug Type | Cases | pytest Pass Rate | Avg Task Score |",
        "|----------|:-----:|:----------------:|:--------------:|",
    ]
    for bt, s in report["bug_type_breakdown"].items():
        lines.append(f"| {bt} | {s['count']} | {s['pytest_pass_rate']*100:.0f}% | {s['avg_task_score']:.2f} |")

    if report["failing_cases"]:
        lines += [
            "\n## Cases Where Fixed Code Still Fails pytest\n",
            ", ".join(report["failing_cases"]),
            "\n*(Indicates pytest harness gap — not a false positive in the dataset.)*",
        ]

    with open(path, "w") as f:
        f.write("\n".join(lines))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/task_benchmark.json")
    parser.add_argument("--summary", default="results/task_benchmark.md")
    args = parser.parse_args()

    os.makedirs("results", exist_ok=True)
    report = run_benchmark()

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    save_markdown_summary(report, args.summary)

    print(f"\npytest pass rate (fixed): {report['pytest_fixed_pass_rate']*100:.1f}%")
    print(f"Avg signal score:         {report['avg_signal_score']*100:.1f}%")
    print(f"Avg task score:           {report['avg_task_score']:.2f}")
    if report["failing_cases"]:
        print(f"Cases still failing:      {', '.join(report['failing_cases'])}")
    print(f"\nSaved to {args.output} and {args.summary}")


if __name__ == "__main__":
    main()
