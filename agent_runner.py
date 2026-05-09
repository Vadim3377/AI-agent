import json
from dataclasses import asdict
from typing import Any, Dict, List

from models import AgentBlueprint, DomainProfile


class AgentRunner:
    """
    Executes a selected AgentBlueprint in a deterministic way.

    This runner does not call an LLM yet. It interprets the generated workflow
    and produces an execution trace showing how the specialised agent would
    process a concrete task input.
    """

    def run(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        executed_steps = []

        for step in blueprint.workflow:
            executed_steps.append(
                {
                    "step": step,
                    "status": "completed",
                    "result": self._execute_step(step, blueprint, task_input),
                }
            )

        return {
            "blueprint_name": blueprint.name,
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "task_input_preview": task_input[:250],
            "executed_steps": executed_steps,
            "final_output": self._build_final_output(blueprint, task_input),
            "final_status": "completed",
        }

    def _execute_step(
        self,
        step: str,
        blueprint: AgentBlueprint,
        task_input: str
    ) -> str:
        step_name = step.lower()
        subdomain = blueprint.domain_profile.subdomain

        if "read" in step_name:
            return "Task input was read and loaded into the execution context."

        if "infer" in step_name or "summarise" in step_name or "summarize" in step_name:
            return "The runner created a high-level interpretation of the task input."

        if "test" in step_name:
            return "The runner marked this as a test-related step. No real tests were executed in this deterministic runner."

        if "bug" in step_name or "failure" in step_name or "fix" in step_name:
            return "The runner marked this as a debugging-related reasoning step."

        if "dead" in step_name or "redundant" in step_name or "refactor" in step_name:
            return "The runner marked this as a code-quality cleanup step."

        if "comment" in step_name or "docstring" in step_name or "documentation" in step_name:
            return "The runner marked this as a documentation-improvement step."

        if "risk" in step_name or "secret" in step_name or "pii" in step_name or "mitigation" in step_name:
            return "The runner marked this as a security-analysis step."

        if "search" in step_name or "source" in step_name or "research" in step_name:
            return "The runner marked this as a research-planning or source-analysis step."

        if "verify" in step_name or "check" in step_name or "cross" in step_name:
            return "The runner marked this as a verification or safeguard step."

        return f"The runner completed workflow step for subdomain '{subdomain}'."

    def _build_final_output(
        self,
        blueprint: AgentBlueprint,
        task_input: str
    ) -> Dict[str, Any]:
        output: Dict[str, Any] = {}

        for key, schema_value in blueprint.output_schema.items():
            output[key] = self._placeholder_for_schema_value(key, schema_value)

        return output

    def _placeholder_for_schema_value(self, key: str, schema_value: Any) -> Any:
        if isinstance(schema_value, list):
            return []

        if isinstance(schema_value, dict):
            return {
                nested_key: f"placeholder_{nested_key}"
                for nested_key in schema_value.keys()
            }

        if isinstance(schema_value, str):
            if "|" in schema_value:
                return schema_value.split("|")[0].strip()

            return f"placeholder_{key}"

        return None


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