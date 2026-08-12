# Test evidence

- python -m pytest tests/caja_diaria -q
- Result: 66 passed, 4 subtests passed
- python -m pytest -q
- Result: 66 passed, 4 subtests passed
- python tools/capture_bc_caja_entrypoint.py artifacts/BC-CAJA-UX-006/entrypoint-final-1366x768.png
- Result: BC_CAJA_REAL_ENTRYPOINT_CAPTURE_OK, 1366x768, result=0

All data used for capture was empty or synthetic and stored in a temporary directory.
- Layout-overlap correction focal suite: 17 passed.
- Post-correction Caja regression: 66 passed, 4 subtests passed.
- Post-correction full regression: 66 passed, 4 subtests passed.

- Final visible-behavior focal suite: 18 passed.
- Final Caja regression: 67 passed, 4 subtests passed.
- Empty and populated 1366x768 captures: PASS.

- Final layout focal suite: 18 passed.
- Caja and full regression: 67 passed, 4 subtests passed.
- Real populated entrypoint (30 synthetic rows): money/total PASS; scroll PASS; effective geometry PASS.
