# Evidencia de pruebas

Regresión completa: **456/456 PASS** (`python -m pytest -q`). El tiempo de reloj depende de la
máquina y no se declara: no es una propiedad del código.
Línea base de la misión anterior: 302. Esta misión suma **154**: 150 de dominio y 4 de interfaz.

Suite del módulo: `tests/gestion_central/` **256/256 PASS**.
Los siete archivos de comisiones juntos (`test_comisiones.py`,
`test_comisiones_ui_interactions.py`, `test_comision_rate_boundary.py` —generación 6—,
`test_comision_period_unpin.py` —generación 7—, `test_comision_legacy_facts.py` —generación 8—,
`test_comision_rate_coherence.py` —generación 9— y `test_comision_reconcile_reach.py`
—generación 10—): 51 → **205** casos, 112 + 8 + 24 + 23 + 14 + 13 + 11 respectivamente.

Todas las cifras anteriores son **casos ejecutados**, que es lo que cuenta pytest. En funciones:
`test_comisiones.py` pasa de 47 a 94 —se agregan 48 y se elimina
`test_policy_is_synthetic_pending_approval_and_optional`, que afirmaba lo contrario de la decisión
aprobada—, y seis de ellas están parametrizadas, aportando 18 casos extra, de donde salen los 112.
La de interfaz pasa de 4 a 8 funciones y 8 casos. El archivo dirigido de la generación 6 aporta 24
funciones sin parametrizar y 24 casos.

De las 48 funciones nuevas de `test_comisiones.py`, **13 son de la generación 5** y cierran los dos
bloqueantes económicos que el Auditor abrió sobre la generación 4. Una de ellas es la matriz de
transiciones, parametrizada sobre 14 transiciones públicas.

La **generación 6** suma **26 casos** (371 → 395): las 24 pruebas dirigidas de
`test_comision_rate_boundary.py` y 2 de interfaz. Además reescribe 23 casos de la generación 5 al
contrato nuevo y retira 2 parametrizaciones —`CALCULADA` y `REVISADA` en
`test_a_rated_period_is_never_re_rated`— porque esos estados **dejaron de estar protegidos a
propósito**: son provisionales y deben poder corregirse.

La **generación 7** suma **23 casos** (395 → 418), todos en `test_comision_period_unpin.py`.

La **generación 8** suma **13 casos** (418 → 431), todos en `test_comision_legacy_facts.py`.

La **generación 9** suma **13 casos** (431 → 444), en 11 funciones —una parametrizada sobre tres
rutas— todos en `test_comision_rate_coherence.py`.

La **generación 10** suma **9 casos** (444 → 453), todos en `test_comision_reconcile_reach.py`.

## Generación 10 — cierre de L3-g9

Nueve pruebas dirigidas. Dos son **estructurales** y no de comportamiento, que es la novedad: una
comprueba que las cuatro funciones que escriben `commission_entries.status` reconcilian su período,
y otra que la lectura del libro existe en un solo sitio. Sostienen por construcción lo que el
invariante 10 afirmaba sin poder cumplir.

| Grupo | Qué demuestra | Pruebas |
|---|---|---|
| Garantía estructural | las cuatro rutas que escriben estado reconcilian; el libro se lee en un solo sitio | 2 |
| Las tres rutas que no pasan por `_set_status` | `recalculate`, la corrección de origen y la promoción a elegible reconcilian de verdad | 3 |
| Claves normalizadas | una clave con fecha completa no deja un período fantasma en la auditoría; `recalculate(period=…)` alcanza esas filas | 2 |
| Auditoría del conflicto | un conflicto nuevo del mismo mes sí se asienta; uno provocado en caliente lleva el nombre de quien lo provocó | 2 |

La **generación 11** suma **3 casos** (453 → 456): la guarda estructural reescrita sobre el árbol
sintáctico, su **autocomprobación** —los tres casos que evadían la versión textual deben ser
detectados— y el importe inventado que ya no llega al pago.

