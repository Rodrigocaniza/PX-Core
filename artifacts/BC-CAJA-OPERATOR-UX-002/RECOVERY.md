# Recovery

En otro equipo:

1. `git fetch origin`
2. `git switch feature/caja-operator-ux-002`
3. `python -m pytest -q`
4. Ejecutar `tools/capture_bc_caja_entrypoint.py` con
   `BC_CAJA_WINDOW_SIZE=1920x1080` y `1366x768`.

No mezclar con la misión previa ni modificar SQLite para reanudar.

