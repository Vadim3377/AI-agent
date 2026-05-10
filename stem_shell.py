"""
stem_shell.py — The stem agent coordinator.

Does not solve domain tasks directly. Instead:
  1. Receives a task-family description.
  2. Uses DomainProfiler to understand the task environment.
  3. Uses ArchitectureGenerator to create an initial AgentBlueprint.
  4. Optionally runs MutationLoop: multi-round evolve → evaluate → select.

The MutationLoop replaces the original single-mutation + single-compare
pattern. Evolution now runs for up to max_rounds and stops when the
combined score (structural + task-level tool results) stops improving.
"""

from models import AgentBlueprint, EvaluationResult
from domain_profiler import DomainProfiler
from architecture_generator import ArchitectureGenerator
from blueprint_mutator import BlueprintMutator
from blueprint_evaluator import BlueprintEvaluator
from mutation_loop import MutationLoop, EvolutionResult


class StemShell:
    """
    Minimal meta-agent coordinator.

    grow_initial_blueprint()  — generate (+ optionally single-mutate) a blueprint.
    grow_and_evaluate()       — generate + multi-round evolve + return best blueprint.
    """

    def __init__(self) -> None:
        self.profiler = DomainProfiler()
        self.architecture_generator = ArchitectureGenerator()
        self.mutator = BlueprintMutator()
        self.evaluator = BlueprintEvaluator()

    def grow_initial_blueprint(
        self,
        task_description: str,
        mutate: bool = False,
    ) -> AgentBlueprint:
        """Generate an initial blueprint, with an optional single mutation."""
        profile = self.profiler.profile(task_description)
        blueprint = self.architecture_generator.generate(profile)
        if mutate:
            blueprint = self.mutator.mutate(blueprint)
        return blueprint

    def grow_and_evaluate(
        self,
        task_description: str,
        task_input: str = "",
        max_rounds: int = 4,
        run_tools: bool = True,
    ) -> tuple[AgentBlueprint, EvolutionResult]:
        """
        Generate a blueprint then run the multi-round MutationLoop.

        Returns (best_blueprint, evolution_result).

        evolution_result.rounds contains per-round structural and task scores.
        evolution_result.summary_table() prints a human-readable comparison.

        Parameters
        ----------
        task_description : str
            The task-family prompt for classification and profiling.
        task_input : str
            Concrete code or text for the runner to execute tools on.
            If empty, task-level scoring falls back to structural score.
        max_rounds : int
            Maximum mutation rounds (default 4).
        run_tools : bool
            Whether to call real tools for task-level evaluation.
        """
        profile = self.profiler.profile(task_description)
        base_blueprint = self.architecture_generator.generate(profile)

        loop = MutationLoop(max_rounds=max_rounds, run_tools=run_tools)
        evolution = loop.run(base_blueprint, task_input=task_input)

        return evolution.best_blueprint, evolution
