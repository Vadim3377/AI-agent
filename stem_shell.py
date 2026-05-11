from models import AgentBlueprint, EvaluationResult, EvaluationComparison
from domain_profiler import DomainProfiler
from architecture_generator import ArchitectureGenerator
from blueprint_mutator import BlueprintMutator
from blueprint_evaluator import BlueprintEvaluator


class StemShell:
    """
    The minimal stem agent coordinator.

    It does not solve domain tasks directly. Instead it:
    1. Receives a task-family description.
    2. Uses DomainProfiler (which calls DomainClassifier) to read the task environment.
    3. Uses ArchitectureGenerator to create an initial specialised-agent blueprint.
    4. Optionally mutates the blueprint.
    5. Optionally evaluates base vs mutated and selects the stronger one.
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
        profile = self.profiler.profile(task_description)
        blueprint = self.architecture_generator.generate(profile)
        if mutate:
            blueprint = self.mutator.mutate(blueprint)
        return blueprint

    def grow_and_evaluate(self, task_description: str) -> EvaluationComparison:
        """
        Run the full differentiation loop and return a named comparison result.

        Returns an EvaluationComparison rather than a bare tuple so callers
        can access fields by name without positional unpacking errors.
        """
        profile = self.profiler.profile(task_description)
        base_blueprint = self.architecture_generator.generate(profile)
        mutated_blueprint = self.mutator.mutate(base_blueprint)

        base_result = self.evaluator.evaluate(base_blueprint)
        mutated_result = self.evaluator.evaluate(mutated_blueprint)

        if mutated_result.score > base_result.score:
            return EvaluationComparison(
                selected_blueprint=mutated_blueprint,
                base_result=base_result,
                mutated_result=mutated_result,
                selected="mutated",
            )
        return EvaluationComparison(
            selected_blueprint=base_blueprint,
            base_result=base_result,
            mutated_result=mutated_result,
            selected="base",
        )
