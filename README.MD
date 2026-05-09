
# Stem Agent

This project implements a minimal **stem-agent pipeline** inspired by the idea of biological stem-cell differentiation. Instead of hand-building a fixed agent for one task, the system starts from a broad task-family prompt, identifies what kind of specialist is needed, generates a specialist blueprint, mutates it, evaluates the mutation, selects the stronger version, and then executes the selected specialist.

The project explores the idea that an AI agent should not only answer a prompt, but should reason about what kind of agent it needs to become for a given class of problems.

---

## Project Idea

A traditional automation script follows a predefined workflow. It performs the same steps every time, with decision points designed in advance by the developer.

A stem agent is different. It starts from a general shell and gradually forms a specialised agent design based on the task description. In this project, specialisation is represented as an explicit `AgentBlueprint`, not as uncontrolled self-modifying code.

The blueprint contains:

- agent role
- domain profile
- workflow
- tools
- output schema
- stopping conditions

This keeps the system inspectable and safe while still allowing controlled specialisation.

---

## Pipeline

```text
Task Prompt
   ↓
DomainClassifier
   ↓
DomainProfiler
   ↓
ArchitectureGenerator
   ↓
BlueprintMutator
   ↓
BlueprintEvaluator
   ↓
Selected AgentBlueprint
   ↓
AgentRunner / LLMAgentRunner
````

---

## Components

### `DomainClassifier`

The classifier receives the task prompt, normalises it, detects task-specific signals, and assigns the prompt to a domain and subdomain.

Current supported categories:

* **QA: debugging**
* **QA: code-quality cleanup**
* **QA: comments and documentation**
* **Security: dangerous operations and data breaches**
* **Deep research: code-related research**

Example:

```text
"Debug this Python function. It gives the wrong output and the test fails."
```

is classified as:

```text
domain: quality_assurance
subdomain: debugging
```

---

### `DomainProfiler`

The profiler expands the classifier result into a fuller domain profile.

It identifies:

* domain
* subdomain
* artefact type
* required capabilities
* candidate tools
* evaluation metrics
* reasoning

For example, a debugging profile may require:

* code understanding
* expected behaviour inference
* bug localisation
* test generation
* runtime failure analysis
* fix suggestion

---

### `ArchitectureGenerator`

The architecture generator converts the domain profile into an initial specialist blueprint.

For example, a debugging profile becomes a `debugging_specialist_agent` with a workflow such as:

```text
read_source_code
infer_expected_behaviour
identify_failure_symptoms
generate_minimal_reproduction_or_tests
run_tests_if_available
localise_likely_bug
suggest_fix
explain_fix_rationale
produce_debugging_report
```

---

### `BlueprintMutator`

The mutator creates a controlled variation of the generated blueprint.

Mutation is applied only to safe configuration fields:

* workflow steps
* output schema
* role description
* stopping conditions

The system does **not** allow arbitrary rewriting of project source code.

For example, a debugging blueprint may be mutated by adding:

```text
verify_fix_against_generated_tests
check_for_regression_risk
```

---

### `BlueprintEvaluator`

The evaluator compares the base blueprint with the mutated blueprint and selects the stronger one.

The current evaluator measures structural blueprint quality. It checks whether the blueprint has:

* domain-specific workflow
* relevant tools
* output schema
* stopping conditions
* domain-specific schema fields
* verification or safeguard steps
* workflow/subdomain alignment

Example result:

```text
Base score: 0.86
Mutated score: 1.00
Selected blueprint: mutated
```

---

### `AgentRunner`

The deterministic runner executes the selected blueprint as a workflow trace.

It does not perform semantic reasoning. Its purpose is to verify that the selected blueprint can be executed structurally and that the pipeline is runnable without external credentials.

---

### `LLMAgentRunner`

The LLM-backed runner optionally executes the selected blueprint using an OpenAI model.

It uses the selected specialist blueprint as execution context:

* role
* domain profile
* workflow
* tools
* output schema
* concrete task input

This allows the final specialist to perform semantic reasoning over real input.

For example, given:

```python
def add(a, b):
    return a - b
```

the LLM-backed debugging runner can identify that the function is intended to add values but incorrectly uses subtraction.

---

## Setup

Python 3.10+ is recommended.

Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` does not exist yet, create it with:

```text
openai
python-dotenv
streamlit
```

---

## Environment Variables

The deterministic pipeline does **not** require an API key.

The LLM-backed runner requires an OpenAI API key. Create a local `.env` file in the project root:

```env
OPENAI_API_KEY=your_api_key_here
```

Do **not** commit `.env`.

Your `.gitignore` should include:

