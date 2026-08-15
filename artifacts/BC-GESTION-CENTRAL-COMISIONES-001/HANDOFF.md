# Handoff

Cadena: Librarian → QA → Auditor, ejecutada con **independencia real** en tres subagentes
separados. Ver `INDEPENDENCE.md`, `generation-1/` y `generation-2/`.

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

Se corrigieron únicamente los bloqueantes, según el protocolo. Estos hallazgos de los revisores
independientes quedan abiertos y ordenados por riesgo:

1. **Cobros genuinos idénticos deduplicados** (QA, obs. 1). La clave de idempotencia de
   `register_payment` incluye monto + fecha + referencia, con referencia opcional. Dos cobros
   reales del mismo monto, el mismo día y sin referencia hacen que el segundo se descarte en
   silencio: el saldo nunca llega a cero y la venta nunca comisiona. Exposición actual baja
   —el panel no da de alta cobros— pero es el candidato número uno del próximo bloque.
   Corrección sugerida: exigir referencia no vacía o incorporar un discriminador de secuencia.
2. **Las liquidaciones `OBSERVADA` suman a los KPIs monetarios** (QA, obs. 2). No hay fuga de
   dinero, pero «Comisión calculada» sobreestima lo realmente liquidable. Sugerido: KPI separado.
3. **Ventas mixtas (convenio parcial) mal clasificadas** en `sync_review_sales` (QA, obs. 3).
   La dirección del error es conservadora —nunca paga de más— y las reglas aprobadas no definen la
   venta mixta. Requiere decisión de negocio antes de tocar código.
4. **`MANIFEST.sha256` no cubría los `PROMPT_*.txt`** (Librarian, obs. 1). Corregido en la
   generación 2: el manifest ahora los incluye.
5. **`assert "float(" not in source` es más débil que la propiedad declarada** (Auditor, obs.).
   Las divisiones `/100` de las etiquetas la eluden, aunque sean sólo de presentación.
6. **Defecto preexistente ajeno a la misión** (Librarian, obs. 4):
   `tests/gestion_central/test_ui_interactions.py` (commit `bb27034`) define dos veces
   `test_detail_uses_horizontal_full_hd_layout_without_primary_vertical_scroll`; pytest sólo
   recolecta la segunda y un cuerpo de aserciones queda muerto. **Fuera del alcance de esta misión**;
   conviene abrirlo como corrección propia.

## Siguiente bloque recomendado

Definir canónicamente el porcentaje de comisión (general, por local o por vendedora) y convertir
`commission_policies` en regla productiva aprobada. Junto con eso, resolver el hallazgo 1.