La guarda de la generación 10 era textual y el Librarian la desarmó: buscaba una cadena exacta, de
modo que partir el literal SQL en dos la evadía; comprobaba el nombre del reconciliador como
subcadena, de modo que un comentario bastaba; y leía un solo fichero. La de la 11 recorre el árbol
sintáctico de todos los módulos, cubre `UPDATE` e `INSERT`, exige una llamada real y declara sus dos
exenciones con motivo. **Verificada contra el módulo real**: inyectar un escritor con el literal
partido y sin reconciliar hace que la reporte por nombre.

## Generación 9 — cierre de AB1-g8

13 pruebas dirigidas. El escenario base es la instalación del piloto con políticas **por vendedora y
por local** —las que la migración retira por diseño—, que deja dos liquidaciones canónicas del mismo
mes a tasas distintas: una aprobada al 9% y un pago vivo al 7%.

| Grupo | Qué demuestra | Pruebas |
|---|---|---|
| La regla de decisión | `resolve_period_rate` es pura y única: sin hechos no hay tasa, con tasas distintas no elige, a igualdad manda el pago y luego el más antiguo; y un solo sitio decide y un solo sitio escribe | 2 |
| El pin nunca contradice sus hechos | mientras la evidencia discrepe no se forma pin; el sobrepago queda eliminado; las rutas de `AB1-g6` no reaparecen sobre la base discrepante; un pin sostenido por su misma tasa no se mueve; una `PAGADA` canónica viva no suelta jamás | 7 |
| La apertura aplica la misma regla | una fijación heredada sin hecho vivo se retira; un pin a una tasa que ningún hecho lleva se corrige; reabrir no escribe nada nuevo; la migración no toca importes | 4 |

**La prueba decisiva se verificó contra la regla anterior.** `test_un_pin_a_una_tasa_que_ningun_hecho_lleva_se_corrige_al_abrir`
importa el estado exacto que la generación 8 dejaba clavado —libro al 100%, único hecho vivo pagado
al 7%— y da `10000` con la regla vieja y `700` con la nueva. Una prueba que pasa en los dos sentidos
no demuestra nada.

**La tasa del escenario es 7%, no 1%, y es correcto.** El mes tiene un pago real vivo al 7%: la
decisión de propietario dice que una `PAGADA` viva conserva la tasa con la que fue pagada. Tres
ventas de 10.000.000 Gs liquidan **2.100.000 Gs** —el 7% que ese mes sí pagó— y no los 30.000.000 Gs
de la generación 8. El 1% gobierna los meses sin tasa histórica viva que preservar.

## Generación 8 — cierre de AB1-g7 y L1-g7

`tests/gestion_central/test_comision_legacy_facts.py`, 13 pruebas dirigidas. El escenario base es
una base del piloto con **una comisión ya pagada** antes de la política aprobada: la forma mínima
que produce la migración oficial sobre cualquier instalación que haya pagado alguna vez.

| Grupo | Qué demuestra | Pruebas |
|---|---|---|
| La comisión legada no es un hecho oficial | ni al migrar ni en caliente; el sobrepago reaparecido queda eliminado; su importe no se toca nunca; una base migrada no nace violando el invariante; y una `PAGADA` **canónica** sí sostiene su mes | 6 |
| Un solo predicado | migrar y operar coinciden; la migración reevalúa un período suelto; un período ya fijado no se resiembra; un `period` de diez caracteres se empareja igual | 4 |
| Un solo escritor | el `UNPINNED` nombra la liquidación retirada; hay un único `INSERT` y ningún `UPDATE` ni `DELETE` sobre el libro en todo el código | 2 |
| Coherencia del recálculo | `recalculate` converge en una sola pasada y no deja un rechazo intermedio | 1 |

**Las cuatro pruebas del primer grupo que cubren `AB1-g7` se verificaron contra el predicado
anterior**: fallan con el `LIVE_OFFICIAL_FACT_SQL` de la generación 7 y pasan con el de la 8. Una
prueba que pasa en los dos sentidos no demuestra nada, y esta suite existe precisamente porque el
fuzz desde bases frescas no podía ver el defecto.

## Generación 7 — cierre de AB1-g6

`tests/gestion_central/test_comision_period_unpin.py`, 23 pruebas dirigidas. El escenario base es
el del Auditor: una tasa promocional del 100% con un cero de más, aprobada sobre una venta de
10.000.000 Gs.

