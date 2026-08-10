# Real workbook contract

- Sheets: `1, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 31`.
- Operational sheets: 1, 3, 4, 5, 6, 7, 8. Header row: 3. Columns A:N retain their supplied order.
- `CAJA INICIAL` is opening state, never a `CashEntry`.
- Each ordinary business row is one `CashEntry`; repeated client/envelope rows remain separate.
- `TOTALES`, blank calculation rows and final-cash rows are never movements.
- A sheet containing only opening/formulas is a future template, not an operational day.
- `Saldo` preserves numeric-looking text or `cancelado`.
- `Ordenes` preserves source case/value (`TR`, `Tr`, `tr`, `Caja Muni`).
- `Cuotas` remains text-compatible, including numeric cell `5`.
- Codes preserve numeric/text input, including textual `.000037`.

Economic equivalence confirmed:

`cash_final = opening_cash + cash_entries - expenses = declared_cash_total - declared_expenses`

The totals row declares Efectivo, Tarj./Cheq. and Gastos; TOTAL (H) is blank. Only actually declared cells are compared. The next operational day's default opening is the latest prior closed day's frozen final cash. Explicit opening remains a deliberate override.
