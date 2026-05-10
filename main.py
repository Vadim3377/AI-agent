"""
main.py — CLI entry point for the stem agent.

Usage
-----
# Generate a blueprint only
python main.py --task "Debug this function." --output configs/bp.json

# Generate + multi-round evolve + select best blueprint
python main.py --task "Debug this function." --evaluate --output configs/bp.json

# Generate + evolve with real tool feedback on a code snippet
python main.py --task "Debug this function." --evaluate \
    --input "def add(a,b): return a-b" --output configs/bp.json

# Execute a saved blueprint deterministically (with real tools)
python main.py --run-blueprint configs/bp.json --input "def add(a,b): return a-b" \
    --run-output results/run.json

# Execute with LLM runner
python main.py --run-blueprint configs/bp.json --input "def add(a,b): return a-b" \
    --use-llm --run-output results/run_llm.json
"""

import argparse
import os

from stem_shell import StemShell
from models import save_blueprint
from agent_runner import AgentRunner, load_blueprint, save_run_result
from llm_agent_runner import LLMAgentRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stem Agent Shell: grow a specialised agent blueprint from a task-family description."
    )
    parser.add_argument("--task", type=str, help="Task-family description.")
    parser.add_argument("--output", type=str, default="configs/initial_blueprint.json",
                        help="Path to save the generated blueprint JSON.")
    parser.add_argument("--mutate", action="store_true",
                        help="Apply a single mutation to the generated blueprint.")
    parser.add_argument("--evaluate", action="store_true",
                        help="Run multi-round evolution and select the best blueprint.")
    parser.add_argument("--input", type=str, default="",
                        help="Concrete task input for the runner or tool-based evaluation.")
    parser.add_argument("--max-rounds", type=int, default=4,
                        help="Maximum mutation rounds when --evaluate is set (default 4).")
    parser.add_argument("--run-blueprint", type=str,
                        help="Path to an existing blueprint JSON to execute.")
    parser.add_argument("--run-output", type=str, default="results/run_result.json",
                        help="Path to save the runner output JSON.")
    parser.add_argument("--use-llm", action="store_true",
                        help="Use the LLM-backed runner instead of the deterministic runner.")
    parser.add_argument("--model", type=str, default="gpt-4.1-mini",
                        help="OpenAI model for the LLM runner.")
    args = parser.parse_args()

    # ------------------------------------------------------------------ #
    # Mode A: execute an existing blueprint                               #
    # ------------------------------------------------------------------ #
    if args.run_blueprint:
        if not args.input:
            raise ValueError("--input is required when using --run-blueprint")

        run_output_dir = os.path.dirname(args.run_output)
        if run_output_dir:
            os.makedirs(run_output_dir, exist_ok=True)

        blueprint = load_blueprint(args.run_blueprint)
        runner = LLMAgentRunner(model=args.model) if args.use_llm else AgentRunner()
        result = runner.run(blueprint, args.input)
        save_run_result(result, args.run_output)

        print("Agent runner completed.")
        print(f"Runner:    {'llm' if args.use_llm else 'deterministic'}")
        print(f"Blueprint: {blueprint.name}")
        print(f"Domain:    {blueprint.domain_profile.domain} / {blueprint.domain_profile.subdomain}")
        if not args.use_llm:
            tools_called = result.get("tools_called", [])
            print(f"Tools called: {tools_called if tools_called else 'none'}")
            print(f"Steps executed: {len(result['executed_steps'])}")
        print(f"Saved to:  {args.run_output}")
        return

    # ------------------------------------------------------------------ #
    # Mode B: grow (+ optionally evolve) a blueprint                     #
    # ------------------------------------------------------------------ #
    if not args.task:
        parser.error("--task is required unless --run-blueprint is set")

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    shell = StemShell()

    if args.evaluate:
        blueprint, evolution = shell.grow_and_evaluate(
            args.task,
            task_input=args.input,
            max_rounds=args.max_rounds,
            run_tools=bool(args.input),
        )
        save_blueprint(blueprint, args.output)

        print("Stem shell completed multi-round evolution.")
        print(f"Domain:    {blueprint.domain_profile.domain} / {blueprint.domain_profile.subdomain}")
        print(f"Blueprint: {blueprint.name}")
        print(f"Best score: {evolution.best_score:.2f}")
        print(f"Rounds run: {evolution.total_mutations}")
        print(f"Stopping reason: {evolution.stopping_reason}")
        print()
        print(evolution.summary_table())
        print(f"\nSaved to: {args.output}")
        return

    # Simple generate (+ optional single mutation)
    blueprint = shell.grow_initial_blueprint(args.task, mutate=args.mutate)
    save_blueprint(blueprint, args.output)

    print("Stem shell completed initial specialisation.")
    print(f"Mutation: {args.mutate}")
    print(f"Domain:   {blueprint.domain_profile.domain} / {blueprint.domain_profile.subdomain}")
    print(f"Blueprint: {blueprint.name}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
