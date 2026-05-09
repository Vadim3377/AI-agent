from models import AgentBlueprint, EvaluationResult


class BlueprintEvaluator:
    """
    Deterministic evaluator for agent blueprints.

    This does not evaluate task-solving performance yet. Instead, it evaluates
    whether a generated blueprint is structurally suitable for its domain:
    workflow specificity, tool relevance, output schema, stopping conditions,
    and safeguards.

    This gives the stem shell its first measurable before/after comparison.
    """

    def evaluate(self, blueprint: AgentBlueprint) -> EvaluationResult:
        passed_checks: list[str] = []
        failed_checks: list[str] = []

        checks = [
            self._has_domain_specific_workflow,
            self._has_relevant_tools,
            self._has_output_schema,
            self._has_stopping_conditions,
            self._has_domain_specific_schema,
            self._has_verification_or_safeguard_step,
            self._workflow_matches_subdomain,
        ]

        for check in checks:
            check_name = check.__name__.replace("_", " ").strip()
            if check(blueprint):
                passed_checks.append(check_name)
            else:
                failed_checks.append(check_name)

        score = round(len(passed_checks) / len(checks), 2)

        notes = (
            f"Blueprint passed {len(passed_checks)} out of {len(checks)} structural checks. "
            f"Subdomain evaluated: {blueprint.domain_profile.subdomain}."
        )

        return EvaluationResult(
            score=score,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            notes=notes
        )

    def _has_domain_specific_workflow(self, blueprint: AgentBlueprint) -> bool:
        return len(blueprint.workflow) >= 5

    def _has_relevant_tools(self, blueprint: AgentBlueprint) -> bool:
        if blueprint.domain_profile.domain == "general":
            return True

        return len(blueprint.tools) > 0

    def _has_output_schema(self, blueprint: AgentBlueprint) -> bool:
        return len(blueprint.output_schema) >= 3

    def _has_stopping_conditions(self, blueprint: AgentBlueprint) -> bool:
        required = {
            "max_evolution_iterations",
            "reject_if_schema_invalid",
            "reject_if_score_regresses",
        }
        return required.issubset(set(blueprint.stopping_condition.keys()))

    def _has_domain_specific_schema(self, blueprint: AgentBlueprint) -> bool:
        schema_keys = set(blueprint.output_schema.keys())
        subdomain = blueprint.domain_profile.subdomain

        expected_keys_by_subdomain = {
            "debugging": {
                "likely_root_cause",
                "suggested_fix",
                "fix_rationale",
            },
            "code_quality_cleanup": {
                "dead_code",
                "redundant_logic",
                "refactor_suggestions",
            },
            "comments_and_documentation": {
                "docstrings_added",
                "inline_comments_added",
                "non_obvious_logic_explained",
            },
            "dangerous_operations_and_data_breaches": {
                "risk_level",
                "findings",
                "final_verdict",
            },
            "code_research": {
                "answer",
                "recommended_approach",
                "sources",
            },
        }

        expected_keys = expected_keys_by_subdomain.get(subdomain)

        if expected_keys is None:
            return True

        return len(schema_keys.intersection(expected_keys)) >= 2

    def _has_verification_or_safeguard_step(self, blueprint: AgentBlueprint) -> bool:
        verification_signals = [
            "verify",
            "verification",
            "check",
            "cross_check",
            "regression",
            "preserves",
            "confirmed",
            "suspected",
            "risk",
            "mitigation",
        ]

        workflow_text = " ".join(blueprint.workflow).lower()
        schema_text = " ".join(blueprint.output_schema.keys()).lower()
        stopping_text = " ".join(blueprint.stopping_condition.keys()).lower()

        combined_text = f"{workflow_text} {schema_text} {stopping_text}"

        return any(signal in combined_text for signal in verification_signals)

    def _workflow_matches_subdomain(self, blueprint: AgentBlueprint) -> bool:
        workflow_text = " ".join(blueprint.workflow).lower()
        subdomain = blueprint.domain_profile.subdomain

        required_signals_by_subdomain = {
            "debugging": ["bug", "failure", "fix", "test"],
            "code_quality_cleanup": ["dead", "redundant", "readability", "refactor"],
            "comments_and_documentation": ["comment", "docstring", "documentation"],
            "dangerous_operations_and_data_breaches": ["dangerous", "secret", "pii", "risk"],
            "code_research": ["search", "source", "research", "documentation"],
        }

        required_signals = required_signals_by_subdomain.get(subdomain)

        if required_signals is None:
            return True

        matched = [signal for signal in required_signals if signal in workflow_text]
        return len(matched) >= 2