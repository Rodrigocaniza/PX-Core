# Evidencia QA

- JSON de Command Center: válido.
- `python -m pytest tests/gestion_central -q`: **8 passed**.
- `python -m pytest tests -q`: **207 passed**.
- `python bc_gestion_central.py --self-check --data-dir <temporal>`:
  `BC_GESTION_CENTRAL_PILOT_OK units=4 synthetic=YES production=NO`.
- `python -m compileall`: correcto.
- `git diff --check`: correcto.

Las pruebas cubren las cuatro unidades, aislamiento del operador local,
auditoría de solo lectura, hashing de contraseñas, idempotencia/conflictos de
sincronización, alertas, reconocimiento y contrato responsive.
