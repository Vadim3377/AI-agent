# Stem Agent

This project implements a minimal **stem-agent pipeline** inspired by biological stem-cell differentiation. Instead of hand-building a fixed agent for one task, the system starts from a broad task-family prompt, identifies what kind of specialist is needed, grows a specialist blueprint through multi-round evolution, and executes the selected specialist using real tools.

---

## Project Idea

A traditional automation script follows a predefined workflow — same input, same path, developer-designed decision points throughout.

A stem agent is different. It starts from a general shell and gradually forms a specialised agent design based on the task description. Specialisation is represented as an explicit `AgentBlueprint` rather than uncontrolled self-modifying code, keeping the process inspectable and safe.

The blueprint contains:

- agent role
- domain profile
- workflow steps
- tools
- output schema
- stopping conditions

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
   ↓                        pytest_runner / static_checker / secret_detector / …
ToolResults            — feed back into BlueprintEvaluator (task-level score)
   ↓
BlueprintEvaluator     — structural (40%) + task-level (60%) combined score
```

---

## Components

### `DomainClassifier`

Receives the task prompt, normalises it, detects task-specific signals, and assigns a domain and subdomain.

Supported categories:

- **QA: debugging**
- **QA: code-quality cleanup**
- **QA: comments and documentation**
- **Security: dangerous operations and data breaches**
- **Deep research: code-related research**

Example:

```
"Debug this Python function. It gives the wrong output and the test fails."
→ domain: quality_assurance / subdomain: debugging
```

---

### `DomainProfiler`

Expands the classifier result into a full domain profile: artefact type, required capabilities, candidate tools, evaluation metrics, and reasoning.

---

### `ArchitectureGenerator`

Converts the domain profile into an initial specialist blueprint. For example, a debugging profile becomes a `debugging_specialist_agent` with a workflow like:

```
read_source_code
infer_expected_behaviour
identify_failure_symptoms
generate_minimal_reproduction_or_tests
run_tests_if_available
localise_likely_bug
suggest_fix
verify_fix_against_generated_tests
check_for_regression_risk
produce_debugging_report
```

---

### `MutationLoop`

Replaces the original single-mutation + single-compare pattern with an iterative evolution loop.

```
round 0: evaluate base blueprint (structural + real tool results)
round 1: mutate → evaluate → if improvement ≥ 3%: keep, continue
round 2: mutate further → evaluate → if improvement < 3%: stop
…up to max_rounds (default 4)
```

The stopping criterion is driven by real tool evidence, not structural self-assessment. If no task input is provided, scoring falls back to structural-only mode.

---

### `BlueprintEvaluator`

Two-layer evaluation.

**Layer 1 — Structural (40% weight)**  
Checks blueprint shape: workflow length, tools, schema completeness, stopping conditions, domain-specific schema fields, safeguard steps, subdomain alignment. 7 checks maximum.

**Layer 2 — Task-level (60% weight)**  
Uses real tool results from `AgentRunner` to score whether the blueprint did useful work:

| Subdomain | Evidence used |
|-----------|--------------|
| debugging | pytest pass/fail + static issue detection |
| code quality | complexity analysis + static issue count |
| documentation | docstring coverage percentage |
| security | secret scan finding count |

Combined score = `0.4 × structural + 0.6 × task_level`.

This breaks the circular dependency: a blueprint can score poorly on task-level even with perfect structural quality, because tool results are independent of the blueprint's declared properties.

---

### `tools.py` — Real Executable Tools

Five tools registered in `TOOL_REGISTRY`, all sandboxed and deterministic:

| Tool | What it does |
|------|-------------|
| `pytest_runner` | Writes code to a temp file, generates smoke tests, runs pytest in a subprocess |
| `static_checker` | AST analysis: missing returns, suspicious operators, unreachable code |
| `complexity_checker` | Cyclomatic complexity per function via AST branch counting |
| `secret_detector` | Regex scan for API keys, tokens, passwords in literals |
| `docstring_checker` | AST docstring coverage: fraction of functions/classes with docstrings |

The `AgentRunner` routes workflow step names to tools via a keyword table. For example, `run_tests_if_available` → `pytest_runner`; `identify_failure_symptoms` → `static_checker`. Each tool is called at most once per run. Results are stored in `runner.last_tool_results` and passed to the evaluator.

---

### `AgentRunner`

Deterministic runner with integrated real tool dispatch.

For each workflow step:
1. Check whether a registered tool matches the step name.
2. If matched (and not yet called this run), call the tool on the task input and record the result.
3. If no tool matches, produce a descriptive placeholder.

Tool results enrich the final output schema where applicable (e.g. `risk_level`, `docstring_coverage`, `tests_passed` are populated from real tool output rather than placeholders).

---

### `LLMAgentRunner`

Optional LLM-backed execution using an OpenAI model. Uses the selected specialist blueprint as context — role, domain profile, workflow, tools, output schema, and concrete task input — to perform semantic reasoning.

The LLM is used only at the final execution stage. The upstream pipeline (classify, profile, generate, mutate, evaluate) remains fully deterministic and inspectable.

---

## Setup

Python 3.10+ recommended.

```bash
pip install -r requirements.txt
```

`requirements.txt`:

```
openai
python-dotenv
streamlit
pytest
```

---

## Environment Variables

The deterministic pipeline does **not** require an API key.

The LLM-backed runner requires an OpenAI API key. Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_api_key_here
```

Do **not** commit `.env`. Your `.gitignore` should include:

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

## Usage

### 1. Generate a blueprint

