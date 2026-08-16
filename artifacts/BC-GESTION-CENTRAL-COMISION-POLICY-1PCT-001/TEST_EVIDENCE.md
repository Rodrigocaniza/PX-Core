# Evidencia de pruebas

Regresión completa: **331/331 PASS** (`python -m pytest -q`, 31,03 s).
Línea base de la misión anterior: 302. Esta misión suma **29**: 27 de dominio y 2 de interfaz.

Suite del módulo: `tests/gestion_central/` **131/131 PASS**.
Los dos archivos de comisiones juntos (`test_comisiones.py` + `test_comisiones_ui_interactions.py`):
51 → **80** pruebas, 74 y 6 respectivamente.

Todas las cifras anteriores son **casos ejecutados**, que es lo que cuenta pytest. En funciones:
`test_comisiones.py` pasa de 47 a 71 —se agregan 25 y se elimina
`test_policy_is_synthetic_pending_approval_and_optional`, que afirmaba lo contrario de la decisión
aprobada—, y tres de las nuevas están parametrizadas sobre `REVISADA` y `APROBADA`, de donde salen
los 74 casos. La de interfaz pasa de 4 a 6 funciones y 6 casos.

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

## Pruebas nuevas de dominio (25 funciones, 28 casos)

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

Todas las demás pruebas de la misión anterior siguen intactas y en verde: los quince bloqueantes
financieros históricos y los cinco invariantes económicos continúan cubiertos por sus pruebas
originales, sin retoques.

## Fuera de alcance

No se corrigieron los hallazgos no bloqueantes heredados del handoff anterior. Siguen abiertos y
registrados; ver `HANDOFF.md`.
