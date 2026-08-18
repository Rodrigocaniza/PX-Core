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

## Paso 5 — siembra de la fijación de tasa por período (generación 6)

`_backfill_rated_periods` siembra `commission_rated_periods`, una fila por período, con
`INSERT OR IGNORE` sobre la clave primaria. Es aditiva e idempotente: no actualiza filas
existentes y correr la migración otra vez no cambia nada.

**Una migración no puede inventar una tasa.** Por eso sólo cuenta como evidencia una liquidación
que reúne las tres condiciones a la vez:

* está en `APROBADA` o `PAGADA` —el mismo boundary económico que fija en caliente—;
* lleva política canónica y una tasa concreta;
* su venta de origen no está anulada.

Las reglas que la siembra respeta sin excepción:

| Regla | Qué significa |
|---|---|
| **No inventa** | un período sin ninguna evidencia oficial no se siembra: queda **sin fijar** y por lo tanto corregible, que es el estado correcto para algo que nadie avaló |
| **No desempata a ciegas** | si el mismo período muestra tasas oficiales distintas, la evidencia es discrepante y no se fija nada: elegir una sería decidir por el propietario cuál de dos importes ya avalados es el bueno |
| **No toca dinero** | no escribe una sola vez sobre `commission_entries`: ni importes, ni tasas, ni aprobaciones, ni pagos |
| **Es idempotente** | `INSERT OR IGNORE` por período; ni la siembra ni el descarte se re-asientan si su asiento ya existe |
| **Es auditable** | todo período sembrado deja `COMMISSION_PERIOD_RATE_SEEDED` y todo período descartado deja `COMMISSION_PERIOD_RATE_SEED_SKIPPED` con su motivo, en `central_audit` |

A igualdad de evidencia, un pago manda sobre una aprobación —es el hecho más fuerte del mes— y a
igualdad de fuerza gana el más antiguo, para que el resultado no dependa del orden de lectura.

**Qué cambió respecto de la generación 5 y por qué.** La siembra anterior miraba `rate_bp IS NOT
NULL` y agrupaba por período tomando la liquidación **más antigua**, sin mirar su estado ni su
venta. De ahí salió `AB1-g5`: un mes pagado dos veces al 5% quedaba fijado al 1% desde una
liquidación `REVERTIDA` cuya venta estaba anulada, bajando una `APROBADA` de 500.000 a 100.000 Gs.
y borrándole el aval, sin una sola fila de auditoría. Ahora la siembra depende del mismo hecho
económico que la fijación en caliente, y no del orden de creación.
