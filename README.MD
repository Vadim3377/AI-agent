# Stem Agent

A minimal stem-agent pipeline inspired by biological stem-cell differentiation. Instead of hand-building a fixed agent for one task, the system starts from a broad task-family prompt, grows a specialist blueprint through multi-round evolution with real tool feedback, and executes the selected specialist.

---

## Quick Start

```bash
git clone https://github.com/Vadim3377/AI-agent.git
cd AI-agent
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Then run the pipeline:

```bash
python main.py --task "Debug this Python function." --evaluate --input "def add(a, b): return a - b" --output configs/selected_debugging.json
```

---

## Requirements

- Python 3.10 or later
- An OpenAI API key for the LLM-backed runner and task benchmark (the deterministic pipeline runs without one)

`requirements.txt`:

```
openai
python-dotenv
streamlit
pytest
```

---

## Environment Variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_api_key_here
```

The deterministic pipeline, benchmark demo, and Streamlit frontend all work without an API key. Only `--use-llm` and `task_benchmark.py` (LLM mode) require one.

Your `.gitignore` should include:

```
.env
__pycache__/
*.py[cod]
configs/*.json
results/*.json
results/selected_blueprints/
results/frontend_last_run.json
.idea/
.vscode/
.venv/
venv/
env/
```

---

## Project Idea

A stem agent starts from a general shell and gradually forms a specialised agent design based on the task description. Specialisation is represented as an explicit `AgentBlueprint` — role, workflow, tools, output schema, stopping conditions — rather than uncontrolled self-modifying code.

The central question: **does a better blueprint actually produce a better agent?** The answer is yes, but the mechanism matters. Blueprint structure alone does not improve fix quality. What matters is whether the blueprint's architecture enables a real tool feedback loop. The mutated blueprint does; the base blueprint does not.

---

## Pipeline

```
Task Prompt
   ↓
DomainClassifier       — keyword signal routing → domain / subdomain
   ↓
DomainProfiler         — expands to capabilities, tools, metrics
   ↓
ArchitectureGenerator  — produces initial AgentBlueprint (JSON)
   ↓
MutationLoop           — multi-round: mutate → evaluate → keep best → repeat
   ↓
Selected AgentBlueprint
   ↓
AgentRunner            — deterministic runner with real tool dispatch
   ↓    pytest_runner / static_checker / secret_detector / ...
ToolResults            — feed back into BlueprintEvaluator (task-level score)
   ↓
BlueprintEvaluator     — structural (40%) + task-level (60%) combined score
```

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/Vadim3377/AI-agent.git
cd AI-agent
python -m venv .venv
```

### 2. Activate

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (cmd):**
```cmd
.venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up API key (optional)

```
OPENAI_API_KEY=your_api_key_here   # in .env file in project root
```

---

## Running

### Generate a blueprint only

```bash
python main.py --task "Debug this Python function." --output configs/debugging_blueprint.json
```

### Generate and evolve (structural scoring)

```bash
python main.py --task "Debug this Python function." --evaluate --output configs/selected_debugging.json
```

### Generate and evolve with real tool feedback

Providing `--input` enables tool-based task-level scoring during evolution:

```bash
python main.py --task "Debug this Python function." --evaluate --input "def add(a, b): return a - b" --output configs/selected_debugging.json
```

Example output:

```
Stem shell completed multi-round evolution.
Domain:    quality_assurance / debugging
Blueprint: debugging_specialist_agent__mutated_debugging_verification
Best score: 1.00
Rounds run: 2
Stopping reason: score_plateau

Rnd  Blueprint                                             Struct   Task   Comb  Best
-------------------------------------------------------------------------------------
0    debugging_specialist_agent                              0.86   1.00   0.94
1    debugging_specialist_agent__mutated_debugging_ver...    1.00   1.00   1.00  OK
2    debugging_specialist_agent__mutated_debugging_ver...    1.00   1.00   1.00  OK
-------------------------------------------------------------------------------------
Stopping reason: score_plateau
Saved to: configs/selected_debugging.json
```

### Execute a saved blueprint — deterministic runner (no API key needed)

```bash
python main.py --run-blueprint configs/selected_debugging.json --input "def add(a, b): return a - b" --run-output results/debugging_run.json
```

Calls real tools (pytest, static analysis) and produces a structured JSON trace. Proves the workflow is runnable. Does not perform semantic reasoning.

### Execute a saved blueprint — LLM runner (requires API key)

```bash
python main.py --run-blueprint configs/selected_debugging.json --input "def add(a, b): return a - b" --use-llm --run-output results/debugging_llm_run.json
```

For debugging blueprints with active verification steps, automatically runs the tool feedback loop: generate fix → run pytest → observe failure → revise → repeat (up to 3 rounds).

### Specify a different model

```bash
python main.py --run-blueprint configs/selected_debugging.json --input "def add(a, b): return a - b" --use-llm --model gpt-4o --run-output results/run_gpt4o.json
```

### Control evolution rounds

```bash
python main.py --task "Debug this Python function." --evaluate --input "def add(a, b): return a - b" --max-rounds 6 --output configs/selected_debugging.json
```

