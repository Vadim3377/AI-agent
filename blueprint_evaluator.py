"""
blueprint_evaluator.py — Two-layer blueprint evaluation.

Layer 1 — Structural (40% weight): unchanged from original.
Checks blueprint shape: workflow length, tools, schema, stopping conditions,
domain-specific fields, safeguard steps, subdomain alignment.

Layer 2 — Task-level (60% weight): NEW.
Uses real tool results from AgentRunner to score whether the blueprint
actually did useful work on the task input. Scores depend on observable
tool output (pytest pass/fail, static issue count, docstring coverage,
secret findings) — not on properties the evaluator itself defines.

Combined score = 0.4 * structural + 0.6 * task_level.
If no tool results are provided, task_level falls back to structural_score
so the evaluator degrades gracefully for runs without task input.

The .score property on the result always returns combined_score, preserving
backward compatibility with all existing callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from models import AgentBlueprint


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    structural_score: float
    task_score: float
    combined_score: float
    passed_checks: List[str]
    failed_checks: List[str]
    task_evidence: List[str]
    notes: str

    @property
    def score(self) -> float:
        """Backward-compatible accessor — returns combined_score."""
        return self.combined_score


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class BlueprintEvaluator:
    """
    Two-layer evaluator.

    Usage
    -----
    evaluator = BlueprintEvaluator()

    # Structural only (original behaviour, no tool results):
    result = evaluator.evaluate(blueprint)

    # With task-level evidence from AgentRunner:
    runner = AgentRunner()
    runner.run(blueprint, task_input)
    result = evaluator.evaluate(blueprint, tool_results=runner.last_tool_results)
    """

    def evaluate(
        self,
        blueprint: AgentBlueprint,
        tool_results: Optional[List[Any]] = None,
    ) -> EvaluationResult:

        passed, failed = self._structural_checks(blueprint)
        structural = round(len(passed) / max(len(passed) + len(failed), 1), 2)

        if tool_results:
            task, evidence = self._task_checks(blueprint, tool_results)
        else:
            task = structural
            evidence = ["No tool results provided — task score mirrors structural score."]

        combined = round(0.4 * structural + 0.6 * task, 2)

        notes = (
            f"Structural: {structural:.2f} ({len(passed)}/{len(passed)+len(failed)} checks). "
            f"Task-level: {task:.2f}. "
            f"Combined: {combined:.2f}. "
            f"Subdomain: {blueprint.domain_profile.subdomain}."
        )

        return EvaluationResult(
            structural_score=structural,
            task_score=task,
            combined_score=combined,
            passed_checks=passed,
            failed_checks=failed,
            task_evidence=evidence,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Layer 1: structural checks
    # ------------------------------------------------------------------

    def _structural_checks(self, bp: AgentBlueprint) -> Tuple[List[str], List[str]]:
        checks = [
            self._has_domain_specific_workflow,
            self._has_relevant_tools,
            self._has_output_schema,
            self._has_stopping_conditions,
            self._has_domain_specific_schema,
            self._has_verification_or_safeguard_step,
            self._workflow_matches_subdomain,
        ]
        passed, failed = [], []
        for check in checks:
            name = check.__name__.replace("_", " ").strip()
            (passed if check(bp) else failed).append(name)
        return passed, failed

    def _has_domain_specific_workflow(self, bp: AgentBlueprint) -> bool:
        return len(bp.workflow) >= 5

    def _has_relevant_tools(self, bp: AgentBlueprint) -> bool:
        return bp.domain_profile.domain == "general" or len(bp.tools) > 0

    def _has_output_schema(self, bp: AgentBlueprint) -> bool:
        return len(bp.output_schema) >= 3

    def _has_stopping_conditions(self, bp: AgentBlueprint) -> bool:
        required = {"max_evolution_iterations", "reject_if_schema_invalid", "reject_if_score_regresses"}
        return required.issubset(set(bp.stopping_condition.keys()))

    def _has_domain_specific_schema(self, bp: AgentBlueprint) -> bool:
        schema_keys = set(bp.output_schema.keys())
        expected_by_subdomain = {
            "debugging":                              {"likely_root_cause", "suggested_fix", "fix_rationale"},
            "code_quality_cleanup":                   {"dead_code", "redundant_logic", "refactor_suggestions"},
            "comments_and_documentation":             {"docstrings_added", "inline_comments_added", "non_obvious_logic_explained"},
            "dangerous_operations_and_data_breaches": {"risk_level", "findings", "final_verdict"},
            "code_research":                          {"answer", "recommended_approach", "sources"},
        }
        expected = expected_by_subdomain.get(bp.domain_profile.subdomain)
        return True if expected is None else len(schema_keys & expected) >= 2

    def _has_verification_or_safeguard_step(self, bp: AgentBlueprint) -> bool:
        signals = ["verify", "verification", "check", "cross_check", "regression",
                   "preserves", "confirmed", "suspected", "risk", "mitigation"]
        text = " ".join(bp.workflow + list(bp.output_schema.keys()) + list(bp.stopping_condition.keys())).lower()
        return any(s in text for s in signals)

    def _workflow_matches_subdomain(self, bp: AgentBlueprint) -> bool:
        text = " ".join(bp.workflow).lower()
        signals_by_subdomain = {
            "debugging":                              ["bug", "failure", "fix", "test"],
            "code_quality_cleanup":                   ["dead", "redundant", "readability", "refactor"],
            "comments_and_documentation":             ["comment", "docstring", "documentation"],
            "dangerous_operations_and_data_breaches": ["dangerous", "secret", "pii", "risk"],
            "code_research":                          ["search", "source", "research", "documentation"],
        }
        signals = signals_by_subdomain.get(bp.domain_profile.subdomain)
        return True if signals is None else sum(1 for s in signals if s in text) >= 2

    # ------------------------------------------------------------------
    # Layer 2: task-level checks using real tool results
    # ------------------------------------------------------------------

    def _task_checks(
        self,
        blueprint: AgentBlueprint,
        tool_results: List[Any],
    ) -> Tuple[float, List[str]]:
        subdomain = blueprint.domain_profile.subdomain
        tl = {r.tool_name: r for r in tool_results}

        if "debugging" in subdomain:
            return self._score_debugging(tl)
        if "code_quality" in subdomain or "cleanup" in subdomain:
            return self._score_code_quality(tl)
        if "documentation" in subdomain or "comment" in subdomain:
            return self._score_documentation(tl)
        if "security" in subdomain or "dangerous" in subdomain:
            return self._score_security(tl)

        # Generic fallback
        any_success = any(r.success for r in tool_results)
        return (0.7 if any_success else 0.3), [f"Tool '{r.tool_name}' ran (success={r.success})." for r in tool_results]

    def _score_debugging(self, tl: Dict) -> Tuple[float, List[str]]:
        evidence, points, total = [], 0.0, 0.0

        if "pytest_runner" in tl:
            r = tl["pytest_runner"]
            total += 1.0
            if r.success:
                points += 1.0
                evidence.append(f"pytest_runner: all {r.output.get('tests_passed', 0)} tests passed.")
            else:
                tp = r.output.get("tests_passed", 0)
                tr = r.output.get("tests_run", 0)
                partial = (tp / tr) * 0.5 if tr > 0 else 0.0
                points += partial
                evidence.append(f"pytest_runner: {tp}/{tr} passed (partial credit {partial:.2f}).")

        if "static_checker" in tl:
            r = tl["static_checker"]
            total += 0.5
            suspicious = [i for i in r.output.get("issues", []) if i.get("type") == "suspicious_operator"]
            if suspicious:
                points += 0.5
                evidence.append(f"static_checker: {len(suspicious)} suspicious operator(s) detected.")
            else:
                evidence.append("static_checker: no suspicious operators detected.")

        return (round(points / total, 2) if total > 0 else 0.5), evidence

    def _score_code_quality(self, tl: Dict) -> Tuple[float, List[str]]:
        evidence, points, total = [], 0.0, 1.0

        if "complexity_checker" in tl:
            r = tl["complexity_checker"]
            funcs = r.output.get("functions", [])
            if funcs:
                points += 0.6
                evidence.append(f"complexity_checker: {len(funcs)} function(s), {r.output.get('flagged_count', 0)} high-complexity.")
            else:
                evidence.append("complexity_checker: no functions found.")

        if "static_checker" in tl:
            r = tl["static_checker"]
            total += 0.5
            points += 0.4
            evidence.append(f"static_checker: {r.output.get('issue_count', 0)} issue(s) found.")

        return round(min(points / total, 1.0), 2), evidence

    def _score_documentation(self, tl: Dict) -> Tuple[float, List[str]]:
        if "docstring_checker" in tl:
            r = tl["docstring_checker"]
            cov = r.output.get("coverage", 0.0)
            missing = r.output.get("missing_count", 0)
            return round(cov, 2), [f"docstring_checker: {cov*100:.0f}% coverage, {missing} item(s) undocumented."]
        return 0.5, ["No documentation tool ran."]

    def _score_security(self, tl: Dict) -> Tuple[float, List[str]]:
        if "secret_detector" in tl:
            r = tl["secret_detector"]
            count = r.output.get("finding_count", 0)
            score = 0.9 if count == 0 else max(0.5, 1.0 - count * 0.1)
            return round(score, 2), [f"secret_detector: {count} potential secret(s) found."]
        return 0.5, ["No security tool ran."]
