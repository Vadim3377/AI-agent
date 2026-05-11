"""
agent_runner.py — Deterministic AgentRunner with integrated real tooling.

For each workflow step the runner checks whether a real tool from tools.py
is applicable. If so, the tool is called on the task input and its output is
recorded in the execution trace. Tool results are also stored in
runner.last_tool_results so that BlueprintEvaluator can use them for
task-level (non-circular) scoring.

Steps without a matching tool fall back to descriptive placeholder text,
exactly as before. The LLMAgentRunner is unchanged.
"""

import json
from typing import Any, Dict, List, Optional

from models import AgentBlueprint, DomainProfile
from tools import run_tool, ToolResult, TOOL_REGISTRY



# Step -> tool routing table
# Each entry: (list_of_keywords_in_step_name, tool_name)
# First match wins.


_STEP_TO_TOOL: List[tuple] = [
    (["run_tests", "execute_tests", "pytest", "test_harness", "verify_fix",
      "verify_against", "check_fix"],                                    "pytest_runner"),
    (["static", "analyse_code", "analyze_code", "lint",
      "identify_failure", "infer_expected", "localise_bug",
      "suspect_bug", "flag_suspicious"],                                 "static_checker"),
    (["complexity", "dead_code", "redundant"],                           "complexity_checker"),
    (["secret", "pii", "dangerous", "sensitive"],                        "secret_detector"),
    (["docstring", "documentation", "comment_coverage"],                 "docstring_checker"),
]


def _resolve_tool_for_step(step: str, blueprint_tools: List[str]) -> Optional[str]:
    """
    Return the best matching registered tool name for a workflow step, or None.
    Priority: keyword match in step name → None.
    """
    step_lower = step.lower()
    for keywords, tool_name in _STEP_TO_TOOL:
        if any(kw in step_lower for kw in keywords):
            if tool_name in TOOL_REGISTRY:
                return tool_name
    return None



# Runner

