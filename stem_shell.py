from models import AgentBlueprint, DomainProfile
from domain_profiler import DomainProfiler


class StemShell:
    """
    The minimal stem agent.

    It does not solve domain tasks directly.
    Instead, it:
    1. Reads the task-family description.
    2. Profiles the domain.
    3. Creates an initial specialised-agent blueprint.
    """

    def __init__(self) -> None:
        self.profiler = DomainProfiler()

    def grow_initial_blueprint(self, task_description: str) -> AgentBlueprint:
        profile = self.profiler.profile(task_description)
        return self._create_blueprint(profile)

    def _create_blueprint(self, profile: DomainProfile) -> AgentBlueprint:
        if profile.domain == "quality_assurance":
            return self._create_code_qa_blueprint(profile)

        if profile.domain == "security":
            return self._create_security_blueprint(profile)

        if profile.domain == "deep_research":
            return self._create_research_blueprint(profile)

        return self._create_generic_blueprint(profile)

    def _create_code_qa_blueprint(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="initial_code_qa_agent",
            role=(
                "Specialised software quality assurance agent for reviewing source code, "
                "finding bugs, generating edge-case tests, and reporting confirmed issues."
            ),
            domain_profile=profile,
            workflow=[
                "read_source_code",
                "summarise_intended_behaviour",
                "identify_possible_bug_classes",
                "generate_edge_case_tests",
                "run_tests_if_tool_available",
                "analyse_failures",
                "separate_confirmed_and_suspected_issues",
                "produce_structured_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"python_runner", "pytest_runner", "static_checker"}
            ],
            output_schema={
                "summary": "string",
                "confirmed_issues": [
                    {
                        "title": "string",
                        "evidence": "string",
                        "severity": "low | medium | high",
                        "suggested_fix": "string"
                    }
                ],
                "suspected_issues": [
                    {
                        "title": "string",
                        "reason": "string",
                        "confidence": "low | medium | high"
                    }
                ],
                "tests_generated": ["string"],
                "final_verdict": "pass | fail | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_f1_score": 0.75,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _create_security_blueprint(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="initial_security_privacy_agent",
            role=(
                "Specialised security and privacy validation agent for detecting possible "
                "sensitive-data leaks and producing evidence-backed diagnostics."
            ),
            domain_profile=profile,
            workflow=[
                "read_input_payload",
                "scan_for_deterministic_patterns",
                "classify_sensitive_data_risks",
                "extract_evidence",
                "assign_severity",
                "produce_diagnostic_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"regex_scanner", "secret_detector", "llm_risk_classifier"}
            ],
            output_schema={
                "summary": "string",
                "risk_level": "none | low | medium | high",
                "findings": [
                    {
                        "type": "string",
                        "evidence": "string",
                        "severity": "low | medium | high",
                        "recommendation": "string"
                    }
                ],
                "final_verdict": "safe | unsafe | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_f1_score": 0.80,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _create_research_blueprint(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="initial_deep_research_agent",
            role=(
                "Specialised research agent for decomposing questions, retrieving evidence, "
                "assessing source quality, and producing cited synthesis."
            ),
            domain_profile=profile,
            workflow=[
                "decompose_research_question",
                "generate_search_queries",
                "retrieve_candidate_sources",
                "assess_source_quality",
                "extract_claims",
                "cross_check_claims",
                "synthesise_answer",
                "produce_cited_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"web_search", "document_reader", "citation_checker"}
            ],
            output_schema={
                "answer": "string",
                "key_claims": [
                    {
                        "claim": "string",
                        "supporting_sources": ["string"],
                        "confidence": "low | medium | high"
                    }
                ],
                "limitations": ["string"],
                "final_verdict": "answered | partially_answered | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_claim_support_rate": 0.80,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _create_generic_blueprint(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="initial_generic_agent",
            role="Generic structured task-solving agent.",
            domain_profile=profile,
            workflow=[
                "understand_task",
                "decompose_task",
                "solve_subtasks",
                "verify_output",
                "produce_structured_answer"
            ],
            tools=[],
            output_schema={
                "answer": "string",
                "reasoning_summary": "string",
                "uncertainties": ["string"],
                "final_verdict": "complete | partial | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )