# Visible-Test Debugging Benchmark

12 multi-bug functions. Both blueprints see the same failing tests; only the
mutated blueprint can run them and revise. Fixes are graded on hidden held-out checks.

| Metric | Base (single-shot) | Mutated (test loop) |
|---|---|---|
| **Held-out pass rate** | **12/12 (100%)** | **12/12 (100%)** |
| Held-out checks passed | 55/55 | 55/55 |
| First attempt passes visible tests | - | 11/12 |
| Avg revision rounds | 0.00 | 0.08 |

| Task | Base | Mutated | Rounds |
|---|---|---|---|
| merge_intervals | 4/4 | 4/4 | 0 |
| roman_to_int | 6/6 | 6/6 | 1 |
| rle_encode | 4/4 | 4/4 | 0 |
| parse_duration | 4/4 | 4/4 | 0 |
| top_k_frequent | 4/4 | 4/4 | 0 |
| spiral_order | 5/5 | 5/5 | 0 |
| semver_compare | 5/5 | 5/5 | 0 |
| rotate_list | 4/4 | 4/4 | 0 |
| flatten_dict | 4/4 | 4/4 | 0 |
| int_to_base | 5/5 | 5/5 | 0 |
| balanced_brackets | 6/6 | 6/6 | 0 |
| moving_average | 4/4 | 4/4 | 0 |

## LLM Usage: base

```
Provider / model : gemini / gemini-3.5-flash
Tasks / LLM calls: 12 / 12
Latency per task : p50 13.34s, p95 23.26s
Avg tokens/task  : 580 in, 3622 out
Cost per task    : $0.0367
```

## LLM Usage: mutated

```
Provider / model : gemini / gemini-3.5-flash
Tasks / LLM calls: 12 / 13
Latency per task : p50 18.45s, p95 39.3s
Avg tokens/task  : 878 in, 4856 out
Cost per task    : $0.0494
```
