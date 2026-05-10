# Evolution Benchmark

Compares single-shot mutation (old) against iterative feedback-driven evolution (new).

The key column is **semantic score** — measured from real tool outputs,
not from structural blueprint checks.

## Old pipeline: structural score vs semantic score

| Task | Structural base→mutated | Semantic base→mutated | Semantic Δ |
|---|---|---|---:|
| debugging_wrong_operator | 0.86 → 1.00 | 0.40 → 0.40 | +0.00 |
| debugging_wrong_base_case | 0.86 → 1.00 | 0.40 → 0.40 | +0.00 |
| security_key_and_eval | 1.00 → 1.00 | 1.00 → 1.00 | +0.00 |
| security_clean_code | 1.00 → 1.00 | 0.60 → 0.60 | +0.00 |

## New pipeline: iterative evolution

| Task | Semantic base | Semantic best | Δ | Iterations | Accepted | Rolled back | Stopped because |
|---|---:|---:|---:|---:|---:|---:|---|
| debugging_wrong_operator | 0.40 | 0.40 | +0.00 | 2 | 0 | 2 | no improvement for 2 consecutive rounds |
| debugging_wrong_base_case | 0.40 | 0.40 | +0.00 | 2 | 0 | 2 | no improvement for 2 consecutive rounds |
| security_key_and_eval | 1.00 | 1.00 | +0.00 | 1 | 0 | 1 | converged at score 1.000 >= 0.9 |
| security_clean_code | 0.60 | 0.60 | +0.00 | 2 | 0 | 2 | no improvement for 2 consecutive rounds |

## What this shows

- The old structural score improvement (0.86→1.00) was real but measured the wrong thing.
- The new semantic score measures what tools actually observed: did pytest run? did the scanner fire? were findings detected?
- Rollbacks are evidence the loop is working: it tried something, measured it honestly, and discarded it when it didn't help.
- Accepted mutations show the blueprint genuinely changed its tool usage pattern across iterations.

## Iteration traces

### debugging_wrong_operator

- Iter 1: `pytest_retry_loop` → score=0.40 ✗ (2 tool invocations)
  - pytest ran but all attempts failed (+0.2)
  - tool-feedback loop used (2 attempts) (+0.2)
- Iter 2: `pytest_retry_loop` → score=0.40 ✗ (2 tool invocations)
  - pytest ran but all attempts failed (+0.2)
  - tool-feedback loop used (2 attempts) (+0.2)

### debugging_wrong_base_case

- Iter 1: `pytest_retry_loop` → score=0.40 ✗ (2 tool invocations)
  - pytest ran but all attempts failed (+0.2)
  - tool-feedback loop used (2 attempts) (+0.2)
- Iter 2: `pytest_retry_loop` → score=0.40 ✗ (2 tool invocations)
  - pytest ran but all attempts failed (+0.2)
  - tool-feedback loop used (2 attempts) (+0.2)

### security_key_and_eval

- Iter 1: `double_scan` → score=1.00 ✗ (3 tool invocations)
  - security tool executed (+0.4)
  - 3 finding(s) detected (+0.4)
  - severity classified (+0.2)

### security_clean_code

- Iter 1: `severity_triage` → score=0.60 ✗ (3 tool invocations)
  - security tool executed (+0.4)
  - scanner ran, no findings (clean input) (+0.2)
- Iter 2: `severity_triage` → score=0.60 ✗ (3 tool invocations)
  - security tool executed (+0.4)
  - scanner ran, no findings (clean input) (+0.2)