```bash
python main.py --task "Debug this Python function." --output configs/debugging_blueprint.json
```

### 2. Multi-round evolve and select (structural scoring only)

```bash
python main.py --task "Debug this Python function." --evaluate \
    --output configs/selected_debugging.json
```

### 3. Multi-round evolve with real tool feedback on a code snippet

```bash
python main.py --task "Debug this Python function." --evaluate \
    --input "def add(a, b): return a - b" \
    --output configs/selected_debugging.json
```

Example output:

```
Stem shell completed multi-round evolution.
Domain:    quality_assurance / debugging
Blueprint: debugging_specialist_agent__mutated_debugging_verification
Best score: 0.94
Rounds run: 2
Stopping reason: score_plateau

Rnd  Blueprint                                              Struct   Task   Comb  Best
---------------------------------------------------------------------
0    debugging_specialist_agent                              0.86   0.72   0.78
1    debugging_specialist_agent__mutated_debugging_...       1.00   0.94   0.96   ✓
2    debugging_specialist_agent__mutated_debugging_...       1.00   0.94   0.96
---------------------------------------------------------------------
Stopping reason: score_plateau
```

### 4. Execute a saved blueprint deterministically (with real tools)

```bash
python main.py --run-blueprint configs/selected_debugging.json \
    --input "def add(a, b): return a - b" \
    --run-output results/debugging_run.json
```

### 5. Execute with the LLM runner

```bash
python main.py --run-blueprint configs/selected_debugging.json \
    --input "def add(a, b): return a - b" \
    --use-llm --run-output results/debugging_llm_run.json
```

---

## Benchmarks

### Pipeline benchmark

```bash
python benchmark_demo.py
```

Runs the full MutationLoop pipeline across all five task categories with real task inputs. Reports base combined score, best combined score, rounds run, and which tools were called.

Generated files:

```
results/benchmark_summary.json
results/benchmark_summary.md
results/selected_blueprints/
```

### Task-level debugging benchmark

```bash
python task_benchmark.py
```

30 hand-curated Python functions with intentional bugs across 6 categories (wrong operator, off-by-one, missing return, wrong comparison, logic error, type/scope error). Scoring is objective:

- `pytest` run on both buggy and fixed code (ground truth = fixed code passes)
- `static_checker` run on buggy code; expected signals checked against actual AST output
- Task score per case = `0.5 × (fixed pytest pass) + 0.3 × (pytest improved) + 0.2 × (signal hit rate)`

Generated files:

```
results/task_benchmark.json
results/task_benchmark.md
```

---

## Evaluation Design

### Why two layers?

The original evaluator measured blueprint shape against properties it defined itself — a circular dependency. Mutation always scored higher because the evaluator rewarded the same features it prompted the mutator to add.

The two-layer design breaks this:

- **Structural layer** (40%): checks blueprint shape, unchanged from v1.
- **Task layer** (60%): scores depend on observable tool output — pytest pass rates, static issue counts, docstring coverage, secret scan findings. A structurally perfect blueprint still scores poorly if the tools find nothing useful.

### Mutation loop behaviour

The loop can now **reject** a mutation. If the combined score does not improve by at least 3 percentage points, the loop stops and keeps the current best. In practice this means some runs stop at round 1 (if the base blueprint already scores well on task-level) and others continue to round 3–4.

---

## Frontend Demo

```bash
streamlit run app.py
```

Interactive demo of the full pipeline: choose a task category, edit the prompt, provide a code snippet, run evolution, inspect the selected blueprint, and execute it with either the deterministic runner or the LLM runner.

---

## Repository Structure

```
.
├── main.py                    # CLI entry point
├── app.py                     # Streamlit frontend
├── benchmark_demo.py          # Pipeline benchmark (all task categories)
├── task_benchmark.py          # Task-level debugging benchmark (30 cases)
├── models.py                  # AgentBlueprint, DomainProfile, EvaluationResult
├── domain_classifier.py       # Keyword-based task classifier
├── domain_profiler.py         # Domain profile expander
├── architecture_generator.py  # Blueprint generator
├── blueprint_mutator.py       # Single-step blueprint mutator
├── mutation_loop.py           # Multi-round evolution loop (NEW)
├── blueprint_evaluator.py     # Two-layer evaluator (structural + task-level)
├── agent_runner.py            # Deterministic runner with real tool dispatch
├── tools.py                   # Real executable tools (NEW)
├── llm_agent_runner.py        # Optional LLM-backed runner
├── requirements.txt
├── configs/                   # Saved blueprints
└── results/                   # Benchmark outputs and run results
```

---

## Design Choices

**Deterministic pipeline, LLM only at execution.** The classifier, profiler, architecture generator, mutator, evaluator, and benchmark are all deterministic and inspectable. The LLM is used only inside the final `LLMAgentRunner` as a semantic reasoning engine over the selected blueprint. This keeps the differentiation process reproducible and debuggable.

**Tools integrated into the deterministic runner, not a separate pipeline.** Tools are called inside `AgentRunner` during step execution, triggered by step name keywords. Their results flow directly into the evaluator's task-level score. The LLM runner is not involved.

**Mutation can lose.** The `MutationLoop` stops when improvement falls below 3%. This means the base blueprint is sometimes the winner — which is the correct behaviour when it already scores well on real tool output.

**Failures are reported, not hidden.** The task benchmark includes cases where the fixed code still fails pytest (e.g. mutable default argument bugs, which the integer smoke tests do not exercise). These are documented in the output rather than excluded.