| Grupo | Qué demuestra | Pruebas |
|---|---|---|
| Fijación | una `APROBADA` fija el período | 1 |
| La fijación no cuelga de una liquidación | con dos aprobaciones, revertir una no suelta nada | 1 |
| Retirar el último hecho suelta | revertir la última `APROBADA` escribe `UNPINNED` y el mes vuelve a resolverse por catálogo | 1 |
| `PAGADA` viva nunca suelta | observar y anular la venta después de pagada no sueltan; revertir una `PAGADA` ni siquiera es transición legal | 2 |
| Cobro rechazado | el cheque que rebota después de aprobar suelta el período: no salió un guaraní y no hay nada que proteger | 1 |
| `void_sale` | anular la venta del último hecho suelta el mes — regla aprobada 8 | 1 |
| `observe` + `revert` | observar ya retira el hecho; revertir después no escribe un segundo evento | 1 |
| Idempotencia | encadenar transiciones deja un solo `UNPINNED`; repetir la anulación es un no-op sin rastro nuevo; una transición inválida no mueve el libro | 3 |
| Refijación | el hecho oficial siguiente vuelve a fijar, y los provisionales entre medio siguen sin fijar | 2 |
| Trazabilidad | `PINNED → UNPINNED → PINNED` completo, con tasa, origen, liquidación causante, razón, actor y fecha, y los tres en `central_audit` | 1 |
| Dinero intacto | soltar no toca importe ni aval; una `PAGADA` de otra liquidación impide el unpin por construcción | 2 |
| Migración | no escribe ningún `UNPINNED`; migrar y operar coinciden; sigue sin inventar ni desempatar; reabrir es idempotente; la fila legada sigue intacta | 4 |
| Regla aprobada 8 | una venta anulada de una base legada no llega al pago | 1 |
| El daño medido | el sobrepago de 9.900.000 Gs por venta queda eliminado, y el subpago de la dirección contraria también | 2 |

La generación 7 además reescribe 5 casos de la 6: los cuatro de la matriz de transiciones cuyo
sujeto era la propia liquidación que sostenía el pin —ahora la matriz separa el ancla del sujeto,
que es lo que le devuelve su pregunta original— y
`test_the_durable_evidence_has_no_public_eraser`, cuya premisa cambió: ahora **sí** existe una
operación pública que suelta un período, pero no borra ni reescribe nada.

## Generación 5 — cierre de B1-g4 y B2-g4

La protección de un período tarifado deja de ser un predicado sobre el estado actual y pasa a ser
evidencia durable en `commission_rated_periods`. Publicar ya no se bloquea.

### B1-g4: ninguna transición posterior reabre un período tarifado

| Prueba | Qué demuestra |
|---|---|
| `test_no_public_transition_reopens_a_rated_period[14 transiciones]` | **La matriz.** Sobre el período `2099-04` ya tarifado se aplica cada transición pública que saca —o podría sacar— la liquidación de los estados liquidados: `observe` desde los cuatro, `revert` desde tres, `void_sale` desde tres, corrección de sobre, corrección de total, reapertura de saldo y cobro adicional. Tras cada una se intenta imponer un 100% sobre el mismo período y se comprueba que **una venta nueva de ese mes sigue comisionando al 1%**. La prueba mira el dinero, no sólo la marca. |
| `test_observing_a_paid_settlement_does_not_reopen_its_period` | La fuga literal del Auditor: `observe()` sobre una PAGADA ya no permite que la segunda vendedora del mes cobre 400.000 donde el 1% son 4.000. |
| `test_the_durable_evidence_has_no_public_eraser` | La evidencia es append-only: revisar, observar, publicar otra tasa y recalcular tres veces no la borran ni la reescriben. |
| `test_a_rate_effective_on_the_same_date_never_re_rates_what_was_already_rated` | Publicar 40% y luego 0% con la vigencia igual **se acepta** y no mueve nada; la aprobada sigue pagable a su importe. |
| `test_a_rated_period_is_never_re_rated[CALCULADA\|REVISADA\|APROBADA\|PAGADA]` | Los cuatro estados resisten tres publicaciones retroactivas cada uno, con recálculo entre medias. |
| `test_a_rate_effective_before_the_last_published_one_is_rejected` | La única guarda que queda: la vigencia no puede retroceder. |

