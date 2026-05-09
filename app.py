import json
import os
from typing import Any, Dict

import streamlit as st

from agent_runner import AgentRunner
from architecture_generator import ArchitectureGenerator
from blueprint_evaluator import BlueprintEvaluator
from blueprint_mutator import BlueprintMutator
from domain_profiler import DomainProfiler
from models import AgentBlueprint, EvaluationResult
from dotenv import load_dotenv


try:
    from llm_agent_runner import LLMAgentRunner
    LLM_AVAILABLE = True
except Exception:
    LLMAgentRunner = None
    LLM_AVAILABLE = False


def blueprint_to_dict(blueprint: AgentBlueprint) -> Dict[str, Any]:
    return {
        "name": blueprint.name,
        "role": blueprint.role,
        "domain_profile": {
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "artifact_type": blueprint.domain_profile.artifact_type,
            "required_capabilities": blueprint.domain_profile.required_capabilities,
            "candidate_tools": blueprint.domain_profile.candidate_tools,
            "evaluation_metrics": blueprint.domain_profile.evaluation_metrics,
            "reasoning": blueprint.domain_profile.reasoning,
        },
        "workflow": blueprint.workflow,
        "tools": blueprint.tools,
        "output_schema": blueprint.output_schema,
        "stopping_condition": blueprint.stopping_condition,
    }


def evaluation_to_dict(result: EvaluationResult) -> Dict[str, Any]:
    return {
        "score": result.score,
        "passed_checks": result.passed_checks,
        "failed_checks": result.failed_checks,
        "notes": result.notes,
    }


def run_pipeline(task_prompt: str) -> Dict[str, Any]:
    profiler = DomainProfiler()
    architecture_generator = ArchitectureGenerator()
    mutator = BlueprintMutator()
    evaluator = BlueprintEvaluator()

    profile = profiler.profile(task_prompt)

    base_blueprint = architecture_generator.generate(profile)
    mutated_blueprint = mutator.mutate(base_blueprint)

    base_eval = evaluator.evaluate(base_blueprint)
    mutated_eval = evaluator.evaluate(mutated_blueprint)

    if mutated_eval.score > base_eval.score:
        selected = "mutated"
        selected_blueprint = mutated_blueprint
        selected_eval = mutated_eval
    else:
        selected = "base"
        selected_blueprint = base_blueprint
        selected_eval = base_eval

    return {
        "profile": profile,
        "base_blueprint": base_blueprint,
        "mutated_blueprint": mutated_blueprint,
        "base_eval": base_eval,
        "mutated_eval": mutated_eval,
        "selected": selected,
        "selected_blueprint": selected_blueprint,
        "selected_eval": selected_eval,
    }

def display_field(key: str, value: Any) -> None:
    title = key.replace("_", " ").title()

    st.write(f"### {title}")

    if isinstance(value, list):
        if not value:
            st.write("_None._")
            return

        for item in value:
            if isinstance(item, dict):
                with st.container(border=True):
                    for nested_key, nested_value in item.items():
                        label = nested_key.replace("_", " ").title()
                        st.write(f"**{label}:** {nested_value}")
            else:
                st.write(f"- {item}")

    elif isinstance(value, dict):
        st.json(value)

    else:
        st.write(value)

def display_structured_result(result: Dict[str, Any]) -> None:
    summary = result.get("summary") or result.get("answer")

    if summary:
        st.write("### Summary")
        st.write(summary)

    verdict = result.get("final_verdict")
    risk_level = result.get("risk_level")

    if verdict or risk_level:
        col1, col2 = st.columns(2)

        with col1:
            if verdict:
                st.metric("Final Verdict", verdict)

        with col2:
            if risk_level:
                st.metric("Risk Level", risk_level)

    priority_keys = [
        "likely_root_cause",
        "suggested_fix",
        "fix_rationale",
        "dead_code",
        "redundant_logic",
        "readability_issues",
        "refactor_suggestions",
        "docstrings_added",
        "inline_comments_added",
        "findings",
        "confirmed_risks",
        "suspected_risks",
        "recommended_approach",
        "sources",
        "limitations",
    ]

    shown_keys = {"summary", "answer", "final_verdict", "risk_level"}

    for key in priority_keys:
        if key in result:
            shown_keys.add(key)
            display_field(key, result[key])

    remaining = {
        key: value
        for key, value in result.items()
        if key not in shown_keys
    }

    if remaining:
        with st.expander("Additional fields"):
            st.json(remaining)

def display_runner_output(run_result: Dict[str, Any]) -> None:
    runner = run_result.get("runner", "deterministic")
    final_status = run_result.get("final_status", "unknown")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Runner", runner)

    with col2:
        st.metric("Status", final_status)

    with col3:
        if runner == "llm":
            st.metric("Model", run_result.get("model", "unknown"))
        else:
            st.metric("Executed Steps", len(run_result.get("executed_steps", [])))

    parsed_output = run_result.get("parsed_output")

    if parsed_output:
        st.subheader("Specialist Output")
        display_structured_result(parsed_output)
    else:
        final_output = run_result.get("final_output")

        if final_output:
            st.subheader("Specialist Output")
            display_structured_result(final_output)

    with st.expander("Workflow"):
        workflow = run_result.get("workflow")

        if workflow:
            for index, step in enumerate(workflow, start=1):
                st.write(f"{index}. `{step}`")
        else:
            for item in run_result.get("executed_steps", []):
                st.write(f"- `{item.get('step')}`: {item.get('status')}")

    with st.expander("Raw runner result"):
        st.json(run_result)


