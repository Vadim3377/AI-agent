from models import AgentBlueprint, DomainProfile


class ArchitectureGenerator:
    """
    Converts a domain profile into an initial specialised-agent architecture.

    The classifier decides what kind of task was given.
    The profiler describes what the specialist needs.
    The architecture generator creates the concrete agent blueprint:
    role, workflow, tools, output schema, and stopping conditions.
    """

    def generate(self, profile: DomainProfile) -> AgentBlueprint:
        if profile.subdomain == "debugging":
            return self._debugging_architecture(profile)

        if profile.subdomain == "code_quality_cleanup":
            return self._code_quality_architecture(profile)

        if profile.subdomain == "comments_and_documentation":
            return self._comments_architecture(profile)

        if profile.subdomain == "dangerous_operations_and_data_breaches":
            return self._security_architecture(profile)

        if profile.subdomain == "code_research":
            return self._research_architecture(profile)

        return self._generic_architecture(profile)

    def _debugging_architecture(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="debugging_specialist_agent",
            role=(
                "Specialised debugging agent for locating defects in source code, "
                "reasoning about expected behaviour, generating tests, and suggesting fixes."
            ),
            domain_profile=profile,
            workflow=[
                "read_source_code",
                "infer_expected_behaviour",
                "identify_failure_symptoms",
                "generate_minimal_reproduction_or_tests",
                "run_tests_if_available",
                "localise_likely_bug",
                "suggest_fix",
                "explain_fix_rationale",
                "produce_debugging_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"python_runner", "pytest_runner", "static_checker"}
            ],
            output_schema={
                "summary": "string",
                "failure_symptoms": ["string"],
                "likely_root_cause": "string",
                "generated_tests": ["string"],
                "suggested_fix": "string",
                "fix_rationale": "string",
                "confidence": "low | medium | high",
                "final_verdict": "fixed | likely_fixed | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_fix_correctness": 0.75,
                "minimum_test_pass_rate": 0.80,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _code_quality_architecture(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="code_quality_cleanup_agent",
            role=(
                "Specialised code-quality agent for improving readability, removing dead code, "
                "reducing redundancy, and suggesting behaviour-preserving refactors."
            ),
            domain_profile=profile,
            workflow=[
                "read_source_code",
                "identify_dead_or_unused_code",
                "identify_redundant_logic",
                "analyse_readability_and_complexity",
                "suggest_behaviour_preserving_refactor",
                "check_for_possible_behaviour_changes",
                "produce_cleanup_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"static_checker", "complexity_analyser", "formatter"}
            ],
            output_schema={
                "summary": "string",
                "dead_code": ["string"],
                "redundant_logic": ["string"],
                "readability_issues": ["string"],
                "refactor_suggestions": [
                    {
                        "issue": "string",
                        "suggestion": "string",
                        "behaviour_risk": "low | medium | high"
                    }
                ],
                "final_verdict": "safe_to_refactor | needs_human_review | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_behaviour_preservation_rate": 0.90,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _comments_architecture(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="comments_documentation_agent",
            role=(
                "Specialised documentation agent for adding concise comments and docstrings "
                "that explain intent and non-obvious logic without adding noise."
            ),
            domain_profile=profile,
            workflow=[
                "read_source_code",
                "identify_public_interfaces",
                "identify_non_obvious_logic",
                "generate_docstrings",
                "generate_inline_comments_only_where_useful",
                "remove_or_avoid_redundant_comments",
                "produce_documentation_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"documentation_generator", "style_checker"}
            ],
            output_schema={
                "summary": "string",
                "docstrings_added": ["string"],
                "inline_comments_added": ["string"],
                "non_obvious_logic_explained": ["string"],
                "redundant_comments_avoided": ["string"],
                "final_verdict": "documented | partially_documented | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_comment_relevance": 0.80,
                "maximum_redundant_comment_rate": 0.20,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _security_architecture(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="security_validation_agent",
            role=(
                "Specialised security validation agent for detecting dangerous operations, "
                "secrets, PII, privacy risks, and possible data breaches."
            ),
            domain_profile=profile,
            workflow=[
                "read_source_or_payload",
                "scan_for_dangerous_operations",
                "scan_for_secrets_and_tokens",
                "scan_for_pii_or_private_data",
                "analyse_possible_data_flows",
                "classify_risk_severity",
                "suggest_mitigation",
                "produce_security_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"regex_scanner", "secret_detector", "static_checker", "llm_risk_classifier"}
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
                "minimum_leak_detection_recall": 0.85,
                "maximum_false_positive_rate": 0.25,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _research_architecture(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="code_research_agent",
            role=(
                "Specialised code-research agent for finding relevant technical sources, "
                "assessing documentation, and synthesising implementation guidance."
            ),
            domain_profile=profile,
            workflow=[
                "extract_research_question",
                "generate_search_queries",
                "retrieve_candidate_sources",
                "filter_sources_by_relevance",
                "assess_source_quality",
                "extract_implementation_guidance",
                "synthesise_recommendation",
                "produce_cited_report"
            ],
            tools=[
                tool for tool in profile.candidate_tools
                if tool in {"web_search", "documentation_reader", "citation_checker"}
            ],
            output_schema={
                "answer": "string",
                "recommended_approach": "string",
                "sources": [
                    {
                        "title": "string",
                        "url_or_reference": "string",
                        "relevance": "low | medium | high"
                    }
                ],
                "limitations": ["string"],
                "final_verdict": "answered | partially_answered | uncertain"
            },
            stopping_condition={
                "max_evolution_iterations": 3,
                "minimum_source_relevance": 0.80,
                "minimum_claim_support_rate": 0.80,
                "reject_if_schema_invalid": True,
                "reject_if_score_regresses": True
            }
        )

    def _generic_architecture(self, profile: DomainProfile) -> AgentBlueprint:
        return AgentBlueprint(
            name="generic_specialist_agent",
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