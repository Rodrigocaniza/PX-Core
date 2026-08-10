# Sanitized real E2E evidence

The E2E used a temporary workbook copy and newly created temporary SQLite database outside the repository.

| Day | Opening | Entries | Cash entries | Card/check | Expenses | Final cash |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,245,500 | 17 | 45,000 | 1,690,000 | 496,000 | 794,500 |
| 3 | 794,500 | 22 | 480,000 | 3,757,500 | 195,000 | 1,079,500 |
| 4 | 1,079,500 | 21 | 410,000 | 4,252,500 | 50,000 | 1,439,500 |
| 5 | 1,439,500 | 21 | 221,500 | 3,836,000 | 100,000 | 1,561,000 |
| 6 | 1,561,000 | 30 | 595,000 | 3,805,000 | 1,328,000 | 828,000 |
| 7 | 828,000 | 16 | 235,000 | 3,705,000 | 200,000 | 863,000 |
| 8 | 863,000 | 6 | 120,000 | 40,000 | 135,000 | 848,000 |

Result: `REAL_E2E_PASS days=7 entries=133 differences=0`.

Regression explicitly validates closed day 1 carrying its frozen final cash into newly created day 3.
