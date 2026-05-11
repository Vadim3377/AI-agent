# QuixBugs External Validation Benchmark

Validates the debugging agent on 10 real Python bugs from the QuixBugs dataset
(https://github.com/jkoppel/QuixBugs). Bugs were not seen during development.

| Metric | Base blueprint | Mutated blueprint |
|---|---|---|
| pytest pass rate | 0/10 (0%) | 5/10 (50%) |
| First-attempt pass rate | — | 3/10 (30%) |
| Avg revision rounds | 0.00 | 1.90 |

| Task | Description | Base | Mutated | Rounds |
|---|---|---|---|---|
| bitcount | Count set bits using Brian Kernighan's method | ✗ | ✓ | 2 |
| find_first_in_sorted | Binary search for first occurrence of x | ✗ | ✗ | 3 |
| flatten | Flatten a nested list | ✗ | ✓ | 0 |
| gcd | Euclidean GCD | ✗ | ✓ | 0 |
| is_valid_parenthesization | Check balanced parentheses | ✗ | ✗ | 3 |
| max_sublist_sum | Kadane's algorithm for maximum subarray sum | ✗ | ✗ | 3 |
| next_palindrome | Find next palindrome greater than n | ✗ | ✗ | 3 |
| pascal | Generate nth row of Pascal's triangle | ✗ | ✓ | 0 |
| possible_change | Count ways to make change | ✗ | ✗ | 3 |
| wrap | Word-wrap text to a given column width | ✗ | ✓ | 2 |

## Notes

- These are real bugs from an independent external dataset, not tasks
  designed by the author.
- pytest evaluation uses the same mechanism as the self-curated benchmark:
  the agent's suggested fix is extracted and run through pytest_runner.
- The mutated blueprint's feedback loop gives it additional revision
  opportunities not available to the base blueprint.