### All CLI flags

```
--task TEXT            Task-family description (required unless --run-blueprint is set)
--output PATH          Where to save the generated blueprint JSON
--mutate               Apply a single mutation without full evaluation
--evaluate             Run multi-round evolution and select the best blueprint
--input TEXT           Concrete code or text for tool-based evaluation and runner execution
--max-rounds INT       Maximum mutation rounds when --evaluate is set (default: 4)
--run-blueprint PATH   Execute an existing saved blueprint
--run-output PATH      Where to save the runner output JSON
--use-llm              Use the LLM-backed runner instead of the deterministic runner
--model TEXT           OpenAI model for the LLM runner (default: gpt-4.1-mini)
```

---

## Frontend Demo

```bash
streamlit run app.py
```

Opens an interactive web UI at `http://localhost:8501`. Lets you choose a task category or enter a custom prompt, provide code as task input, run the full multi-round evolution pipeline, inspect the evolution table, and execute the selected blueprint with either the deterministic or LLM runner. Shows revision rounds taken and first-attempt vs final pytest result.

---

## Benchmarks

### Pipeline benchmark (all task categories)

```bash
python benchmark_demo.py
```

Runs the full `MutationLoop` pipeline across all five task categories with real code inputs. For each task: grows base blueprint, runs multi-round evolution with real tool feedback, selects best blueprint, executes with deterministic runner.

Sample output:

```
Task                           Base   Best  Rounds Tools
------------------------------------------------------------------------
debugging                      0.94   1.00       2   static_checker, pytest_runner
code_quality_cleanup           0.76   0.76       1   complexity_checker
comments_and_documentation     0.34   0.40       2   docstring_checker, complexity_checker
security                       0.88   0.88       1   secret_detector
code_research                  0.86   1.00       2   --
```

Generated files:
```
results/benchmark_summary.json
results/benchmark_summary.md
results/selected_blueprints/<task>_selected_blueprint.json
```

### Task-level agent benchmark (requires API key)

```bash
python task_benchmark.py
```

Feeds buggy code to the agent, extracts the suggested fix from the LLM output, and runs pytest on the agent's own fix — not the ground-truth. Tests whether the mutation loop produces a specialist that actually fixes bugs better.

Sample output:

```
Metric                               Base  Selected   delta
-------------------------------------------------------------
Fix extracted rate                   100%      100%
First-attempt pass rate               73%       70%   -3%
Final pytest pass rate                73%       97%  +24%
Avg revision rounds taken            0.00      0.43  +0.43
Avg agent score                     0.813     0.977  +0.164
```

Generated files:
```
results/task_benchmark.json
results/task_benchmark.md
```

**Static-only mode (no API key):**

```bash
python task_benchmark.py --no-llm
```

Runs static analysis only — no LLM fix generation. Useful for verifying the harness without API calls.

**Debug a single case:**

```bash
python task_benchmark.py --debug-case op_001
```

Prints the full raw LLM output, extracted fix, and pytest result for one case.

---

## Testing

### Verify tools work

```bash
python -c "
from tools import pytest_runner, static_checker, secret_detector, docstring_checker

r = pytest_runner('def add(a, b): return a - b')
print('pytest_runner buggy add: passed =', r.success)

r = static_checker('def add(a, b): return a - b')
print('static_checker issues:', [i['type'] for i in r.output['issues']])

r = secret_detector('api_key = \"sk-abcdefghij1234567890abcdefghijkl\"')
print('secret_detector findings:', r.output['finding_count'])

r = docstring_checker('def foo(x): return x\ndef bar(x):\n    \"\"\"documented\"\"\"\n    return x')
print('docstring_checker coverage:', r.output['coverage'])
"
```

Expected output:
```
pytest_runner buggy add: passed = False
static_checker issues: ['suspicious_operator']
secret_detector findings: 1
docstring_checker coverage: 0.5
```

### Verify the full pipeline

```bash
python main.py --task "Debug this Python function." --evaluate --input "def add(a, b): return a - b" --output configs/test_run.json
```

Expected: evolution table printed, `configs/test_run.json` created.

### Verify the benchmark runs (no API key needed)

```bash
python benchmark_demo.py
```

Expected: table of 5 tasks printed, files created in `results/`.

### Verify the task benchmark in static mode (no API key needed)

```bash
python task_benchmark.py --no-llm
```

Expected: signal scores printed, `results/task_benchmark.json` created.

### Verify the deterministic runner with real tools

```bash
python main.py --run-blueprint configs/test_run.json --input "def add(a, b): return a - b" --run-output results/test_result.json
```

Expected: `results/test_result.json` created with `tools_called` listing `static_checker` and `pytest_runner`.

### Verify the LLM runner on a single debug case (requires API key)

```bash
python task_benchmark.py --debug-case op_001
```

Expected: raw LLM output shown, extracted fix is `def add(a, b):\n    return a + b`, pytest result is `success = True`.

---

## Components

### `DomainClassifier`

Normalises the task prompt and assigns it to a domain and subdomain via keyword signals.

