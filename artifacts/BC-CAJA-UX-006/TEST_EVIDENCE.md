# Test evidence

- Focal domain/repository/controller/UI suite: 33 passed, 4 subtests passed.
- Full regression: 75 passed, 4 subtests passed.
- Real command: python tools/capture_bc_caja_entrypoint.py artifacts/BC-CAJA-UX-006/final-1366x768.png --rows 30
- Integrated expense: Ferretería, 200.000, no sale data: PASS.
- Expense persistence, movement count, KPI/domain cash invariant and closed-day rejection: PASS.
- Cash count expected 1.500.000: PASS.
- 15 x 100.000 = counted 1.500.000, difference 0: saved PASS.
- Counted 1.450.000, difference -50.000: alert and saved PASS.
- Counted 1.550.000, difference +50.000: alert and saved PASS.
- SQLite round-trip of expected, counted, difference, status, denominations and timestamp: PASS.
- Capture data: synthetic/demo only.