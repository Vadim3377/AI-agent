"""
Held-out grading for debugging benchmarks.

A fix is graded by evaluating test expressions (e.g. "gcd(37, 600)") against
it and comparing with the same expressions evaluated against the ground-truth
fix. The model never sees these expressions, so it cannot tailor its fix to
them. Each run happens in a fresh interpreter with a timeout, so infinite
loops, crashes and global state in candidate code stay contained.
"""

import json
import subprocess
import sys
from typing import Any, Dict, List

TIMEOUT_S = 2

_HARNESS = """
import json, sys, types
_results = []
for _expr in json.loads(sys.stdin.read()):
    try:
        _value = eval(_expr)
        if isinstance(_value, types.GeneratorType):
            _value = list(_value)
        _results.append(["ok", _value])
    except Exception as _e:
        _results.append(["error", type(_e).__name__])
print(json.dumps(_results, default=repr))
"""


def evaluate(code: str, exprs: List[str]) -> List[List[Any]]:
    """
    Evaluate each expression after executing code; return [status, value] pairs.
    Expressions share one interpreter, so put stateful sequences in one expression.
    """
    if not code:
        return [["error", "NoFix"]] * len(exprs)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code + "\n" + _HARNESS],
            input=json.dumps(exprs), capture_output=True, text=True, timeout=TIMEOUT_S,
        )
        results = json.loads(proc.stdout.strip().splitlines()[-1])
        if len(results) == len(exprs):
            return results
    except subprocess.TimeoutExpired:
        return [["error", "Timeout"]] * len(exprs)
    except (IndexError, json.JSONDecodeError):
        pass
    # Code failed before the harness ran (syntax error, crash at import time).
    return [["error", "NoOutput"]] * len(exprs)


def expected_outputs(fixed_code: str, exprs: List[str]) -> List[List[Any]]:
    """Evaluate the ground-truth fix; every expression must succeed."""
    expected = evaluate(fixed_code, exprs)
    failed = [e for e, (status, _) in zip(exprs, expected) if status != "ok"]
    if failed:
        raise ValueError(f"ground-truth fix errors on: {failed}")
    return expected


def grade(fix: str, exprs: List[str], expected: List[List[Any]]) -> int:
    """Number of expressions on which the fix matches the ground truth."""
    return sum(got == want for got, want in zip(evaluate(fix, exprs), expected))


def check_task(buggy: str, fixed: str, exprs: List[str]) -> Dict[str, Any]:
    """Expected outputs, plus whether the buggy code actually fails any check."""
    expected = expected_outputs(fixed, exprs)
    return {
        "expected": expected,
        "bug_observable": grade(buggy, exprs, expected) < len(exprs),
    }
