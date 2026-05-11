# Task-Level Agent Benchmark

**Mode:** llm  
**Base blueprint:** `debugging_specialist_agent`  
**Selected blueprint:** `debugging_specialist_agent__mutated_debugging_verification`  
**Evolution rounds:** 2  best score 0.65

## Before / After Comparison

| Metric | Base Blueprint | Selected Blueprint | delta |
|--------|:--------------:|:-----------------:|:---:|
| Fix extracted rate | 100% | 100% | -- |
| First-attempt pass rate | 73% | 70% | **-3%** |
| Final pytest pass rate | 73% | 97% | **+24%** |
| Avg revision rounds | 0.00 | 0.43 | **+0.43** |
| Static signal score | 100% | 100% | -- |
| **Avg agent score** | **0.813** | **0.977** | **+0.164** |

## Bug Type Breakdown (Selected Blueprint)

| Bug Type | Cases | Fix Extracted | pytest Pass | Avg Score |
|----------|:-----:|:-------------:|:-----------:|:---------:|
| wrong_operator | 8 | 8/8 | 100% | 1.00 |
| off_by_one | 3 | 3/3 | 67% | 0.77 |
| missing_return | 5 | 5/5 | 100% | 1.00 |
| wrong_comparison | 3 | 3/3 | 100% | 1.00 |
| logic_error | 6 | 6/6 | 100% | 1.00 |
| type_scope_error | 5 | 5/5 | 100% | 1.00 |

## Cases Improved by Mutation

op_005, obo_003, ret_002, typ_002, typ_003, typ_004, typ_005

## Failed Both Blueprints

obo_002

*(Agent extracted a fix but pytest still failed -- genuinely hard cases.)*