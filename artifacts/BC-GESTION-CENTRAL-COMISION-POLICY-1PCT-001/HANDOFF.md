# Handoff

Cadena: Librarian → QA → Auditor, en tres runners independientes sobre el mismo snapshot
inmutable. Estado de revisión: `INDEPENDENCE.md`. Evidencia por generación en `generation-N/`.

## Matriz de revisión

- Política canónica, aritmética `Decimal`/`HALF_UP` y estados de política → `modulos/gestion_central/comision_policy.py`
- Resolución, recálculo, versionado, guardas y export → `modulos/gestion_central/comisiones.py`
- Esquema, columnas de traza y migración → `modulos/gestion_central/repository.py`
- Encabezado, KPI, columnas y desglose → `modulos/gestion_central/comisiones_ui.py`
- Validación de dominio y migración → `tests/gestion_central/test_comisiones.py`
- Validación de interfaz y Full HD → `tests/gestion_central/test_comisiones_ui_interactions.py`
- Contrato del porcentaje → `COMMISSION_POLICY_1PCT.md`
- Reglas económicas ya canónicas → `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/COMMISSION_RULES.md`
- Arquitectura base → `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/ARCHITECTURE.md`

## Hallazgos no bloqueantes abiertos

Los **treinta y siete** del handoff de BC-GESTION-CENTRAL-COMISIONES-001 siguen abiertos y sin
corregir: esta misión no los tocó por estar fuera de su alcance. Se consultan en
`artifacts/BC-GESTION-CENTRAL-COMISIONES-001/HANDOFF.md`, y `WORKFLOW.json` de esa misión registra
los mismos treinta y siete. Cuatro de ellos cambian de estado:

1. **El signo «×» delante de un importe que ya es el producto** (heredado 8, parcial). Cerrado: la
   línea de comisión del desglose ahora usa «=». El badge de piloto duplicado entre shell y panel
   sigue abierto.
2. **Ni `register_payment` ni `sync_review_sales` tienen llamador productivo** (heredado 11). Sigue
   abierto y es ahora el bloqueante funcional principal: con la política aprobada, el cableado del
   ciclo de cobros es lo único que separa a la bandeja de ser operable desde el producto.
3. **`assert "float(" not in source` es más débil que la propiedad declarada** (heredado 7). Sigue
   abierto y ahora importa más, porque el cálculo pasó a `Decimal`: la aserción no distingue un
   `Decimal` bien usado de uno mal usado.
4. **`COMMISSION_RULES.md` y `ARCHITECTURE.md` generalizan de más** (heredado 16). Sigue abierto;
   esta misión no reescribió esos documentos.

Nuevos, abiertos y **no** corregidos:

5. **La vigencia se compara por período, no por fecha de cancelación.** Una venta cancelada el
   2026-07-31 y otra el 2026-08-01 caen en meses distintos y reciben trato distinto, que es lo
   deseado; pero una vigencia fijada a mitad de mes (`2026-08-15`) rige igual desde el 2026-08-01,
   porque la comparación es `período >= effective_from[:7]`. Está documentado en
   `COMMISSION_POLICY_1PCT.md` y es coherente con la granularidad mensual del módulo, pero una
   vigencia intramensual no se respetaría al día.
6. **Una `POLITICA_HISTORICA_PREVIA` ya pagada no tiene corrección.** `recalculate` no la alcanza
   —correctamente, porque el dinero salió— y `revert` está bloqueado. Es el mismo callejón que el
   hallazgo heredado 4 para la `OBSERVADA` pagada, ahora con un importe que además no es el
   oficial. Las **no** pagadas sí tienen salida: la repara `recalculate`.
7. **`POLICY_STATUSES` se define y no se usa.** Es documentación ejecutable del conjunto de
   estados, pero ninguna guarda lo valida contra lo que se escribe en `policy_status`.
8. **El retiro de políticas por alcance es una eliminación de filas.** Queda auditada con su
   `rate_bp` previo en `central_audit`, que es suficiente para reconstruirla, pero la fila en sí
   no se conserva en `commission_policy_versions`.
9. **`set_general_rate` no ofrece una vista previa del impacto.** Publicar una versión no dice
   cuántas liquidaciones cambiarían al recalcular. Con una sola política y un solo porcentaje el
   riesgo es bajo, pero es un paso a ciegas.

## Siguiente paso propuesto

Cablear `register_payment` y `sync_review_sales` desde el producto (heredado 11), que es lo único
que impide que el ciclo cobro → elegibilidad → 1% → aprobación → pago sea alcanzable sin el
capturador sintético.
