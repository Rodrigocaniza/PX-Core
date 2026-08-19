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

## Paso 5 — reconciliación del libro de tasas por período (generación 9)

`_backfill_period_rate_events` ya no es una siembra aparte: recorre cada período que tenga hechos
vivos o que ya tenga libro y llama a `reconcile_period_rate`, **exactamente la misma función que
corre en cada transición**. Es idempotente: si el libro ya dice lo que la regla dice, no escribe
nada, y reabrir la base mil veces deja lo mismo que abrirla una.

Que la apertura y el runtime tuvieran reglas distintas costó un bloqueante económico por
generación: `AB1-g6`, `AB1-g7` y `AB1-g8`. Aquí no hay dos reglas que puedan separarse.

**Una migración no puede inventar una tasa.** Por eso sólo cuenta como evidencia una liquidación
que reúne las tres condiciones a la vez:

* sostiene un **hecho económico vivo**: está en `APROBADA` o `PAGADA` sobre una venta no anulada,
  o conserva `paid_at`, que significa que el dinero salió de verdad;
* lleva política canónica y una tasa concreta;
* y se evalúa con **exactamente el mismo SQL que el código en caliente**,
  `comision_policy.LIVE_OFFICIAL_FACT_SQL`, emparejando el período con `PERIOD_MATCH_SQL`. No son
  dos textos equivalentes: es uno solo. Tenerlo escrito dos veces falló dos generaciones seguidas
  —en la 6 la migración excluía las `REVERTIDA` y el código no; en la 7 la migración exigía política
  canónica y el código no, que fue `AB1-g7`—.

**Todo período vuelve a evaluarse**, tenga el libro que tenga. Uno cuyo último evento es `UNPINNED`
se fija si la base trae evidencia viva; uno fijado a una tasa que ninguno de sus hechos vivos lleva
—el estado que dejaba la generación 8— se suelta y se vuelve a fijar con la que sus hechos sí
sostienen. No es inventar nada: que un pin no esté respaldado es **observable**, y aplicar la regla
a una observación es lo mismo que hace cada transición. Los retiros escritos aquí llevan
`origin='MIGRACION'` para distinguirse de los operativos.

Las reglas que la siembra respeta sin excepción:

| Regla | Qué significa |
|---|---|
| **No inventa** | un período sin evidencia oficial viva no se siembra: queda **sin fijar** y por lo tanto corregible, que es el estado correcto para algo que hoy nadie avala |
| **No inventa retiradas** | **no escribe un solo `UNPINNED`**. Una fijación de la generación 5 o 6 que hoy no tiene evidencia viva simplemente no se siembra, y queda asentada como descartada con motivo `SIN_HECHO_ECONOMICO_VIVO`. Afirmar que fue «retirada» sería inventar un hecho que nadie produjo |
| **No desempata a ciegas** | si el mismo período muestra tasas oficiales distintas, la evidencia es discrepante y no se fija nada: elegir una sería decidir por el propietario cuál de dos importes ya avalados es el bueno |
| **No toca dinero** | no escribe una sola vez sobre `commission_entries`: ni importes, ni tasas, ni aprobaciones, ni pagos |
| **Es idempotente** | sólo mira períodos cuyo último evento no sea ya `PINNED`, y ni la siembra ni el descarte se re-asientan si su asiento ya existe. No hay `INSERT OR IGNORE`: el libro usa `INSERT` normal y la idempotencia sale de consultar el estado, que además no oculta violaciones de esquema |
| **Es auditable** | todo período sembrado deja `COMMISSION_PERIOD_RATE_SEEDED` y todo período descartado deja `COMMISSION_PERIOD_RATE_SEED_SKIPPED` con su motivo, en `central_audit` |

A igualdad de evidencia, un pago manda sobre una aprobación —es el hecho más fuerte del mes— y a
igualdad de fuerza gana el más antiguo, para que el resultado no dependa del orden de lectura.

La tabla `commission_rated_periods` de la generación 5 queda **congelada**: no se escribe y no se
borra. Sí se lee, en un único sitio y para un único fin: asentar como descartada toda fijación
heredada que hoy no tenga un hecho vivo detrás. Así una base que venía con una fijación
injustificada la pierde al migrar —que es la corrección de `AB1-g6` aplicada hacia atrás— sin que
nada de lo que el sistema afirmó alguna vez desaparezca.

**Qué cambió respecto de la generación 5 y por qué.** La siembra de entonces miraba `rate_bp IS NOT
NULL` y agrupaba por período tomando la liquidación **más antigua**, sin mirar su estado ni su
venta. De ahí salió `AB1-g5`: un mes pagado dos veces al 5% quedaba fijado al 1% desde una
liquidación `REVERTIDA` cuya venta estaba anulada, bajando una `APROBADA` de 500.000 a 100.000 Gs.
y borrándole el aval, sin una sola fila de auditoría. La generación 6 lo corrigió apoyándose en el
boundary; la 7 completa la corrección exigiendo que el hecho siga **vivo**.
