# Recovery

En otro equipo:

1. `git fetch origin`
2. `git switch feature/caja-window-bugfix-001`
3. `python -m pytest -q`
4. `python tools/validate_bc_caja_window_lifecycle.py`

La validación usa un directorio temporal y no toca datos reales.

