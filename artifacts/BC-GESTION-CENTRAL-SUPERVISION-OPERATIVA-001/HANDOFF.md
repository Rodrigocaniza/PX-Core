# Handoff

Orden obligatorio: Librarian → QA → Auditor. Cada receptor debe revisar la candidata actual del worktree `.worktrees/gc-sol-001`, no confiar en conteos anteriores, y registrar un reporte dentro de este artifact. Un FAIL invalida el cierre hasta corregir y regenerar la evidencia afectada.

Matriz: rango/resumen/detalle/alertas/mensajes/revisión diaria → `operations.py`, `ui.py`, `test_operations.py`, `screenshots/supervision-1920x1080.png`; revisión de ventas → `real_sync.py`, `review_ui.py`, pruebas `test_real_sync_review.py` y `test_review_ui_interactions.py`; límites → `ARCHITECTURE.md` y contratos heredados.
