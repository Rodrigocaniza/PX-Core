# QA — PASS

Escenarios A–L: PASS.

- A. `pending_alerts` lista la cola con estado `PENDING`, mensaje y sucursal.
- B. Filtro por sucursal; sucursal ajena devuelve vacío.
- C. `reviews.read` ausente: falla cerrado para operador de sucursal.
- D. Reencolar la misma alerta no duplica la cola (idempotencia respetada).
- E. `merge_log` ordena observaciones y eventos en una única línea temporal.
- F. El evento de reapertura conserva motivo, campo y transición de estado.
- G. El fuente de la pantalla no invoca escritura ni despacho alguno.
- H. Ambas colas se listan con sobre, sucursal, fecha, campo, motivo y autor.
- I. Seleccionar corrección o alerta abre la bitácora de la misma fila.
- J. Orden estable: tres recargas no alteran la secuencia con igual segundo.
- K. Cola vacía: sin filas, KPI en cero y «Sin pendientes».
- L. Ventana piloto: abre «Pendientes y bitácora» y regresa al panel.

Resultados de ejecución:

- Focalizada: `12 passed in 2.02s`
  (`pytest tests/gestion_central/test_pending_and_log_v1.py`).
- Módulo Gestión Central: `66 passed in 12.38s` (`pytest tests/gestion_central`).
- Regresión completa: `1476 passed in 212.09s` (`pytest tests`).
- `compileall pending_ui.py real_sync.py ui.py`: PASS.
- `git diff --check`: PASS.
