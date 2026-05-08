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

    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    shell = StemShell()
    blueprint = shell.grow_initial_blueprint(args.task)

    save_blueprint(blueprint, args.output)

    print("Stem shell completed initial specialisation.")
    print(f"Domain: {blueprint.domain_profile.domain}")
    print(f"Subdomain: {blueprint.domain_profile.subdomain}")
    print(f"Blueprint name: {blueprint.name}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()