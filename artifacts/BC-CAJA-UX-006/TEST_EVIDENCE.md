# Test evidence

- Focal controller/visual contracts: 21 passed.
- Full regression: 72 passed, 4 subtests passed.
- Real command: python tools/capture_bc_caja_entrypoint.py artifacts/BC-CAJA-UX-006/final-1366x768.png --rows 30
- Entrypoint result: BC_CAJA_REAL_ENTRYPOINT_CAPTURE_OK, 1366x768, result=0.
- Sale values: frame 1.500.000, lens 250.000, total 1.750.000, pending 250.000.
- Expense: Ferretería, 200.000, no observations; persisted in temporary SQLite and included in 31 movements.
- Closed day: new expense rejected with canonical CashDayClosedError.
- Scroll: yview changed from (0.0, 0.3548387096774194) to (0.16129032258064516, 0.5161290322580645).
- Capture data: synthetic/demo only.