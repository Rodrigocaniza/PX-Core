# Recovery / cross-PC

1. `git fetch origin`
2. `git switch feature/caja-operator-fixes-003`
3. `python -m pytest -q`
4. `python tools/validate_bc_caja_window_lifecycle.py`
5. Para regenerar evidencia: `python tools/capture_bc_caja_entrypoint.py <salida.png> --rows 30`.

La migración `009_order_phone.sql` se aplica automáticamente al abrir una base existente.
