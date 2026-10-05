"""
Benchmark debugging performance for base and mutated blueprints.

For each bug case, the script runs the base blueprint and the selected mutated
blueprint with the same LLM runner, extracts each suggested fix, and executes
pytest on the proposed code. This is the main before/after comparison for the
debugging specialist.
"""

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import held_out
import llm_backend
from tools import pytest_runner, static_checker
from domain_profiler import DomainProfiler
from architecture_generator import ArchitectureGenerator
from mutation_loop import MutationLoop
# Benchmark dataset
@dataclass
class BugCase:
    id: str
    bug_type: str
    description: str
    buggy_code: str
    fixed_code: str
    expected_signals: List[str]


DATASET: List[BugCase] = [
    BugCase("op_001", "wrong_operator", "add subtracts",
            "def add(a, b):\n    return a - b",
            "def add(a, b):\n    return a + b",
            ["suspicious_operator"]),
    BugCase("op_002", "wrong_operator", "multiply divides",
            "def multiply(a, b):\n    return a / b",
            "def multiply(a, b):\n    return a * b", []),
    BugCase("op_003", "wrong_operator", "subtract adds",
            "def subtract(a, b):\n    return a + b",
            "def subtract(a, b):\n    return a - b",
            ["suspicious_operator"]),
    BugCase("op_004", "wrong_operator", "total_sum uses subtraction",
            "def total_sum(x, y, z):\n    return x - y - z",
            "def total_sum(x, y, z):\n    return x + y + z",
            ["suspicious_operator"]),
    BugCase("op_005", "wrong_operator", "sum_all reduces",
            "def sum_all(items):\n    result = 0\n    for item in items:\n        result -= item\n    return result",
            "def sum_all(items):\n    result = 0\n    for item in items:\n        result += item\n    return result", []),
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
    BugCase("obo_001", "off_by_one", "range misses last element",
            "def count_up_to(n):\n    return list(range(1, n))",
            "def count_up_to(n):\n    return list(range(1, n + 1))", []),
    BugCase("obo_002", "off_by_one", "first element skipped",
            "def first_n(lst, n):\n    return lst[1:n+1]",
            "def first_n(lst, n):\n    return lst[0:n]", []),
    BugCase("obo_003", "off_by_one", "loop runs one too many",
            "def repeat(s, n):\n    result = ''\n    for i in range(n + 1):\n        result += s\n    return result",
            "def repeat(s, n):\n    result = ''\n    for i in range(n):\n        result += s\n    return result", []),
    BugCase("ret_001", "missing_return", "modifies local no return",
            "def double(x):\n    x = x * 2",
            "def double(x):\n    return x * 2",
            ["missing_return"]),
    BugCase("ret_002", "missing_return", "conditional no else",
            "def safe_div(a, b):\n    if b != 0:\n        return a / b",
            "def safe_div(a, b):\n    if b != 0:\n        return a / b\n    return 0", []),
    BugCase("ret_003", "missing_return", "appends returns nothing",
            "def make_list(n):\n    result = []\n    for i in range(n):\n        result.append(i)",
            "def make_list(n):\n    result = []\n    for i in range(n):\n        result.append(i)\n    return result",
            ["missing_return"]),
    BugCase("ret_004", "missing_return", "square no return",
            "def square(x):\n    result = x * x",
            "def square(x):\n    return x * x",
            ["missing_return"]),
    BugCase("ret_005", "missing_return", "negate stores locally",
            "def negate(x):\n    y = -x",
            "def negate(x):\n    return -x",
            ["missing_return"]),
    BugCase("cmp_001", "wrong_comparison", "is instead of ==",
            "def is_zero(x):\n    return x is 0",
            "def is_zero(x):\n    return x == 0", []),
    BugCase("cmp_002", "wrong_comparison", "> should be >=",
            "def is_adult(age):\n    return age > 18",
            "def is_adult(age):\n    return age >= 18", []),
    BugCase("cmp_003", "wrong_comparison", "== True instead of truthy",
            "def check_flag(flag):\n    if flag == True:\n        return 'yes'\n    return 'no'",
            "def check_flag(flag):\n    if flag:\n        return 'yes'\n    return 'no'", []),
    BugCase("log_001", "logic_error", "and should be or",
            "def clamp(x, lo, hi):\n    if x < lo and x > hi:\n        return lo\n    return x",
            "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x > hi:\n        return hi\n    return x", []),
    BugCase("log_002", "logic_error", "negation flipped",
            "def is_even(n):\n    return n % 2 != 0",
            "def is_even(n):\n    return n % 2 == 0", []),
    BugCase("log_003", "logic_error", "max returns min",
            "def maximum(a, b):\n    return a if a < b else b",
            "def maximum(a, b):\n    return a if a > b else b", []),
    BugCase("log_004", "logic_error", "factorial multiplies by 0",
            "def factorial(n):\n    result = 1\n    for i in range(n):\n        result *= i\n    return result",
            "def factorial(n):\n    result = 1\n    for i in range(1, n + 1):\n        result *= i\n    return result", []),
    BugCase("log_005", "logic_error", "fibonacci wrong variable",
            "def fib(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(n - 1):\n        a, b = b, a + b\n    return a",
            "def fib(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(n - 1):\n        a, b = b, a + b\n    return b", []),
    BugCase("log_006", "logic_error", "absolute wrong sign",
            "def absolute(x):\n    if x < 0:\n        return x\n    return x",
            "def absolute(x):\n    if x < 0:\n        return -x\n    return x", []),
    BugCase("typ_001", "type_scope_error", "string concat not int add",
            "def add_nums(a, b):\n    return str(a) + str(b)",
            "def add_nums(a, b):\n    return a + b", []),
    BugCase("typ_002", "type_scope_error", "global not declared",
            "counter = 0\ndef increment():\n    counter += 1",
            "counter = 0\ndef increment():\n    global counter\n    counter += 1",
            ["missing_return"]),
    BugCase("typ_003", "type_scope_error", "floor div not float",
            "def average(nums):\n    return sum(nums) // len(nums)",
            "def average(nums):\n    return sum(nums) / len(nums)", []),
    BugCase("typ_004", "type_scope_error", "mutable default argument",
            "def append_to(element, to=[]):\n    to.append(element)\n    return to",
            "def append_to(element, to=None):\n    if to is None:\n        to = []\n    to.append(element)\n    return to", []),
    BugCase("typ_005", "type_scope_error", "int used as bool",
            "def is_positive(x):\n    return x > 0\n\ndef check(x):\n    if is_positive(x) == 1:\n        return 'yes'\n    return 'no'",
            "def is_positive(x):\n    return x > 0\n\ndef check(x):\n    if is_positive(x):\n        return 'yes'\n    return 'no'", []),
]
# Held-out checks: expressions evaluated against the agent's fix and the
# ground-truth fix (see held_out.py). The model never sees these. Stateful
# checks are written as one tuple expression so they run in order.
HELD_OUT_CHECKS: Dict[str, List[str]] = {
    "op_001": ["add(2, 3)", "add(-4, 10)", "add(0, 0)", "add(2.5, 0.5)"],
    "op_002": ["multiply(2, 3)", "multiply(-4, 5)", "multiply(7, 0)", "multiply(1.5, 4)"],
    "op_003": ["subtract(10, 3)", "subtract(3, 10)", "subtract(0, 5)", "subtract(-2, -2)"],
    "op_004": ["total_sum(1, 2, 3)", "total_sum(10, -5, 2)", "total_sum(0, 0, 0)"],
    "op_005": ["sum_all([1, 2, 3])", "sum_all([])", "sum_all([-1, 5, 10])"],
    "op_006": ["plus_one(0)", "plus_one(41)", "plus_one(-1)"],
    "op_007": ["sum_pair(2, 3)", "sum_pair(-1, 1)", "sum_pair(100, 23)"],
    "op_008": ["total(1, 2, 3)", "total(10, 20, 30)", "total(-1, -2, -3)"],
    "obo_001": ["count_up_to(3)", "count_up_to(1)", "count_up_to(0)", "count_up_to(5)"],
    "obo_002": ["first_n([1, 2, 3, 4], 2)", "first_n(['a', 'b', 'c'], 3)", "first_n([9, 8], 0)"],
    "obo_003": ["repeat('ab', 3)", "repeat('x', 0)", "repeat('-', 1)"],
    "ret_001": ["double(2)", "double(-3)", "double(0)"],
    "ret_002": ["safe_div(6, 3)", "safe_div(1, 4)", "safe_div(5, 0) is not None"],
    "ret_003": ["make_list(3)", "make_list(0)", "make_list(1)"],
    "ret_004": ["square(3)", "square(-4)", "square(0)"],
    "ret_005": ["negate(5)", "negate(-2)", "negate(0)"],
    "cmp_001": ["is_zero(0)", "is_zero(0.0)", "is_zero(5)", "is_zero(-1)"],
    "cmp_002": ["is_adult(18)", "is_adult(17)", "is_adult(30)"],
    "cmp_003": ["check_flag(True)", "check_flag(False)", "check_flag('x')", "check_flag(0)", "check_flag([1])"],
    "log_001": ["clamp(5, 0, 10)", "clamp(-3, 0, 10)", "clamp(15, 0, 10)", "clamp(0, 0, 10)"],
    "log_002": ["is_even(4)", "is_even(7)", "is_even(0)", "is_even(-3)"],
    "log_003": ["maximum(3, 7)", "maximum(9, 2)", "maximum(-1, -5)", "maximum(4, 4)"],
    "log_004": ["factorial(0)", "factorial(1)", "factorial(5)", "factorial(6)"],
    "log_005": ["fib(0)", "fib(1)", "fib(2)", "fib(3)", "fib(10)"],
    "log_006": ["absolute(-5)", "absolute(3)", "absolute(0)"],
    "typ_001": ["add_nums(2, 3)", "add_nums(-1, 1)", "add_nums(10, 5)"],
    "typ_002": ["(increment(), increment(), counter)[-1]"],
    "typ_003": ["average([1, 2])", "average([1, 2, 4])", "average([5])"],
    "typ_004": ["(append_to(1), append_to(2))[-1]", "append_to(3, [1, 2])"],
    "typ_005": ["check(5)", "check(-1)", "check(0)"],
}


