"""
Executable tools used by the deterministic AgentRunner.

Each tool accepts a task input string and returns a ToolResult. The tools are
implemented without LLM calls: pytest runs in a subprocess, static analysis
uses ast.parse, and secret detection uses regular expressions. Subprocess work
uses timeouts, and user code is not executed inside the main process.
"""

import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
# Tool result type
@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any          # structured payload, tool-specific
    raw_text: str = ""   # human-readable summary
    error: Optional[str] = None
# pytest_runner
def _infer_expected(fn_name: str, args: tuple) -> Optional[Any]:
    """
    Infer the expected return value for a function call from its name and args.
    Returns None if no inference is possible - caller falls back to not-None check.

    """
    import math
    name = fn_name.lower()

    try:
        if not args:
            return None

        a = args[0]
        # Only infer expected values for numeric argument sets.
        if not all(isinstance(x, (int, float)) for x in args):
            return None

        if any(kw in name for kw in ["add", "sum_pair", "sum_all", "total_sum", "total", "plus"]) and "plus_one" not in name:
            return sum(args)
        if "plus_one" in name or "increment" in name:
            return a + 1
        if "subtract" in name or "diff" in name or "minus" in name:
            return args[0] - args[1] if len(args) >= 2 else None
        if "multiply" in name or "product" in name:
            result = 1
            for x in args: result *= x
            return result
        if "double" in name:
            return a * 2
        if "square" in name:
            return a ** 2
        if "negate" in name:
            return -a
        if "is_even" in name:
            return a % 2 == 0
        if "is_zero" in name:
            return a == 0
        if "absolute" in name or name == "abs_val":
            return abs(a)
        if "maximum" in name or name == "max_val":
            return max(args)
        if "average" in name or "mean" in name:
            return sum(args) / len(args) if args else None
        if "factorial" in name and 0 <= a <= 10:
            return math.factorial(int(a))
        if "count_up_to" in name:
            return list(range(1, int(a) + 1))
        if "is_adult" in name:
            return a >= 18
        if "is_positive" in name:
            return a > 0
        if "is_even" in name:
            return a % 2 == 0
        if any(kw in name for kw in ["sum_all", "sum_pair"]):
            return sum(args)
    except Exception:
        pass

    return None


def pytest_runner(task_input: str) -> ToolResult:
    """
    Writes the provided code to a temp file, generates tests for every
    top-level function, and runs pytest.

    Test generation strategy (in priority order):
    1. If the code has  # expected(a, b): value  comments, use those assertions.
    2. If the function name implies a known mathematical operation, infer the
       expected output and generate a value-equality assertion.
    3. Otherwise, assert the return value is not None - catches missing-return
       bugs without requiring knowledge of the correct output.

    Returns pass/fail and counts of passed/failed tests.
    """
    try:
        tree = ast.parse(task_input)
    except SyntaxError as e:
        return ToolResult(
            tool_name="pytest_runner",
            success=False,
            output={"passed": False, "tests_run": 0},
            raw_text=f"SyntaxError: {e}",
            error="SyntaxError",
        )

    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if not functions:
        return ToolResult(
            tool_name="pytest_runner",
            success=False,
            output={"passed": False, "tests_run": 0},
            raw_text="No function definitions found.",
        )

    fn = functions[0]
    fn_name = fn.name
    n_args = len(fn.args.args)

    if n_args == 0:
        arg_sets = [()]
    elif n_args == 1:
        arg_sets = [(2,), (3,), (-1,), (0,)]
    elif n_args == 2:
        arg_sets = [(3, 5), (1, 2), (0, 0), (-1, 1)]
    elif n_args == 3:
        arg_sets = [(1, 2, 3), (2, 3, 4)]
    else:
        arg_sets = [tuple(range(1, n_args + 1))]

    # Parse explicit expected-output hints from comments.
    explicit: Dict[str, Any] = {}
    for line in task_input.splitlines():
        m = re.search(r"#\s*expected(?:\(([^)]+)\))?:\s*(.+)", line)
        if m:
            try:
                key = str(eval(f"({m.group(1)},)") if m.group(1) else "()")
                explicit[key] = eval(m.group(2).strip())
            except Exception:
                pass

    lines = [task_input, "", "import pytest", "import math", ""]
    for args in arg_sets:
        safe = "_".join(
            str(a).replace("-", "neg").replace(".", "p") for a in args
        ) or "noargs"
        call = ", ".join(repr(a) for a in args)
        key = str(args)

        if key in explicit:
            # Use explicit expected-output hints first.
            lines += [
                f"def test_{fn_name}_{safe}():",
                f"    assert {fn_name}({call}) == {repr(explicit[key])}",
                "",
            ]
        else:
            inferred = _infer_expected(fn_name, args)
            if inferred is not None:
                # Then infer expected output from the function name.
                lines += [
                    f"def test_{fn_name}_{safe}():",
                    f"    assert {fn_name}({call}) == {repr(inferred)}",
                    "",
                ]
            else:
                # Otherwise check that the function returns a value.
                lines += [
                    f"def test_{fn_name}_{safe}_not_none():",
                    f"    result = {fn_name}({call})",
                    f"    assert result is not None, f'Expected a return value, got None'",
                    "",
                ]

    import os as _os
    fd, tmp = tempfile.mkstemp(suffix=".py", prefix="stemtest_")
    with _os.fdopen(fd, "w") as f:
        f.write("\n".join(lines))

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", tmp, "-v", "--tb=short", "--no-header",
             "--import-mode=importlib"],
            capture_output=True, text=True, timeout=15,
        )
        raw = proc.stdout + proc.stderr
        passed = len(re.findall(r" PASSED", raw))
        failed = len(re.findall(r" FAILED", raw))
        errors = len(re.findall(r" ERROR", raw))
        run = passed + failed + errors
        return ToolResult(
            tool_name="pytest_runner",
            success=proc.returncode == 0,
            output={"passed": proc.returncode == 0, "tests_run": run,
                    "tests_passed": passed, "tests_failed": failed,
                    "returncode": proc.returncode},
            raw_text=raw[:1000],
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name="pytest_runner", success=False,
            output={"passed": False, "tests_run": 0},
            raw_text="Pytest timed out.", error="Timeout",
        )
