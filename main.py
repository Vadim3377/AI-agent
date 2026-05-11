import argparse
import os

from dotenv import load_dotenv

from stem_shell import StemShell
from models import save_blueprint, load_blueprint
from agent_runner import AgentRunner, save_run_result
from llm_agent_runner import LLMAgentRunner

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Stem Agent Shell: classify a task, profile the domain, "
            "generate a specialist blueprint, mutate and evaluate it, "
            "then execute the selected specialist."
        )
    )
    parser.add_argument(
        "--task",
        type=str,
        required=False,
        help="Description of the task family the stem agent should specialise for.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="configs/initial_blueprint.json",
        help="Path where the generated blueprint JSON should be saved.",
    )
    parser.add_argument(
        "--mutate",
        action="store_true",
        help="Apply a controlled mutation to the generated blueprint.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate base and mutated blueprints, then save the better one.",
    )
    parser.add_argument(
        "--run-blueprint",
        type=str,
        help="Path to an existing blueprint JSON file to execute.",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Task input string for the agent runner.",
    )
    parser.add_argument(
        "--run-output",
        type=str,
        default="results/run_result.json",
        help="Path where the runner output JSON should be saved.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the OpenAI-backed LLM runner instead of the deterministic runner.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1-mini",
        help="OpenAI model to use for the LLM runner.",
    )

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Run an existing blueprint
    # ------------------------------------------------------------------
    if args.run_blueprint:
        if not args.input:
            raise ValueError("--input is required when using --run-blueprint")

        run_output_dir = os.path.dirname(args.run_output)
        if run_output_dir:
            os.makedirs(run_output_dir, exist_ok=True)

        blueprint = load_blueprint(args.run_blueprint)

        if args.use_llm:
            runner = LLMAgentRunner(model=args.model)
        else:
            runner = AgentRunner()

        result = runner.run(blueprint, args.input)
        save_run_result(result, args.run_output)

        print("Agent runner completed blueprint execution.")
        print(f"Runner      : {'llm' if args.use_llm else 'deterministic'}")
        print(f"Blueprint   : {blueprint.name}")
        print(f"Domain      : {blueprint.domain_profile.domain}")
        print(f"Subdomain   : {blueprint.domain_profile.subdomain}")
        if args.use_llm:
            print(f"Model       : {args.model}")
        else:
            print(f"Steps run   : {len(result.get('executed_steps', []))}")
        print(f"Saved to    : {args.run_output}")
        return

    # ------------------------------------------------------------------
    # Generate (and optionally evaluate) a blueprint from a task prompt
    # ------------------------------------------------------------------
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    shell = StemShell()

    if args.evaluate:
        comparison = shell.grow_and_evaluate(args.task)
        blueprint = comparison.selected_blueprint
        base_result = comparison.base_result
        mutated_result = comparison.mutated_result
        selected = comparison.selected

        save_blueprint(blueprint, args.output)

        print("Stem shell completed evaluation-guided specialisation.")
        print()
        _print_classification(blueprint)
        print()
        print(f"Base score          : {base_result.score}")
        print(f"Base passed checks  : {base_result.passed_checks}")
        print(f"Base failed checks  : {base_result.failed_checks}")
        print(f"Mutated score       : {mutated_result.score}")
        print(f"Mutated passed      : {mutated_result.passed_checks}")
        print(f"Mutated failed      : {mutated_result.failed_checks}")
        print(f"Selected blueprint  : {selected}")
        print(f"Blueprint name      : {blueprint.name}")
        print(f"Saved to            : {args.output}")
        return

    blueprint = shell.grow_initial_blueprint(args.task, mutate=args.mutate)
    save_blueprint(blueprint, args.output)

    print("Stem shell completed initial specialisation.")
    print()
    _print_classification(blueprint)
    print()
    print(f"Mutation enabled  : {args.mutate}")
    print(f"Blueprint name    : {blueprint.name}")
    print(f"Saved to          : {args.output}")


def _print_classification(blueprint) -> None:
    """Print classifier metadata from the blueprint's domain profile."""
    profile = blueprint.domain_profile
    method = profile.classification_method
    method_label = {
        "llm": "LLM (semantic)",
        "keyword": "keyword fallback",
        "fallback": "generic fallback",
    }.get(method, method)

    print(f"Domain            : {profile.domain}")
    print(f"Subdomain         : {profile.subdomain}")
    print(f"Classifier        : {method_label}")
    if profile.llm_reasoning:
        print(f"LLM reasoning     : {profile.llm_reasoning}")


if __name__ == "__main__":
    main()