### Hallazgo 25: sin frontera global por `MAX(period)`

| Prueba | Qué demuestra |
|---|---|
| `test_a_rated_period_does_not_block_a_later_effective_date` | `2099-07` tarifado no impide publicar para `2099-08` ni para `2100-01`; el mes siguiente cobra de verdad la tasa nueva. |
| `test_a_far_future_typo_does_not_freeze_any_intermediate_period` | Una venta fechada por error en `2136` protege `2136-04` y **nada más**: se publican diez vigencias intermedias y un período de `2105` cobra la tasa que le corresponde. |
| `test_protection_is_per_period_and_never_a_global_maximum` | Con `2099-04` y `2101-09` tarifados, el hueco intermedio **no** está protegido: se publica y rige; los dos extremos siguen intactos. |
| `test_a_settled_but_unrated_period_protects_nothing` | Un período `CALCULADA` anterior a la vigencia, sin tasa aplicada, no fija nada. |

### B2-g4: la corrección de origen también deja rastro

| Prueba | Qué demuestra |
|---|---|
| `test_a_source_correction_records_the_amount_it_annuls` | Una corrección cosmética de sobre asienta `replaced` con los 4.000 y el 1% retirados. |
| `test_a_source_correction_on_migrated_data_records_the_legacy_amount` | El caso que motivaba el bloqueante: 33.250 Gs heredados, sin asiento previo, quedan registrados. |
| `test_a_source_correction_without_a_previous_amount_records_nothing` | Sin importe anterior el bloque no se inventa. |
| `test_repeated_source_corrections_keep_every_annulled_amount` | Dos correcciones dejan dos asientos; reaplicar la misma no añade un tercero. |
| `test_a_correction_that_reopens_the_balance_records_the_previous_amount` | Reabrir el saldo anula la comisión y asienta lo retirado. |
| `test_a_recalculation_down_to_zero_records_the_previous_amount` | Importe anterior distinto de cero y resultado **cero**: el retirado se asienta igual. Desde la generación 6 el mes sigue **sin fijar**, porque recalcular es provisional. |

La exactitud monetaria no se toca: `comision_policy.py` no cambia, el único `HALF_UP` sigue donde
estaba, y las pruebas de redondeo de la generación 3 siguen en verde sin retoques.

> **Advertencia añadida al registrar la generación 5 — resuelta en la 6.** La tabla de arriba era
> cierta en lo que afirmaba, pero el Auditor demostró que no cubría el caso completo: la fecha
> errónea ya no congelaba la publicación, pero **fijaba ese mes para siempre y lo hacía pagar mal
> en silencio**, incluso después de que el propio sistema registrara por dos vías que fue un error
> (`AB2-g5`). Ninguna prueba de la generación 5 cubría lo que ocurre *después* de que un pin se
> graba mal, ni por la ruta del tipeo ni por la de la siembra de la migración (`AB1-g5`).
>
> La generación 6 elimina la premisa en vez de tapar el síntoma: **un cálculo ya no graba un pin**,
> así que no hay «después de que un pin se graba mal» por la ruta del tipeo. Y la siembra de la
> migración deja de depender del orden de creación. Lo cubre `test_comision_rate_boundary.py`,
> abajo.

## Generación 6 — cierre de AB1-g5, AB2-g5, QB1-g5 y QB2-g5

`tests/gestion_central/test_comision_rate_boundary.py`, 24 pruebas dirigidas, agrupadas por el
invariante que defienden y no por el método que llaman.

