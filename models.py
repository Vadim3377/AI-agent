from dataclasses import dataclass, asdict
from typing import List, Dict, Any
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


@dataclass
class AgentBlueprint:
    name: str
    role: str
    domain_profile: DomainProfile
    workflow: List[str]
    tools: List[str]
    output_schema: Dict[str, Any]
    stopping_condition: Dict[str, Any]


def save_blueprint(blueprint: AgentBlueprint, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(blueprint), f, indent=2)