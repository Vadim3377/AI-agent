# Stem Agent Benchmark Summary

Two-layer evaluation: structural (40%) + task-level from real tool results (60%).

| Task | Domain | Subdomain | Base Combined | Best Combined | Rounds | Tools Called |
|------|--------|-----------|:-------------:|:-------------:|:------:|--------------|
| debugging | quality_assurance | debugging | 0.94 | 1.00 | 2 | static_checker, pytest_runner |
| code_quality_cleanup | quality_assurance | code_quality_cleanup | 0.76 | 0.76 | 1 | complexity_checker |
| comments_and_documentation | quality_assurance | comments_and_documentation | 0.34 | 0.40 | 2 | docstring_checker, complexity_checker |
| security | security | dangerous_operations_and_data_breaches | 0.88 | 0.88 | 1 | secret_detector |
| code_research | deep_research | code_research | 0.86 | 1.00 | 2 | — |

## Per-Task Evolution Tables

### debugging

```
Rnd  Blueprint                                             Struct   Task   Comb  Best
-------------------------------------------------------------------------------------
0    debugging_specialist_agent                              0.86   1.00   0.94
1    debugging_specialist_agent__mutated_debugging_ver...    1.00   1.00   1.00  ✓
2    debugging_specialist_agent__mutated_debugging_ver...    1.00   1.00   1.00  ✓
-------------------------------------------------------------------------------------
Stopping reason: score_plateau
```

### code_quality_cleanup

```
Rnd  Blueprint                                             Struct   Task   Comb  Best
-------------------------------------------------------------------------------------
0    code_quality_cleanup_agent                              1.00   0.60   0.76  ✓
1    code_quality_cleanup_agent__mutated_cleanup_behav...    1.00   0.60   0.76  ✓
-------------------------------------------------------------------------------------
Stopping reason: score_plateau
```

### comments_and_documentation

```
Rnd  Blueprint                                             Struct   Task   Comb  Best
-------------------------------------------------------------------------------------
0    comments_documentation_agent                            0.86   0.00   0.34
1    comments_documentation_agent__mutated_comment_qua...    1.00   0.00   0.40  ✓
2    comments_documentation_agent__mutated_comment_qua...    1.00   0.00   0.40  ✓
-------------------------------------------------------------------------------------
Stopping reason: score_plateau
```

### security

```
Rnd  Blueprint                                             Struct   Task   Comb  Best
-------------------------------------------------------------------------------------
0    security_validation_agent                               1.00   0.80   0.88  ✓
1    security_validation_agent__mutated_security_risk_...    1.00   0.80   0.88  ✓
-------------------------------------------------------------------------------------
Stopping reason: score_plateau
```

### code_research

```
Rnd  Blueprint                                             Struct   Task   Comb  Best
-------------------------------------------------------------------------------------
0    code_research_agent                                     0.86   0.86   0.86
1    code_research_agent__mutated_research_claim_verif...    1.00   1.00   1.00  ✓
2    code_research_agent__mutated_research_claim_verif...    1.00   1.00   1.00  ✓
-------------------------------------------------------------------------------------
Stopping reason: score_plateau
```