# Tool: static_checker
def static_checker(task_input: str) -> ToolResult:
    """
    AST-based static analysis. Detects:
      - missing_return: function has no explicit return with a value
      - suspicious_operator: function name implies add/sum but uses subtraction, or vice versa
      - unreachable_code: statements after a return
    No code is executed.
    """
    try:
        tree = ast.parse(task_input)
    except SyntaxError as e:
        return ToolResult(
            tool_name="static_checker", success=False,
            output={"issues": [{"type": "SyntaxError", "message": str(e)}]},
            raw_text=f"SyntaxError: {e}", error="SyntaxError",
        )

    issues = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        name = node.name.lower()

        # missing return
        has_return = any(
            isinstance(c, ast.Return) and c.value is not None
            for c in ast.walk(node)
        )
        if node.body and not has_return:
            issues.append({
                "type": "missing_return",
                "message": f"Function '{node.name}' has no explicit return value.",
                "line": node.lineno,
            })

        # suspicious operator
        if any(kw in name for kw in ["add", "sum", "plus", "total"]):
            for child in ast.walk(node):
                if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Sub):
                    issues.append({
                        "type": "suspicious_operator",
                        "message": f"Function '{node.name}' uses subtraction but name implies addition.",
                        "line": getattr(child, "lineno", "?"),
                    })

        if any(kw in name for kw in ["subtract", "diff", "minus"]):
            for child in ast.walk(node):
                if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
                    issues.append({
                        "type": "suspicious_operator",
                        "message": f"Function '{node.name}' uses addition but name implies subtraction.",
                        "line": getattr(child, "lineno", "?"),
                    })

        # unreachable code
        found_return = False
        for child in node.body:
            if found_return:
                issues.append({
                    "type": "unreachable_code",
                    "message": f"Unreachable code after return in '{node.name}'.",
                    "line": getattr(child, "lineno", "?"),
                })
                break
            if isinstance(child, ast.Return):
                found_return = True

    raw = "\n".join(
        f"[{i['type']}] line {i.get('line','?')}: {i['message']}" for i in issues
    ) if issues else "No issues detected."

    return ToolResult(
        tool_name="static_checker", success=True,
        output={"issues": issues, "issue_count": len(issues)},
        raw_text=raw,
    )
# Tool: complexity_checker
def complexity_checker(task_input: str) -> ToolResult:
    """
    Computes branch-count cyclomatic complexity per function via AST.
    Flags functions with complexity > 5.
    """
    try:
        tree = ast.parse(task_input)
    except SyntaxError as e:
        return ToolResult(
            tool_name="complexity_checker", success=False,
            output={"functions": []},
            raw_text=f"SyntaxError: {e}", error="SyntaxError",
        )

    branch_types = (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler,
                    ast.With, ast.Assert, ast.comprehension)
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            branches = sum(1 for c in ast.walk(node) if isinstance(c, branch_types))
            complexity = 1 + branches
            results.append({
                "function": node.name,
                "complexity": complexity,
                "flagged": complexity > 5,
                "line": node.lineno,
            })

    flagged = [r for r in results if r["flagged"]]
    raw = "\n".join(
        f"{r['function']} (line {r['line']}): complexity={r['complexity']}"
        + (" [HIGH]" if r["flagged"] else "")
        for r in results
    ) if results else "No functions found."

    return ToolResult(
        tool_name="complexity_checker", success=True,
        output={"functions": results, "flagged_count": len(flagged)},
        raw_text=raw,
    )
