"""
Provider-agnostic LLM backend.

Every LLM call in the project goes through complete(), so runners and
benchmarks do not care whether OpenAI or Gemini (Vertex AI) answers.

Gemini uses Vertex AI with Application Default Credentials: on Cloud Run the
service account authenticates, locally run `gcloud auth application-default
login`. OpenAI uses OPENAI_API_KEY as before.

Environment:
    LLM_PROVIDER           default provider when none is passed ("openai")
    GEMINI_MODEL           default Gemini model ID (check the Vertex AI docs)
    GOOGLE_CLOUD_PROJECT   GCP project for Vertex AI
    GOOGLE_CLOUD_LOCATION  Vertex AI region (default europe-west2)
    LLM_PRICE_IN_PER_M     optional USD per 1M input tokens, for cost estimates
    LLM_PRICE_OUT_PER_M    optional USD per 1M output tokens
"""

import os
import statistics
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

PROVIDERS = ("openai", "gemini")

Messages = Union[str, List[Dict[str, str]]]


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float


def default_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").lower()


def default_model(provider: str) -> str:
    if provider == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def add_cli_args(parser) -> None:
    """Add --provider / --model to a benchmark's argparse parser."""
    parser.add_argument("--provider", choices=PROVIDERS, default=default_provider(),
                        help="LLM provider (default: $LLM_PROVIDER or openai).")
    parser.add_argument("--model", default=None,
                        help="Model ID (default: $GEMINI_MODEL / $OPENAI_MODEL).")


def apply_cli_args(args) -> None:
    """Make --provider / --model the process-wide defaults read by runners and the classifier."""
    os.environ["LLM_PROVIDER"] = args.provider
    if args.model:
        os.environ["GEMINI_MODEL" if args.provider == "gemini" else "OPENAI_MODEL"] = args.model


def results_path(path: str, provider: str) -> str:
    """Suffix non-OpenAI result files so they sit next to the OpenAI baseline."""
    if provider == "openai":
        return path
    root, ext = os.path.splitext(path)
    return f"{root}_{provider}{ext}"


def is_configured(provider: str) -> bool:
    """True if credentials for the provider are plausibly present."""
    if provider == "gemini":
        return bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
    return bool(os.getenv("OPENAI_API_KEY"))


def complete(
    messages: Messages,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    system: Optional[str] = None,
) -> LLMResponse:
    """
    Send a prompt string or a [{"role", "content"}, ...] conversation and
    return the reply with token usage and wall-clock latency.
    """
    provider = (provider or default_provider()).lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}; expected one of {PROVIDERS}")
    model = model or default_model(provider)

    start = time.perf_counter()
    if provider == "gemini":
        text, tokens_in, tokens_out = _complete_gemini(messages, model, system)
    else:
        text, tokens_in, tokens_out = _complete_openai(messages, model, system)
    return LLMResponse(text or "", tokens_in, tokens_out, time.perf_counter() - start)


# Gemini (Vertex AI)

@lru_cache(maxsize=1)
def _gemini_client():
    from google import genai
    return genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west2"),
    )


def _complete_gemini(messages: Messages, model: str, system: Optional[str]):
    from google.genai import types

    if isinstance(messages, str):
        contents: Any = messages
    else:
        # Gemini calls the assistant role "model".
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]

    # No tools are passed, so disable automatic function calling (silences an SDK warning).
    config = types.GenerateContentConfig(
        system_instruction=system,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = _gemini_client().models.generate_content(
        model=model, contents=contents, config=config
    )
    usage = response.usage_metadata
    if not usage:
        return response.text, 0, 0
    # Thinking tokens are billed as output, so count them for cost estimates.
    output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    return response.text, usage.prompt_token_count or 0, output_tokens


# OpenAI

@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI
    return OpenAI()


def _complete_openai(messages: Messages, model: str, system: Optional[str]):
    kwargs: Dict[str, Any] = {"model": model, "input": messages}
    if system:
        kwargs["instructions"] = system
    response = _openai_client().responses.create(**kwargs)
    usage = response.usage
    return (
        response.output_text,
        usage.input_tokens if usage else 0,
        usage.output_tokens if usage else 0,
    )


# Usage summaries for benchmarks

def estimate_cost(input_tokens: int, output_tokens: int) -> Optional[float]:
    """USD cost from LLM_PRICE_*_PER_M, or None if prices are not set."""
    price_in = os.getenv("LLM_PRICE_IN_PER_M")
    price_out = os.getenv("LLM_PRICE_OUT_PER_M")
    if price_in is None or price_out is None:
        return None
    return (input_tokens * float(price_in) + output_tokens * float(price_out)) / 1_000_000


def summarise_runs(run_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-task usage records produced by LLMAgentRunner.run()."""
    if not run_log:
        return {"tasks": 0}
    latencies = sorted(r["latency_s"] for r in run_log)
    tokens_in = [r["input_tokens"] for r in run_log]
    tokens_out = [r["output_tokens"] for r in run_log]
    cost = estimate_cost(sum(tokens_in), sum(tokens_out))
    return {
        "provider": run_log[0]["provider"],
        "model": run_log[0]["model"],
        "tasks": len(run_log),
        "llm_calls": sum(r["calls"] for r in run_log),
        "p50_latency_s": round(statistics.median(latencies), 2),
        "p95_latency_s": round(latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))], 2),
        "avg_input_tokens": round(statistics.mean(tokens_in)),
        "avg_output_tokens": round(statistics.mean(tokens_out)),
        "cost_per_task_usd": round(cost / len(run_log), 5) if cost is not None else None,
    }


def format_usage(summary: Dict[str, Any]) -> str:
    if not summary.get("tasks"):
        return "No LLM usage recorded."
    cost = summary["cost_per_task_usd"]
    cost_str = f"${cost:.4f}" if cost is not None else "n/a (set LLM_PRICE_IN_PER_M / LLM_PRICE_OUT_PER_M)"
    return (
        f"Provider / model : {summary['provider']} / {summary['model']}\n"
        f"Tasks / LLM calls: {summary['tasks']} / {summary['llm_calls']}\n"
        f"Latency per task : p50 {summary['p50_latency_s']}s, p95 {summary['p95_latency_s']}s\n"
        f"Avg tokens/task  : {summary['avg_input_tokens']} in, {summary['avg_output_tokens']} out\n"
        f"Cost per task    : {cost_str}"
    )
