"""
Run the deterministic stem-agent pipeline on the supported task categories.

The benchmark reports base and mutated blueprint scores, the classifier used
for each task, and whether semantic routing agrees with the keyword fallback.
It is intended as a quick sanity check for the full pipeline, not as the main
task-level evaluation.
"""

import json
import os
from typing import Any, Dict, List

from agent_runner import AgentRunner
from architecture_generator import ArchitectureGenerator
from blueprint_evaluator import BlueprintEvaluator
from blueprint_mutator import BlueprintMutator
from domain_classifier import DomainClassifier, _classify_with_keywords
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
    Runs the full stem-agent pipeline on the benchmark task set.
    """

    def __init__(self) -> None:
        self.classifier = DomainClassifier()
        self.profiler = DomainProfiler()
        self.architecture_generator = ArchitectureGenerator()
        self.mutator = BlueprintMutator()
        self.evaluator = BlueprintEvaluator()
        self.runner = AgentRunner()

    def run(self) -> List[Dict[str, Any]]:
        results = []
        for task_case in BENCHMARK_TASKS:
            result = self._run_case(task_case)
            results.append(result)
            _print_case(result)
        return results

    def _run_case(self, task_case: Dict[str, str]) -> Dict[str, Any]:
        task_text = task_case["task"]

        # Compare semantic routing with the deterministic fallback.
        llm_classification = self.classifier.classify(task_text)

        # Run the fallback explicitly so the routing decision is inspectable.
        keyword_classification = _classify_with_keywords(
            " ".join(task_text.lower().split())
        )

        classifiers_agree = (
            llm_classification.domain == keyword_classification.domain
            and llm_classification.subdomain == keyword_classification.subdomain
        )

        # Generate, mutate, evaluate, and execute the selected blueprint.
        profile = self.profiler.profile(task_text)
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
            "task": task_text,
            # Compare semantic routing with the deterministic fallback.
            "classification_method": llm_classification.classification_method,
            "llm_domain": llm_classification.domain,
            "llm_subdomain": llm_classification.subdomain,
            "llm_confidence": llm_classification.confidence,
            "llm_reasoning": llm_classification.llm_reasoning or "",
            "keyword_domain": keyword_classification.domain,
            "keyword_subdomain": keyword_classification.subdomain,
            "classifiers_agree": classifiers_agree,
            # Blueprint evaluation
            "domain": profile.domain,
            "subdomain": profile.subdomain,
            "base_blueprint": base_blueprint.name,
            "mutated_blueprint": mutated_blueprint.name,
            "base_score": base_eval.score,
            "mutated_score": mutated_eval.score,
            "selected": selected,
            "selected_blueprint": selected_blueprint.name,
            "selected_score": selected_eval.score,
            # Runner trace
            "executed_steps": len(run_result.get("executed_steps", [])),
            "final_status": run_result["final_status"],
            "base_failed_checks": base_eval.failed_checks,
            "mutated_failed_checks": mutated_eval.failed_checks,
        }


# Reporting helpers

def _print_case(result: Dict[str, Any]) -> None:
    agree_str = " agree" if result["classifiers_agree"] else " DISAGREE"
    method = result["classification_method"]
    reasoning = result["llm_reasoning"]
    print(
        f"\n[{result['task_id']}]"
        f"\n  Classification method : {method}"
        f"\n  LLM    -> {result['llm_domain']} / {result['llm_subdomain']}"
        f"  (confidence {result['llm_confidence']:.2f})"
        f"\n  Keyword-> {result['keyword_domain']} / {result['keyword_subdomain']}"
        f"\n  Agreement             : {agree_str}"
    )
    if reasoning:
        print(f"  LLM reasoning         : {reasoning}")
    print(
        f"  Blueprint scores      : base={result['base_score']:.2f}"
        f"  mutated={result['mutated_score']:.2f}"
        f"  selected={result['selected']}"
    )


def save_json(results: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def save_markdown(results: List[Dict[str, Any]], path: str) -> None:
    n_tasks = len(results)
    n_llm = sum(1 for r in results if r["classification_method"] == "llm")
    n_disagree = sum(1 for r in results if not r["classifiers_agree"])

    lines = [
        "# Stem Agent Benchmark Summary",
        "",
        "## Compare semantic routing with the deterministic fallback. method comparison",
        "",
        f"Across {n_tasks} benchmark tasks, the LLM classifier was used in "
        f"**{n_llm}** cases. "
        f"In **{n_disagree}** case(s) the LLM and keyword classifiers disagreed "
        f"on domain or subdomain.",
        "",
        "| Task | Method | LLM route | Keyword route | Agree | LLM reasoning |",
        "|---|---|---|---|---|---|",
    ]

    for r in results:
        agree_mark = "yes" if r["classifiers_agree"] else "no"
        llm_route = f"{r['llm_domain']} / {r['llm_subdomain']}"
        kw_route = f"{r['keyword_domain']} / {r['keyword_subdomain']}"
        reasoning = r["llm_reasoning"].replace("|", "/") if r["llm_reasoning"] else "-"
        lines.append(
            f"| {r['task_id']} | {r['classification_method']} "
            f"| {llm_route} | {kw_route} | {agree_mark} | {reasoning} |"
        )

    lines += [
        "",
        "## Blueprint evolution",
        "",
        "| Task | Domain | Subdomain | Base Score | Mutated Score | Selected |"
        " Executed Steps | Status |",
        "|---|---|---|---:|---:|---|---:|---|",
    ]

    for r in results:
        lines.append(
            f"| {r['task_id']} "
            f"| {r['domain']} "
            f"| {r['subdomain']} "
            f"| {r['base_score']:.2f} "
            f"| {r['mutated_score']:.2f} "
            f"| {r['selected']} "
            f"| {r['executed_steps']} "
            f"| {r['final_status']} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- The benchmark is deterministic (no LLM execution of blueprints).",
        "- Blueprint scores measure structural quality: workflow specificity, "
          "tool relevance, schema completeness, and verification steps.",
        "- Classification method reflects whether OPENAI_API_KEY was available.",
        "- Disagreement between LLM and keyword classifiers indicates cases where "
          "semantic reading changes the routing decision.",
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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
            mutated_blueprint if mutated_eval.score > base_eval.score else base_blueprint
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

    # Summary stats
    n_llm = sum(1 for r in results if r["classification_method"] == "llm")
    n_disagree = sum(1 for r in results if not r["classifiers_agree"])

    print("\n" + "=" * 60)
    print("Benchmark complete.")
    print(f"  Tasks run             : {len(results)}")
    print(f"  LLM classifier used   : {n_llm}/{len(results)}")
    print(f"  Classifier disagreed  : {n_disagree}/{len(results)}")
    print("  Saved JSON:   results/benchmark_summary.json")
    print("  Saved MD:     results/benchmark_summary.md")
    print("  Blueprints:   results/selected_blueprints/")


if __name__ == "__main__":
    main()
