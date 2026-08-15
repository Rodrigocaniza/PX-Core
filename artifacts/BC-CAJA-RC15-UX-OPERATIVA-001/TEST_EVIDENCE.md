# Test evidence

- `python -m pytest tests/caja_diaria/test_rc15_ux_operativa.py -q --basetemp=.test-tmp/rc15-target`: 6 PASS.
- `python -m pytest tests/caja_diaria -q --basetemp=.test-tmp/rc15-full`: 205 PASS.
- GUI real: `tools/capture_caja_ux006.py`, SQLite temporal, 1366×768, captura inspeccionada.
- Packaging: `pilot/build_pilot.ps1` PASS (segundo intento; el primero tuvo un lock transitorio al comprimir).
