# Stem Agent Benchmark Summary

## Compare semantic routing with the deterministic fallback. method comparison

Across 5 benchmark tasks, the LLM classifier was used in **5** cases. In **0** case(s) the LLM and keyword classifiers disagreed on domain or subdomain.

| Task | Method | LLM route | Keyword route | Agree | LLM reasoning |
|---|---|---|---|---|---|
| debugging | llm | quality_assurance / debugging | quality_assurance / debugging | yes | The task specifically involves debugging a Python function that produces incorrect output and fails testing, making debugging the clear focus. |
| code_quality_cleanup | llm | quality_assurance / code_quality_cleanup | quality_assurance / code_quality_cleanup | yes | The task explicitly involves removing dead code, simplifying logic, and improving readability, which falls under quality assurance and code quality cleanup. |
| comments_and_documentation | llm | quality_assurance / comments_and_documentation | quality_assurance / comments_and_documentation | yes | The task explicitly requires adding comments and docstrings to explain the code, which aligns with comments and documentation in quality assurance. |
| security | llm | security / dangerous_operations_and_data_breaches | security / dangerous_operations_and_data_breaches | yes | The task explicitly requests checking for dangerous operations, API key leaks, passwords, and data breaches, which falls clearly under security and data protection. |
| code_research | llm | deep_research / code_research | deep_research / code_research | yes | The task involves investigating and gathering information on implementing a Python plugin system, which is best suited to deep research in code. |

## Blueprint evolution

| Task | Domain | Subdomain | Base Score | Mutated Score | Selected | Executed Steps | Status |
|---|---|---|---:|---:|---|---:|---|
| debugging | quality_assurance | debugging | 0.86 | 1.00 | mutated | 11 | completed |
| code_quality_cleanup | quality_assurance | code_quality_cleanup | 1.00 | 1.00 | base | 7 | completed |
| comments_and_documentation | quality_assurance | comments_and_documentation | 0.86 | 1.00 | mutated | 10 | completed |
| security | security | dangerous_operations_and_data_breaches | 1.00 | 1.00 | base | 8 | completed |
| code_research | deep_research | code_research | 0.86 | 1.00 | mutated | 10 | completed |

## Notes

- The benchmark is deterministic (no LLM execution of blueprints).
- Blueprint scores measure structural quality: workflow specificity, tool relevance, schema completeness, and verification steps.
- Classification method reflects whether OPENAI_API_KEY was available.
- Disagreement between LLM and keyword classifiers indicates cases where semantic reading changes the routing decision.
