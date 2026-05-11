"""
blueprint_mutator.py — Controlled blueprint mutation.

This module applies safe mutations to an AgentBlueprint. It does not rewrite
source code. It changes blueprint configuration: workflow steps, output schema,
stopping conditions, and role description.

Documentation mutation (updated)
---------------------------------
The original mutation added comment-quality checks. This version additionally
adds "verify_docstring_coverage" as an ACTIVE verification step. The runner
checks for this exact signal to decide whether to run the docstring-checker
→ revise loop. Without the active step the runner runs single-shot; with it,
the loop is triggered.

This mirrors the debugging design: "run_tests_if_available" is passive;
"verify_fix_against_generated_tests" is active. The same active/passive
distinction now applies to documentation.
"""

from copy import deepcopy

from models import AgentBlueprint


class BlueprintMutator:
    """
    Applies controlled mutations to an AgentBlueprint.

    Mutation is applied only to safe configuration fields:
    - workflow steps
    - output schema
    - stopping conditions
    - role description

    Source code is never modified.
    """

    def mutate(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        mutated = deepcopy(blueprint)
        subdomain = mutated.domain_profile.subdomain

        if subdomain == "debugging":
            return self._mutate_debugging_blueprint(mutated)
        if subdomain == "code_quality_cleanup":
            return self._mutate_code_quality_blueprint(mutated)
        if subdomain == "comments_and_documentation":
            return self._mutate_comments_blueprint(mutated)
        if subdomain == "dangerous_operations_and_data_breaches":
            return self._mutate_security_blueprint(mutated)
        if subdomain == "code_research":
            return self._mutate_research_blueprint(mutated)
        return self._mutate_generic_blueprint(mutated)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _mark_mutated(
        self, blueprint: AgentBlueprint, mutation_name: str
    ) -> AgentBlueprint:
        blueprint.name = f"{blueprint.name}__mutated_{mutation_name}"
        blueprint.role = (
            blueprint.role
            + " This version has been mutated to add a more explicit verification "
            "step before producing its final answer."
        )
        blueprint.stopping_condition["mutation_applied"] = mutation_name
        blueprint.stopping_condition["mutation_strategy"] = (
            "safe_blueprint_configuration_mutation"
        )
        return blueprint

    def _insert_before_final_step(
        self, blueprint: AgentBlueprint, new_step: str
    ) -> None:
        if new_step in blueprint.workflow:
            return
        if not blueprint.workflow:
            blueprint.workflow.append(new_step)
            return
        blueprint.workflow.insert(len(blueprint.workflow) - 1, new_step)

    # ------------------------------------------------------------------
    # Domain-specific mutations
    # ------------------------------------------------------------------

    def _mutate_debugging_blueprint(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        # Active step — triggers the pytest feedback loop in LLMAgentRunner
        self._insert_before_final_step(
            blueprint, "verify_fix_against_generated_tests"
        )
        self._insert_before_final_step(blueprint, "check_for_regression_risk")
        blueprint.output_schema["regression_risk"] = "low | medium | high"
        blueprint.output_schema["verification_summary"] = "string"
        blueprint.stopping_condition["minimum_regression_safety"] = 0.80
        return self._mark_mutated(blueprint, "debugging_verification")

    def _mutate_code_quality_blueprint(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        self._insert_before_final_step(
            blueprint, "verify_refactor_preserves_external_behaviour"
        )
        self._insert_before_final_step(
            blueprint, "rank_cleanup_suggestions_by_risk"
        )
        blueprint.output_schema["behaviour_preservation_notes"] = ["string"]
        blueprint.output_schema["risk_ranked_suggestions"] = ["string"]
        blueprint.stopping_condition["maximum_high_risk_refactors"] = 1
        return self._mark_mutated(blueprint, "cleanup_behaviour_preservation")

    def _mutate_comments_blueprint(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        """
        Documentation mutation (updated).

        Added steps:
        - verify_docstring_coverage   ← ACTIVE: triggers the docstring-checker
                                        feedback loop in LLMAgentRunner.
                                        This is the key behavioural difference
                                        between base and mutated blueprints.
        - check_comments_explain_why  ← quality check (unchanged)
        - remove_obvious_comments     ← noise filter (unchanged)

        The stopping condition now includes a measurable coverage threshold
        (0.80) that the feedback loop uses to decide when to stop revising.
        This makes the stopping criterion evidence-driven rather than based on
        a fixed iteration count.
        """
        # Active step — triggers docstring coverage loop in LLMAgentRunner
        self._insert_before_final_step(
            blueprint, "verify_docstring_coverage"
        )
        # Quality checks (passive — do not trigger a separate loop)
        self._insert_before_final_step(
            blueprint, "check_comments_explain_why_not_only_what"
        )
        self._insert_before_final_step(
            blueprint, "remove_obvious_or_noisy_comments"
        )

        blueprint.output_schema["comment_quality_checks"] = ["string"]
        blueprint.output_schema["removed_or_avoided_noisy_comments"] = ["string"]
        blueprint.output_schema["docstring_coverage_verified"] = "bool"

        blueprint.stopping_condition["maximum_redundant_comment_rate"] = 0.15
        # Coverage threshold — used by the runner's stopping criterion
        blueprint.stopping_condition["minimum_docstring_coverage"] = 0.80

        return self._mark_mutated(blueprint, "comment_quality_and_coverage")

    def _mutate_security_blueprint(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        self._insert_before_final_step(
            blueprint, "separate_confirmed_risks_from_suspected_risks"
        )
        self._insert_before_final_step(blueprint, "map_each_risk_to_mitigation")
        blueprint.output_schema["confirmed_risks"] = ["string"]
        blueprint.output_schema["suspected_risks"] = ["string"]
        blueprint.output_schema["mitigation_map"] = {"risk": "mitigation"}
        blueprint.stopping_condition["minimum_confirmed_risk_precision"] = 0.80
        return self._mark_mutated(blueprint, "security_risk_triage")

    def _mutate_research_blueprint(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        self._insert_before_final_step(
            blueprint, "cross_check_claims_against_multiple_sources"
        )
        self._insert_before_final_step(
            blueprint, "separate_documented_facts_from_recommendations"
        )
        blueprint.output_schema["verified_claims"] = ["string"]
        blueprint.output_schema["implementation_recommendations"] = ["string"]
        blueprint.stopping_condition["minimum_cross_checked_claim_rate"] = 0.75
        return self._mark_mutated(blueprint, "research_claim_verification")

    def _mutate_generic_blueprint(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        self._insert_before_final_step(blueprint, "self_check_output_against_task")
        blueprint.output_schema["self_check"] = "string"
        return self._mark_mutated(blueprint, "generic_self_check")
