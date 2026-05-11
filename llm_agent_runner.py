"""
Execute selected blueprints with an OpenAI-backed runner.

The runner supports single-shot execution and two active feedback loops:
debugging, where generated fixes are checked with pytest and revised on
failure, and documentation, where generated docstrings are checked for
quality-aware coverage and revised when incomplete.

Only blueprints containing active verification steps trigger these loops. This
keeps base and mutated blueprint comparisons meaningful because both use the
same model while differing in workflow structure.
"""

import ast
import json
import os
import re
import textwrap
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from models import AgentBlueprint
from tools import pytest_runner, extract_fix_from_code

load_dotenv()

MAX_REVISION_ROUNDS = 3
MAX_DOC_REVISION_ROUNDS = 2
MIN_DOCSTRING_COVERAGE = 0.90   # requires all-but-one complete in 5-symbol modules
# Blueprint capability detection
_VERIFICATION_SIGNALS = [
    "verify_fix", "verify_against", "check_fix",
    "regression_risk", "rerun", "validate_fix",
]

_DOC_VERIFICATION_SIGNALS = [
    "verify_docstring", "check_coverage", "docstring_coverage",
    "verify_comment", "coverage_check", "check_docstrings",
]


def _blueprint_expects_verification(blueprint: AgentBlueprint) -> bool:
    text = " ".join(blueprint.workflow).lower()
    return any(signal in text for signal in _VERIFICATION_SIGNALS)


def _blueprint_expects_doc_verification(blueprint: AgentBlueprint) -> bool:
    text = " ".join(blueprint.workflow).lower()
    return any(signal in text for signal in _DOC_VERIFICATION_SIGNALS)
# Quality-aware docstring checker used by the runner and benchmark
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


def _get_public_nodes(tree: ast.Module) -> List[ast.AST]:
    """
    Return module-level and class-level function/class nodes only.

    ast.walk traverses the entire tree, picking up nested functions
    (closures, helpers defined inside other functions). These are
    implementation details that should not be required to have docstrings.

    This function uses ast.iter_child_nodes at two levels:
      - Module children: top-level functions and classes
      - Class children: methods (one level inside a class body)

    Nested functions defined inside other functions are excluded.
    """
    nodes: List[ast.AST] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            nodes.append(node)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nodes.append(child)
    return nodes


def _measure_docstring_coverage(code: str) -> Dict[str, Any]:
    """
    Quality-aware docstring coverage.

    A symbol is COMPLETE if:
    - It has any docstring, AND
    - Functions with params have an Args: section, AND
    - Functions with return values have a Returns: section
    - Classes need only a docstring (no Args/Returns required)

    Only top-level and class-level symbols are counted.
    Nested functions (closures) are excluded.

    Returns:
        coverage  : fraction of public symbols with complete docstrings
        total     : total public symbols examined
        complete  : count of complete symbols
        missing   : names of symbols with no docstring
        incomplete: names of symbols with docstring but missing Args/Returns
        success   : False if code could not be parsed
    """
    if not code.strip():
        return {
            "coverage": 0.0, "total": 0, "complete": 0,
            "missing": [], "incomplete": [], "success": False,
        }

    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError as exc:
        return {
            "coverage": 0.0, "total": 0, "complete": 0,
            "missing": [], "incomplete": [], "error": str(exc), "success": False,
        }

    total = 0
    complete = 0
    missing: List[str] = []
    incomplete: List[str] = []

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
        "missing": missing,
        "incomplete": incomplete,
        "success": True,
    }
