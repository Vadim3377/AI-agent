import json
import os
from typing import Any, Dict, List

from agent_runner import AgentRunner, load_blueprint
from llm_agent_runner import LLMAgentRunner


DEBUGGING_TESTS = [
    {
        "id": "add_uses_subtraction",
        "input": "def add(a, b):\n    return a - b",
        "expected_signals": ["a - b", "a + b", "subtraction", "addition"],
    },
    {
        "id": "subtract_uses_addition",
        "input": "def subtract(a, b):\n    return a + b",
        "expected_signals": ["a + b", "a - b", "addition", "subtraction"],
    },
    {
        "id": "is_even_wrong_condition",
        "input": "def is_even(n):\n    return n % 2 == 1",
        "expected_signals": ["% 2", "== 1", "== 0", "even"],
    },
    {
        "id": "is_odd_wrong_condition",
        "input": "def is_odd(n):\n    return n % 2 == 0",
        "expected_signals": ["% 2", "== 0", "== 1", "odd"],
    },
    {
        "id": "max_value_returns_min",
        "input": "def max_value(values):\n    return min(values)",
        "expected_signals": ["min", "max", "maximum", "max_value"],
    },
    {
        "id": "min_value_returns_max",
        "input": "def min_value(values):\n    return max(values)",
        "expected_signals": ["max", "min", "minimum", "min_value"],
    },
    {
        "id": "absolute_value_wrong_sign",
        "input": "def absolute_value(x):\n    if x < 0:\n        return x\n    return x",
        "expected_signals": ["x < 0", "-x", "negative", "absolute"],
    },
    {
        "id": "factorial_wrong_base_case",
        "input": "def factorial(n):\n    if n == 0:\n        return 0\n    return n * factorial(n - 1)",
        "expected_signals": ["n == 0", "return 1", "base case", "factorial"],
    },
    {
        "id": "divide_swapped_operands",
        "input": "def divide(a, b):\n    return b / a",
        "expected_signals": ["b / a", "a / b", "swapped", "divide"],
    },
    {
        "id": "contains_uses_not_in",
        "input": "def contains(items, target):\n    return target not in items",
        "expected_signals": ["not in", "in", "contains", "target"],
    },
    {
        "id": "first_item_returns_last",
        "input": "def first_item(items):\n    return items[-1]",
        "expected_signals": ["items[-1]", "items[0]", "first", "last"],
    },
    {
        "id": "last_item_returns_first",
        "input": "def last_item(items):\n    return items[0]",
        "expected_signals": ["items[0]", "items[-1]", "last", "first"],
    },
    {
        "id": "average_uses_length_minus_one",
        "input": "def average(values):\n    return sum(values) / (len(values) - 1)",
        "expected_signals": ["len(values) - 1", "len(values)", "average", "division"],
    },
    {
        "id": "reverse_returns_same_list",
        "input": "def reverse(items):\n    return items",
        "expected_signals": ["items", "reversed", "reverse", "[::-1]"],
    },
    {
        "id": "square_returns_cube",
        "input": "def square(x):\n    return x * x * x",
        "expected_signals": ["x * x * x", "x * x", "square", "cube"],
    },
]