Supported categories:
- **QA: debugging** — bugs, errors, failing tests, wrong output
- **QA: code-quality cleanup** — dead code, redundancy, readability, refactoring
- **QA: comments and documentation** — docstrings, inline comments, explanations
- **Security: dangerous operations and data breaches** — API keys, eval, PII, secrets
- **Deep research: code-related research** — documentation, examples, implementation approaches

### `DomainProfiler`

Expands the classification into a full domain profile: artefact type, required capabilities, candidate tools, evaluation metrics, and reasoning.

### `ArchitectureGenerator`

Converts a domain profile into an initial specialist blueprint with a domain-appropriate workflow, tool list, output schema, and stopping conditions.

### `MutationLoop`

Multi-round evolution loop. Runs up to `max_rounds` (default 4), stopping when combined score improvement falls below 3%. Uses real tool results for task-level scoring when `task_input` is provided.

### `BlueprintEvaluator`

Two-layer scoring:

| Layer | Weight | What it measures |
|-------|--------|-----------------|
| Structural | 40% | Workflow length, tools, schema, stopping conditions, safeguard steps, subdomain alignment |
| Task-level | 60% | Real tool output: pytest pass rate, static issues, docstring coverage, secret findings |

Combined score = `0.4 × structural + 0.6 × task_level`.

### `tools.py` — Real Executable Tools

| Tool | Triggered by step keyword | What it does |
|------|--------------------------|-------------|
| `pytest_runner` | `run_tests`, `verify_fix` | Name-inferred assertions, subprocess pytest |
| `static_checker` | `identify_failure`, `localise_bug` | AST: suspicious operators, missing returns, unreachable code |
| `complexity_checker` | `complexity`, `dead_code` | Cyclomatic complexity via AST |
| `secret_detector` | `secret`, `pii`, `dangerous` | Regex scan for API keys, tokens, passwords |
| `docstring_checker` | `docstring`, `documentation` | AST docstring coverage |

### `AgentRunner`

Deterministic runner. For each workflow step, checks for a matching tool, calls it if not yet called this run, records the result. Falls back to a descriptive placeholder if no tool matches. Tool results enrich the output schema where applicable.

### `LLMAgentRunner`

Semantic execution using OpenAI. For debugging blueprints with active verification steps (`verify_fix_against_generated_tests`), runs a tool feedback loop:

1. LLM produces initial fix
2. `pytest_runner` evaluates it
3. If failed: failure output sent back as a new conversation turn
4. LLM revises using the test evidence
5. Repeat up to 3 rounds

The base blueprint's `run_tests_if_available` is **passive** and does not trigger the loop. The mutated blueprint's `verify_fix_against_generated_tests` is **active** and does. This is the mechanism behind the +24% benchmark improvement.

---

## Benchmark Results Summary

| Benchmark | Before | After |
|-----------|:------:|:-----:|
| Blueprint structural score | 0.86 | 1.00 |
| Deterministic vs LLM runner | 0.60 | 0.95 |
| 30-task final pytest pass rate | 73% | 97% |
| 30-task avg agent score | 0.813 | 0.977 |

---

## Repository Structure

```
.
├── main.py                    # CLI entry point
├── app.py                     # Streamlit frontend
├── benchmark_demo.py          # Pipeline benchmark (all 5 task categories)
├── task_benchmark.py          # Task-level agent benchmark (30 bug cases)
├── models.py                  # AgentBlueprint, DomainProfile, EvaluationResult
├── domain_classifier.py       # Keyword-based task classifier
├── domain_profiler.py         # Domain profile expander
├── architecture_generator.py  # Blueprint generator
├── blueprint_mutator.py       # Single-step blueprint mutator
├── mutation_loop.py           # Multi-round evolution loop
├── blueprint_evaluator.py     # Two-layer evaluator (structural + task-level)
├── agent_runner.py            # Deterministic runner with real tool dispatch
├── tools.py                   # Real executable tools
├── llm_agent_runner.py        # LLM-backed runner with tool feedback loop
├── stem_shell.py              # Coordinator: grow_initial_blueprint, grow_and_evaluate
├── requirements.txt
├── .env                       # Not committed — add OPENAI_API_KEY here
├── configs/                   # Saved blueprint JSONs (git-ignored)
└── results/                   # Benchmark outputs and run results (git-ignored)
```

---

## Design Choices

**Deterministic pipeline, LLM only at execution.** Classification, profiling, architecture generation, mutation, and evaluation are all deterministic and inspectable. The LLM is used only inside `LLMAgentRunner`. This keeps the differentiation process reproducible and debuggable.

**Tools integrated into the runner, not a separate pipeline.** Tools are called inside `AgentRunner` during step execution, triggered by step name keywords. Their results flow directly into the evaluator's task-level score.

**Mutation can lose.** The `MutationLoop` stops when improvement falls below 3%. The base blueprint is kept when it already scores well on real tool output.

**Failures are reported, not hidden.** The task benchmark reports cases where the agent fix still fails pytest. Type/scope bugs reach 80% final pass rate — not 100%. This is documented rather than excluded.
