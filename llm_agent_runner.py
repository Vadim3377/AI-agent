import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from models import AgentBlueprint


class LLMAgentRunner:
    """
    Executes a selected AgentBlueprint using an OpenAI model.

    The deterministic AgentRunner proves that the generated workflow is runnable.
    This LLM-backed runner performs semantic execution: it uses the blueprint's
    role, workflow, tools, and output schema to reason over a concrete task input.
    """

    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        load_dotenv()

        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY is missing. Set it in your environment or in a .env file."
            )

        self.client = OpenAI()
        self.model = model

    def run(self, blueprint: AgentBlueprint, task_input: str) -> Dict[str, Any]:
        prompt = self._build_prompt(blueprint, task_input)

        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )

        raw_text = response.output_text

        parsed_output = self._try_parse_json(raw_text)

        return {
            "runner": "llm",
            "model": self.model,
            "blueprint_name": blueprint.name,
            "domain": blueprint.domain_profile.domain,
            "subdomain": blueprint.domain_profile.subdomain,
            "workflow": blueprint.workflow,
            "task_input_preview": task_input[:250],
            "raw_output": raw_text,
            "parsed_output": parsed_output,
            "final_status": "completed",
        }

    def _build_prompt(self, blueprint: AgentBlueprint, task_input: str) -> str:
        return f"""
You are executing a specialised AI agent blueprint.

Agent name:
{blueprint.name}

Agent role:
{blueprint.role}

Domain:
{blueprint.domain_profile.domain}

Subdomain:
{blueprint.domain_profile.subdomain}

Domain reasoning:
{blueprint.domain_profile.reasoning}

Available tools described by the blueprint:
{json.dumps(blueprint.tools, indent=2)}

Workflow steps:
{json.dumps(blueprint.workflow, indent=2)}

Expected output schema:
{json.dumps(blueprint.output_schema, indent=2)}

Task input:
{task_input}

Instructions:
1. Follow the workflow steps in order.
2. Perform the reasoning required by the specialist role.
3. Do not invent tool outputs. If a tool is unavailable, reason from the provided input.
4. Return only valid JSON.
5. The JSON should match the expected output schema as closely as possible.
"""

    def _try_parse_json(self, raw_text: str) -> Any:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            return None