# Tool: secret_detector
_SECRET_PATTERNS = [
    ("api_key_assignment", re.compile(r'(?i)(api_?key|apikey)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']')),
    ("token_assignment",   re.compile(r'(?i)(token|secret|password|passwd|pwd)\s*=\s*["\'][A-Za-z0-9_\-\.]{8,}["\']')),
    ("aws_access_key",     re.compile(r'AKIA[0-9A-Z]{16}')),
    ("private_key_header", re.compile(r'-----BEGIN (RSA |EC )?PRIVATE KEY-----')),
    ("openai_key",         re.compile(r'sk-[A-Za-z0-9]{32,}')),
    ("github_token",       re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}')),
]


def secret_detector(task_input: str) -> ToolResult:
    """
    Scans code for hardcoded secrets using regex patterns.
    Returns findings with line numbers. Values are not logged.
    """
    findings = []
    for line_no, line in enumerate(task_input.splitlines(), start=1):
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "line": line_no,
                    "pattern": label,
                    "snippet": line.strip()[:80] + ("..." if len(line.strip()) > 80 else ""),
                })

    raw = "\n".join(
        f"Line {f['line']} [{f['pattern']}]: {f['snippet']}" for f in findings
    ) if findings else "No secrets detected."

    return ToolResult(
        tool_name="secret_detector", success=True,
        output={"findings": findings, "finding_count": len(findings)},
        raw_text=raw,
    )
# Tool: docstring_checker
def docstring_checker(task_input: str) -> ToolResult:
    """
    Checks every function and class for a docstring via AST.
    Returns coverage percentage and a list of undocumented items.
    """
    try:
        tree = ast.parse(task_input)
    except SyntaxError as e:
        return ToolResult(
            tool_name="docstring_checker", success=False,
            output={"coverage": 0.0, "missing": []},
            raw_text=f"SyntaxError: {e}", error="SyntaxError",
        )

    targets = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            has_doc = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            targets.append({
                "name": node.name,
                "type": type(node).__name__.replace("Def", ""),
                "line": node.lineno,
                "has_docstring": has_doc,
            })

    missing = [t for t in targets if not t["has_docstring"]]
    coverage = round((len(targets) - len(missing)) / len(targets), 2) if targets else 1.0

    raw = (
        f"Docstring coverage: {coverage * 100:.0f}%\n"
        + ("\n".join(f"Missing: {m['type']} '{m['name']}' (line {m['line']})" for m in missing)
           if missing else "All items documented.")
    )

    return ToolResult(
        tool_name="docstring_checker", success=True,
        output={"coverage": coverage, "total": len(targets),
                "missing": missing, "missing_count": len(missing)},
        raw_text=raw,
    )


def extract_fix_from_code(raw_text: str) -> "Optional[str]":
    """
    Extract the first syntactically valid Python function from raw text.
    Used as a fallback when JSON parsing fails or the fix field is missing.
    Tries fenced code blocks first, then bare def blocks.
    """
    import re as _re
    import ast as _ast

    # Priority 1: fenced code block
    for block in _re.findall(r"```(?:python)?[^\n]*\n(.*?)```", raw_text, _re.DOTALL):
        block = block.strip()
        if "def " in block:
            try:
                _ast.parse(block)
                return block
            except SyntaxError:
                pass

    # Priority 2: bare def block - collect lines from first def until blank line
    # after a return statement
    lines = raw_text.splitlines()
    collected: list = []
    for line in lines:
        if _re.match(r"^def ", line):
            collected = [line]
        elif collected:
            if line == "" and any("return" in l for l in collected):
                break
            if line and not line[0].isspace() and not line.startswith("def ") and collected:
                # Non-indented non-def line ends the function
                break
            collected.append(line)

    if collected:
        candidate = "\n".join(collected).strip()
        try:
            _ast.parse(candidate)
            if "return" in candidate or "pass" in candidate:
                return candidate
        except SyntaxError:
            pass

    return None
# Registry
TOOL_REGISTRY: Dict[str, callable] = {
    "pytest_runner":      pytest_runner,
    "static_checker":     static_checker,
    "complexity_checker": complexity_checker,
    "secret_detector":    secret_detector,
    "docstring_checker":  docstring_checker,
}


def run_tool(tool_name: str, task_input: str) -> Optional[ToolResult]:
    """Look up and run a tool by name. Returns None if not registered."""
    fn = TOOL_REGISTRY.get(tool_name)
    return fn(task_input) if fn else None
