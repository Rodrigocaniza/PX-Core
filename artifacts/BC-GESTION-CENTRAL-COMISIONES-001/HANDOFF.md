# Handoff

Cadena: Librarian -> QA -> Auditor, **sin independencia real** (ver `INDEPENDENCE.md`).

Matriz de revision:

- Reglas economicas, estados, periodo, identidad e idempotencia -> `modulos/gestion_central/comisiones.py`
- Persistencia, indices parciales unicos y migracion -> `modulos/gestion_central/repository.py`
- Bandeja, filtros, KPIs, desglose, acciones e historial -> `modulos/gestion_central/comisiones_ui.py`
- Entrada desde el panel -> `modulos/gestion_central/ui.py`
- Validacion de dominio -> `tests/gestion_central/test_comisiones.py`
- Validacion de interfaz y Full HD -> `tests/gestion_central/test_comisiones_ui_interactions.py`
- Evidencia visual -> `tools/capture_gestion_central_comisiones.py` y `VISUAL_EVIDENCE.md`
- Contrato economico -> `COMMISSION_RULES.md`
- Arquitectura y limites -> `ARCHITECTURE.md`

Siguiente bloque recomendado: definir canonicamente el porcentaje de comision (general,
por local o por vendedora) y convertir `commission_policies` en regla productiva aprobada.
