from models import AgentBlueprint
from domain_profiler import DomainProfiler
from architecture_generator import ArchitectureGenerator
from blueprint_mutator import BlueprintMutator


class StemShell:
    """
    The minimal stem agent coordinator.

    It does not solve domain tasks directly.
    Instead, it:
    1. Receives a task-family description.
    2. Uses the DomainProfiler to understand the task environment.
    3. Uses the ArchitectureGenerator to create an initial specialised-agent blueprint.
    4. Optionally mutates the blueprint to create a safer or more specialised variant.
    """

    def __init__(self) -> None:
        self.profiler = DomainProfiler()
        self.architecture_generator = ArchitectureGenerator()
        self.mutator = BlueprintMutator()

    def grow_initial_blueprint(
        self,
        task_description: str,
        mutate: bool = False
    ) -> AgentBlueprint:
        profile = self.profiler.profile(task_description)
        blueprint = self.architecture_generator.generate(profile)

        if mutate:
            blueprint = self.mutator.mutate(blueprint)

        return blueprint