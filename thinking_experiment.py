"""
Thinking x feedback-loop experiment (2 x 2), on 22 debugging tasks.

Cells: Gemini thinking {default, off ("minimal")} x blueprint {single-shot,
test loop}. Tasks: the 12 visible-test tasks (hard_benchmark.py) plus the 10
QuixBugs tasks with their visible tests. Every cell sees the same failing tests;
only the loop can run them. Fixes are graded on hidden held-out checks.

Per cell: held-out pass rate, p50 latency per task, cost per task.

Pre-registered claim (fixed before any results were seen)
---------------------------------------------------------
Headline: "A test-execution loop without model thinking matches thinking-mode
single-shot accuracy at a fraction of the cost and latency."

It holds only if ALL of the following are true for (loop, thinking off)
versus (single-shot, thinking on):
  1. Accuracy: held-out passes are no more than 1 task lower (out of 22).
  2. Cost per task is at most 50% of single-shot with thinking.
  3. p50 latency per task is at most 50% of single-shot with thinking.
Supporting check, reported but not required: the loop "recovers" accuracy
only if (loop, off) passes more tasks than (single-shot, off).
If any of 1-3 fails, the headline is not claimed and the README says so.
"""

import argparse
import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

import held_out
import llm_backend

load_dotenv()

THINKING_SETTINGS = {"on": None, "off": "minimal"}  # None = model default thinking
MAX_ACCURACY_GAP = 1
MAX_COST_RATIO = 0.5
MAX_LATENCY_RATIO = 0.5


def load_tasks() -> List[Dict[str, Any]]:
    """Both task sets in one format, each validated before any LLM call."""
    import hard_benchmark
    import quixbugs_benchmark as quix

    tasks = []
    hard_expected = hard_benchmark.validate_tasks()
    for t in hard_benchmark.HARD_TASKS:
        tasks.append({
            "id": t["id"], "set": "visible_test", "buggy": t["buggy"],
            "tests": hard_benchmark.visible_tests(t), "checks": t["held_out"],
            "expected": hard_expected[t["id"]],
        })
    quix_expected = quix.validate_tasks()
    for t in quix.QUIXBUGS_TASKS:
        tasks.append({
            "id": t["id"], "set": "quixbugs", "buggy": t["buggy"],
            "tests": quix.visible_tests(t), "checks": quix._case_exprs(t),
            "expected": quix_expected[t["id"]],
        })
    return tasks


def run_cell(tasks: List[Dict[str, Any]], blueprint, thinking: str) -> Dict[str, Any]:
    from llm_agent_runner import LLMAgentRunner

    level = THINKING_SETTINGS[thinking]
    if level:
        os.environ["GEMINI_THINKING_LEVEL"] = level
    else:
        os.environ.pop("GEMINI_THINKING_LEVEL", None)

    runner = LLMAgentRunner()
    rows = []
    for task in tasks:
        result = runner.run(blueprint, task["buggy"], tests=task["tests"])
        fix = result.get("final_fix") or runner._extract_fix(
            result.get("parsed_output"), result.get("raw_output", "")
        ) or ""
        passed = held_out.grade(fix, task["checks"], task["expected"])
        rows.append({
            "id": task["id"], "set": task["set"],
            "checks_passed": passed, "checks": len(task["checks"]),
            "passed": passed == len(task["checks"]),
            "rounds_taken": result.get("rounds_taken", 0),
            "latency_s": result["usage"]["latency_s"],
            "fix": fix,
        })
        print(f"    {task['id']:28} {passed}/{len(task['checks'])}"
              f"  rounds={rows[-1]['rounds_taken']}  {rows[-1]['latency_s']:.1f}s", flush=True)
    usage = llm_backend.summarise_runs(runner.run_log)
    return {
        "thinking": thinking, "rows": rows, "usage": usage,
        "passed": sum(r["passed"] for r in rows), "tasks": len(rows),
    }


