"""
EvolutionEngine — iterative blueprint evolution with real tool feedback.

Replaces the single mutate-compare-stop loop with:

  1. Grow base blueprint
  2. Execute with real tools → semantic score
  3. For up to max_iterations:
     a. Mutate based on observed weakness (FeedbackMutator)
     b. Execute candidate with real tools
     c. Score candidate semantically
     d. If better: accept (new best), else: rollback
     e. Stop if converged (score >= threshold or no improvement for 2 rounds)
  4. Return best blueprint + full evolution trace

The trace is the evidence: it shows what the agent tried, what scored
better, what was rolled back, and why it stopped.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_runner import UnifiedAgentRunner
from blueprint_evaluator import BlueprintEvaluator
from feedback_mutator import FeedbackMutator
from models import AgentBlueprint
from semantic_scorer import SemanticScorer
from stem_shell import StemShell
from tool_registry import ToolRegistry, build_default_registry


@dataclass
class IterationRecord:
    iteration: int
    blueprint_name: str
    semantic_score: float
    structural_score: float
    score_reasons: List[str]
    accepted: bool
    mutation_tag: str
    tool_invocations: int
    duration_seconds: float


@dataclass
class EvolutionResult:
    best_blueprint: AgentBlueprint
    base_semantic_score: float
    best_semantic_score: float
    iterations: List[IterationRecord]
    stopping_reason: str
    total_duration_seconds: float

    def improvement(self) -> float:
        return round(self.best_semantic_score - self.base_semantic_score, 3)

    def summary(self) -> Dict[str, Any]:
        return {
            "base_semantic_score": self.base_semantic_score,
            "best_semantic_score": self.best_semantic_score,
            "improvement": self.improvement(),
            "iterations_run": len(self.iterations),
            "accepted_mutations": sum(1 for it in self.iterations if it.accepted),
            "rolled_back": sum(1 for it in self.iterations if not it.accepted),
            "stopping_reason": self.stopping_reason,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "iteration_trace": [
                {
                    "iteration": it.iteration,
                    "blueprint": it.blueprint_name,
                    "semantic_score": it.semantic_score,
                    "structural_score": it.structural_score,
                    "accepted": it.accepted,
                    "mutation": it.mutation_tag,
                    "tool_invocations": it.tool_invocations,
                    "reasons": it.score_reasons,
                }
                for it in self.iterations
            ],
        }


class EvolutionEngine:

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_threshold: float = 0.90,
        no_improvement_patience: int = 2,
        use_llm: bool = False,
        model: str = "gpt-4.1-mini",
        registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.no_improvement_patience = no_improvement_patience
        self.use_llm = use_llm
        self.model = model

        self.registry = registry or build_default_registry()
        self.shell = StemShell(registry=self.registry)
        self.runner = UnifiedAgentRunner(use_llm=use_llm, model=model)
        self.semantic_scorer = SemanticScorer()
        self.feedback_mutator = FeedbackMutator()
        self.structural_evaluator = BlueprintEvaluator()

    def evolve(self, task_description: str, task_input: str) -> EvolutionResult:
        start = time.perf_counter()
        iterations: List[IterationRecord] = []

        # --- Step 1: grow and score base blueprint ---
        best_blueprint = self.shell.grow_initial_blueprint(task_description, mutate=False)
        base_run = self.runner.run(best_blueprint, task_input)
        base_score_result = self.semantic_scorer.score(base_run, task_input)
        base_semantic = base_score_result["score"]
        best_semantic = base_semantic
        best_run = base_run

        no_improvement_rounds = 0

        print(f"  Base blueprint: {best_blueprint.name}")
        print(f"  Base semantic score: {base_semantic:.3f}")
        print(f"  Reasons: {base_score_result['reasons']}")
        print()

        # --- Step 2: iterative evolution ---
        for i in range(1, self.max_iterations + 1):
            iter_start = time.perf_counter()
            print(f"  Iteration {i}/{self.max_iterations}")

            # Mutate based on what the previous run revealed
            candidate = self.feedback_mutator.mutate(
                best_blueprint,
                score_result=base_score_result if i == 1 else score_result,
                run_result=best_run,
            )
            self.registry.attach(candidate)

            mutation_tag = candidate.stopping_condition.get("feedback_mutation", "unknown")

            # Execute candidate with real tools
            candidate_run = self.runner.run(candidate, task_input)
            score_result = self.semantic_scorer.score(candidate_run, task_input)
            candidate_semantic = score_result["score"]

            structural_eval = self.structural_evaluator.evaluate(candidate)
            accepted = candidate_semantic > best_semantic

            print(f"    Mutation: {mutation_tag}")
            print(f"    Candidate score: {candidate_semantic:.3f} (best so far: {best_semantic:.3f})")
            print(f"    {'✓ accepted' if accepted else '✗ rolled back'}")

            iterations.append(IterationRecord(
                iteration=i,
                blueprint_name=candidate.name,
                semantic_score=candidate_semantic,
                structural_score=structural_eval.score,
                score_reasons=score_result["reasons"],
                accepted=accepted,
                mutation_tag=mutation_tag,
                tool_invocations=score_result["tool_invocations"],
                duration_seconds=round(time.perf_counter() - iter_start, 2),
            ))

            if accepted:
                best_blueprint = candidate
                best_semantic = candidate_semantic
                best_run = candidate_run
                no_improvement_rounds = 0
            else:
                no_improvement_rounds += 1

            # Stopping conditions
            if best_semantic >= self.convergence_threshold:
                stopping_reason = f"converged at score {best_semantic:.3f} >= {self.convergence_threshold}"
                print(f"  Stopping: {stopping_reason}")
                break

            if no_improvement_rounds >= self.no_improvement_patience:
                stopping_reason = f"no improvement for {no_improvement_rounds} consecutive rounds"
                print(f"  Stopping: {stopping_reason}")
                break
        else:
            stopping_reason = f"reached max iterations ({self.max_iterations})"

        total_duration = time.perf_counter() - start
        print(f"\n  Final score: {best_semantic:.3f} (was {base_semantic:.3f}, +{best_semantic - base_semantic:.3f})")
        print(f"  Stopping reason: {stopping_reason}")

        return EvolutionResult(
            best_blueprint=best_blueprint,
            base_semantic_score=base_semantic,
            best_semantic_score=best_semantic,
            iterations=iterations,
            stopping_reason=stopping_reason,
            total_duration_seconds=total_duration,
        )
