"""
mutation_loop.py — Multi-round blueprint evolution with real tool feedback.

Replaces the single BlueprintMutator + BlueprintEvaluator call in StemShell
with an iterative loop:

    base → evaluate → mutate → evaluate → keep best → repeat

The loop stops when:
  - score improvement falls below MIN_IMPROVEMENT (plateau), or
  - max_rounds is reached.

Scoring uses BlueprintEvaluator's two-layer score: structural (40%) +
task-level from real tool results (60%). This means the stopping criterion
is grounded in observable tool output, not structural self-assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from models import AgentBlueprint
from blueprint_mutator import BlueprintMutator
from blueprint_evaluator import BlueprintEvaluator, EvaluationResult
from agent_runner import AgentRunner


MIN_IMPROVEMENT = 0.03   # stop if gain < 3 percentage points
DEFAULT_MAX_ROUNDS = 4


@dataclass
class EvolutionRound:
    round_number: int
    blueprint_name: str
    structural_score: float
    task_score: float
    combined_score: float
    tool_evidence: List[str]
    selected: bool = False


@dataclass
class EvolutionResult:
    best_blueprint: AgentBlueprint
    best_score: float
    rounds: List[EvolutionRound]
    total_mutations: int
    stopping_reason: str

    def summary_table(self) -> str:
        header = f"{'Rnd':<4} {'Blueprint':<52} {'Struct':>7} {'Task':>6} {'Comb':>6} {'Best':>5}"
        sep = "-" * len(header)
        rows = [header, sep]
        for r in self.rounds:
            name = (r.blueprint_name[:49] + "...") if len(r.blueprint_name) > 52 else r.blueprint_name
            tick = "  ✓" if r.selected else ""
            rows.append(
                f"{r.round_number:<4} {name:<52} {r.structural_score:>7.2f} "
                f"{r.task_score:>6.2f} {r.combined_score:>6.2f}{tick}"
            )
        rows += [sep, f"Stopping reason: {self.stopping_reason}"]
        return "\n".join(rows)


class MutationLoop:
    """
    Multi-round evolution loop.

    Parameters
    ----------
    max_rounds : int
        Maximum mutation rounds (default 4).
    min_improvement : float
        Minimum combined-score gain to continue (default 0.03).
    run_tools : bool
        If True, AgentRunner is used to collect tool results for task-level
        scoring. Set False for fast structural-only mode.
    """

    def __init__(
        self,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        min_improvement: float = MIN_IMPROVEMENT,
        run_tools: bool = True,
    ) -> None:
        self.max_rounds = max_rounds
        self.min_improvement = min_improvement
        self.run_tools = run_tools
        self._mutator = BlueprintMutator()
        self._evaluator = BlueprintEvaluator()
        self._runner = AgentRunner()

    def run(
        self,
        blueprint: AgentBlueprint,
        task_input: str = "",
    ) -> EvolutionResult:
        """
        Evolve the blueprint for up to max_rounds. Returns an EvolutionResult
        containing the best blueprint found, all round records, and the
        stopping reason.
        """
        rounds: List[EvolutionRound] = []

        # Round 0: evaluate the base blueprint
        base_eval = self._evaluate(blueprint, task_input)
        best_bp = blueprint
        best_score = base_eval.combined_score

        rounds.append(EvolutionRound(
            round_number=0,
            blueprint_name=blueprint.name,
            structural_score=base_eval.structural_score,
            task_score=base_eval.task_score,
            combined_score=base_eval.combined_score,
            tool_evidence=base_eval.task_evidence,
            selected=True,
        ))

        stopping_reason = "max_rounds_reached"
        current_bp = blueprint

        for rnd in range(1, self.max_rounds + 1):
            mutated = self._mutator.mutate(current_bp)
            mut_eval = self._evaluate(mutated, task_input)

            gain = mut_eval.combined_score - best_score
            improved = gain >= self.min_improvement

            rounds.append(EvolutionRound(
                round_number=rnd,
                blueprint_name=mutated.name,
                structural_score=mut_eval.structural_score,
                task_score=mut_eval.task_score,
                combined_score=mut_eval.combined_score,
                tool_evidence=mut_eval.task_evidence,
                selected=False,
            ))

            if improved:
                best_bp = mutated
                best_score = mut_eval.combined_score
                current_bp = mutated
            else:
                stopping_reason = "score_plateau"
                break

        # Mark the winning round
        winning = max(r.combined_score for r in rounds)
        for r in rounds:
            r.selected = r.combined_score == winning

        return EvolutionResult(
            best_blueprint=best_bp,
            best_score=best_score,
            rounds=rounds,
            total_mutations=len(rounds) - 1,
            stopping_reason=stopping_reason,
        )

    def _evaluate(self, blueprint: AgentBlueprint, task_input: str) -> EvaluationResult:
        tool_results = []
        if self.run_tools and task_input.strip():
            self._runner.run(blueprint, task_input)
            tool_results = self._runner.last_tool_results
        return self._evaluator.evaluate(blueprint, tool_results=tool_results)