def evaluate_claim(cells: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    ref = cells["single_on"]
    loop_off = cells["loop_off"]
    cost_ref = ref["usage"]["cost_per_task_usd"]
    cost_loop = loop_off["usage"]["cost_per_task_usd"]
    checks = {
        "accuracy_within_1_task": loop_off["passed"] >= ref["passed"] - MAX_ACCURACY_GAP,
        "cost_at_most_50pct": (cost_loop is not None and cost_ref is not None
                               and cost_loop <= MAX_COST_RATIO * cost_ref),
        "p50_latency_at_most_50pct": (loop_off["usage"]["p50_latency_s"]
                                      <= MAX_LATENCY_RATIO * ref["usage"]["p50_latency_s"]),
    }
    return {
        "checks": checks,
        "headline_holds": all(checks.values()),
        "loop_recovers_accuracy": loop_off["passed"] > cells["single_off"]["passed"],
        "cost_ratio": round(cost_loop / cost_ref, 3) if cost_loop and cost_ref else None,
        "latency_ratio": round(loop_off["usage"]["p50_latency_s"] / ref["usage"]["p50_latency_s"], 3),
    }


def save_markdown(cells: Dict[str, Dict[str, Any]], claim: Dict[str, Any], path: str) -> None:
    names = {
        "single_on": "Single-shot, thinking on",
        "loop_on": "Test loop, thinking on",
        "single_off": "Single-shot, thinking off",
        "loop_off": "Test loop, thinking off",
    }
    lines = [
        "# Thinking x Feedback-Loop Experiment",
        "",
        "Gemini 3.5 Flash on 22 debugging tasks (12 visible-test + 10 QuixBugs). Every cell",
        "sees the same failing tests; only the loop runs them. Graded on hidden held-out checks.",
        "Thinking off = `thinking_level=\"minimal\"`.",
        "",
        "| Cell | Held-out pass rate | p50 latency/task | Cost/task |",
        "|---|---|---|---|",
    ]
    for key, label in names.items():
        c = cells[key]
        cost = c["usage"]["cost_per_task_usd"]
        lines.append(
            f"| {label} | {c['passed']}/{c['tasks']} ({c['passed']/c['tasks']:.0%}) "
            f"| {c['usage']['p50_latency_s']} s | {'$%.4f' % cost if cost is not None else 'n/a'} |"
        )
    verdict = "HOLDS" if claim["headline_holds"] else "DOES NOT HOLD"
    lines += [
        "",
        "## Pre-registered claim",
        "",
        "\"A test-execution loop without model thinking matches thinking-mode single-shot",
        "accuracy at a fraction of the cost and latency.\" Criteria (loop/off vs single/on):",
        "within 1 task on accuracy, at most 50% of the cost, at most 50% of the p50 latency.",
        "",
        f"- Accuracy within 1 task: **{claim['checks']['accuracy_within_1_task']}**",
        f"- Cost at most 50%: **{claim['checks']['cost_at_most_50pct']}** (ratio {claim['cost_ratio']})",
        f"- p50 latency at most 50%: **{claim['checks']['p50_latency_at_most_50pct']}** "
        f"(ratio {claim['latency_ratio']})",
        f"- Loop recovers accuracy lost by turning thinking off: **{claim['loop_recovers_accuracy']}**",
        "",
        f"**Verdict: the headline {verdict}.**",
        "",
        "## Per task (held-out checks passed)",
        "",
        "| Task | Set | " + " | ".join(names[k] for k in names) + " |",
        "|---|---|" + "---|" * len(names),
    ]
    for i, row in enumerate(cells["single_on"]["rows"]):
        cols = " | ".join(
            f"{cells[k]['rows'][i]['checks_passed']}/{cells[k]['rows'][i]['checks']}" for k in names
        )
        lines.append(f"| {row['id']} | {row['set']} | {cols} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Thinking x feedback-loop experiment (Gemini)")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    os.environ["LLM_PROVIDER"] = "gemini"
    print("Validating 22 tasks...")
    tasks = load_tasks()
    print(f"  {len(tasks)} tasks OK")
    if args.validate_only:
        return
    if os.getenv("LLM_PRICE_IN_PER_M") is None or os.getenv("LLM_PRICE_OUT_PER_M") is None:
        raise SystemExit("Set LLM_PRICE_IN_PER_M and LLM_PRICE_OUT_PER_M so cost can be compared.")

    from architecture_generator import ArchitectureGenerator
    from blueprint_mutator import BlueprintMutator
    from domain_profiler import DomainProfiler

    profile = DomainProfiler().profile(
        "Debug this Python function. It gives the wrong output and the test fails."
    )
    base = ArchitectureGenerator().generate(profile)
    blueprints = {"single": base, "loop": BlueprintMutator().mutate(base)}

    cells = {}
    for thinking in ("on", "off"):
        for kind, blueprint in blueprints.items():
            key = f"{kind}_{thinking}"
            print(f"\n[{key}]")
            cells[key] = run_cell(tasks, blueprint, thinking)
            c = cells[key]
            print(f"  -> {c['passed']}/{c['tasks']}  p50 {c['usage']['p50_latency_s']}s"
                  f"  ${c['usage']['cost_per_task_usd']}/task")

    claim = evaluate_claim(cells)
    os.makedirs("results", exist_ok=True)
    with open("results/thinking_experiment.json", "w", encoding="utf-8") as f:
        json.dump({"cells": cells, "claim": claim}, f, indent=2)
    save_markdown(cells, claim, "results/thinking_experiment.md")
    print(f"\nHeadline holds: {claim['headline_holds']}  {claim['checks']}")
    print("Saved -> results/thinking_experiment.json, results/thinking_experiment.md")


if __name__ == "__main__":
    main()
