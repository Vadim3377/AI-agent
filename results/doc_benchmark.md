# Documentation Feedback Loop Benchmark

## Scoring: quality-aware coverage

A docstring is **complete** only if it contains an `Args:` section (for functions with parameters) and a `Returns:` section (for functions that return a value). One-liner docstrings score 0.

**Base blueprint**: single direct LLM call asking for documented code.  
**Mutated blueprint**: `verify_docstring_coverage` step triggers an AST-based checker; incomplete symbols are sent back for revision.

| Task | Symbols | Base complete | Mutated complete | Rounds | Improved |
|---|---:|---:|---:|---:|---|
| stats_module | 5 | 5/5 (100%) | 5/5 (100%) | 0 | — |
| cache_module | 5 | 4/5 (80%) | 5/5 (100%) | 1 | ✓ |
| graph_module | 4 | 4/4 (100%) | 4/4 (100%) | 0 | — |
| text_processing_module | 6 | 6/6 (100%) | 6/6 (100%) | 0 | — |
| pagination_module | 4 | 4/4 (100%) | 4/4 (100%) | 0 | — |
| retry_module | 4 | 4/4 (100%) | 4/4 (100%) | 0 | — |
| validation_module | 6 | 6/6 (100%) | 6/6 (100%) | 0 | — |
| config_module | 5 | 5/5 (100%) | 5/5 (100%) | 0 | — |
| event_module | 6 | 5/6 (83%) | 6/6 (100%) | 1 | ✓ |
| data_pipeline_module | 5 | 5/5 (100%) | 5/5 (100%) | 0 | — |
| **Average** | **5.0** | **96%** | **100%** | **0.20** | **2/10** |

## Key observations

- Base blueprint (single-shot) average quality coverage: **96%**
- Mutated blueprint (feedback loop) average quality coverage: **100%**
- Coverage improved in **2 of 10** tasks.
- Average revision rounds: **0.20**

The LLM reliably adds *some* docstring on the first pass, but frequently writes one-liners that omit Args/Returns sections for helper functions. The mutated blueprint's quality checker surfaces these gaps and sends back a targeted revision request.
