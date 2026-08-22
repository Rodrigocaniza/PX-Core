# QA — PASS

Escenarios A–M: PASS.

- A. Orden estable por `occurred_at`/`event_id` idéntico al del receptor.
- B. Traducción de categoría y de branch a unidad canónica.
- C. Filtros por categoría, sucursal, estado FactuFácil y texto libre.
- D. Totales por categoría y por sucursal, más última recepción.
- E. Duplicados y rechazos contabilizados desde la auditoría del receptor.
- F. Motivo de rechazo saneado, sin saltos de línea ni secretos.
- G. `audit.read` ausente: rechazos fallan cerrado y su total queda en cero.
- H. Principal atado a una unidad ve sólo su sucursal en filas, totales y auditoría.
- I. `dashboard.read` ausente: la lectura falla cerrado.
- J. `INSERT`/`UPDATE`/`DELETE` rechazados sobre la conexión real.
- K. Base inexistente: lectura vacía y el archivo no se crea.
- L. Pantalla: KPI, filtros, selección, detalle y volver, sin acción de escritura.
- M. Ventana piloto: abre «Recepción Sync», lista y regresa al panel.

Resultados de ejecución:

- Focalizada: `13 passed in 1.52s`
  (`pytest tests/gestion_central/test_sync_projection_view_v1.py`).
- Módulo Gestión Central: `67 passed in 13.02s` (`pytest tests/gestion_central`).
- Regresión completa: `1477 passed in 232.59s` (`pytest tests`).
- `compileall sync_projection_view.py sync_projection_ui.py ui.py`: PASS.
- `git diff --check`: PASS.