| Grupo | Qué demuestra | Pruebas |
|---|---|---|
| Comisión provisional sin tasa fijada | calcular y revisar no fijan el período: no escriben ningún evento | 2 |
| Corrección de estados provisionales | publicar y recalcular corrige un mes sólo calculado; un tipeo de fecha no fija nada; anular tras calcular tampoco (`AB2-g5`) | 3 |
| Fijación en el boundary oficial | `APROBADA` fija; `PAGADA` fija; una publicación posterior ya no re-tarifa; observar o revertir después no desfija | 4 |
| Dinero aprobado o pagado no se reinterpreta | recálculo con `changed == 0` sobre una `APROBADA` fijada; `PAGADA` fuera de todo recálculo; una venta nueva del mes cobra la tasa fijada | 3 |
| Migración segura (`AB1-g5`) | no siembra desde `REVERTIDA`; no siembra desde venta anulada; no inventa tasa para un mes sólo provisional; no desempata evidencia discrepante; no toca importes ni avales; asienta cada período sembrado; es idempotente y no duplica su auditoría | 7 |
| Reintentos e idempotencia | dos aprobaciones del mismo mes dejan una sola fijación y un solo asiento; aprobar y luego pagar también | 2 |
| Auditoría | `COMMISSION_PERIOD_RATE_PINNED` con período, tasa, boundary, liquidación y traza de política | 1 |
| Rotulado (`QB1-g5`, `QB2-g5`) | el export no emite `None%` y distingue tasa fijada de provisional | 2 |

Las dos pruebas de interfaz nuevas viven en `test_comisiones_ui_interactions.py`:

- `test_the_header_says_whether_the_rate_is_fixed_or_still_provisional`.
- `test_a_period_without_a_rate_in_force_is_never_labelled_with_the_global_policy` — comprueba
  además que el rótulo **no contiene ningún `%`** cuando no rige tasa alguna, que es la forma
  directa de negar `QB1-g5`.

## Validaciones dirigidas exigidas por la misión

| Validación | Prueba |
|---|---|
| Venta común 400.000 cancelada → 4.000 | `test_a_cancelled_common_sale_of_400000_commissions_exactly_4000` |
| Venta común con saldo → comisión pagable 0 | `test_a_common_sale_with_balance_has_zero_payable_commission` |
| Convenio 500.000 → 25.000 / 475.000 / 4.750 | `test_an_agreement_of_500000_discounts_25000_and_commissions_4750` |
| Mismo 1% para toda vendedora y local | `test_the_same_one_percent_applies_to_every_saleswoman_and_branch` |
| Recalcular no duplica | `test_recalculating_never_duplicates_and_never_reapplies` |
| `PAGADA` no cambia en silencio | `test_a_paid_settlement_is_never_touched_by_a_policy_change` |
| Anulación/reversión conserva auditoría | `test_voiding_and_reverting_keep_the_audit_trail_of_the_policy` |
| Redondeo `HALF_UP` probado | `test_half_up_rounding_to_whole_guarani_is_explicit` |
| Persistencia y reapertura | `test_the_official_commission_survives_reopening_the_database` |
| Interfaz correcta | `test_the_screen_names_the_official_one_percent_policy` |
| Export correcto | `test_structured_export_has_stable_contract_and_no_customer_data` |
| Un porcentaje retirado nunca se paga | `test_a_retired_rate_can_never_be_paid_through_the_normal_flow` |
| La reparación existe y no destruye la comisión | `test_recalculating_repairs_a_retired_rate_and_withdraws_its_approval` |
| Programar la vigencia siguiente no borra el mes en curso | `test_scheduling_the_next_rate_never_touches_the_current_period` |
| Una versión superada nunca se paga | `test_a_settlement_calculated_under_an_older_version_is_never_paid` |
| Ninguna liquidación legada queda varada | `test_a_legacy_settlement_without_any_rate_is_repaired_too` |
| El KPI oficial no suma importes de otra política | `test_the_official_kpi_never_counts_an_amount_from_a_retired_policy` |

## Pruebas nuevas de dominio de las generaciones 1 a 3 (25 funciones, 28 casos)

1. `test_the_official_policy_is_the_approved_general_one_percent` — 1%, alcance único `GENERAL`,
   estado `CANONICA_APROBADA`, versión 1, vigencia, redondeo, moneda, y ninguna etiqueta retirada.
2. `test_a_cancelled_common_sale_of_400000_commissions_exactly_4000`.
3. `test_a_common_sale_with_balance_has_zero_payable_commission` — incluye el cobro parcial
   posterior, que sigue sin generar comisión.
4. `test_an_agreement_of_500000_discounts_25000_and_commissions_4750` — orden 5% → 1%.
5. `test_the_same_one_percent_applies_to_every_saleswoman_and_branch` — tres locales, tres
   vendedoras, un único `rate_bp` y un único importe.
