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

5. **La vigencia es de granularidad mensual aunque el parámetro sea una fecha completa.**
   `is_in_effect` compara `período >= effective_from[:7]`, así que una vigencia fijada al
   `2026-08-20` rige igual desde el `2026-08-01`. Está documentado, es coherente con la
   granularidad mensual del módulo, y la vigencia canónica es día 1; pero la API acepta un día que
   no se respeta.
6. **Una liquidación con importe no oficial ya pagada no tiene corrección.** `recalculate` no la
   alcanza —correctamente, porque el dinero salió— y `revert` está bloqueado. Es el mismo callejón
   que el hallazgo heredado 4 para la `OBSERVADA` pagada. Las **no** pagadas sí tienen salida.
7. **Una `OBSERVADA` legada conserva su importe no oficial indefinidamente.** No es pagable y los
   agregados la informan aparte, pero `recalculate` no la alcanza y la única salida pública,
   `revert`, no crea liquidación de reemplazo. Es el complemento del hallazgo heredado 4.
8. **`POLICY_STATUSES` se define y no se usa.** Es documentación ejecutable del conjunto de
   estados, pero ninguna guarda lo valida contra lo que se escribe en `policy_status`.
9. **El retiro de políticas por alcance es una eliminación de filas.** Queda auditada con su
   `rate_bp` previo en `central_audit`, que es suficiente para reconstruirla, pero la fila en sí
   no se conserva en `commission_policy_versions`.
10. **`set_general_rate` no ofrece una vista previa del impacto**, ni exige un permiso distinto del
    de pagar: el mismo principal publica el porcentaje y cobra con él. Con una sola política
    general y auditoría de cada publicación el riesgo es acotado, pero no hay separación de
    funciones ni segunda barrera para un 0% o un 100%.
11. **`cancelled_date` viaja siempre nulo en el contrato v2.** `ENTRY_EXPORT_FIELDS` lo declara,
    pero `list_entries` expone la fecha de la venta como `sale_cancelled_date`, así que el campo
    sale vacío en el 100% de las filas. Viene de la misión anterior y el contrato v2 lo arrastró.
12. **El chequeo de consistencia trata la generación en curso como revisada.** Calcula
    `reviewed = max(generation)` sin mirar `status`, de modo que su regla de «no anticipar la
    revisión en curso» queda inerte justo para la generación que se está revisando.
13. **Una corrección de origen sobre una `OBSERVADA` con importe no oficial lo borra sin
    registrarlo.** `_apply_source_update` no la considera un estado revisado, así que entra por la
    rama de recálculo y anula `rate_bp` y `commission_amount`; el asiento `SOURCE_UPDATED` guarda
    la base nueva pero no el importe reemplazado, a diferencia de `COMMISSION_POLICY_REPAIRED`.
14. **La nota de una `SIN_POLITICA_APLICADA` ya pagada invita a recalcular** aunque `recalculate`
    jamás la alcanzará. La rama `POLITICA_HISTORICA_PREVIA` sí distingue si movió dinero; esta no.

## Siguiente paso propuesto

Cablear `register_payment` y `sync_review_sales` desde el producto (heredado 11), que es lo único
que impide que el ciclo cobro → elegibilidad → 1% → aprobación → pago sea alcanzable sin el
capturador sintético.