class AgentRunner:
    """
    Executes a selected AgentBlueprint step-by-step.

    For each workflow step:
    1. Attempt to match a real tool (_resolve_tool_for_step).
    2. If matched and not yet called this run, call the tool and record results.
    3. If no tool matches, produce a descriptive placeholder.

    Tool results are aggregated in self._tool_results so that
    BlueprintEvaluator can perform task-level scoring using real evidence.
    """

    def run(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        self._tool_results: List[ToolResult] = []
        self._tools_called: List[str] = []

        executed_steps = []
        for step in blueprint.workflow:
            tool_name = _resolve_tool_for_step(step, blueprint.tools)
            tool_result: Optional[ToolResult] = None

            if tool_name and tool_name not in self._tools_called:
                tool_result = run_tool(tool_name, task_input)
                if tool_result is not None:
                    self._tool_results.append(tool_result)
                    self._tools_called.append(tool_name)

            executed_steps.append({
                "step": step,
                "status": "completed",
                "tool_used": tool_name if tool_result else None,
                "tool_success": tool_result.success if tool_result else None,
                "result": (
                    self._format_tool_result(tool_result)
                    if tool_result
                    else self._describe_step(step, blueprint)
                ),
            })

        return {
            "blueprint_name": blueprint.name,
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "task_input_preview": task_input[:250],
            "executed_steps": executed_steps,
            "tool_results": [self._tool_to_dict(r) for r in self._tool_results],
            "tools_called": self._tools_called,
            "final_output": self._build_final_output(blueprint, task_input),
            "final_status": "completed",
        }


    # Internal helpers

    def _format_tool_result(self, result: ToolResult) -> str:
        status = "passed" if result.success else "failed"
        return f"[{result.tool_name}] {status}: {result.raw_text[:300]}"

    def _tool_to_dict(self, result: ToolResult) -> Dict[str, Any]:
        return {
            "tool": result.tool_name,
            "success": result.success,
            "output": result.output,
            "summary": result.raw_text[:500],
            "error": result.error,
        }

    def _describe_step(self, step: str, blueprint: AgentBlueprint) -> str:
        s = step.lower()
        subdomain = blueprint.domain_profile.subdomain
        if "read" in s:
            return "Task input loaded into execution context."
        if "infer" in s or "summarise" in s or "summarize" in s:
            return "High-level interpretation of the task input produced."
        if "bug" in s or "failure" in s or "fix" in s:
            return "Debugging reasoning step recorded (no tool matched for this step)."
        if "dead" in s or "redundant" in s or "refactor" in s:
            return "Code-quality cleanup step recorded."
        if "comment" in s or "docstring" in s or "documentation" in s:
            return "Documentation improvement step recorded."
        if "risk" in s or "secret" in s or "pii" in s or "mitigation" in s:
            return "Security analysis step recorded."
        if "search" in s or "source" in s or "research" in s:
            return "Research planning step recorded."
        if "verify" in s or "check" in s or "cross" in s:
            return "Verification step recorded."
        return f"Workflow step completed for subdomain '{subdomain}'."

    def _build_final_output(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        tool_lookup = {r.tool_name: r for r in self._tool_results}
        output = {}
        for key, schema_value in blueprint.output_schema.items():
            enriched = self._enrich(key, tool_lookup)
            output[key] = enriched if enriched is not None else self._placeholder(key, schema_value)
        return output

    def _enrich(self, key: str, tool_lookup: Dict[str, ToolResult]) -> Optional[Any]:
        k = key.lower()
        if k in ("tests_passed", "tests_run") and "pytest_runner" in tool_lookup:
            return tool_lookup["pytest_runner"].output.get(k)
        if k == "static_issues" and "static_checker" in tool_lookup:
            return tool_lookup["static_checker"].output.get("issues", [])
        if k == "issue_count" and "static_checker" in tool_lookup:
            return tool_lookup["static_checker"].output.get("issue_count", 0)
        if k in ("complexity_report", "high_complexity_functions") and "complexity_checker" in tool_lookup:
            return tool_lookup["complexity_checker"].output.get("functions", [])
        if k in ("findings", "secrets_found") and "secret_detector" in tool_lookup:
            return tool_lookup["secret_detector"].output.get("findings", [])
        if k == "risk_level" and "secret_detector" in tool_lookup:
            count = tool_lookup["secret_detector"].output.get("finding_count", 0)
            return "low" if count == 0 else ("medium" if count <= 2 else "high")
        if k == "final_verdict" and "secret_detector" in tool_lookup:
            count = tool_lookup["secret_detector"].output.get("finding_count", 0)
            return "clean" if count == 0 else f"{count} secret(s) detected"
        if k == "docstring_coverage" and "docstring_checker" in tool_lookup:
            return tool_lookup["docstring_checker"].output.get("coverage")
        if k in ("missing_docstrings", "undocumented") and "docstring_checker" in tool_lookup:
            return [m["name"] for m in tool_lookup["docstring_checker"].output.get("missing", [])]
        return None

    def _placeholder(self, key: str, schema_value: Any) -> Any:
        if isinstance(schema_value, list):
            return []
        if isinstance(schema_value, dict):
            return {k: f"placeholder_{k}" for k in schema_value}
        if isinstance(schema_value, str):
            return schema_value.split("|")[0].strip() if "|" in schema_value else f"placeholder_{key}"
        return None

    @property
    def last_tool_results(self) -> List[ToolResult]:
        return getattr(self, "_tool_results", [])


# ---------------------------------------------------------------------------
# Serialisation helpers (unchanged API)
# ---------------------------------------------------------------------------

def load_blueprint(path: str) -> AgentBlueprint:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    profile_data = data["domain_profile"]
    profile = DomainProfile(
        domain=profile_data["domain"],
        subdomain=profile_data["subdomain"],
        artifact_type=profile_data["artifact_type"],
        required_capabilities=profile_data["required_capabilities"],
        candidate_tools=profile_data["candidate_tools"],
        evaluation_metrics=profile_data["evaluation_metrics"],
        reasoning=profile_data["reasoning"],
    )
    return AgentBlueprint(
        name=data["name"],
        role=data["role"],
        domain_profile=profile,
        workflow=data["workflow"],
        tools=data["tools"],
        output_schema=data["output_schema"],
        stopping_condition=data["stopping_condition"],
    )


def save_run_result(result: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
