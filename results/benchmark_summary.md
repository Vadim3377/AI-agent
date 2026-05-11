# Stem Agent Benchmark Summary

## Classification method comparison

Across 5 benchmark tasks, the LLM classifier was used in **5** cases. In **0** case(s) the LLM and keyword classifiers disagreed on domain or subdomain.

| Task | Method | LLM route | Keyword route | Agree | LLM reasoning |
|---|---|---|---|---|---|
| debugging | llm | quality_assurance / debugging | quality_assurance / debugging | ✓ | The task specifically asks to debug a Python function with incorrect output causing a test failure, which aligns directly with debugging in quality assurance. |
| code_quality_cleanup | llm | quality_assurance / code_quality_cleanup | quality_assurance / code_quality_cleanup | ✓ | The task focuses on improving code quality by removing dead code and simplifying logic, which fits well into code quality cleanup. |
| comments_and_documentation | llm | quality_assurance / comments_and_documentation | quality_assurance / comments_and_documentation | ✓ | The task explicitly requires adding comments and docstrings to explain the code, fitting clearly within comments_and_documentation under quality_assurance. |
| security | llm | security / dangerous_operations_and_data_breaches | security / dangerous_operations_and_data_breaches | ✓ | The task explicitly asks to check for dangerous operations, API key leaks, passwords, and possible data breaches, which aligns closely with security and specifically dangerous operations and data breaches subdomain. |
| code_research | llm | deep_research / code_research | deep_research / code_research | ✓ | The task involves researching documentation and examples related to code implementation, which aligns with deep research in code_research. |

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
