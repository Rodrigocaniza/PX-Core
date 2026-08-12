# Test evidence

- python -m pytest tests/caja_diaria -q
- Result: 66 passed, 4 subtests passed
- python -m pytest -q
- Result: 66 passed, 4 subtests passed
- python tools/capture_bc_caja_entrypoint.py artifacts/BC-CAJA-UX-006/entrypoint-final-1366x768.png
- Result: BC_CAJA_REAL_ENTRYPOINT_CAPTURE_OK, 1366x768, result=0

All data used for capture was empty or synthetic and stored in a temporary directory.