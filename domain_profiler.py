from models import DomainProfile
from domain_classifier import DomainClassifier, ClassificationResult


class DomainProfiler:
    """
    Expands a task classification into a structured domain profile.

    The classifier decides which category the prompt belongs to.
    The profiler then converts that category into capabilities, tools,
    evaluation metrics, and reasoning that the StemShell can use to
    generate an agent blueprint.
    """

    def __init__(self) -> None:
        self.classifier = DomainClassifier()

    def profile(self, task_description: str) -> DomainProfile:
        classification = self.classifier.classify(task_description)

        if classification.subdomain == "debugging":
            return self._debugging_profile(classification)

        if classification.subdomain == "code_quality_cleanup":
            return self._code_quality_cleanup_profile(classification)

        if classification.subdomain == "comments_and_documentation":
            return self._comments_profile(classification)

        if classification.subdomain == "dangerous_operations_and_data_breaches":
            return self._security_profile(classification)

        if classification.subdomain == "code_research":
            return self._deep_research_profile(classification)

        return self._generic_profile(classification)

    def _debugging_profile(self, classification: ClassificationResult) -> DomainProfile:
        return DomainProfile(
            domain=classification.domain,
            subdomain=classification.subdomain,
            artifact_type="source_code",
            required_capabilities=[
                "code_understanding",
                "expected_behaviour_inference",
                "bug_localisation",
                "test_generation",
                "runtime_failure_analysis",
                "fix_suggestion",
                "structured_reporting"
            ],
            candidate_tools=[
                "python_runner",
                "pytest_runner",
                "static_checker"
            ],
            evaluation_metrics=[
                "bug_recall",
                "fix_correctness",
                "test_pass_rate",
                "precision",
                "f1_score"
            ],
            reasoning=(
                "The classifier identified this as a debugging task. "
                "The specialised agent should inspect the code, infer intended behaviour, "
                "reproduce or reason about the failure, generate tests, locate the defect, "
                "and suggest a fix."
            )
        )

    def _code_quality_cleanup_profile(self, classification: ClassificationResult) -> DomainProfile:
        return DomainProfile(
            domain=classification.domain,
            subdomain=classification.subdomain,
            artifact_type="source_code",
            required_capabilities=[
                "code_understanding",
                "dead_code_detection",
                "redundancy_detection",
                "readability_analysis",
                "performance_smell_detection",
                "behaviour_preservation",
                "refactoring_suggestion",
                "structured_reporting"
            ],
            candidate_tools=[
                "static_checker",
                "complexity_analyser",
                "formatter"
            ],
            evaluation_metrics=[
                "behaviour_preservation_rate",
                "complexity_reduction",
                "redundancy_reduction",
                "readability_score",
                "review_precision"
            ],
            reasoning=(
                "The classifier identified this as a code-quality cleanup task. "
                "The specialised agent should improve maintainability without changing "
                "the intended behaviour of the code."
            )
        )

    def _comments_profile(self, classification: ClassificationResult) -> DomainProfile:
        return DomainProfile(
            domain=classification.domain,
            subdomain=classification.subdomain,
            artifact_type="source_code",
            required_capabilities=[
                "code_understanding",
                "intent_extraction",
                "non_obvious_logic_detection",
                "comment_generation",
                "docstring_generation",
                "redundant_comment_avoidance"
            ],
            candidate_tools=[
                "documentation_generator",
                "style_checker"
            ],
            evaluation_metrics=[
                "comment_relevance",
                "comment_conciseness",
                "coverage_of_non_obvious_logic",
                "redundant_comment_rate"
            ],
            reasoning=(
                "The classifier identified this as a comments and documentation task. "
                "The specialised agent should explain non-obvious logic and improve "
                "understandability without adding noisy or redundant comments."
            )
        )

    def _security_profile(self, classification: ClassificationResult) -> DomainProfile:
        return DomainProfile(
            domain=classification.domain,
            subdomain=classification.subdomain,
            artifact_type="source_code_or_structured_payload",
            required_capabilities=[
                "dangerous_operation_detection",
                "secret_detection",
                "pii_detection",
                "data_leak_risk_classification",
                "evidence_extraction",
                "mitigation_suggestion",
                "structured_security_reporting"
            ],
            candidate_tools=[
                "regex_scanner",
                "secret_detector",
                "static_checker",
                "llm_risk_classifier"
            ],
            evaluation_metrics=[
                "leak_detection_recall",
                "security_precision",
                "false_positive_rate",
                "severity_classification_accuracy",
                "f1_score"
            ],
            reasoning=(
                "The classifier identified this as a security task involving dangerous "
                "operations or possible data breaches. The specialised agent should detect "
                "unsafe operations, exposed secrets, PII, and risky data flows."
            )
        )

    def _deep_research_profile(self, classification: ClassificationResult) -> DomainProfile:
        return DomainProfile(
            domain=classification.domain,
            subdomain=classification.subdomain,
            artifact_type="technical_question_or_code_context",
            required_capabilities=[
                "technical_query_planning",
                "source_retrieval",
                "documentation_analysis",
                "source_relevance_assessment",
                "implementation_guidance_synthesis",
                "citation_generation"
            ],
            candidate_tools=[
                "web_search",
                "documentation_reader",
                "citation_checker"
            ],
            evaluation_metrics=[
                "source_relevance",
                "answer_correctness",
                "citation_coverage",
                "implementation_usefulness",
                "claim_support_rate"
            ],
            reasoning=(
                "The classifier identified this as a code-related research task. "
                "The specialised agent should search for relevant technical information, "
                "assess source quality, and summarise implementation-relevant findings."
            )
        )

    def _generic_profile(self, classification: ClassificationResult) -> DomainProfile:
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
                "The classifier could not confidently assign this task to a supported "
                "specialist category. A generic structured reasoning profile is used."
            )
        )