def main() -> None:
    load_dotenv()
    st.set_page_config(
        page_title="Stem Agent Demo",
        layout="wide",
    )

    st.title("Stem Agent Demo")
    st.write(
        "This demo runs the stem-agent pipeline: classify the task, profile the domain, "
        "generate a blueprint, mutate it, evaluate both versions, select the stronger blueprint, "
        "and execute the selected specialist."
    )

    st.sidebar.header("Settings")

    example = st.sidebar.selectbox(
        "Choose an example task",
        [
            "Debugging",
            "Code quality cleanup",
            "Comments and documentation",
            "Security validation",
            "Code research",
            "Custom",
        ],
    )

    examples = {
        "Debugging": {
            "prompt": "Debug this Python function. It gives the wrong output and the test fails.",
            "input": "def add(a, b):\n    return a - b",
        },
        "Code quality cleanup": {
            "prompt": "Clean up this code, remove dead code, simplify redundant logic, and improve readability.",
            "input": "def calculate(x):\n    unused = 123\n    result = x * 1\n    if True:\n        return result",
        },
        "Comments and documentation": {
            "prompt": "Add useful comments and docstrings to explain the code.",
            "input": "def normalise(values):\n    m = max(values)\n    return [v / m for v in values]",
        },
        "Security validation": {
            "prompt": "Check this code for dangerous operations, API key leaks, passwords, and possible data breaches.",
            "input": "API_KEY = 'sk-test-123'\npassword = 'admin'\neval(user_input)",
        },
        "Code research": {
            "prompt": "Research relevant documentation and examples for implementing a plugin system in Python.",
            "input": "Need to design a plugin discovery mechanism for a Python CLI tool.",
        },
    }

    if example == "Custom":
        default_prompt = ""
        default_input = ""
    else:
        default_prompt = examples[example]["prompt"]
        default_input = examples[example]["input"]

    task_prompt = st.text_area(
        "Task-family prompt",
        value=default_prompt,
        height=100,
    )

    task_input = st.text_area(
        "Concrete task input",
        value=default_input,
        height=160,
    )

    runner_type = st.sidebar.radio(
        "Runner",
        ["Deterministic", "LLM-backed"],
    )

    model = st.sidebar.text_input(
        "OpenAI model",
        value="gpt-4.1-mini",
        disabled=(runner_type != "LLM-backed"),
    )

    if st.button("Run Stem Agent Pipeline", type="primary"):
        if not task_prompt.strip():
            st.error("Please provide a task-family prompt.")
            return

        with st.spinner("Growing specialist agent..."):
            pipeline_result = run_pipeline(task_prompt)

        profile = pipeline_result["profile"]
        base_blueprint = pipeline_result["base_blueprint"]
        mutated_blueprint = pipeline_result["mutated_blueprint"]
        base_eval = pipeline_result["base_eval"]
        mutated_eval = pipeline_result["mutated_eval"]
        selected = pipeline_result["selected"]
        selected_blueprint = pipeline_result["selected_blueprint"]

        st.success("Pipeline completed.")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Domain", profile.domain)

        with col2:
            st.metric("Subdomain", profile.subdomain)

        with col3:
            st.metric("Selected", selected)

        st.subheader("Evaluation Comparison")

        eval_col1, eval_col2 = st.columns(2)

        with eval_col1:
            st.metric("Base Score", base_eval.score)
            st.write("Failed checks:")
            st.write(base_eval.failed_checks)

        with eval_col2:
            st.metric("Mutated Score", mutated_eval.score)
            st.write("Failed checks:")
            st.write(mutated_eval.failed_checks)

        st.subheader("Selected Blueprint")

        st.write(f"**Blueprint name:** `{selected_blueprint.name}`")
        st.write(f"**Role:** {selected_blueprint.role}")

        with st.expander("Workflow", expanded=True):
            for index, step in enumerate(selected_blueprint.workflow, start=1):
                st.write(f"{index}. `{step}`")

        with st.expander("Full selected blueprint JSON"):
            st.json(blueprint_to_dict(selected_blueprint))

        st.subheader("Runner Output")

        if not task_input.strip():
            st.warning("No concrete task input was provided, so runner execution was skipped.")
            return

        if runner_type == "LLM-backed":
            if not LLM_AVAILABLE:
                st.error("LLM runner is not available. Check that llm_agent_runner.py exists and dependencies are installed.")
                return

            if not os.getenv("OPENAI_API_KEY"):
                st.error("OPENAI_API_KEY is missing. Add it to your environment or .env file.")
                return

            with st.spinner("Running selected blueprint with LLM-backed runner..."):
                runner = LLMAgentRunner(model=model)
                run_result = runner.run(selected_blueprint, task_input)
        else:
            with st.spinner("Running selected blueprint deterministically..."):
                runner = AgentRunner()
                run_result = runner.run(selected_blueprint, task_input)

        st.success("Runner completed.")

        display_runner_output(run_result)

        os.makedirs("results", exist_ok=True)
        with open("results/frontend_last_run.json", "w", encoding="utf-8") as file:
            json.dump(run_result, file, indent=2)

        st.caption("Saved latest run to results/frontend_last_run.json")


if __name__ == "__main__":
    main()