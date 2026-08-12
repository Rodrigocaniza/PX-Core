# BC-CAJA-OPERATIONS-001

State: IMPLEMENTED_AND_VERIFIED.

- Canonical base: `origin/main` at `f0ad079b8fc275385f844c6e76dbc452669c5e1c`.
- Weekday overtime: zero through 18:10:59; real whole minutes from 18:11:00.
- Saturday overtime: zero through 12:10:59; real whole minutes from 12:11:00.
- No rounding or monetary overtime policy was introduced; Sunday remains undefined.
- Persisted `overtime_triggered` and `overtime_minutes` continue using migration 004.
- Expenses always reduce expected cash and never reduce card/transfer totals.
- Close confirmation and cash count now show the complete operational breakdown.
- UX-004 layout was preserved.
