"""
llm_agent_runner.py — LLM-backed agent runner with tool feedback loop.

The runner executes an AgentBlueprint using an OpenAI model. Unlike the
deterministic AgentRunner, it performs semantic reasoning over real input.

Tool feedback loop (new)
------------------------
After the initial fix attempt, the runner checks whether the blueprint's
workflow contains verification steps (e.g. verify_fix_against_generated_tests).
If so, it calls pytest_runner on the suggested fix and observes the result.
If pytest fails, it sends the failure output back to the LLM as a new message
and asks for a revision. This repeats for up to MAX_REVISION_ROUNDS.

This makes the blueprint's verification workflow steps real rather than
descriptive: a blueprint that includes explicit verification steps triggers
more revision rounds, giving it a meaningful behavioural advantage over a
base blueprint that does not.

Metrics tracked per run
-----------------------
- rounds_taken: how many revision rounds were needed (0 = first attempt passed)
- first_attempt_passed: whether the initial fix passed pytest without revision
- final_pytest_passed: whether the final fix passes pytest

These metrics feed directly into task_benchmark.py's before/after comparison.
A mutated blueprint that produces better first-attempt fixes will show lower
rounds_taken on average — a real, measurable difference.
"""

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from models import AgentBlueprint
from tools import pytest_runner, extract_fix_from_code


MAX_REVISION_ROUNDS = 3

# Workflow step keywords that indicate the blueprint expects verification
# Active verification signals — steps that explicitly verify a fix against tests.
# "run_tests_if_available" is passive and does NOT trigger the loop.
# "verify_fix_against_generated_tests" is active and DOES trigger it.
# This is the key behavioural difference between base and mutated blueprints.
_VERIFICATION_SIGNALS = [
    "verify_fix",
    "verify_against",
    "check_fix",
    "regression_risk",
    "rerun",
    "validate_fix",
]


def _blueprint_expects_verification(blueprint: AgentBlueprint) -> bool:
    """
    Return True if the blueprint's workflow contains ACTIVE verification steps.

    Passive steps like "run_tests_if_available" do not trigger the feedback loop.
    Active steps like "verify_fix_against_generated_tests" do.
    This creates a real behavioural difference between base and mutated blueprints:
      - Base blueprint:    single-shot LLM call (no revision rounds)
      - Mutated blueprint: up to MAX_REVISION_ROUNDS with pytest feedback
    """
    text = " ".join(blueprint.workflow).lower()
    return any(signal in text for signal in _VERIFICATION_SIGNALS)