```gitignore
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

### 1. Generate a Blueprint

```bash
python main.py --task "Debug this Python function. It gives the wrong output and the test fails." --output configs/debugging_blueprint.json
```

---

### 2. Generate, Mutate, Evaluate, and Select a Blueprint

```bash
python main.py --task "Debug this Python function. It gives the wrong output and the test fails." --evaluate --output configs/selected_debugging.json
```

Example output:

```text
Stem shell completed evaluation-guided specialisation.
Base score: 0.86
Mutated score: 1.0
Selected blueprint: mutated
Domain: quality_assurance
Subdomain: debugging
Blueprint name: debugging_specialist_agent__mutated_debugging_verification
```

---

### 3. Run a Selected Blueprint Deterministically

```bash
python main.py --run-blueprint configs/selected_debugging.json --input "def add(a, b): return a - b" --run-output results/debugging_run.json
```

This produces a structured workflow trace.

---

### 4. Run a Selected Blueprint with the LLM Runner

```bash
python main.py --run-blueprint configs/selected_debugging.json --input "def add(a, b): return a - b" --use-llm --run-output results/debugging_llm_run.json
```

This performs semantic execution using the selected specialist blueprint.

---

## Frontend Demo

A small Streamlit frontend is included to demonstrate the full pipeline interactively.

Run:

```bash
streamlit run app.py
```

The frontend lets you:

* choose a task category
* edit the task-family prompt
* provide concrete task input
* generate a base blueprint
* mutate the blueprint
* compare base vs mutated scores
* inspect the selected blueprint
* execute the selected blueprint with either:

  * deterministic workflow trace
  * LLM-backed semantic execution

---

## Benchmark Demo

Run:

```bash
python benchmark_demo.py
```

This runs the full deterministic stem-agent pipeline across the supported task categories:

* debugging
* code-quality cleanup
* comments and documentation
* security validation
* code-related research

For each task, the benchmark:

1. profiles the prompt
2. generates a base blueprint
3. mutates the blueprint
4. evaluates base vs mutated
5. selects the stronger blueprint
6. executes the selected blueprint

Generated files:

```text
results/benchmark_summary.json
results/benchmark_summary.md
results/selected_blueprints/
```

Example benchmark result:

```text
Task type              Base score    Mutated score    Selected
Debugging              0.86          1.00             Mutated
Code Cleanup           0.86          1.00             Mutated
Comments/Docs          0.86          1.00             Mutated
Security Validation    0.86          1.00             Mutated
Code Research          0.86          1.00             Mutated
```

---

## Runner Comparison Benchmark

Run:

```bash
python llm_runner_tests.py
```

This compares the deterministic runner with the LLM-backed runner on 15 debugging tasks.

Latest result:

```text
Deterministic average score: 0.60
LLM average score: 0.95
```

The deterministic runner validates structural execution, while the LLM-backed runner performs semantic debugging.

Generated files:

```text
results/runner_comparison.json
results/runner_comparison.md
```

---

## Evaluation

The project currently has two evaluation layers.

### 1. Blueprint-Level Evaluation

This evaluates whether mutation improves the generated specialist blueprint.

The evaluator checks:

* workflow relevance
* tool relevance
* output schema completeness
* stopping conditions
* verification/safeguard steps
* subdomain alignment

Example:

```text
Base score: 0.86
Mutated score: 1.00
Selected: mutated
```

This measures the quality of the differentiation process.

---

### 2. Runner-Level Evaluation

This evaluates whether the final execution backend can perform useful work on concrete inputs.

The deterministic runner executes the workflow structurally.

The LLM-backed runner performs semantic reasoning.

Example:

```text
Deterministic runner: 0.60
LLM-backed runner: 0.95
```

---

## Example: Real Project Code

The system was also tested on real code from this project.

Using the prompt:

```text
Add useful comments and docstrings to explain the code.
```

and passing the frontend function `display_runner_output` as input, the system classified the task as:

```text
domain: quality_assurance
subdomain: comments_and_documentation
```

It generated a documentation-specialist blueprint, mutated it with comment-quality verification steps, and selected the mutated blueprint.

Result:

```text
Base score: 0.86
Mutated score: 1.00
Selected: mutated
```

The deterministic runner produced schema-compliant placeholder output, while the LLM-backed runner generated:

* a meaningful function-level docstring
* targeted inline comments
* a final verdict of `documented`

This demonstrated the difference between structural execution and semantic execution on real project code.

---

## Repository Structure

```text
.
├── main.py
├── app.py
├── benchmark_demo.py
├── llm_runner_tests.py
├── models.py
├── domain_classifier.py
├── domain_profiler.py
├── architecture_generator.py
├── blueprint_mutator.py
├── blueprint_evaluator.py
├── agent_runner.py
├── llm_agent_runner.py
├── requirements.txt
├── README.md
├── configs/
└── results/
```

---

## Current Project Status

Implemented:

* stem shell
* domain classifier
* domain profiler
* architecture generator
* controlled blueprint mutation
* blueprint evaluation and selection
* deterministic agent runner
* optional OpenAI-backed LLM runner
* benchmark demo
* runner comparison benchmark
* Streamlit frontend demo

---

## Limitations

The current blueprint evaluator measures structural quality rather than full real-world task-solving ability.

The runner comparison benchmark uses expected diagnostic signals rather than a human-graded benchmark.

The deterministic runner is intentionally limited: it proves workflow execution but does not perform semantic reasoning.

The current mutation loop performs one mutation and one comparison. It does not yet perform multiple rounds of evolution.

The tools listed in blueprints are currently descriptive. Some, such as `pytest_runner`, `static_checker`, or `secret_detector`, are not yet implemented as real executable tools.

---

## Future Work

With more time, the system could be extended with:

* multiple mutation rounds
* real `pytest` execution for debugging tasks
* labelled debugging benchmark with expected fixes
* real static-analysis integration
* deterministic secret scanning for security tasks
* source retrieval for code-research tasks
* LLM-generated candidate architectures
* stronger rejection rules for unsafe mutations
* regression testing for selected blueprints
* human-rated evaluation of documentation/comment quality

---

## Design Choice

The main design choice was to keep the stem-agent differentiation process deterministic and inspectable.

The OpenAI API is used only as an optional semantic execution backend. The core pipeline can still run without external credentials.

This separation keeps the project reproducible while allowing the final specialised agent to perform useful reasoning when an API key is available.

```
```
