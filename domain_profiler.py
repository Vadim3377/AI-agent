from models import DomainProfile


class DomainProfiler:
    """
    Converts a broad task description into a structured domain profile.

    This is the first 'environment reading' step of the stem agent.
    The shell agent does not solve the task yet. It only identifies what
    kind of specialist it may need to become.
    """

    def profile(self, task_description: str) -> DomainProfile:
        text = task_description.lower()

        if self._looks_like_code_qa(text):
            return DomainProfile(
                domain="quality_assurance",
                subdomain="code_review_and_bug_detection",
                artifact_type="source_code",
                required_capabilities=[
                    "code_understanding",
                    "bug_detection",
                    "edge_case_generation",
                    "test_generation",
                    "runtime_failure_analysis",
                    "structured_reporting"
                ],
                candidate_tools=[
                    "python_runner",
                    "pytest_runner",
                    "static_checker"
                ],
                evaluation_metrics=[
                    "bug_recall",
                    "precision",
                    "f1_score",
                    "false_positive_rate"
                ],
                reasoning=(
                    "The task appears to involve software quality assurance. "
                    "A specialised agent should inspect code, generate tests, "
                    "run them, analyse failures, and report confirmed or suspected issues."
                )
            )

        if self._looks_like_security(text):
            return DomainProfile(
                domain="security",
                subdomain="privacy_and_leak_detection",
                artifact_type="text_or_structured_payload",
                required_capabilities=[
                    "sensitive_data_detection",
                    "risk_classification",
                    "evidence_extraction",
                    "policy_based_reasoning",
                    "structured_reporting"
                ],
                candidate_tools=[
                    "regex_scanner",
                    "secret_detector",
                    "llm_risk_classifier"
                ],
                evaluation_metrics=[
                    "leak_detection_recall",
                    "precision",
                    "f1_score",
                    "false_positive_rate"
                ],
                reasoning=(
                    "The task appears security-related. A specialised agent should "
                    "identify possible leaks, classify risk, and provide evidence-backed diagnostics."
                )
            )

        if self._looks_like_deep_research(text):
            return DomainProfile(
                domain="deep_research",
                subdomain="evidence_synthesis",
                artifact_type="documents_or_web_sources",
                required_capabilities=[
                    "query_planning",
                    "source_retrieval",
                    "source_quality_assessment",
                    "claim_extraction",
                    "synthesis",
                    "citation_generation"
                ],
                candidate_tools=[
                    "web_search",
                    "document_reader",
                    "citation_checker"
                ],
                evaluation_metrics=[
                    "answer_correctness",
                    "source_quality",
                    "citation_coverage",
                    "claim_support_rate"
                ],
                reasoning=(
                    "The task appears to involve deep research. A specialised agent should "
                    "retrieve sources, assess evidence quality, extract claims, and produce cited synthesis."
                )
            )

        return DomainProfile(
            domain="general",
            subdomain="unknown",
            artifact_type="unknown",
            required_capabilities=[
                "task_decomposition",
                "reasoning",
                "structured_output"
            ],
            candidate_tools=[],
            evaluation_metrics=[
                "task_success_rate",
                "output_quality"
            ],
            reasoning=(
                "The task could not be confidently assigned to QA, security, or research. "
                "A generic structured reasoning agent is proposed as the initial fallback."
            )
        )

    def _looks_like_code_qa(self, text: str) -> bool:
        keywords = [
            "code", "bug", "test", "pytest", "unit test", "review",
            "quality", "qa", "function", "class", "repository",
            "static analysis", "lint"
        ]
        return any(keyword in text for keyword in keywords)

    def _looks_like_security(self, text: str) -> bool:
        keywords = [
            "security", "pii", "privacy", "leak", "secret",
            "token", "api key", "password", "vulnerability",
            "data breach", "deanonymization", "de-anonymization"
        ]
        return any(keyword in text for keyword in keywords)

    def _looks_like_deep_research(self, text: str) -> bool:
        keywords = [
            "research", "sources", "citations", "literature",
            "compare", "investigate", "summarise", "summarize",
            "evidence", "papers", "web"
        ]
        return any(keyword in text for keyword in keywords)