def normalise_output(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.lower()

    return json.dumps(value, ensure_ascii=False).lower()


def score_output(output: Dict[str, Any], expected_signals: List[str]) -> Dict[str, Any]:
    output_text = normalise_output(output)

    matched = [
        signal
        for signal in expected_signals
        if signal.lower() in output_text
    ]

    missing = [
        signal
        for signal in expected_signals
        if signal.lower() not in output_text
    ]

    score = len(matched) / len(expected_signals)

    return {
        "score": round(score, 2),
        "matched_signals": matched,
        "missing_signals": missing,
    }


def run_single_test(
    test_case: Dict[str, Any],
    deterministic_runner: AgentRunner,
    llm_runner: LLMAgentRunner,
    blueprint: Any,
) -> Dict[str, Any]:
    deterministic_output = deterministic_runner.run(
        blueprint=blueprint,
        task_input=test_case["input"],
    )

    llm_output = llm_runner.run(
        blueprint=blueprint,
        task_input=test_case["input"],
    )

    deterministic_score = score_output(
        deterministic_output,
        test_case["expected_signals"],
    )

    llm_score = score_output(
        llm_output,
        test_case["expected_signals"],
    )

    return {
        "test_id": test_case["id"],
        "input": test_case["input"],
        "expected_signals": test_case["expected_signals"],
        "deterministic_score": deterministic_score["score"],
        "deterministic_matched_signals": deterministic_score["matched_signals"],
        "deterministic_missing_signals": deterministic_score["missing_signals"],
        "llm_score": llm_score["score"],
        "llm_matched_signals": llm_score["matched_signals"],
        "llm_missing_signals": llm_score["missing_signals"],
        "llm_raw_output": llm_output.get("raw_output"),
        "llm_parsed_output": llm_output.get("parsed_output"),
    }


def save_json(data: Dict[str, Any], path: str) -> None:
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def save_markdown(summary: Dict[str, Any], path: str) -> None:
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    lines = [
        "# Runner Comparison Benchmark",
        "",
        "This benchmark compares the deterministic runner with the LLM-backed runner on debugging tasks.",
        "",
        f"- Blueprint: `{summary['blueprint']}`",
        f"- Model: `{summary['model']}`",
        f"- Number of tests: {summary['num_tests']}",
        f"- Deterministic average score: {summary['deterministic_average_score']:.2f}",
        f"- LLM average score: {summary['llm_average_score']:.2f}",
        "",
        "| Test | Deterministic Score | LLM Score |",
        "|---|---:|---:|",
    ]

    for result in summary["results"]:
        lines.append(
            f"| {result['test_id']} "
            f"| {result['deterministic_score']:.2f} "
            f"| {result['llm_score']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The deterministic runner is expected to score low because it only executes the generated workflow structurally.",
            "The LLM-backed runner is expected to score higher because it performs semantic reasoning over the input code.",
            "",
            "This benchmark is still lightweight: it checks for expected diagnostic signals rather than using a full human-graded evaluation.",
        ]
    )

    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def run_comparison_benchmark(
    blueprint_path: str = "configs/selected_debugging.json",
    model: str = "gpt-4.1-mini",
) -> None:
    blueprint = load_blueprint(blueprint_path)

    deterministic_runner = AgentRunner()
    llm_runner = LLMAgentRunner(model=model)

    results = []

    for test_case in DEBUGGING_TESTS:
        print(f"Running test: {test_case['id']}")
        result = run_single_test(
            test_case=test_case,
            deterministic_runner=deterministic_runner,
            llm_runner=llm_runner,
            blueprint=blueprint,
        )
        results.append(result)

    deterministic_average = sum(
        result["deterministic_score"] for result in results
    ) / len(results)

    llm_average = sum(
        result["llm_score"] for result in results
    ) / len(results)

    summary = {
        "blueprint": blueprint.name,
        "model": model,
        "num_tests": len(results),
        "deterministic_average_score": round(deterministic_average, 2),
        "llm_average_score": round(llm_average, 2),
        "results": results,
    }

    save_json(summary, "results/runner_comparison.json")
    save_markdown(summary, "results/runner_comparison.md")

    print()
    print("Runner comparison benchmark completed.")
    print(f"Blueprint: {blueprint.name}")
    print(f"Model: {model}")
    print(f"Tests run: {len(results)}")
    print(f"Deterministic average score: {deterministic_average:.2f}")
    print(f"LLM average score: {llm_average:.2f}")
    print("Saved JSON summary to: results/runner_comparison.json")
    print("Saved Markdown summary to: results/runner_comparison.md")


if __name__ == "__main__":
    run_comparison_benchmark()