class LLMAgentRunner:
    """
    Executes a selected AgentBlueprint using an OpenAI model with a
    tool feedback loop for debugging tasks.

    For non-debugging domains the runner behaves as before (single-shot).
    For debugging, it runs up to MAX_REVISION_ROUNDS of:
      1. Generate fix
      2. Run pytest_runner on fix
      3. If failed: send failure output back, ask for revision
      4. Repeat until pass or rounds exhausted
    """

    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        load_dotenv()
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is missing. Set it in .env or environment."
            )
        self.client = OpenAI()
        self.model = model

    def run(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        is_debugging = "debug" in blueprint.domain_profile.subdomain.lower()
        use_loop = is_debugging and _blueprint_expects_verification(blueprint)

        if use_loop:
            return self._run_with_feedback_loop(blueprint, task_input)
        else:
            return self._run_single_shot(blueprint, task_input)

    # ------------------------------------------------------------------
    # Single-shot execution (non-debugging domains, unchanged behaviour)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Tool feedback loop (debugging domain)
    # ------------------------------------------------------------------

    def _run_with_feedback_loop(
        self, blueprint: AgentBlueprint, task_input: str
    ) -> Dict[str, Any]:
        """
        Multi-turn execution loop:
          round 0: initial fix attempt
          round 1+: revision based on pytest failure output
        Stops when pytest passes or MAX_REVISION_ROUNDS is reached.
        """
        history: List[Dict[str, str]] = []
        initial_prompt = self._build_initial_prompt(blueprint, task_input)
        history.append({"role": "user", "content": initial_prompt})

        rounds_taken = 0
        first_attempt_passed: Optional[bool] = None
        final_fix: Optional[str] = None
        final_parsed: Optional[Dict] = None
        final_raw: str = ""
        final_pytest_passed = False

        for round_no in range(MAX_REVISION_ROUNDS + 1):
            # Call LLM with full conversation history
            raw_text = self._call_llm_with_history(history)
            final_raw = raw_text
            history.append({"role": "assistant", "content": raw_text})

            parsed = self._try_parse_json(raw_text)
            final_parsed = parsed

            # Extract the fix from parsed JSON or raw text
            fix = self._extract_fix(parsed, raw_text)
            final_fix = fix

            if not fix:
                # No code found — ask for clarification in next round
                if round_no < MAX_REVISION_ROUNDS:
                    history.append({
                        "role": "user",
                        "content": (
                            "Your response did not contain a complete Python function "
                            "in the suggested_fix field. Please provide the full corrected "
                            "function starting with 'def '. Return only valid JSON."
                        ),
                    })
                rounds_taken = round_no
                continue

            # Run pytest on the fix
            pytest_result = pytest_runner(fix)
            final_pytest_passed = pytest_result.success

            if round_no == 0:
                first_attempt_passed = pytest_result.success

            if pytest_result.success:
                rounds_taken = round_no
                break

            # pytest failed — build revision prompt with failure evidence
            if round_no < MAX_REVISION_ROUNDS:
                failure_summary = self._summarise_pytest_failure(
                    pytest_result.raw_text, fix
                )
                revision_prompt = self._build_revision_prompt(
                    task_input, fix, failure_summary, round_no + 1
                )
                history.append({"role": "user", "content": revision_prompt})
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

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_initial_prompt(self, blueprint: AgentBlueprint, task_input: str) -> str:
        schema_str = json.dumps(blueprint.output_schema, indent=2)
        tools_str = json.dumps(blueprint.tools, indent=2)
        workflow_str = json.dumps(blueprint.workflow, indent=2)

        verification_note = ""
        if _blueprint_expects_verification(blueprint):
            verification_note = (
                "\nThis blueprint includes verification steps. After producing your "
                "initial fix, reason carefully about whether it would pass tests — "
                "check for off-by-one errors, missing returns, wrong operators, and "
                "edge cases before finalising your answer.\n"
            )

        return (
            "You are executing a specialised AI agent blueprint.\n\n"
            f"Agent name:\n{blueprint.name}\n\n"
            f"Agent role:\n{blueprint.role}\n\n"
            f"Domain:\n{blueprint.domain_profile.domain} / "
            f"{blueprint.domain_profile.subdomain}\n\n"
            f"Workflow steps:\n{workflow_str}\n\n"
            f"Available tools:\n{tools_str}\n\n"
            f"Expected output schema:\n{schema_str}\n\n"
            f"{verification_note}"
            f"Task input (buggy code to debug):\n{task_input}\n\n"
            "Instructions:\n"
            "1. Follow the workflow steps in order.\n"
            "2. Return only valid JSON matching the output schema. No markdown fences.\n"
            "3. CRITICAL: the 'suggested_fix' field MUST contain the complete corrected "
            "Python function as runnable code — NOT a description. It must start with "
            "'def ' and be syntactically valid Python.\n"
            "   Correct:   \"suggested_fix\": \"def add(a, b):\\n    return a + b\"\n"
            "   Incorrect: \"suggested_fix\": \"Change minus to plus\"\n"
        )

    def _build_revision_prompt(
        self,
        original_buggy_code: str,
        previous_fix: str,
        failure_summary: str,
        round_no: int,
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
        """Extract the most useful part of pytest output for the revision prompt."""
        lines = raw_pytest_output.splitlines()
        # Keep FAILED lines, assertion errors, and short lines
        useful = []
        for line in lines:
            if any(kw in line for kw in ["FAILED", "AssertionError", "assert", "Error", "def test_"]):
                useful.append(line.strip())
        summary = "\n".join(useful[:20]) if useful else raw_pytest_output[:400]
        return summary or "Tests failed but no detailed output was captured."

    # ------------------------------------------------------------------
    # LLM call helpers
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )
        return response.output_text

    def _call_llm_with_history(self, history: List[Dict[str, str]]) -> str:
        # Responses API: pass full history as a list of message dicts
        response = self.client.responses.create(
            model=self.model,
            input=history,
        )
        return response.output_text

    # ------------------------------------------------------------------
    # Fix extraction
    # ------------------------------------------------------------------

    def _extract_fix(self, parsed: Optional[Dict], raw_text: str) -> Optional[str]:
        """Extract a runnable Python fix from parsed JSON or raw text."""
        if parsed and isinstance(parsed, dict):
            for key in ("suggested_fix", "fix", "fixed_code", "corrected_code",
                        "fix_code", "proposed_fix", "solution", "corrected_function"):
                val = parsed.get(key, "")
                if isinstance(val, str) and val.strip():
                    cleaned = self._clean_code(val.strip())
                    if cleaned.startswith("def ") or "return" in cleaned:
                        return cleaned

        # Fallback: extract from raw text
        return extract_fix_from_code(raw_text)

    def _clean_code(self, code: str) -> str:
        if code.startswith("```"):
            lines = code.splitlines()
            inner = lines[1:] if lines[0].startswith("```") else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            code = "\n".join(inner).strip()
        return code

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

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
