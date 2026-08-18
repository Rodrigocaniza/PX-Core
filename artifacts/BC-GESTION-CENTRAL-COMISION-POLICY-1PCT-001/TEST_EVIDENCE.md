# Evidencia de pruebas

Regresión completa: **371/371 PASS** (`python -m pytest -q`, 34,33 s).
Línea base de la misión anterior: 302. Esta misión suma **69**: 67 de dominio y 2 de interfaz.

Suite del módulo: `tests/gestion_central/` **171/171 PASS**.
Los dos archivos de comisiones juntos (`test_comisiones.py` + `test_comisiones_ui_interactions.py`):
51 → **120** pruebas, 114 y 6 respectivamente.

Todas las cifras anteriores son **casos ejecutados**, que es lo que cuenta pytest. En funciones:
`test_comisiones.py` pasa de 47 a 94 —se agregan 48 y se elimina
`test_policy_is_synthetic_pending_approval_and_optional`, que afirmaba lo contrario de la decisión
aprobada—, y seis de ellas están parametrizadas, aportando 20 casos extra, de donde salen los 114.
La de interfaz pasa de 4 a 6 funciones y 6 casos.

De esas 48 funciones nuevas, **13 son de la generación 5** y cierran los dos bloqueantes económicos
que el Auditor abrió sobre la generación 4. Una de ellas es la matriz de transiciones, parametrizada
sobre 14 transiciones públicas; con sus 13 casos extra suman los **26** casos nuevos de esta
generación (345 → 371).

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
| `test_a_recalculation_down_to_zero_records_the_previous_amount` | Importe anterior distinto de cero y resultado **cero**: el retirado se asienta igual, y el período queda fijado al 0% que de verdad se aplicó. |

La exactitud monetaria no se toca: `comision_policy.py` no cambia, el único `HALF_UP` sigue donde
estaba, y las pruebas de redondeo de la generación 3 siguen en verde sin retoques.

> **Advertencia añadida al registrar la generación 5.** La tabla de arriba es cierta en lo que
> afirma, pero el Auditor demostró que no cubre el caso completo: la fecha errónea ya no congela la
> publicación, pero **fija ese mes para siempre y lo hace pagar mal en silencio**, incluso después
> de que el propio sistema registre por dos vías que fue un error. Es el bloqueante `AB2-g5`.
> Ninguna prueba de esta generación cubre lo que ocurre *después* de que un pin se graba mal, ni
> por la ruta del tipeo ni por la de la siembra de la migración (`AB1-g5`).

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
  período ya liquidado. Desde la generación 5 esa deriva no es alcanzable publicando —el período
  queda fijado al tarifarse—, así que la prueba conserva su intención —una liquidación con sello
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
