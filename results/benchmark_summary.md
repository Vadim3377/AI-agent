# Stem Agent Benchmark Summary

This benchmark compares the base generated blueprint with the mutated blueprint. The evaluator scores structural blueprint quality, selects the stronger blueprint, and then executes the selected blueprint with the deterministic agent runner.

| Task | Domain | Subdomain | Base Score | Mutated Score | Selected | Executed Steps | Status |
|---|---|---|---:|---:|---|---:|---|
| debugging | quality_assurance | debugging | 0.86 | 1.00 | mutated | 11 | completed |
| code_quality_cleanup | quality_assurance | code_quality_cleanup | 1.00 | 1.00 | base | 7 | completed |
| comments_and_documentation | quality_assurance | comments_and_documentation | 0.86 | 1.00 | mutated | 9 | completed |
| security | security | dangerous_operations_and_data_breaches | 1.00 | 1.00 | base | 8 | completed |
| code_research | deep_research | code_research | 0.86 | 1.00 | mutated | 10 | completed |

## Notes

- The benchmark is deterministic.
- It evaluates the stem-agent pipeline rather than a foundation model.
- The current scores measure blueprint structure, safeguard coverage, workflow relevance, and schema completeness.
- A future version should evaluate semantic task-solving performance using labelled debugging, security, documentation, and research tasks.