6. `test_the_policy_used_is_traceable_on_every_settlement` — los cinco campos de traza, el bloque
   `policy` del desglose, la línea «Comisión oficial (1,00%…)» y la política en el historial.
7. `test_a_period_before_the_effective_date_never_applies_the_rate` — `FUERA_DE_VIGENCIA` y
   rechazo de `review`.
8. `test_half_up_rounding_to_whole_guarani_is_explicit` — 0,50→1; 1,50→2; 0,49→0; 12.345,67→12.346,
   más el mismo borde extremo a extremo por el servicio.
9. `test_recalculating_never_duplicates_and_never_reapplies` — cuatro recálculos, dos asientos
   de historial.
10. `test_a_paid_settlement_is_never_touched_by_a_policy_change` — se publica la versión 2 al 2% y
    la `PAGADA` conserva importe, `rate_bp`, `policy_version` y hasta su `updated_at`.
11. `test_publishing_a_policy_version_is_audited_and_idempotent` — idempotencia, versionado,
    porcentaje y vigencia inválidos, y el asiento de auditoría.
12. `test_voiding_and_reverting_keep_the_audit_trail_of_the_policy`.
13. `test_the_official_commission_survives_reopening_the_database` — reabrir no duplica ni cambia.
14. `test_migration_retires_the_synthetic_label_without_touching_money`.
15. `test_a_retired_rate_can_never_be_paid_through_the_normal_flow[REVISADA]` y `[APROBADA]` — el
    paso siguiente de la cadena de pago se corta en cada punto de entrada posible, y el desglose no
    llama «oficial» a un porcentaje retirado.
16. `test_recalculating_repairs_a_retired_rate_and_withdraws_its_approval[REVISADA]` y `[APROBADA]`
    — 33.250 → 4.750, vuelta a `CALCULADA`, revisión y aprobación retiradas, importe reemplazado en
    el historial bajo `COMMISSION_POLICY_REPAIRED`, idempotencia, y la cadena rehecha hasta el pago
    con el importe correcto.
17. `test_a_paid_legacy_settlement_keeps_its_amount_and_is_never_repaired` — lo que ya movió dinero
    conserva su importe histórico y `recalculate` no lo alcanza.
18. `test_a_complete_trace_means_a_policy_evaluated_it_and_an_empty_one_means_none_did` — los
    **cuatro** estados de política conviviendo en una misma base, con una liquidación pagada que
    conserva importe y traza vacía, que es el caso por el que el invariante existe.
19. `test_scheduling_the_next_rate_never_touches_the_current_period` — se publica la vigencia del
    año siguiente y el mes en curso no cambia; la venta del período nuevo sí toma el porcentaje
    nuevo.
20. `test_a_policy_version_can_never_re_rate_a_closed_period` — la vigencia no retrocede.
21. `test_a_settlement_calculated_under_an_older_version_is_never_paid` — deriva de versión: el
    sello `CANONICA_APROBADA` no alcanza; se rechaza el pago y `recalculate` repara.
22. `test_a_legacy_settlement_without_any_rate_is_repaired_too[REVISADA]` y `[APROBADA]` — el
    estado por defecto del piloto anterior, que nunca sembró política, tampoco queda varado.
23. `test_recalculate_never_reaches_anything_that_moved_money` — `paid_at IS NULL` sobre el `WHERE`
    entero, verificado con un estado que la API pública no puede producir.
24. `test_the_official_kpi_never_counts_an_amount_from_a_retired_policy` — separación de
    `commission_amount` y `non_official_amount` en el reporte y en el export; `paid_amount` sí
    incluye lo pagado, porque ese dinero salió.

Y la vigesimoquinta, `test_the_retired_label_survives_only_as_the_thing_the_migration_removes`,
que verifica sobre el fuente que `SINTETICA_PENDIENTE_APROBACION` no aparece en `comisiones.py`, `comisiones_ui.py` ni
`repository.py`, y que en `comision_policy.py` figura una sola vez, dentro de
`RETIRED_POLICY_STATUSES`. Reemplaza a `test_policy_is_synthetic_pending_approval_and_optional`,
que afirmaba lo contrario y ya no puede ser cierto.

