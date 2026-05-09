from dataclasses import dataclass
from typing import List


@dataclass
class ClassificationResult:
    domain: str
    subdomain: str
    intent: str
    confidence: float
    matched_signals: List[str]


class DomainClassifier:
    """
    First routing layer of the stem agent.

    It receives a broad task prompt, normalises it, detects task-specific
    signals, and classifies the task into a domain and subdomain. The result
    is then expanded by the DomainProfiler into a full agent profile.
    """

    def classify(self, prompt: str) -> ClassificationResult:
        text = self._normalise(prompt)

        candidates = [
            self._score_debugging(text),
            self._score_code_quality_cleanup(text),
            self._score_comments(text),
            self._score_security(text),
            self._score_deep_research(text),
        ]

        best = max(candidates, key=lambda result: result.confidence)

        if best.confidence == 0:
            return ClassificationResult(
                domain="general",
                subdomain="unknown",
                intent="general_task_handling",
                confidence=0.0,
                matched_signals=[]
            )

        return best

    def _normalise(self, prompt: str) -> str:
        return " ".join(prompt.lower().split())

    def _score_category(
        self,
        text: str,
        domain: str,
        subdomain: str,
        intent: str,
        signals: List[str]
    ) -> ClassificationResult:
        matched = [signal for signal in signals if signal in text]

        # Three matched signals are treated as high confidence.
        confidence = min(1.0, len(matched) / 3)

        return ClassificationResult(
            domain=domain,
            subdomain=subdomain,
            intent=intent,
            confidence=round(confidence, 2),
            matched_signals=matched
        )

    def _score_debugging(self, text: str) -> ClassificationResult:
        return self._score_category(
            text=text,
            domain="quality_assurance",
            subdomain="debugging",
            intent="find_and_fix_bugs",
            signals=[
                "bug",
                "debug",
                "debugging",
                "error",
                "exception",
                "failing test",
                "test fails",
                "wrong output",
                "traceback",
                "crash",
                "fix this",
                "broken",
                "does not work"
            ]
        )

    def _score_code_quality_cleanup(self, text: str) -> ClassificationResult:
        return self._score_category(
            text=text,
            domain="quality_assurance",
            subdomain="code_quality_cleanup",
            intent="improve_code_quality_without_changing_behaviour",
            signals=[
                "clean up",
                "cleanup",
                "refactor",
                "optimise",
                "optimize",
                "dead code",
                "unused code",
                "redundant",
                "redundancy",
                "simplify",
                "readability",
                "maintainability",
                "performance"
            ]
        )

    def _score_comments(self, text: str) -> ClassificationResult:
        return self._score_category(
            text=text,
            domain="quality_assurance",
            subdomain="comments_and_documentation",
            intent="add_or_improve_code_explanations",
            signals=[
                "add comments",
                "comments",
                "comment",
                "docstring",
                "docstrings",
                "documentation",
                "document this",
                "explain the code",
                "annotate",
                "readme"
            ]
        )

    def _score_security(self, text: str) -> ClassificationResult:
        return self._score_category(
            text=text,
            domain="security",
            subdomain="dangerous_operations_and_data_breaches",
            intent="detect_security_risks_and_sensitive_data_leaks",
            signals=[
                "security",
                "secure",
                "unsafe",
                "dangerous operation",
                "data breach",
                "pii",
                "privacy",
                "leak",
                "secret",
                "api key",
                "token",
                "password",
                "eval",
                "exec",
                "subprocess",
                "sql injection",
                "path traversal"
            ]
        )

    def _score_deep_research(self, text: str) -> ClassificationResult:
        return self._score_category(
            text=text,
            domain="deep_research",
            subdomain="code_research",
            intent="research_relevant_information_for_code_tasks",
            signals=[
                "research",
                "search",
                "find docs",
                "documentation",
                "library",
                "libraries",
                "api",
                "compare approaches",
                "best way",
                "examples",
                "relevant sources",
                "implementation approach"
            ]
        )