def held_out_expected() -> Dict[str, Dict[str, Any]]:
    """Expected outputs per case, and whether the bug is observable at all."""
    return {
        case.id: held_out.check_task(case.buggy_code, case.fixed_code, HELD_OUT_CHECKS[case.id])
        for case in DATASET
    }


def grade_held_out(case_id: str, fix: Optional[str], expected: Dict[str, Dict[str, Any]]) -> bool:
    checks = HELD_OUT_CHECKS[case_id]
    return held_out.grade(fix or "", checks, expected[case_id]["expected"]) == len(checks)
# Fix extraction from LLM output
def extract_fix(parsed_output: Optional[Dict]) -> Optional[str]:
    if not parsed_output or not isinstance(parsed_output, dict):
        return None
    for key in ("suggested_fix", "fix", "fixed_code", "corrected_code",
                "fix_code", "proposed_fix", "solution", "corrected_function"):
        if key in parsed_output and isinstance(parsed_output[key], str):
            val = parsed_output[key].strip()
            if val and ("def " in val or "return" in val or "=" in val):
                return _clean_code(val)
    for val in parsed_output.values():
        if isinstance(val, str) and "def " in val and "return" in val:
            return _clean_code(val)
    return None


def _clean_code(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        code = "\n".join(inner).strip()
    return code


def _extract_first_function(code: str) -> "Optional[str]":
    """Return the first syntactically valid function found in model output."""
    import ast as _ast
    lines = code.splitlines()
    for start in range(len(lines)):
        if lines[start].startswith("def "):
            for end in range(len(lines), start, -1):
                candidate = "\n".join(lines[start:end])
                try:
                    _ast.parse(candidate)
                    if "return" in candidate or "pass" in candidate:
                        return candidate
                except SyntaxError:
                    continue
    return None


def extract_fix_from_raw(raw_text: str) -> "Optional[str]":
    """Fallback: extract Python code from raw LLM text."""
    import re as _re
    # Fenced code block
    for block in _re.findall(r"```(?:python)?[^\n]*\n(.*?)```", raw_text, _re.DOTALL):
        block = block.strip()
        if "def " in block or "return" in block:
            return block
    # Bare def block
    lines = raw_text.splitlines()
    collected: list = []
    for line in lines:
        if _re.match(r"^def ", line):
            collected = [line]
        elif collected:
            if line == "" and any("return" in l for l in collected):
                break
            collected.append(line)
    if collected and any("return" in l for l in collected):
        return "\n".join(collected).strip()
    return None
# Per-case scoring
@dataclass
class CaseResult:
    case_id: str
    bug_type: str
    description: str
    static_signals_found: List[str]
    signal_score: float
    agent_fix: Optional[str]
    fix_extracted: bool
    pytest_passed: bool
    agent_score: float
    rounds_taken: int = 0
    first_attempt_passed: Optional[bool] = None
    raw_output: Optional[str] = None


def evaluate_case(case: BugCase, blueprint, llm_runner, use_llm: bool) -> CaseResult:
    # Static analysis always runs
    static_r = static_checker(case.buggy_code)
    static_text = " ".join(
        f"{i.get('type','')} {i.get('message','')}"
        for i in static_r.output.get("issues", [])
    ).lower()
    signals_found = [s for s in case.expected_signals if s.lower() in static_text]
    signal_score = (
        len(signals_found) / len(case.expected_signals)
        if case.expected_signals else 1.0
    )

    if not use_llm or llm_runner is None:
        return CaseResult(
            case_id=case.id, bug_type=case.bug_type, description=case.description,
            static_signals_found=signals_found, signal_score=signal_score,
            agent_fix=None, fix_extracted=False, pytest_passed=False,
            agent_score=round(0.3 * signal_score, 2),
        )

    try:
        result = llm_runner.run(blueprint, case.buggy_code)
        raw_output = result.get("raw_output", "")
        # Try structured JSON first, fall back to extracting code from raw text
        agent_fix = extract_fix(result.get("parsed_output"))
        if not agent_fix and raw_output:
            agent_fix = extract_fix_from_raw(raw_output)
    except Exception as e:
        return CaseResult(
            case_id=case.id, bug_type=case.bug_type, description=case.description,
            static_signals_found=signals_found, signal_score=signal_score,
            agent_fix=None, fix_extracted=False, pytest_passed=False,
            agent_score=round(0.3 * signal_score, 2), raw_output=str(e),
        )

    if not agent_fix:
        return CaseResult(
            case_id=case.id, bug_type=case.bug_type, description=case.description,
            static_signals_found=signals_found, signal_score=signal_score,
            agent_fix=None, fix_extracted=False, pytest_passed=False,
            agent_score=round(0.3 * signal_score, 2), raw_output=raw_output,
        )

    # Validate the extracted code is syntactically valid before running pytest
    import ast as _ast
    try:
        _ast.parse(agent_fix)
    except SyntaxError:
        # Try stripping to just the first function definition
        agent_fix = _extract_first_function(agent_fix) or agent_fix

    # Use final_pytest_passed and rounds_taken from runner if feedback loop was used
    rounds_taken = result.get("rounds_taken", 0)
    first_attempt_passed = result.get("first_attempt_passed", None)
    final_pytest_passed = result.get("final_pytest_passed", None)

    if final_pytest_passed is not None:
        # Runner ran the feedback loop and already tested the fix
        pytest_passed = final_pytest_passed
        # Use the final fix from the loop if available
        loop_fix = result.get("final_fix")
        if loop_fix:
            agent_fix = loop_fix
    else:
        # Single-shot runner: run pytest ourselves
        pytest_r = pytest_runner(agent_fix)
        pytest_passed = pytest_r.success
        if first_attempt_passed is None:
            first_attempt_passed = pytest_passed

    agent_score = round(0.7 * (1.0 if pytest_passed else 0.0) + 0.3 * signal_score, 2)

    return CaseResult(
        case_id=case.id, bug_type=case.bug_type, description=case.description,
        static_signals_found=signals_found, signal_score=signal_score,
        agent_fix=agent_fix, fix_extracted=True, pytest_passed=pytest_passed,
        agent_score=agent_score, rounds_taken=rounds_taken,
        first_attempt_passed=first_attempt_passed, raw_output=raw_output,
    )
# Full benchmark
def run_agent_benchmark(use_llm: bool = True) -> Dict[str, Any]:
    load_dotenv()

    task_prompt = (
        "Debug this Python function. "
        "Identify the bug, explain the root cause, and provide the corrected code."
    )
    sample_input = "def add(a, b):\n    return a - b"

    print("Growing base blueprint...")
    profiler = DomainProfiler()
    arch_gen = ArchitectureGenerator()
    profile = profiler.profile(task_prompt)
    base_blueprint = arch_gen.generate(profile)

    print("Running multi-round evolution...")
    loop = MutationLoop(max_rounds=4, run_tools=True)
    evolution = loop.run(base_blueprint, task_input=sample_input)
    selected_blueprint = evolution.best_blueprint

    print(f"  Base:     {base_blueprint.name}")
    print(f"  Selected: {selected_blueprint.name}")
    print(f"  Rounds:   {evolution.total_mutations}  Best score: {evolution.best_score:.2f}\n")

    llm_runner = None
    if use_llm:
        try:
            from llm_agent_runner import LLMAgentRunner
            llm_runner = LLMAgentRunner()
            print(f"LLM runner ready (model: {llm_runner.model})\n")
        except Exception as e:
            print(f"LLM runner unavailable: {e}\nFalling back to static-only mode.\n")
            use_llm = False

    base_results, selected_results = [], []
    total = len(DATASET)

    for i, case in enumerate(DATASET, 1):
        print(f"  [{i:02d}/{total}] {case.id}: {case.description}")
        base_r = evaluate_case(case, base_blueprint, llm_runner, use_llm)
        sel_r = evaluate_case(case, selected_blueprint, llm_runner, use_llm)
        base_results.append(base_r)
        selected_results.append(sel_r)
        if use_llm:
            b_s = "OK" if base_r.pytest_passed else "FAIL"
            s_s = "OK" if sel_r.pytest_passed else "FAIL"
            print(f"         base={b_s}({base_r.agent_score:.2f},r={base_r.rounds_taken})"
                  f"  selected={s_s}({sel_r.agent_score:.2f},r={sel_r.rounds_taken})")

    def aggregate(results):
        n = len(results)
        fe = sum(1 for r in results if r.fix_extracted)
        pp = sum(1 for r in results if r.pytest_passed)
        by_type = {}
        for r in results:
            by_type.setdefault(r.bug_type, []).append(r)
        rounds_list = [r.rounds_taken for r in results]
        first_pass = [r for r in results if r.first_attempt_passed is True]
        return {
            "total_cases": n,
            "fix_extracted_rate": round(fe / n, 2),
            "pytest_pass_rate": round(pp / n, 2),
            "avg_agent_score": round(sum(r.agent_score for r in results) / n, 3),
            "avg_signal_score": round(sum(r.signal_score for r in results) / n, 3),
            "avg_rounds_taken": round(sum(rounds_list) / n, 2),
            "first_attempt_pass_rate": round(len(first_pass) / n, 2),
            "bug_type_breakdown": {
                bt: {
                    "count": len(cs),
                    "fix_extracted": sum(1 for c in cs if c.fix_extracted),
                    "pytest_pass_rate": round(sum(1 for c in cs if c.pytest_passed) / len(cs), 2),
                    "avg_agent_score": round(sum(c.agent_score for c in cs) / len(cs), 2),
                }
                for bt, cs in by_type.items()
            },
        }

    base_agg = aggregate(base_results)
    sel_agg = aggregate(selected_results)
    imp_score = round(sel_agg["avg_agent_score"] - base_agg["avg_agent_score"], 3)
    imp_pytest = round(sel_agg["pytest_pass_rate"] - base_agg["pytest_pass_rate"], 3)

    return {
        "mode": "llm" if use_llm else "static_only",
        "llm_usage": llm_backend.summarise_runs(llm_runner.run_log) if use_llm else None,
        "base_blueprint": base_blueprint.name,
        "selected_blueprint": selected_blueprint.name,
        "evolution_rounds": evolution.total_mutations,
        "evolution_best_score": evolution.best_score,
        "base": base_agg,
        "selected": sel_agg,
        "improvement": {
            "avg_agent_score_delta": imp_score,
            "pytest_pass_rate_delta": imp_pytest,
            "cases_improved": [
                r.case_id for r, b in zip(selected_results, base_results)
                if r.agent_score > b.agent_score
            ],
            "cases_regressed": [
                r.case_id for r, b in zip(selected_results, base_results)
                if r.agent_score < b.agent_score
            ],
            "cases_failed_both": [
                r.case_id for r, b in zip(selected_results, base_results)
                if not r.pytest_passed and not b.pytest_passed and r.fix_extracted
            ],
        },
        "case_results": {
            "base": [
                {"id": r.case_id, "bug_type": r.bug_type, "fix_extracted": r.fix_extracted,
                 "pytest_passed": r.pytest_passed, "signal_score": r.signal_score,
                 "agent_score": r.agent_score, "rounds_taken": r.rounds_taken,
                 "first_attempt_passed": r.first_attempt_passed, "agent_fix": r.agent_fix}
                for r in base_results
            ],
            "selected": [
                {"id": r.case_id, "bug_type": r.bug_type, "fix_extracted": r.fix_extracted,
                 "pytest_passed": r.pytest_passed, "signal_score": r.signal_score,
                 "agent_score": r.agent_score, "rounds_taken": r.rounds_taken,
                 "first_attempt_passed": r.first_attempt_passed, "agent_fix": r.agent_fix}
                for r in selected_results
            ],
        },
    }


def add_held_out_grading(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Grade each blueprint's final fix on the held-out checks and add the results
    to the report. Cases whose buggy code passes every check are excluded.
    """
    expected = held_out_expected()
    excluded = sorted(cid for cid, e in expected.items() if not e["bug_observable"])
    summary: Dict[str, Any] = {"excluded_no_observable_bug": excluded}
    for name in ("base", "selected"):
        passed = 0
        graded = 0
        for case in report["case_results"][name]:
            ok = grade_held_out(case["id"], case.get("agent_fix"), expected)
            case["held_out_passed"] = ok
            if case["id"] not in excluded:
                graded += 1
                passed += ok
        summary[name] = {"passed": passed, "graded": graded,
                         "pass_rate": round(passed / graded, 2) if graded else 0.0}
    report["held_out"] = summary
    return report


def save_markdown(report: Dict, path: str) -> None:
    mode = report["mode"]
    base = report["base"]
    sel = report["selected"]
    imp = report["improvement"]

    lines = [
        "# Task-Level Agent Benchmark\n",
        f"**Mode:** {mode}  ",
        f"**Base blueprint:** `{report['base_blueprint']}`  ",
        f"**Selected blueprint:** `{report['selected_blueprint']}`  ",
        f"**Evolution rounds:** {report['evolution_rounds']}  best score {report['evolution_best_score']:.2f}\n",
        "## Before / After Comparison\n",
        "| Metric | Base Blueprint | Selected Blueprint | delta |",
        "|--------|:--------------:|:-----------------:|:---:|",
    ]
    held = report.get("held_out")
    if mode == "llm" and held:
        hb, hs = held["base"], held["selected"]
        lines.append(
            f"| **Held-out pass rate (correctness)** | **{hb['passed']}/{hb['graded']} ({hb['pass_rate']:.0%})** "
            f"| **{hs['passed']}/{hs['graded']} ({hs['pass_rate']:.0%})** "
            f"| **{hs['pass_rate'] - hb['pass_rate']:+.0%}** |"
        )
    if mode == "llm":
        lines += [
            f"| Fix extracted rate | {base['fix_extracted_rate']*100:.0f}% | {sel['fix_extracted_rate']*100:.0f}% | -- |",
            f"| First-attempt self-check pass rate | {base['first_attempt_pass_rate']*100:.0f}% | {sel['first_attempt_pass_rate']*100:.0f}% | **{(sel['first_attempt_pass_rate']-base['first_attempt_pass_rate'])*100:+.0f}%** |",
            f"| Final self-check (pytest_runner smoke tests) | {base['pytest_pass_rate']*100:.0f}% | {sel['pytest_pass_rate']*100:.0f}% | **{imp['pytest_pass_rate_delta']:+.0%}** |",
            f"| Avg revision rounds | {base['avg_rounds_taken']:.2f} | {sel['avg_rounds_taken']:.2f} | **{sel['avg_rounds_taken']-base['avg_rounds_taken']:+.2f}** |",
        ]
    lines += [
        f"| Static signal score | {base['avg_signal_score']*100:.0f}% | {sel['avg_signal_score']*100:.0f}% | -- |",
        f"| **Avg agent score** | **{base['avg_agent_score']:.3f}** | **{sel['avg_agent_score']:.3f}** | **{imp['avg_agent_score_delta']:+.3f}** |",
        "",
    ]
    if report.get("llm_usage"):
        lines += ["## LLM Usage (per task = one runner.run, incl. revision rounds)\n",
                  "```", llm_backend.format_usage(report["llm_usage"]), "```", ""]
    lines += [
        "## Bug Type Breakdown (Selected Blueprint)\n",
        "| Bug Type | Cases | Fix Extracted | pytest Pass | Avg Score |",
        "|----------|:-----:|:-------------:|:-----------:|:---------:|",
    ]
    for bt, s in sel["bug_type_breakdown"].items():
        fe = f"{s['fix_extracted']}/{s['count']}" if mode == "llm" else "--"
        pp = f"{s['pytest_pass_rate']*100:.0f}%" if mode == "llm" else "--"
        lines.append(f"| {bt} | {s['count']} | {fe} | {pp} | {s['avg_agent_score']:.2f} |")

    if mode == "llm":
        if imp["cases_improved"]:
            lines += ["\n## Cases Improved by Mutation\n", ", ".join(imp["cases_improved"])]
        if imp["cases_regressed"]:
            lines += ["\n## Cases Regressed\n", ", ".join(imp["cases_regressed"]),
                      "\n*(Mutated blueprint produced a worse fix for these cases.)*"]
        if imp["cases_failed_both"]:
            lines += ["\n## Failed Both Blueprints\n", ", ".join(imp["cases_failed_both"]),
                      "\n*(Agent extracted a fix but pytest still failed -- genuinely hard cases.)*"]
        if held:
            failed = {
                name: [c["id"] for c in report["case_results"][name]
                       if not c.get("held_out_passed") and c["id"] not in held["excluded_no_observable_bug"]]
                for name in ("base", "selected")
            }
            lines += [
                "\n## Held-out Grading\n",
                "Each final fix is run on held-out checks whose expected outputs come from the",
                "case's ground-truth fix; the model never sees them. The self-check rows use",
                "pytest_runner, which for most bug types only asserts a non-None return value,",
                "so they overstate correctness.\n",
                f"- Failed held-out (base): {', '.join(failed['base']) or 'none'}",
                f"- Failed held-out (selected): {', '.join(failed['selected']) or 'none'}",
                f"- Excluded (buggy code passes every check, no observable bug): "
                f"{', '.join(held['excluded_no_observable_bug']) or 'none'}",
            ]
    else:
        lines += ["\n---\n",
                  "*Static-only mode. Re-run with an LLM provider configured to get fix-quality scores.*"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _debug_one_case(case_id: str, use_llm: bool = True) -> None:
    """Print full detail for a single bug case: raw LLM output, extracted fix, pytest result."""
    load_dotenv()
    case = next((c for c in DATASET if c.id == case_id), None)
    if case is None:
        print(f"Case {case_id!r} not found. Available: {[c.id for c in DATASET]}")
        return

    from domain_profiler import DomainProfiler
    from architecture_generator import ArchitectureGenerator
    from mutation_loop import MutationLoop

    profiler = DomainProfiler()
    arch_gen = ArchitectureGenerator()
    profile = profiler.profile("Debug this Python function.")
    blueprint = arch_gen.generate(profile)

    print(f"Case: {case.id} - {case.description}")
    print(f"Buggy code:\n{case.buggy_code}\n")

    if use_llm:
        from llm_agent_runner import LLMAgentRunner
        runner = LLMAgentRunner()
        result = runner.run(blueprint, case.buggy_code)
        print(f"--- RAW LLM OUTPUT ---\n{result.get('raw_output', '')}\n")
        print(f"--- PARSED OUTPUT ---\n{result.get('parsed_output')}\n")
        fix = extract_fix(result.get("parsed_output"))
        if not fix:
            fix = extract_fix_from_raw(result.get("raw_output", ""))
        print(f"--- EXTRACTED FIX ---\n{fix}\n")
        if fix:
            r = pytest_runner(fix)
            print(f"--- PYTEST RESULT --- success={r.success}")
            print(r.raw_text[:600])
    else:
        print("(--no-llm mode, skipping LLM call)")
        from tools import static_checker
        r = static_checker(case.buggy_code)
        print(f"Static issues: {r.output['issues']}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/task_benchmark.json")
    parser.add_argument("--summary", default="results/task_benchmark.md")
    parser.add_argument("--no-llm", action="store_true",
                        help="Static analysis only, no API calls.")
    parser.add_argument("--debug-case", type=str, default=None,
                        help="Run and print full detail for one case ID (e.g. op_001).")
    parser.add_argument("--regrade", action="store_true",
                        help="Re-grade the fixes saved in --output on held-out checks; no API calls.")
    llm_backend.add_cli_args(parser)
    args = parser.parse_args()
    llm_backend.apply_cli_args(args)
    args.output = llm_backend.results_path(args.output, args.provider)
    args.summary = llm_backend.results_path(args.summary, args.provider)

    os.makedirs("results", exist_ok=True)

    if args.debug_case:
        _debug_one_case(args.debug_case, use_llm=not args.no_llm)
        return

    if args.regrade:
        with open(args.output, encoding="utf-8") as f:
            report = json.load(f)
    else:
        report = run_agent_benchmark(use_llm=not args.no_llm)
    if report["mode"] == "llm":
        add_held_out_grading(report)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    save_markdown(report, args.summary)

    print(f"\n{'='*55}")
    base = report["base"]
    sel = report["selected"]
    imp = report["improvement"]
    if report["mode"] == "llm":
        print(f"{'Metric':<36} {'Base':>7} {'Selected':>9} {'delta':>7}")
        print("-" * 61)
        hb, hs = report["held_out"]["base"], report["held_out"]["selected"]
        print(f"{'Held-out pass rate (correctness)':<36} {hb['pass_rate']*100:>6.0f}% {hs['pass_rate']*100:>8.0f}%  {(hs['pass_rate']-hb['pass_rate'])*100:>+.0f}%")
        print(f"{'Fix extracted rate':<36} {base['fix_extracted_rate']*100:>6.0f}% {sel['fix_extracted_rate']*100:>8.0f}%")
        print(f"{'First-attempt pass rate':<36} {base['first_attempt_pass_rate']*100:>6.0f}% {sel['first_attempt_pass_rate']*100:>8.0f}%  {(sel['first_attempt_pass_rate']-base['first_attempt_pass_rate'])*100:>+.0f}%")
        print(f"{'Final pytest pass rate':<36} {base['pytest_pass_rate']*100:>6.0f}% {sel['pytest_pass_rate']*100:>8.0f}%  {imp['pytest_pass_rate_delta']*100:>+.0f}%")
        print(f"{'Avg revision rounds taken':<36} {base['avg_rounds_taken']:>7.2f} {sel['avg_rounds_taken']:>9.2f}  {sel['avg_rounds_taken']-base['avg_rounds_taken']:>+.2f}")
    print(f"{'Avg agent score':<36} {base['avg_agent_score']:>7.3f} {sel['avg_agent_score']:>9.3f}  {imp['avg_agent_score_delta']:>+.3f}")
    if report.get("llm_usage"):
        print("\n" + llm_backend.format_usage(report["llm_usage"]))
    print(f"\nSaved: {args.output}  {args.summary}")


if __name__ == "__main__":
    main()
