# Stem Agent

A minimal stem-agent pipeline inspired by biological stem-cell differentiation. Instead of
hand-building a fixed agent for one task, the system starts from a broad task-family prompt,
grows a specialist blueprint through multi-round evolution with real tool feedback, and executes
the selected specialist.

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

Then run the full pipeline:

```bash
python main.py --task "Debug this Python function." --evaluate --input "def add(a, b): return a - b" --output configs/selected_debugging.json
```

---

## Requirements

- Python 3.10 or later
- An OpenAI API key for the LLM classifier, LLM-backed runner, and task benchmarks.
  The deterministic pipeline runs without one (keyword fallback classifier is used automatically).

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

Without an API key: the keyword fallback classifier is used, the deterministic runner works
fully, and `benchmark_demo.py` runs end-to-end. Only `--use-llm`, `quixbugs_benchmark.py`,
and `doc_benchmark.py` require an API key.

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

A stem agent starts from a general shell and gradually forms a specialised agent design based
on the task description. Specialisation is represented as an explicit `AgentBlueprint` -- role,
workflow, tools, output schema, stopping conditions -- rather than uncontrolled self-modifying code.

The central question: does a better blueprint actually produce a better agent? The answer is yes,
but the mechanism matters. Blueprint structure alone does not improve output quality. What matters
is whether the blueprint's architecture enables a real tool feedback loop. The mutated blueprint
does; the base blueprint does not.

---

## Pipeline

```
Task Prompt
   |
   v
DomainClassifier       -- LLM reads prompt semantically -> domain / subdomain / reasoning
   |                      (keyword fallback used automatically if no API key)
   v
DomainProfiler         -- expands to capabilities, tools, metrics
   |
   v
ArchitectureGenerator  -- produces initial AgentBlueprint (JSON)
   |
   v
MutationLoop           -- multi-round: mutate -> evaluate -> keep best -> repeat
   |
   v
Selected AgentBlueprint
   |
   v
AgentRunner            -- deterministic runner with real tool dispatch
   |    pytest_runner / static_checker / secret_detector / docstring_checker / ...
   v
ToolResults            -- feed back into BlueprintEvaluator (task-level score)
   |
   v
BlueprintEvaluator     -- structural (40%) + task-level (60%) combined score
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

Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```

Windows (cmd):
```cmd
.venv\Scripts\activate.bat
```

macOS / Linux:
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up API key (optional for deterministic path)

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
python main.py --task "Debug this Python function." --evaluate \
  --input "def add(a, b): return a - b" \
  --output configs/selected_debugging.json
```

Example output:

```
Domain:     quality_assurance / debugging
Classifier: LLM (semantic)
LLM reasoning: The task involves debugging a function with wrong output and a failing test.

Base score: 0.86
Mutated score: 1.00
Selected blueprint: mutated
Blueprint name: debugging_specialist_agent__mutated_debugging_verification
Saved to: configs/selected_debugging.json
```

### Execute a saved blueprint -- deterministic runner (no API key needed)

```bash
python main.py --run-blueprint configs/selected_debugging.json \
  --input "def add(a, b): return a - b" \
  --run-output results/debugging_run.json
```

Calls real tools (pytest, static analysis) and produces a structured JSON trace. Proves the
workflow is runnable without performing semantic reasoning.

### Execute a saved blueprint -- LLM runner (requires API key)

```bash
python main.py --run-blueprint configs/selected_debugging.json \
  --input "def add(a, b): return a - b" \
  --use-llm \
  --run-output results/debugging_llm_run.json
```

For debugging blueprints with active verification steps, automatically runs the tool feedback
loop: generate fix -> run pytest -> observe failure -> revise -> repeat (up to 3 rounds).

For documentation blueprints with `verify_docstring_coverage`, runs the docstring quality
feedback loop: document code -> measure Args:/Returns: coverage -> revise if below 90% ->
repeat (up to 2 rounds).

### Specify a different model

```bash
python main.py --run-blueprint configs/selected_debugging.json \
  --input "def add(a, b): return a - b" \
  --use-llm --model gpt-4o \
  --run-output results/run_gpt4o.json
```

### All CLI flags

```
--task TEXT            Task-family description (required unless --run-blueprint is set)
--output PATH          Where to save the generated blueprint JSON
--mutate               Apply a single mutation without full evaluation
--evaluate             Run multi-round evolution and select the best blueprint
--input TEXT           Concrete code or text for tool-based evaluation and runner execution
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

The frontend shows:
- Classification method (LLM or keyword) and the LLM's one-sentence reasoning
- Whether the LLM and keyword classifiers agreed on routing
- Evolution table with structural and task-level scores per round
- Base vs selected blueprint comparison
- Runner output with tool results and feedback loop metrics

---

## Benchmarks

### Pipeline structural benchmark (no API key needed)

```bash
python benchmark_demo.py
```

Runs the full pipeline across all five task categories. Reports classification method and
LLM reasoning per task, blueprint scores, and whether LLM and keyword routing agreed.

