# QuixBugs External Validation Benchmark

Validates the debugging agent on 10 real Python bugs from the QuixBugs dataset
(https://github.com/jkoppel/QuixBugs). Bugs were not seen during development.

A fix counts as passed only if it is correct on every held-out test case.

| Metric | Base blueprint | Mutated blueprint |
|---|---|---|
| Held-out pass rate (all cases) | 8/10 (80%) | 8/10 (80%) |
| Held-out cases passed | 60/64 | 60/64 |
| Agent self-check (pytest_runner) | - | 10/10 |
| Avg revision rounds | 0.00 | 0.80 |

| Task | Description | Base cases | Mutated cases | Self-check | Rounds |
|---|---|---|---|---|---|
| bitcount | Count set bits using Brian Kernighan's method | 9/9 | 9/9 | yes | 1 |
| find_first_in_sorted | Binary search for first occurrence of x | 7/7 | 7/7 | yes | 1 |
| flatten | Flatten a nested list | 7/7 | 7/7 | yes | 0 |
| gcd | Euclidean GCD | 6/6 | 6/6 | yes | 0 |
| is_valid_parenthesization | Check balanced parentheses | 6/6 | 6/6 | yes | 2 |
| max_sublist_sum | Kadane's algorithm for maximum subarray sum | 5/6 | 5/6 | yes | 1 |
| next_palindrome | Find the next palindrome greater than a number given as a digit list | 6/6 | 6/6 | yes | 1 |
| pascal | Generate the first n rows of Pascal's triangle | 5/5 | 5/5 | yes | 0 |
| possible_change | Count the ways to make change for a total from given coin denominations | 7/7 | 7/7 | yes | 1 |
| wrap | Word-wrap text to a given column width | 2/5 | 2/5 | yes | 1 |

## LLM Usage: base blueprint (per task = one runner.run, incl. revision rounds)

```
Provider / model : gemini / gemini-3.5-flash
Tasks / LLM calls: 10 / 10
Latency per task : p50 13.89s, p95 28.33s
Avg tokens/task  : 441 in, 3975 out
Cost per task    : $0.0400
```

## LLM Usage: mutated blueprint (per task = one runner.run, incl. revision rounds)

```
Provider / model : gemini / gemini-3.5-flash
Tasks / LLM calls: 10 / 18
Latency per task : p50 51.09s, p95 82.67s
Avg tokens/task  : 1957 in, 10677 out
Cost per task    : $0.1086
```

## Notes

- These are real bugs from an independent external dataset, not tasks
  designed by the author. The buggy code is sent without hints.
- Held-out grading runs each final fix on test inputs whose expected outputs
  come from the ground-truth fix; the model never sees them.
- Self-check is the agent's own pytest_runner result inside the feedback loop.
  It uses generic smoke tests, so it can pass on fixes that are still wrong.
- The mutated blueprint's feedback loop gives it additional revision
  opportunities not available to the base blueprint.
