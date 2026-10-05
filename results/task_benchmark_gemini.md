# Task-Level Agent Benchmark

**Mode:** llm  
**Base blueprint:** `debugging_specialist_agent`  
**Selected blueprint:** `debugging_specialist_agent__mutated_debugging_verification`  
**Evolution rounds:** 2  best score 0.65

## Before / After Comparison

| Metric | Base Blueprint | Selected Blueprint | delta |
|--------|:--------------:|:-----------------:|:---:|
| **Held-out pass rate (correctness)** | **27/29 (93%)** | **29/29 (100%)** | **+7%** |
| Fix extracted rate | 97% | 100% | -- |
| First-attempt self-check pass rate | 73% | 70% | **-3%** |
| Final self-check (pytest_runner smoke tests) | 73% | 100% | **+27%** |
| Avg revision rounds | 0.00 | 0.33 | **+0.33** |
| Static signal score | 100% | 100% | -- |
| **Avg agent score** | **0.813** | **1.000** | **+0.187** |

## LLM Usage (per task = one runner.run, incl. revision rounds)

```
Provider / model : gemini / gemini-3.5-flash
Tasks / LLM calls: 59 / 69
Latency per task : p50 8.68s, p95 39.73s
Avg tokens/task  : 669 in, 3165 out
Cost per task    : $0.0323
```

## Bug Type Breakdown (Selected Blueprint)

| Bug Type | Cases | Fix Extracted | pytest Pass | Avg Score |
|----------|:-----:|:-------------:|:-----------:|:---------:|
| wrong_operator | 8 | 8/8 | 100% | 1.00 |
| off_by_one | 3 | 3/3 | 100% | 1.00 |
| missing_return | 5 | 5/5 | 100% | 1.00 |
| wrong_comparison | 3 | 3/3 | 100% | 1.00 |
| logic_error | 6 | 6/6 | 100% | 1.00 |
| type_scope_error | 5 | 5/5 | 100% | 1.00 |

## Cases Improved by Mutation

op_005, obo_002, obo_003, ret_002, typ_002, typ_003, typ_004, typ_005

## Held-out Grading

Each final fix is run on held-out checks whose expected outputs come from the
case's ground-truth fix; the model never sees them. The self-check rows use
pytest_runner, which for most bug types only asserts a non-None return value,
so they overstate correctness.

- Failed held-out (base): ret_002, typ_002
- Failed held-out (selected): none
- Excluded (buggy code passes every check, no observable bug): typ_005