# Code extraction helper
def _extract_python_code(raw: str) -> str:
    blocks = re.findall(r"```python\s*\n(.*?)```", raw, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    blocks = re.findall(r"```\s*\n(.*?)```", raw, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    try:
        ast.parse(raw.strip())
        return raw.strip()
    except SyntaxError:
        return ""
# Main runner
class LLMAgentRunner:
    """
    Executes a selected AgentBlueprint using an OpenAI model with
    tool feedback loops for debugging and documentation domains.
    """

    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is missing. Set it in .env or environment.")
        self.client = OpenAI()
        self.model = model

    def run(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        subdomain = blueprint.domain_profile.subdomain.lower()

        if "debug" in subdomain and _blueprint_expects_verification(blueprint):
            return self._run_debugging_loop(blueprint, task_input)

        if ("doc" in subdomain or "comment" in subdomain) and _blueprint_expects_doc_verification(blueprint):
            return self._run_documentation_loop(blueprint, task_input)

        return self._run_single_shot(blueprint, task_input)
    # Single-shot execution
    def _run_single_shot(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        prompt = self._build_initial_prompt(blueprint, task_input)
        raw_text = self._call_llm(prompt)
        parsed = self._try_parse_json(raw_text)
        return {
            "runner": "llm",
            "model": self.model,
            "blueprint_name": blueprint.name,
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "workflow": blueprint.workflow,
            "task_input_preview": task_input[:250],
            "raw_output": raw_text,
            "parsed_output": parsed,
            "final_status": "completed",
            "rounds_taken": 0,
            "first_attempt_passed": None,
            "final_pytest_passed": None,
        }
    # Debugging feedback loop
    def _run_debugging_loop(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        history: List[Dict[str, str]] = []
        history.append({"role": "user", "content": self._build_initial_prompt(blueprint, task_input)})

        rounds_taken = 0
        first_attempt_passed: Optional[bool] = None
        final_fix: Optional[str] = None
        final_parsed: Optional[Dict] = None
        final_raw: str = ""
        final_pytest_passed = False

        for round_no in range(MAX_REVISION_ROUNDS + 1):
            raw_text = self._call_llm_with_history(history)
            final_raw = raw_text
            history.append({"role": "assistant", "content": raw_text})
            parsed = self._try_parse_json(raw_text)
            final_parsed = parsed

            fix = self._extract_fix(parsed, raw_text)
            final_fix = fix

            if not fix:
                if round_no < MAX_REVISION_ROUNDS:
                    history.append({
                        "role": "user",
                        "content": (
                            "Your response did not contain a complete Python function. "
                            "Please provide the full corrected function starting with 'def '. "
                            "Return only valid JSON."
                        ),
                    })
                rounds_taken = round_no
                continue

            pytest_result = pytest_runner(fix)
            final_pytest_passed = pytest_result.success

            if round_no == 0:
                first_attempt_passed = pytest_result.success

            if pytest_result.success:
                rounds_taken = round_no
                break

            if round_no < MAX_REVISION_ROUNDS:
                failure_summary = self._summarise_pytest_failure(pytest_result.raw_text, fix)
                history.append({
                    "role": "user",
                    "content": self._build_revision_prompt(
                        task_input, fix, failure_summary, round_no + 1
                    ),
                })
                rounds_taken = round_no + 1
            else:
                rounds_taken = round_no

        return {
            "runner": "llm_with_feedback",
            "model": self.model,
            "blueprint_name": blueprint.name,
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "workflow": blueprint.workflow,
            "task_input_preview": task_input[:250],
            "raw_output": final_raw,
            "parsed_output": final_parsed,
            "final_fix": final_fix,
            "final_status": "completed",
            "rounds_taken": rounds_taken,
            "first_attempt_passed": first_attempt_passed,
            "final_pytest_passed": final_pytest_passed,
            "history_length": len(history),
        }
    # Documentation feedback loop
    def _run_documentation_loop(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        """
        Multi-turn documentation loop using quality-aware coverage.

        round 0: ask for documented code with Google-style Args/Returns sections
        round 1+: measure quality coverage with the AST checker; if below
                  MIN_DOCSTRING_COVERAGE, send back the list of incomplete
                  symbols and request a targeted revision

        Stops when quality coverage >= MIN_DOCSTRING_COVERAGE or
        MAX_DOC_REVISION_ROUNDS is reached. The stopping criterion is
        evidence-driven: the agent stops when a real tool confirms the quality
        target is met, not when a fixed iteration count is exhausted.
        """
        history: List[Dict[str, str]] = []
        history.append({"role": "user", "content": self._build_doc_prompt(blueprint, task_input)})

        doc_rounds_taken = 0
        initial_coverage: Optional[float] = None
        final_coverage: Optional[float] = None
        final_code: str = ""
        final_raw: str = ""

        for round_no in range(MAX_DOC_REVISION_ROUNDS + 1):
            raw_text = self._call_llm_with_history(history)
            final_raw = raw_text
            history.append({"role": "assistant", "content": raw_text})

            code = _extract_python_code(raw_text)
            if not code:
                parsed = self._try_parse_json(raw_text)
                if parsed and isinstance(parsed, dict):
                    for key in ("documented_code", "code", "result", "output"):
                        val = parsed.get(key, "")
                        if isinstance(val, str) and val.strip():
                            code = _extract_python_code(val) or val.strip()
                            break

            final_code = code

            cov_result = _measure_docstring_coverage(code)
            coverage = cov_result["coverage"]
            missing = cov_result.get("missing", [])
            incomplete = cov_result.get("incomplete", [])
            all_needing_work = missing + incomplete

            if round_no == 0:
                initial_coverage = coverage

            final_coverage = coverage
            doc_rounds_taken = round_no

            if coverage >= MIN_DOCSTRING_COVERAGE or not all_needing_work:
                break

            if round_no < MAX_DOC_REVISION_ROUNDS:
                history.append({
                    "role": "user",
                    "content": self._build_doc_revision_prompt(
                        coverage, missing, incomplete, round_no + 1
                    ),
                })

        return {
            "runner": "llm_with_doc_feedback",
            "model": self.model,
            "blueprint_name": blueprint.name,
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "workflow": blueprint.workflow,
            "task_input_preview": task_input[:250],
            "raw_output": final_raw,
            "final_code": final_code,
            "final_status": "completed",
            "doc_rounds_taken": doc_rounds_taken,
            "initial_coverage": initial_coverage,
            "final_coverage": final_coverage,
            "coverage_improved": (final_coverage or 0) > (initial_coverage or 0),
            "history_length": len(history),
        }
    # Prompt builders
    def _build_initial_prompt(self, blueprint: AgentBlueprint, task_input: str) -> str:
        schema_str = json.dumps(blueprint.output_schema, indent=2)
        tools_str = json.dumps(blueprint.tools, indent=2)
        workflow_str = json.dumps(blueprint.workflow, indent=2)
        verification_note = ""
        if _blueprint_expects_verification(blueprint):
            verification_note = (
                "\nThis blueprint includes verification steps. After producing your "
                "initial fix, reason carefully about whether it would pass tests - "
                "check for off-by-one errors, missing returns, wrong operators, and "
                "edge cases before finalising your answer.\n"
            )
        return (
            "You are executing a specialised AI agent blueprint.\n\n"
            f"Agent name:\n{blueprint.name}\n\n"
            f"Agent role:\n{blueprint.role}\n\n"
            f"Domain:\n{blueprint.domain_profile.domain} / {blueprint.domain_profile.subdomain}\n\n"
            f"Workflow steps:\n{workflow_str}\n\n"
            f"Available tools:\n{tools_str}\n\n"
            f"Expected output schema:\n{schema_str}\n\n"
            f"{verification_note}"
            f"Task input:\n{task_input}\n\n"
            "Instructions:\n"
            "1. Follow the workflow steps in order.\n"
            "2. Return only valid JSON matching the output schema. No markdown fences.\n"
            "3. CRITICAL: the 'suggested_fix' field MUST contain the complete corrected "
            "Python function as runnable code starting with 'def '.\n"
        )

    def _build_doc_prompt(self, blueprint: AgentBlueprint, task_input: str) -> str:
        workflow_str = json.dumps(blueprint.workflow, indent=2)
        return (
            "You are executing a documentation-specialist agent blueprint.\n\n"
            f"Agent name:\n{blueprint.name}\n\n"
            f"Agent role:\n{blueprint.role}\n\n"
            f"Workflow steps:\n{workflow_str}\n\n"
            "Task: Add Google-style docstrings to every public function and class "
            "in the following Python code.\n\n"
            "Requirements:\n"
            "- Every public function must have a docstring.\n"
            "- Functions with parameters MUST include an Args: section listing "
            "each parameter with its type and description.\n"
            "- Functions that return a value MUST include a Returns: section.\n"
            "- Keep all code logic unchanged.\n\n"
            f"Code to document:\n{task_input}\n\n"
            "Return ONLY the documented Python code inside a ```python ... ``` block. "
            "No JSON, no explanation."
        )

    def _build_doc_revision_prompt(
        self,
        current_coverage: float,
        missing: List[str],
        incomplete: List[str],
        round_no: int,
    ) -> str:
        lines = [
            f"Quality coverage check (round {round_no}):",
            f"Current quality coverage: {current_coverage:.0%}",
            f"Target: {MIN_DOCSTRING_COVERAGE:.0%}",
        ]
        if missing:
            lines.append(f"No docstring at all: {', '.join(missing)}")
        if incomplete:
            lines.append(
                f"Docstring present but missing Args:/Returns: sections: {', '.join(incomplete)}"
            )
        lines += [
            "",
            "Please add or complete the docstrings for all listed symbols.",
            "Each function with parameters needs an Args: section.",
            "Each function that returns a value needs a Returns: section.",
            "Return the updated code inside a ```python ... ``` block.",
        ]
        return "\n".join(lines)

    def _build_revision_prompt(
        self, original_buggy_code: str, previous_fix: str, failure_summary: str, round_no: int
    ) -> str:
        return (
            f"Your fix from round {round_no - 1} was tested and FAILED.\n\n"
            f"Original buggy code:\n{original_buggy_code}\n\n"
            f"Your previous fix:\n{previous_fix}\n\n"
            f"Test failure output:\n{failure_summary}\n\n"
            "Please analyse the failure, identify what is still wrong, and provide "
            "a corrected fix. Return valid JSON with the same schema. "
            "The 'suggested_fix' field must contain the complete corrected Python "
            "function as runnable code starting with 'def '."
        )

    def _summarise_pytest_failure(self, raw_pytest_output: str, fix: str) -> str:
        lines = raw_pytest_output.splitlines()
        useful = [
            line.strip() for line in lines
            if any(kw in line for kw in ["FAILED", "AssertionError", "assert", "Error", "def test_"])
        ]
        return "\n".join(useful[:20]) if useful else raw_pytest_output[:400]
    # LLM helpers
    def _call_llm(self, prompt: str) -> str:
        response = self.client.responses.create(model=self.model, input=prompt)
        return response.output_text

    def _call_llm_with_history(self, history: List[Dict[str, str]]) -> str:
        response = self.client.responses.create(model=self.model, input=history)
        return response.output_text
    # Fix extraction (debugging)
    def _extract_fix(self, parsed: Optional[Dict], raw_text: str) -> Optional[str]:
        if parsed and isinstance(parsed, dict):
            for key in (
                "suggested_fix", "fix", "fixed_code", "corrected_code",
                "fix_code", "proposed_fix", "solution", "corrected_function",
            ):
                val = parsed.get(key, "")
                if isinstance(val, str) and val.strip():
                    cleaned = self._clean_code(val.strip())
                    if cleaned.startswith("def ") or "return" in cleaned:
                        return cleaned
        return extract_fix_from_code(raw_text)

    def _clean_code(self, code: str) -> str:
        if code.startswith("```"):
            lines = code.splitlines()
            inner = lines[1:] if lines[0].startswith("```") else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            code = "\n".join(inner).strip()
        return code
    # JSON parsing
    def _try_parse_json(self, raw_text: str) -> Any:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass
        stripped = raw_text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            inner = lines[1:] if lines[0].startswith("```") else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            stripped = "\n".join(inner).strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
