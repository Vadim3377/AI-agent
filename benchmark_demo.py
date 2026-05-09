import json
import os
from typing import Any, Dict, List

from agent_runner import AgentRunner
from architecture_generator import ArchitectureGenerator
from blueprint_evaluator import BlueprintEvaluator
from blueprint_mutator import BlueprintMutator
from domain_profiler import DomainProfiler
from models import save_blueprint


BENCHMARK_TASKS = [
    {
        "id": "debugging",
        "task": "Debug this Python function. It gives the wrong output and the test fails.",
        "input": "def add(a, b):\n    return a - b",
    },
    {
        "id": "code_quality_cleanup",
        "task": "Clean up this code, remove dead code, simplify redundant logic, and improve readability.",
        "input": "def calculate(x):\n    unused = 123\n    result = x * 1\n    if True:\n        return result",
    },
    {
        "id": "comments_and_documentation",
        "task": "Add useful comments and docstrings to explain the code.",
        "input": "def normalise(values):\n    m = max(values)\n    return [v / m for v in values]",
    },
    {
        "id": "security",
        "task": "Check this code for dangerous operations, API key leaks, passwords, and possible data breaches.",
        "input": "API_KEY = 'sk-test-123'\npassword = 'admin'\neval(user_input)",
    },
    {
        "id": "code_research",
        "task": "Research relevant documentation and examples for implementing a plugin system in Python.",
        "input": "Need to design a plugin discovery mechanism for a Python CLI tool.",
    },
]


class BenchmarkDemo:
    """
    Runs the full stem-agent pipeline on a small deterministic benchmark.

    For each task:
    1. profile the prompt
    2. generate a base blueprint
    3. mutate the blueprint
    4. evaluate base vs mutated
    5. select the stronger blueprint
    6. execute the selected blueprint using AgentRunner
    """

    def __init__(self) -> None:
        self.profiler = DomainProfiler()
        self.architecture_generator = ArchitectureGenerator()
        self.mutator = BlueprintMutator()
        self.evaluator = BlueprintEvaluator()
        self.runner = AgentRunner()

    def run(self) -> List[Dict[str, Any]]:
        results = []

        for task_case in BENCHMARK_TASKS:
            results.append(self._run_case(task_case))

        return results

    def _run_case(self, task_case: Dict[str, str]) -> Dict[str, Any]:
        profile = self.profiler.profile(task_case["task"])

        base_blueprint = self.architecture_generator.generate(profile)
        mutated_blueprint = self.mutator.mutate(base_blueprint)

        base_eval = self.evaluator.evaluate(base_blueprint)
        mutated_eval = self.evaluator.evaluate(mutated_blueprint)

        if mutated_eval.score > base_eval.score:
            selected = "mutated"
            selected_blueprint = mutated_blueprint
            selected_eval = mutated_eval
        else:
            selected = "base"
            selected_blueprint = base_blueprint
            selected_eval = base_eval

        run_result = self.runner.run(selected_blueprint, task_case["input"])

        return {
            "task_id": task_case["id"],
            "task": task_case["task"],
            "domain": profile.domain,
            "subdomain": profile.subdomain,
            "base_blueprint": base_blueprint.name,
            "mutated_blueprint": mutated_blueprint.name,
            "base_score": base_eval.score,
            "mutated_score": mutated_eval.score,
            "selected": selected,
            "selected_blueprint": selected_blueprint.name,
            "selected_score": selected_eval.score,
            "executed_steps": len(run_result["executed_steps"]),
            "final_status": run_result["final_status"],
            "base_failed_checks": base_eval.failed_checks,
            "mutated_failed_checks": mutated_eval.failed_checks,
        }


def save_json(results: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)


def save_markdown(results: List[Dict[str, Any]], path: str) -> None:
    lines = [
        "# Stem Agent Benchmark Summary",
        "",
        "This benchmark compares the base generated blueprint with the mutated blueprint. "
        "The evaluator scores structural blueprint quality, selects the stronger blueprint, "
        "and then executes the selected blueprint with the deterministic agent runner.",
        "",
        "| Task | Domain | Subdomain | Base Score | Mutated Score | Selected | Executed Steps | Status |",
        "|---|---|---|---:|---:|---|---:|---|",
    ]

    for result in results:
        lines.append(
            f"| {result['task_id']} "
            f"| {result['domain']} "
            f"| {result['subdomain']} "
            f"| {result['base_score']:.2f} "
            f"| {result['mutated_score']:.2f} "
            f"| {result['selected']} "
            f"| {result['executed_steps']} "
            f"| {result['final_status']} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The benchmark is deterministic.",
            "- It evaluates the stem-agent pipeline rather than a foundation model.",
            "- The current scores measure blueprint structure, safeguard coverage, workflow relevance, and schema completeness.",
            "- A future version should evaluate semantic task-solving performance using labelled debugging, security, documentation, and research tasks.",
            "",
        ]
    )

    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def save_selected_blueprints(results_dir: str) -> None:
    selected_dir = os.path.join(results_dir, "selected_blueprints")
    os.makedirs(selected_dir, exist_ok=True)

    profiler = DomainProfiler()
    architecture_generator = ArchitectureGenerator()
    mutator = BlueprintMutator()
    evaluator = BlueprintEvaluator()

    for task_case in BENCHMARK_TASKS:
        profile = profiler.profile(task_case["task"])
        base_blueprint = architecture_generator.generate(profile)
        mutated_blueprint = mutator.mutate(base_blueprint)

        base_eval = evaluator.evaluate(base_blueprint)
        mutated_eval = evaluator.evaluate(mutated_blueprint)

        selected_blueprint = (
            mutated_blueprint
            if mutated_eval.score > base_eval.score
            else base_blueprint
        )

        save_blueprint(
            selected_blueprint,
            os.path.join(selected_dir, f"{task_case['id']}_selected_blueprint.json"),
        )


def main() -> None:
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    benchmark = BenchmarkDemo()
    results = benchmark.run()

    save_json(results, os.path.join(results_dir, "benchmark_summary.json"))
    save_markdown(results, os.path.join(results_dir, "benchmark_summary.md"))
    save_selected_blueprints(results_dir)

    print("Benchmark demo completed.")
    print(f"Cases run: {len(results)}")
    print("Saved JSON summary to: results/benchmark_summary.json")
    print("Saved Markdown summary to: results/benchmark_summary.md")
    print("Saved selected blueprints to: results/selected_blueprints/")
    print()

    print("Summary:")
    for result in results:
        print(
            f"- {result['task_id']}: "
            f"base={result['base_score']:.2f}, "
            f"mutated={result['mutated_score']:.2f}, "
            f"selected={result['selected']}, "
            f"steps={result['executed_steps']}"
        )


if __name__ == "__main__":
    main()