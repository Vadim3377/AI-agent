from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class DomainProfile:
    domain: str
    subdomain: str
    artifact_type: str
    required_capabilities: List[str]
    candidate_tools: List[str]
    evaluation_metrics: List[str]
    reasoning: str
    # Classification metadata — carried through from DomainClassifier
    # so callers don't need to re-classify to find out how routing happened.
    classification_method: str = "keyword"   # "llm" | "keyword" | "fallback"
    llm_reasoning: str = ""                  # LLM's one-sentence justification


@dataclass
class AgentBlueprint:
    name: str
    role: str
    domain_profile: DomainProfile
    workflow: List[str]
    tools: List[str]
    output_schema: Dict[str, Any]
    stopping_condition: Dict[str, Any]


@dataclass
class EvaluationResult:
    score: float
    passed_checks: List[str]
    failed_checks: List[str]
    notes: str


@dataclass
class EvaluationComparison:
    """
    Named result of a base-vs-mutated blueprint evaluation.

    Replaces the bare 4-tuple previously returned by StemShell.grow_and_evaluate.
    Named fields prevent silent positional unpacking errors.
    """
    selected_blueprint: AgentBlueprint
    base_result: EvaluationResult
    mutated_result: EvaluationResult
    selected: str   # "base" | "mutated"


def save_blueprint(blueprint: AgentBlueprint, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(blueprint), f, indent=2)


def load_blueprint(path: str) -> AgentBlueprint:
    """
    Load an AgentBlueprint from a JSON file saved by save_blueprint.

    Args:
        path: Path to the blueprint JSON file.

    Returns:
        A fully reconstructed AgentBlueprint dataclass instance.
    """
    with open(path, encoding="utf-8") as f:
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
        classification_method=profile_data.get("classification_method", "keyword"),
        llm_reasoning=profile_data.get("llm_reasoning", ""),
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
