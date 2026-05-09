import argparse
import os

from stem_shell import StemShell
from models import save_blueprint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stem Agent Shell: profile a task family and create an initial specialised-agent blueprint."
    )

    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="Description of the task family the stem agent should specialise for."
    )

    parser.add_argument(
        "--output",
        type=str,
        default="configs/initial_blueprint.json",
        help="Path where the generated blueprint JSON should be saved."
    )

    parser.add_argument(
        "--mutate",
        action="store_true",
        help="Apply a controlled mutation to the generated blueprint."
    )

    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate the base and mutated blueprints, then save the better one."
    )

    args = parser.parse_args()

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    shell = StemShell()

    if args.evaluate:
        blueprint, base_result, mutated_result, selected = shell.grow_and_evaluate(args.task)

        save_blueprint(blueprint, args.output)

        print("Stem shell completed evaluation-guided specialisation.")
        print(f"Base score: {base_result.score}")
        print(f"Base passed checks: {base_result.passed_checks}")
        print(f"Base failed checks: {base_result.failed_checks}")
        print(f"Mutated score: {mutated_result.score}")
        print(f"Mutated passed checks: {mutated_result.passed_checks}")
        print(f"Mutated failed checks: {mutated_result.failed_checks}")
        print(f"Selected blueprint: {selected}")
        print(f"Domain: {blueprint.domain_profile.domain}")
        print(f"Subdomain: {blueprint.domain_profile.subdomain}")
        print(f"Blueprint name: {blueprint.name}")
        print(f"Reasoning: {blueprint.domain_profile.reasoning}")
        print(f"Saved to: {args.output}")
        return

    blueprint = shell.grow_initial_blueprint(args.task, mutate=args.mutate)

    save_blueprint(blueprint, args.output)

    print("Stem shell completed initial specialisation.")
    print(f"Mutation enabled: {args.mutate}")
    print(f"Domain: {blueprint.domain_profile.domain}")
    print(f"Subdomain: {blueprint.domain_profile.subdomain}")
    print(f"Blueprint name: {blueprint.name}")
    print(f"Reasoning: {blueprint.domain_profile.reasoning}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()