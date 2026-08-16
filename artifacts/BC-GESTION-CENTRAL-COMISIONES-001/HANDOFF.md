# Handoff

Cadena: Librarian → QA → Auditor, con independencia real en tres subagentes separados por
generación. Estado de revisión de este snapshot: ver `INDEPENDENCE.md`. Evidencia de las
generaciones ya revisadas en `generation-1/` y `generation-2/`.

## Matriz de revisión

- Reglas económicas, estados, período, identidad e idempotencia → `modulos/gestion_central/comisiones.py`
- Persistencia, índices parciales únicos y migración → `modulos/gestion_central/repository.py`
- Bandeja, filtros, KPIs, desglose, acciones e historial → `modulos/gestion_central/comisiones_ui.py`
- Entrada desde el panel → `modulos/gestion_central/ui.py`
- Validación de dominio → `tests/gestion_central/test_comisiones.py`
- Validación de interfaz y Full HD → `tests/gestion_central/test_comisiones_ui_interactions.py`
- Evidencia visual → `tools/capture_gestion_central_comisiones.py` y `VISUAL_EVIDENCE.md`
- Contrato económico → `COMMISSION_RULES.md`
- Arquitectura, invariantes y límites → `ARCHITECTURE.md`

## Hallazgos no bloqueantes registrados y NO corregidos

Se corrigieron únicamente los bloqueantes, según el protocolo. Abiertos, ordenados por riesgo:

1. **Cobros genuinos idénticos deduplicados** (QA-001 obs. 1). La clave de idempotencia de
   `register_payment` incluye monto + fecha + referencia, con referencia opcional. Dos cobros
   reales del mismo monto, el mismo día y sin referencia: el segundo se descarta en silencio, el
   saldo nunca llega a cero y la venta nunca comisiona. Candidato número uno del próximo bloque.
   Corrección sugerida: exigir referencia no vacía o incorporar un discriminador de secuencia.
2. **Fechas ISO en formato básico o de semana** (QA-002 obs. 1). `date.fromisoformat` acepta
   `"20990410"` y `"2099-W15-3"`; el período derivado queda bien formado, pero los consumidores
   que cortan la cadena (`substr(sale_date,1,7)`, el KPI `sales_in_period`, el desplegable de
   meses) no las reconocen. No se pierde ni se duplica dinero. Normalizar al almacenar
   (`date.fromisoformat(...).isoformat()`) lo cerraría de raíz.
3. **`paid_amount` se calcula por estado y no por `paid_at`** (QA-002 obs. 3, AUD-002 O2). Al
   observar una liquidación ya pagada, el KPI «Pagado» cae a 0 aunque el dinero salió.
4. **Las liquidaciones `OBSERVADA` suman a los KPIs monetarios** (QA-001 obs. 2, QA-002 obs. 4).
   No hay fuga de dinero, pero «Comisión calculada» sobreestima lo liquidable y el contador
   `observed` que el KPI ya calcula no se muestra en pantalla.
5. **Ventas mixtas (convenio parcial) mal clasificadas** en `sync_review_sales` (QA-001 obs. 3).
   El error es conservador —nunca paga de más— y las reglas aprobadas no definen la venta mixta.
   Requiere decisión de negocio antes de tocar código.
6. **`test_state_contract_and_append_only_history` no prueba append-only** (AUD-002 O3). Ejecuta
   `DELETE` + `rollback()`, que demuestra que el rollback de SQLite funciona. La propiedad real se
   cumple, pero la suite no la protege ante regresiones.
7. **`assert "float(" not in source` es más débil que la propiedad declarada** (AUD-001 obs.).
8. **Defecto preexistente ajeno a la misión** (LIB-001 obs. 4):
   `tests/gestion_central/test_ui_interactions.py` (commit `bb27034`) define dos veces
   `test_detail_uses_horizontal_full_hd_layout_without_primary_vertical_scroll`; pytest sólo
   recolecta la segunda y un cuerpo de aserciones queda muerto. **Fuera del alcance de esta
   misión**; conviene abrirlo como corrección propia.

## Siguiente bloque recomendado

Definir canónicamente el porcentaje de comisión (general, por local o por vendedora) y convertir
`commission_policies` en regla productiva aprobada. Junto con eso, resolver los hallazgos 1 a 4.
