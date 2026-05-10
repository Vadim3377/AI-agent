"""
benchmark_demo.py — Full pipeline benchmark across all supported task categories.

For each task the benchmark:
  1. Profiles the prompt (DomainProfiler)
  2. Generates a base blueprint (ArchitectureGenerator)
  3. Runs the multi-round MutationLoop with real tool feedback
  4. Selects the best blueprint
  5. Executes the selected blueprint (AgentRunner, with real tools)
  6. Records structural score, task-level score, and tools called

This replaces the original single-mutation + structural-only comparison.
The per-task input snippets are real code so tools have something to run on.
"""

import json
import os
from typing import Any, Dict, List

from agent_runner import AgentRunner
from architecture_generator import ArchitectureGenerator
from blueprint_evaluator import BlueprintEvaluator
from blueprint_mutator import BlueprintMutator
from domain_profiler import DomainProfiler
from models import save_blueprint
from mutation_loop import MutationLoop


BENCHMARK_TASKS = [
    {
        "id": "debugging",
        "task": "Debug this Python function. It gives the wrong output and the test fails.",
        "input": "def add(a, b):\n    return a - b",
    },
    {
        "id": "code_quality_cleanup",
        "task": "Clean up this code, remove dead code, simplify redundant logic, and improve readability.",
        "input": (
            "def calculate(x):\n"
            "    unused = 123\n"
            "    result = x * 1\n"
            "    if True:\n"
            "        return result\n"
        ),
    },
    {
        "id": "comments_and_documentation",
        "task": "Add useful comments and docstrings to explain the code.",
        "input": (
            "def normalise(values):\n"
            "    m = max(values)\n"
            "    return [v / m for v in values]\n"
        ),
    },
    {
        "id": "security",
        "task": "Check this code for dangerous operations, API key leaks, passwords, and possible data breaches.",
        "input": (
            "API_KEY = 'sk-test-abcdefghij123456789012345678'\n"
            "password = 'admin123'\n"
            "eval(user_input)\n"
        ),
    },
    {
        "id": "code_research",
        "task": "Research relevant documentation and examples for implementing a plugin system in Python.",
        "input": "Need to design a plugin discovery mechanism for a Python CLI tool.",
    },
]


class BenchmarkDemo:
    """
    Runs the full stem-agent pipeline on all supported task categories.
    Uses MutationLoop (multi-round) instead of a single mutation.
    """

    def __init__(self) -> None:
        self.profiler = DomainProfiler()
        self.architecture_generator = ArchitectureGenerator()
        self.evaluator = BlueprintEvaluator()
        self.runner = AgentRunner()

    def run(self) -> List[Dict[str, Any]]:
        return [self._run_case(task) for task in BENCHMARK_TASKS]

    def _run_case(self, task_case: Dict[str, str]) -> Dict[str, Any]:
        profile = self.profiler.profile(task_case["task"])
        base_blueprint = self.architecture_generator.generate(profile)

        # Multi-round evolution with real tool feedback
        loop = MutationLoop(max_rounds=4, run_tools=bool(task_case["input"].strip()))
        evolution = loop.run(base_blueprint, task_input=task_case["input"])

        selected_blueprint = evolution.best_blueprint
        base_round = evolution.rounds[0]
        best_round = max(evolution.rounds, key=lambda r: r.combined_score)

        # Execute selected blueprint with real tools
        run_result = self.runner.run(selected_blueprint, task_case["input"])

        return {
            "task_id": task_case["id"],
            "task": task_case["task"],
            "domain": profile.domain,
            "subdomain": profile.subdomain,
            "base_blueprint": base_blueprint.name,
            "selected_blueprint": selected_blueprint.name,
            "base_structural_score": base_round.structural_score,
            "base_task_score": base_round.task_score,
            "base_combined_score": base_round.combined_score,
            "best_structural_score": best_round.structural_score,
            "best_task_score": best_round.task_score,
            "best_combined_score": best_round.combined_score,
            "total_rounds": evolution.total_mutations,
            "stopping_reason": evolution.stopping_reason,
            "tools_called": run_result.get("tools_called", []),
            "executed_steps": len(run_result["executed_steps"]),
            "final_status": run_result["final_status"],
            "evolution_table": evolution.summary_table(),
        }


def save_json(results: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def save_markdown(results: List[Dict[str, Any]], path: str) -> None:
    lines = [
        "# Stem Agent Benchmark Summary\n",
        "Two-layer evaluation: structural (40%) + task-level from real tool results (60%).\n",
        "| Task | Domain | Subdomain | Base Combined | Best Combined | Rounds | Tools Called |",
        "|------|--------|-----------|:-------------:|:-------------:|:------:|--------------|",
    ]
    for r in results:
        tools = ", ".join(r["tools_called"]) if r["tools_called"] else "—"
        lines.append(
            f"| {r['task_id']} | {r['domain']} | {r['subdomain']} "
            f"| {r['base_combined_score']:.2f} | {r['best_combined_score']:.2f} "
            f"| {r['total_rounds']} | {tools} |"
        )

    lines += [
        "\n## Per-Task Evolution Tables\n",
    ]
    for r in results:
        lines += [f"### {r['task_id']}\n", "```", r["evolution_table"], "```\n"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def save_selected_blueprints(results_dir: str) -> None:
    selected_dir = os.path.join(results_dir, "selected_blueprints")
    os.makedirs(selected_dir, exist_ok=True)

    profiler = DomainProfiler()
    arch_gen = ArchitectureGenerator()

    for task_case in BENCHMARK_TASKS:
        profile = profiler.profile(task_case["task"])
        base_bp = arch_gen.generate(profile)
        loop = MutationLoop(max_rounds=4, run_tools=bool(task_case["input"].strip()))
        evolution = loop.run(base_bp, task_input=task_case["input"])
        save_blueprint(
            evolution.best_blueprint,
            os.path.join(selected_dir, f"{task_case['id']}_selected_blueprint.json"),
        )


def main() -> None:
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    print("Running benchmark (multi-round evolution + real tools)...")
    benchmark = BenchmarkDemo()
    results = benchmark.run()

    save_json(results, os.path.join(results_dir, "benchmark_summary.json"))
    save_markdown(results, os.path.join(results_dir, "benchmark_summary.md"))
    save_selected_blueprints(results_dir)

    print(f"\nBenchmark complete — {len(results)} tasks\n")
    print(f"{'Task':<30} {'Base':>6} {'Best':>6} {'Rounds':>7} {'Tools'}")
    print("-" * 72)
    for r in results:
        tools = ", ".join(r["tools_called"]) if r["tools_called"] else "—"
        print(
            f"{r['task_id']:<30} {r['base_combined_score']:>6.2f} "
            f"{r['best_combined_score']:>6.2f} {r['total_rounds']:>7}   {tools}"
        )

    print("\nSaved:")
    print("  results/benchmark_summary.json")
    print("  results/benchmark_summary.md")
    print("  results/selected_blueprints/")


if __name__ == "__main__":
    main()
