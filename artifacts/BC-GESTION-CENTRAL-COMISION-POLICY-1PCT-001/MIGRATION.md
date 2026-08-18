# Migración

`CentralRepository._migrate_commission_policy` corre dentro de `migrate()`, en la misma
transacción que el resto del esquema, cada vez que se abre la base. Es idempotente y **no toca
dinero**.

## Pasos

1. **Columnas aditivas** (`_add_missing_columns`). Siete columnas nuevas sobre dos tablas
   existentes, más la tabla `commission_policy_versions`. Las tres de `commission_policies` son
   `NOT NULL` con `DEFAULT`; las cuatro de traza en `commission_entries` son anulables y se añaden
   sin `DEFAULT`, porque una liquidación aún sin recalcular no tiene traza que declarar. Una base
   ya migrada las tiene y el paso se saltea.
2. **Retiro de políticas superadas.** Toda fila de `commission_policies` con una etiqueta retirada
   o con alcance distinto de `GENERAL` se asienta en `central_audit` como
   `COMMISSION_POLICY_RETIRED`, con su `rate_bp` y su estado anteriores. Las de alcance
   `VENDEDORA` o `LOCAL` se eliminan: contradicen la decisión aprobada de un mismo 1% para todas.
   Nada desaparece en silencio — el valor previo queda en la auditoría.
3. **Instalación de la política canónica.** Si no hay una `GENERAL` con estado
   `CANONICA_APROBADA`, se inserta (o se actualiza por `ON CONFLICT(scope, scope_value)`) con
   `rate_bp = 100`, `code = COMISION_GENERAL_1PCT`, `version = 1`,
   `effective_from = 2026-08-01`, `created_by = MIGRACION`. La fila de versión se asienta con
   `INSERT OR IGNORE` sobre `UNIQUE(policy_id, version)`, de modo que reabrir la base no duplica
   versiones.
4. **Retiro de la etiqueta en las liquidaciones.** Una liquidación con etiqueta retirada y
   `rate_bp` no nulo pasa a `POLITICA_HISTORICA_PREVIA`; con `rate_bp` nulo, a
   `SIN_POLITICA_APLICADA`. **`rate_bp` y `commission_amount` no se tocan.**

## Qué le pasa a cada liquidación existente

| Estado previo | Efecto de la migración | Efecto del primer `recalculate` |
|---|---|---|
| `ELEGIBLE` / `CALCULADA` con 3% sintético | etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto | pasa al 1% oficial con traza completa |
| `ELEGIBLE` / `CALCULADA` sin porcentaje | etiqueta → `SIN_POLITICA_APLICADA` | pasa al 1% oficial |
| `REVISADA` / `APROBADA` con importe histórico | etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto | **reparada**: vuelve a `CALCULADA` al 1%, y pierde revisión y aprobación |
| `REVISADA` / `APROBADA` sin porcentaje | etiqueta → `SIN_POLITICA_APLICADA` | **reparada** igual: es el estado por defecto del piloto, que nunca sembró política |
| `PAGADA` | etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto | **no alcanzada**: ya movió dinero |
| `OBSERVADA` / `REVERTIDA` | ídem | **no alcanzada** |

Si el período de la liquidación es anterior a la vigencia, la reparación no la lleva al 1%: la deja
`CALCULADA` con `FUERA_DE_VIGENCIA`, sin importe y no pagable, con el importe anterior asentado en
el historial. Es el mismo criterio que para una venta nueva de ese período —no se aplica el
porcentaje hacia atrás— y no un caso especial de la migración.

## El importe histórico nunca es pagable

Entre la migración y el primer recálculo, una `REVISADA` o `APROBADA` legada conserva su importe
histórico —que puede ser varias veces el oficial, o ninguno—. **No es pagable en ese estado**:
`review`, `approve` y `mark_paid` exigen que el importe lleve la política que rige hoy su período y
la rechazan. El desglose la rotula «Comisión con política anterior (no pagable)», su nota indica
recalcular, y los agregados de la bandeja la informan aparte de la comisión oficial.

La reparación la hace `recalculate`, que alcanza `REVISADA` y `APROBADA` —nunca con `paid_at`, y
sólo cuando su importe no es ya el oficial—: las lleva al porcentaje vigente, las devuelve a
`CALCULADA` y **retira su revisión y su aprobación**, porque el importe que esos avales respaldaban
ya no existe. El importe reemplazado queda en el historial bajo `COMMISSION_POLICY_REPAIRED`.
Después se rehace la cadena sobre el importe correcto, sin perder la comisión.

Lo cubren `test_a_retired_rate_can_never_be_paid_through_the_normal_flow`,
`test_recalculating_repairs_a_retired_rate_and_withdraws_its_approval`,
`test_a_legacy_settlement_without_any_rate_is_repaired_too`,
`test_a_paid_legacy_settlement_keeps_its_amount_and_is_never_repaired` y
`test_recalculate_never_reaches_anything_that_moved_money`.

## Reversibilidad

El esquema es aditivo, así que una base migrada sigue siendo legible por el código anterior salvo
por las políticas de alcance eliminadas, cuyos valores quedaron en `central_audit`. No hay
`DROP`, no hay `ALTER` destructivo y no se reescribe ningún importe.

## Verificación

`test_migration_retires_the_synthetic_label_without_touching_money` reconstruye una base del
piloto anterior —3% sintético en la liquidación, política `GENERAL` sintética y una `VENDEDORA` al
5%—, la reabre y comprueba: una sola política `GENERAL` al 1%, el importe histórico de 14.250
intacto bajo `POLITICA_HISTORICA_PREVIA`, los dos retiros asentados en auditoría, y el recálculo
posterior trayéndola a 4.750 porque no estaba pagada.

`test_the_official_commission_survives_reopening_the_database` comprueba que reabrir vuelve a
migrar sin duplicar políticas ni versiones y sin cambiar nada (`changed == 0`).

## Paso 5 — evidencia durable de períodos tarifados (generación 5)

`_backfill_rated_periods` siembra `commission_rated_periods` desde las liquidaciones que ya llevan
`rate_bp` **y política canónica**, una fila por período, con `INSERT OR IGNORE` sobre la clave
primaria. Es aditiva e idempotente: no actualiza filas existentes y correr la migración otra vez no
cambia nada.

Sólo siembran las canónicas. Un importe heredado del piloto anterior lleva `POLITICA_HISTORICA_PREVIA`
y no es oficial: fijar el período con ese porcentaje lo volvería incorregible, que es lo contrario de
lo que la misión persigue. Esas liquidaciones siguen siendo reparables por `recalculate`, y al
repararse fijan el período con la tasa canónica que les corresponda.

Una base migrada puede traer liquidaciones cuyo estado ya cambió —observadas, revertidas— pero que
conservan su tasa: ésas **sí** siembran su período, que es justamente lo que la protección por estado
no veía. Las que ya perdieron la tasa por una corrección de origen no pueden sembrarse desde aquí;
desde la generación 5 su importe retirado queda en el asiento `SOURCE_UPDATED`.