Generated files:
```
results/benchmark_summary.json
results/benchmark_summary.md
results/selected_blueprints/<task>_selected_blueprint.json
```

### Debugging task-level benchmark (requires API key)

```bash
python task_benchmark.py
```

Runs both base and mutated blueprints against 30 hand-curated Python functions across six
bug categories. Extracts the agent's suggested fix and runs pytest on it -- not the
ground-truth. Tests whether blueprint mutation produces a specialist that actually fixes bugs.

Sample output:
```
Metric                          Base   Selected   delta
-------------------------------------------------------
Fix extracted rate              100%      100%
First-attempt pass rate          73%       70%    -3%
Final pytest pass rate           73%       97%   +24%
Avg revision rounds             0.00      0.43  +0.43
Avg agent score                0.813     0.977  +0.164
```

Generated files:
```
results/task_benchmark.json
results/task_benchmark.md
```

### QuixBugs external validation (requires API key)

```bash
python quixbugs_benchmark.py
```

Validates the debugging agent on 10 real Python bugs from the QuixBugs dataset -- an
independent external benchmark not seen during development. Runs base and mutated blueprints
on each bug and reports pytest pass rates.

Sample output:
```
Base blueprint pass rate   : 0/10 (0%)
Mutated blueprint pass rate: 7/10 (70%)
```

Generated files:
```
results/quixbugs_benchmark.json
results/quixbugs_benchmark.md
```

### Documentation feedback loop benchmark (requires API key)

```bash
python doc_benchmark.py
```

Runs base (single-shot) and mutated (verify_docstring_coverage feedback loop) blueprints
against 10 multi-function Python modules. Uses quality-aware scoring: a docstring counts
as complete only if it has Args: and Returns: sections where required -- one-liner docstrings
score zero.

Sample output:
```
Base blueprint avg quality coverage   : 96%
Mutated blueprint avg quality coverage: 100%
Improved in                           : 2/10 tasks
```

Generated files:
```
results/doc_benchmark.json
results/doc_benchmark.md
```

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

### Verify the full pipeline (no API key needed)

```bash
python main.py --task "Debug this Python function." --evaluate \
  --input "def add(a, b): return a - b" \
  --output configs/test_run.json
```

Expected: classifier method and reasoning printed, evolution table shown, `configs/test_run.json` created.

### Verify the benchmark runs (no API key needed)

```bash
python benchmark_demo.py
```

Expected: 5-task classification comparison table printed, files created in `results/`.

### Verify the deterministic runner with real tools

```bash
python main.py --run-blueprint configs/test_run.json \
  --input "def add(a, b): return a - b" \
  --run-output results/test_result.json
```

Expected: `results/test_result.json` created with `tools_called` listing `static_checker`
and `pytest_runner`.

---

## Components

### `DomainClassifier`

When an API key is available, sends the raw task prompt to the LLM and asks it to propose
domain, subdomain, intent, confidence, and a one-sentence reasoning field as structured JSON.
The LLM reads the environment semantically rather than matching against keyword lists.

A keyword fallback is used automatically when no API key is set. The `classification_method`
field on the result records which path ran (`llm` | `keyword` | `fallback`).

Supported categories:
- QA: debugging
- QA: code-quality cleanup
- QA: comments and documentation
- Security: dangerous operations and data breaches
- Deep research: code-related research

### `DomainProfiler`

Expands the classification into a full domain profile: artifact type, required capabilities,
candidate tools, evaluation metrics, and reasoning. Preserves `classification_method` and
`llm_reasoning` from the classifier into the `DomainProfile` so callers don't need to
re-classify to find out how routing happened.

### `ArchitectureGenerator`

Converts a domain profile into an initial specialist blueprint with a domain-appropriate
workflow, tool list, output schema, and stopping conditions.

### `MutationLoop`

Multi-round evolution loop. Runs up to `max_rounds` (default 4), stopping when combined
score improvement falls below 3%. Uses real tool results for task-level scoring when
`task_input` is provided.

### `BlueprintEvaluator`

Two-layer scoring:

```
Layer        Weight   What it measures
------       ------   ----------------
Structural    40%     Workflow length, tools, schema, stopping conditions,
                      safeguard steps, subdomain alignment
Task-level    60%     Real tool output: pytest pass rate, static issues,
                      docstring coverage, secret findings
```

Combined score = 0.4 * structural + 0.6 * task_level.

### `tools.py` -- Real Executable Tools

```
Tool                Triggered by step keyword       What it does
----                -------------------------       ------------
pytest_runner       run_tests, verify_fix           Name-inferred assertions, subprocess pytest
static_checker      identify_failure, localise_bug  AST: suspicious operators, missing returns
complexity_checker  complexity, dead_code           Cyclomatic complexity via AST
secret_detector     secret, pii, dangerous          Regex scan for API keys, tokens, passwords
docstring_checker   docstring, documentation        AST docstring coverage (presence-based)
```

