# Thinking x Feedback-Loop Experiment

Gemini 3.5 Flash on 22 debugging tasks (12 visible-test + 10 QuixBugs). Every cell
sees the same failing tests; only the loop runs them. Graded on hidden held-out checks.
Thinking off = `thinking_level="minimal"`.

| Cell | Held-out pass rate | p50 latency/task | Cost/task |
|---|---|---|---|
| Single-shot, thinking on | 21/22 (95%) | 12.45 s | $0.0350 |
| Test loop, thinking on | 21/22 (95%) | 18.16 s | $0.0475 |
| Single-shot, thinking off | 22/22 (100%) | 3.02 s | $0.0072 |
| Test loop, thinking off | 22/22 (100%) | 4.94 s | $0.0088 |

## Pre-registered claim

"A test-execution loop without model thinking matches thinking-mode single-shot
accuracy at a fraction of the cost and latency." Criteria (loop/off vs single/on):
within 1 task on accuracy, at most 50% of the cost, at most 50% of the p50 latency.

- Accuracy within 1 task: **True**
- Cost at most 50%: **True** (ratio 0.251)
- p50 latency at most 50%: **True** (ratio 0.397)
- Loop recovers accuracy lost by turning thinking off: **False**

**Verdict: the headline HOLDS.**

## Per task (held-out checks passed)

| Task | Set | Single-shot, thinking on | Test loop, thinking on | Single-shot, thinking off | Test loop, thinking off |
|---|---|---|---|---|---|
| merge_intervals | visible_test | 4/4 | 4/4 | 4/4 | 4/4 |
| roman_to_int | visible_test | 6/6 | 6/6 | 6/6 | 6/6 |
| rle_encode | visible_test | 4/4 | 4/4 | 4/4 | 4/4 |
| parse_duration | visible_test | 0/4 | 0/4 | 4/4 | 4/4 |
| top_k_frequent | visible_test | 4/4 | 4/4 | 4/4 | 4/4 |
| spiral_order | visible_test | 5/5 | 5/5 | 5/5 | 5/5 |
| semver_compare | visible_test | 5/5 | 5/5 | 5/5 | 5/5 |
| rotate_list | visible_test | 4/4 | 4/4 | 4/4 | 4/4 |
| flatten_dict | visible_test | 4/4 | 4/4 | 4/4 | 4/4 |
| int_to_base | visible_test | 5/5 | 5/5 | 5/5 | 5/5 |
| balanced_brackets | visible_test | 6/6 | 6/6 | 6/6 | 6/6 |
| moving_average | visible_test | 4/4 | 4/4 | 4/4 | 4/4 |
| bitcount | quixbugs | 9/9 | 9/9 | 9/9 | 9/9 |
| find_first_in_sorted | quixbugs | 7/7 | 7/7 | 7/7 | 7/7 |
| flatten | quixbugs | 7/7 | 7/7 | 7/7 | 7/7 |
| gcd | quixbugs | 6/6 | 6/6 | 6/6 | 6/6 |
| is_valid_parenthesization | quixbugs | 6/6 | 6/6 | 6/6 | 6/6 |
| max_sublist_sum | quixbugs | 6/6 | 6/6 | 6/6 | 6/6 |
| next_palindrome | quixbugs | 6/6 | 6/6 | 6/6 | 6/6 |
| pascal | quixbugs | 5/5 | 5/5 | 5/5 | 5/5 |
| possible_change | quixbugs | 7/7 | 7/7 | 7/7 | 7/7 |
| wrap | quixbugs | 5/5 | 5/5 | 5/5 | 5/5 |
