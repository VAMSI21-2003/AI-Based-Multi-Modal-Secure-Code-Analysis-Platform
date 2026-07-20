# Metrics Extraction Run Summary
**Script:** src/metrics/extract_metrics.py

## Results
| Item | Value |
|---|---|
| Total samples processed | 27231 |
| Vulnerable samples | 12411 |
| Non-Vulnerable samples | 14820 |
| Output file | dataset/processed/metrics_features.csv |

## Feature Averages by Label
| Metric | Vulnerable Avg | Safe Avg | Difference |
|---|---|---|---|
| loc | 54.57 | 49.58 | +4.99 |
| function_count | 1.11 | 1.10 | +0.00 |
| loop_count | 1.27 | 1.01 | +0.26 |
| if_count | 5.85 | 5.06 | +0.79 |
| return_count | 2.06 | 1.90 | +0.15 |
| avg_line_length | 33.89 | 33.49 | +0.40 |
| max_line_length | 78.27 | 77.00 | +1.27 |
| comment_count | 3.42 | 3.14 | +0.28 |
| total_lines | 104.14 | 98.15 | +5.98 |
| blank_lines | 49.57 | 48.58 | +0.99 |
| nesting_depth | 3.05 | 2.54 | +0.52 |
| operator_count | 8.70 | 7.24 | +1.46 |
| pointer_count | 26.75 | 22.95 | +3.80 |