### `AgentRunner`

Deterministic runner. For each workflow step, checks for a matching tool, calls it if not
yet called this run, records the result. Falls back to a descriptive placeholder if no tool
matches. Tool results enrich the output schema where applicable.

### `LLMAgentRunner`

Semantic execution using OpenAI. Implements tool feedback loops for two domains.

Debugging loop (up to 3 rounds):
```
1. LLM produces initial fix
2. pytest_runner evaluates it
3. If failed: failure output sent back as a new conversation turn
4. LLM revises using the test evidence
5. Repeat until pytest passes or rounds exhausted
```

Documentation loop (up to 2 rounds):
```
1. LLM adds Google-style docstrings
2. Quality-aware AST checker measures coverage
   (complete = has Args: + Returns: sections where required)
3. If quality coverage below 90%: incomplete symbol names sent back
4. LLM adds missing sections
5. Repeat until coverage >= 90% or rounds exhausted
```

The base blueprint's passive steps (`run_tests_if_available`) do not trigger the loops.
The mutated blueprint's active steps (`verify_fix_against_generated_tests`,
`verify_docstring_coverage`) do. This is the mechanism behind the benchmark improvements.

### `StemShell`

Coordinator. `grow_initial_blueprint` and `grow_and_evaluate` are the two main entry points.
`grow_and_evaluate` returns an `EvaluationComparison` dataclass with named fields
(`selected_blueprint`, `base_result`, `mutated_result`, `selected`) rather than a bare tuple.

---

## Benchmark Results Summary

```
Benchmark                               Before    After
-------                                 ------    -----
Blueprint structural score               0.86     1.00
Deterministic vs LLM runner              0.60     0.95
30-task final pytest pass rate           73%      97%
30-task avg agent score                 0.813    0.977
QuixBugs external pass rate (mutated)    --       50-70%
Doc quality coverage (mutated)           --       100%
```

---

## Repository Structure

```
.
|-- main.py                    CLI entry point
|-- app.py                     Streamlit frontend
|-- benchmark_demo.py          Pipeline benchmark (all 5 task categories, classifier comparison)
|-- task_benchmark.py          Debugging task-level benchmark (30 self-curated bug cases)
|-- quixbugs_benchmark.py      External validation on 10 real QuixBugs Python bugs
|-- doc_benchmark.py           Documentation feedback loop benchmark (quality-aware coverage)
|-- models.py                  AgentBlueprint, DomainProfile, EvaluationResult, EvaluationComparison
|-- domain_classifier.py       LLM-powered semantic classifier with keyword fallback
|-- domain_profiler.py         Domain profile expander (preserves classification metadata)
|-- architecture_generator.py  Blueprint generator
|-- blueprint_mutator.py       Controlled blueprint mutator
|-- mutation_loop.py           Multi-round evolution loop
|-- blueprint_evaluator.py     Two-layer evaluator (structural + task-level)
|-- agent_runner.py            Deterministic runner with real tool dispatch
|-- tools.py                   Real executable tools (pytest, AST, regex)
|-- llm_agent_runner.py        LLM-backed runner with feedback loops (debugging + documentation)
|-- stem_shell.py              Coordinator: grow_initial_blueprint, grow_and_evaluate
|-- requirements.txt
|-- .env                       Not committed -- add OPENAI_API_KEY here
|-- configs/                   Saved blueprint JSONs (git-ignored)
`-- results/                   Benchmark outputs and run results (git-ignored)
```

---

## Design Choices

**LLM classifier with deterministic fallback.** The classifier sends the raw task prompt
to the LLM and reads the environment semantically. The keyword fallback ensures the pipeline
is fully runnable without an API key. Both paths produce a `ClassificationResult` with a
`classification_method` field so callers can see which path ran.

**Deterministic pipeline, LLM only at execution.** Classification uses the LLM but the
result is then passed into a deterministic profiler, generator, mutator, and evaluator.
The LLM is used for semantic reasoning only inside `LLMAgentRunner`. This keeps the
differentiation process reproducible and inspectable.

**Active vs passive workflow steps.** Whether a blueprint triggers a tool feedback loop
depends on its workflow steps. Passive steps (`run_tests_if_available`) describe intent.
Active steps (`verify_fix_against_generated_tests`, `verify_docstring_coverage`) trigger
real tool calls and multi-turn revision. Only mutation adds active steps.

**Tools integrated into the runner, not a separate pipeline.** Tools are called inside
`AgentRunner` during step execution, triggered by step name keywords. Their results flow
directly into the evaluator's task-level score.

**Mutation can lose.** The `MutationLoop` stops when improvement falls below 3%. The base
blueprint is kept when it already scores well on real tool output.

**Failures are reported, not hidden.** The task benchmark reports cases where the agent fix
still fails pytest. Type/scope bugs reach 80% final pass rate -- not 100%. Three QuixBugs
tasks hit MAX_REVISION_ROUNDS without passing. These are documented rather than excluded.
