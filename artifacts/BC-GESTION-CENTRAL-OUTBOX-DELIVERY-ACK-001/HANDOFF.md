# Handoff

Cadena obligatoria: Librarian → QA → Auditor. Cada gate revisa la candidata actual; un FAIL invalida el cierre y exige regeneración.

Matriz: dominio/transporte → `delivery.py`, persistencia → `repository.py`, bandeja → `delivery_ui.py` y `ui.py`, pruebas → `test_delivery.py`, `test_delivery_ui_interactions.py`, `test_alert_time_boundary.py`; contratos → `TRANSPORT_CONTRACT.md` y `FUTURE_FACTUFACIL_COMMISSION_CONTRACTS.md`; visual → captura y `VISUAL_EVIDENCE.md`.
