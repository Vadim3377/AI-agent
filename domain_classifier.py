"""
Classify task prompts into supported stem-agent domains.

When OPENAI_API_KEY is available, the classifier asks an LLM to route the raw
task prompt into a domain and subdomain with a short justification. Without an
API key, it uses a deterministic keyword fallback. The fallback keeps the
pipeline runnable and provides a baseline for comparison.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# Supported routing targets

SUPPORTED_DOMAINS = {
    "quality_assurance": [
        "debugging",
        "code_quality_cleanup",
        "comments_and_documentation",
    ],
    "security": [
        "dangerous_operations_and_data_breaches",
    ],
    "deep_research": [
        "code_research",
    ],
}


@dataclass
class ClassificationResult:
    domain: str
    subdomain: str
    intent: str
    confidence: float
    matched_signals: List[str]
    classification_method: str = "keyword"  # "llm" | "keyword" | "fallback"
    llm_reasoning: Optional[str] = None


# LLM routing

_CLASSIFICATION_SYSTEM_PROMPT = """\
You are the classification layer of a stem agent. Your only job is to read a
task description and determine what kind of specialist agent is needed.

Return ONLY a JSON object - no markdown fences, no preamble. The object must
have exactly these fields:

{
  "domain": "<one of: quality_assurance | security | deep_research>",
  "subdomain": "<one of: debugging | code_quality_cleanup | comments_and_documentation | dangerous_operations_and_data_breaches | code_research>",
  "intent": "<short snake_case description of the agent's goal, e.g. find_and_fix_bugs>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explaining why you chose this classification>"
}

Domain and subdomain must be chosen from the allowed values above. If the task
does not clearly fit any category, choose the closest one and set confidence
below 0.5.
"""


def _classify_with_llm(prompt: str) -> Optional[ClassificationResult]:
    """
    Ask the LLM to classify the task prompt.
    Returns None if the API key is missing or the call fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI()

        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions=_CLASSIFICATION_SYSTEM_PROMPT,
            input=f"Task description:\n{prompt}",
        )
        raw = response.output_text.strip()

        # Accept fenced JSON if the model returns it despite the prompt.
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            ).strip()

        data = json.loads(raw)

        domain = data.get("domain", "").strip()
        subdomain = data.get("subdomain", "").strip()
        intent = data.get("intent", "general_task_handling").strip()
        confidence = float(data.get("confidence", 0.5))
        reasoning = data.get("reasoning", "")

        # Clamp unexpected model output to the supported domain set.
        if domain not in SUPPORTED_DOMAINS:
            domain = "quality_assurance"
            confidence = min(confidence, 0.4)

        allowed_subdomains = SUPPORTED_DOMAINS.get(domain, [])
        if subdomain not in allowed_subdomains:
            subdomain = allowed_subdomains[0] if allowed_subdomains else "debugging"
            confidence = min(confidence, 0.4)

        return ClassificationResult(
            domain=domain,
            subdomain=subdomain,
            intent=intent,
            confidence=round(confidence, 2),
            matched_signals=[],          # LLM routing is explained by llm_reasoning.
            classification_method="llm",
            llm_reasoning=reasoning,
        )

    except Exception:
        return None


# Deterministic fallback

def _score_category(
    text: str,
    domain: str,
    subdomain: str,
    intent: str,
    signals: List[str],
) -> ClassificationResult:
    matched = [s for s in signals if s in text]
    confidence = min(1.0, len(matched) / 3)
    return ClassificationResult(
        domain=domain,
        subdomain=subdomain,
        intent=intent,
        confidence=round(confidence, 2),
        matched_signals=matched,
        classification_method="keyword",
    )


def _classify_with_keywords(text: str) -> ClassificationResult:
    candidates = [
        _score_category(text, "quality_assurance", "debugging",
                        "find_and_fix_bugs",
                        ["bug", "debug", "debugging", "error", "exception",
                         "failing test", "test fails", "wrong output",
                         "traceback", "crash", "fix this", "broken",
                         "does not work"]),
        _score_category(text, "quality_assurance", "code_quality_cleanup",
                        "improve_code_quality_without_changing_behaviour",
                        ["clean up", "cleanup", "refactor", "optimise",
                         "optimize", "dead code", "unused code", "redundant",
                         "redundancy", "simplify", "readability",
                         "maintainability", "performance"]),
        _score_category(text, "quality_assurance", "comments_and_documentation",
                        "add_or_improve_code_explanations",
                        ["add comments", "comments", "comment", "docstring",
                         "docstrings", "documentation", "document this",
                         "explain the code", "annotate", "readme"]),
        _score_category(text, "security", "dangerous_operations_and_data_breaches",
                        "detect_security_risks_and_sensitive_data_leaks",
                        ["security", "secure", "unsafe", "dangerous operation",
                         "data breach", "pii", "privacy", "leak", "secret",
                         "api key", "token", "password", "eval", "exec",
                         "subprocess", "sql injection", "path traversal"]),
        _score_category(text, "deep_research", "code_research",
                        "research_relevant_information_for_code_tasks",
                        ["research", "search", "find docs", "documentation",
                         "library", "libraries", "api", "compare approaches",
                         "best way", "examples", "relevant sources",
                         "implementation approach"]),
    ]

    best = max(candidates, key=lambda r: r.confidence)

    if best.confidence == 0:
        return ClassificationResult(
            domain="general",
            subdomain="unknown",
            intent="general_task_handling",
            confidence=0.0,
            matched_signals=[],
            classification_method="fallback",
        )

    return best


# Public classifier

class DomainClassifier:
    """
    First routing layer of the stem agent.

    Classification strategy (in priority order):

    1. LLM path (requires OPENAI_API_KEY): the task prompt is sent to the LLM,
       which reasons about domain, subdomain, and intent from scratch. This is
       genuinely emergent: the model reads the prompt semantically rather than
       matching against a fixed keyword list.

    2. Keyword fallback (no API key, or LLM call failed): the original
       signal-matching logic runs. Retained for reproducibility and to provide
       a measurable baseline.

    The `classification_method` field on the result records which path ran,
    making it possible to compare LLM vs keyword classification in evaluation.
    """

    def classify(self, prompt: str) -> ClassificationResult:
        # Try LLM classification first
        llm_result = _classify_with_llm(prompt)
        if llm_result is not None:
            return llm_result

        # Fall back to keyword matching
        text = " ".join(prompt.lower().split())
        return _classify_with_keywords(text)
