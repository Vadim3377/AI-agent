# Runner Comparison Benchmark

This benchmark compares the deterministic runner with the LLM-backed runner on debugging tasks.

- Blueprint: `debugging_specialist_agent__mutated_debugging_verification`
- Model: `gpt-4.1-mini`
- Number of tests: 15
- Deterministic average score: 0.60
- LLM average score: 0.95

| Test | Deterministic Score | LLM Score |
|---|---:|---:|
| add_uses_subtraction | 0.25 | 1.00 |
| subtract_uses_addition | 0.25 | 1.00 |
| is_even_wrong_condition | 0.75 | 1.00 |
| is_odd_wrong_condition | 0.75 | 0.75 |
| max_value_returns_min | 0.75 | 1.00 |
| min_value_returns_max | 0.75 | 1.00 |
| absolute_value_wrong_sign | 0.50 | 1.00 |
| factorial_wrong_base_case | 0.50 | 1.00 |
| divide_swapped_operands | 0.50 | 0.75 |
| contains_uses_not_in | 1.00 | 1.00 |
| first_item_returns_last | 0.50 | 1.00 |
| last_item_returns_first | 0.50 | 1.00 |
| average_uses_length_minus_one | 0.75 | 1.00 |
| reverse_returns_same_list | 0.50 | 0.75 |
| square_returns_cube | 0.75 | 1.00 |

## Interpretation

The deterministic runner is expected to score low because it only executes the generated workflow structurally.
The LLM-backed runner is expected to score higher because it performs semantic reasoning over the input code.

This benchmark is still lightweight: it checks for expected diagnostic signals rather than using a full human-graded evaluation.