## Pruebas nuevas de interfaz (2)

`test_the_screen_names_the_official_one_percent_policy` — encabezado con porcentaje, código,
versión, vigencia y redondeo; KPI `COMISIÓN OFICIAL 1,00%`; columnas tituladas «Comisión» a secas,
porque una fila puede arrastrar un importe que no es el 1%; el aviso oculto cuando no hay ninguno;
y la fila de una venta cancelada mostrando base 300.000 y comisión 3.000 sin abrir el desglose.

`test_the_screen_never_calls_official_an_amount_from_a_retired_policy` — con una liquidación legada
pagada al 7% en la misma bandeja: el KPI oficial marca 3.000 y no 36.250, el aviso aparece con los
33.250 separados, el resumen por vendedora no los mezcla y el desglose los rotula «no pagable».

## Pruebas preexistentes actualizadas

- `test_amounts_stay_integers_end_to_end`: sin `set_policy`; el 1% sobre 316.666 da 3.167.
- `test_source_correction_before_review_recomputes_the_whole_base`: 855.000 → 8.550.
- `test_an_agreement_total_can_be_corrected_downwards`,
  `test_source_correction_after_review_never_pays_a_stale_base`: se retira el `set_policy` sintético.
- `test_structured_export_has_stable_contract_and_no_customer_data`: `contract_version: 2`, bloque
  `policy` completo y los cuatro campos de traza en cada entrada.
- `test_navigation_filters_and_state_reasons` y `test_observe_revert_recalculate_and_export`: el
  desglose del convenio ahora tiene cuatro líneas y el export lleva la política.

La generación 4 modifica **una sola** prueba, y era propia de esta misión, no heredada:

- `test_a_settlement_calculated_under_an_older_version_is_never_paid` (añadida en la generación 3
  para el bloqueante G2-A1). Construía la deriva de versión publicando una tasa que gobernaba un
  período ya liquidado. Desde la generación 5 esa deriva no es alcanzable publicando sobre un
  período fijado —y desde la generación 6 «fijado» significa que una liquidación suya alcanzó
  `APROBADA` o `PAGADA`—, así que la prueba conserva su intención —una liquidación con sello
  desfasado no llega al pago— y reconstruye el estado borrando la evidencia del período con
  `clear_rated_periods`, que es como llega una base migrada de una instalación anterior. La
  aserción de excepción que tuvo en la generación 4 **ya no existe**: publicar dejó de rechazarse.

La generación 5 modifica seis pruebas, todas propias de esta misión y ninguna heredada, porque
el contrato que verificaban cambió por decisión de propietario:

- `test_a_rate_effective_on_the_same_date_never_re_rates_what_was_already_rated` y
  `test_a_rated_period_is_never_re_rated` (antes
  `test_a_rate_effective_on_the_same_date_as_the_last_one_is_rejected` y
  `test_a_settled_period_is_never_re_rated`):
  publicar dejó de rechazarse, así que ahora asertan lo que de verdad protege —que el período
  tarifado no se mueve— en lugar de la excepción. La intención económica es la misma y **más
  fuerte**: antes comprobaban que la operación fallaba, ahora que el dinero no cambia.
- `test_a_settlement_calculated_under_an_older_version_is_never_paid` y
  `test_a_replaced_amount_is_recorded_when_a_rate_changes_before_review`: la deriva de versión ya no
  es alcanzable publicando, así que reconstruyen el estado borrando la evidencia del período, que es
  como llega una base migrada de una instalación anterior. La guarda de pago sigue verificándose.
- `test_structured_export_has_stable_contract_and_no_customer_data` y
  `test_observe_revert_recalculate_and_export`: el export sube a `contract_version: 3`.

Todas las demás pruebas de la misión anterior siguen intactas y en verde: los quince bloqueantes
financieros históricos y los cinco invariantes económicos continúan cubiertos por sus pruebas
originales, sin retoques.

## Fuera de alcance

No se corrigieron los hallazgos no bloqueantes heredados del handoff anterior. Siguen abiertos y
registrados; ver `HANDOFF.md`.
