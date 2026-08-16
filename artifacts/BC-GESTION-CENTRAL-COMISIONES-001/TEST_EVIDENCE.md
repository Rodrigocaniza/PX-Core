# Evidencia de pruebas

## Generación 3 (vigente)

- Dominio de comisiones: **32/32 PASS**.
- Interacción Tk y Full HD: **4/4 PASS**.
- Regresión completa: **287/287 PASS** en 24.69 s.
- Línea base heredada: 251 pruebas; esta misión suma 36 sin romper ninguna existente.

## FAIL de revisores independientes (generación 2) y su corrección

6. **Comisión pagable sobre una base congelada — bloqueante del QA independiente de generación 2.**
   La guarda de `_apply_source_update` sólo cubría `PAGADA` y `APROBADA`. Una corrección de origen
   sobre una liquidación `REVISADA` reescribía `gross_amount` y `sale_kind` sin recalcular
   `agreement_discount`, `commissionable_base` ni `commission_amount`; como `REVISADA` no es
   recalculable, el camino `REVISADA → APROBADA → PAGADA` liquidaba sobre la base anterior.
   Verificado por el revisor: 11.400 Gs. de subpago y 54.150 Gs. de sobrepago en sus escenarios, y
   omisión completa del 5% al cambiar el tipo de venta. Alcanzable sin intervención humana desde
   `sync_review_sales`. Defecto **preexistente** de la generación 1 que su QA no había encontrado.
   Corregido con `REVIEWED_STATES` y recálculo completo de la base antes de la revisión. Cubierto
   por `test_source_correction_after_review_never_pays_a_stale_base` y
   `test_source_correction_before_review_recomputes_the_whole_base`.

7. **Reatribución de comisión ya pagada — observación O1 del Auditor de generación 2.** La misma
   guarda permitía reescribir `saleswoman` y `gross_amount` de una entrada `OBSERVADA` que antes
   estuvo `PAGADA`, reagrupando bajo otra vendedora dinero ya desembolsado. Cerrada por la misma
   corrección, al pasar la guarda a `_was_paid`. Cubierta por
   `test_source_correction_cannot_reattribute_already_paid_commission`.

8. **Defectos documentales — bloqueantes B1/B2/B3 del Librarian y B1/B2 del Auditor.** El paquete
   describía en pasado una revisión de generación 2 que aún no había ocurrido, remitía a un
   directorio inexistente, y el ZIP transportaba un `ARTIFACT_CONSISTENCY.md` obsoleto que se
   auto-certificaba con cifras de la generación invalidada, en un archivo excluido del manifest.
   Errores de la ejecución implementadora, no del producto. Corregidos: todo documento se escribe
   antes de empaquetar, el manifest cubre ahora `ARTIFACT_CONSISTENCY.md`, y ningún documento
   describe una revisión no ocurrida.

## FAIL de revisores independientes (generación 1) y su corrección

Los dos bloqueantes se reprodujeron con los escenarios exactos de cada revisor y se verificaron
muertos tras la corrección.

4. **`_month()` no validaba la fecha — bloqueante Q1 del QA independiente.**
   `"2099-4-10"` producía el período `"2099-4-"`: la venta quedaba CALCULADA con base y comisión
   correctas pero no aparecía en ningún reporte mensual, sin error ni marca de estado. Alcanzable
   desde `sync_review_sales`, que pasaba sin validar la fecha del snapshot SQLite externo.
   Corregido con `date.fromisoformat` y validación en la ingesta, que ahora devuelve
   `invalid_date` en vez de perder la fila. Cubierto por
   `test_invalid_dates_are_rejected_and_never_produce_a_period` y
   `test_review_sync_reports_invalid_dates_instead_of_losing_them`.

5. **`PAGADA → OBSERVADA → REVERTIDA` — bloqueantes A1, A2 y A3 del Auditor independiente.**
   Una liquidación pagada alcanzaba `REVERTIDA` en dos llamadas autorizadas, liberando el índice
   parcial de unicidad y habilitando un segundo pago de la misma venta mientras `report()` ocultaba
   el primero por excluir las revertidas. Además, `ARCHITECTURE.md` afirmaba explícitamente que esa
   ruta no existía. Corregido con el invariante `_was_paid`, aplicado en las tres rutas que pueden
   producir `REVERTIDA` (`revert`, `_revert_commission_effect`, `void_sale`). Cubierto por
   `test_paid_settlement_can_never_reach_reverted_even_through_observed` y
   `test_voiding_a_paid_sale_observes_instead_of_reverting`.

## Generaciones históricas invalidadas

- Generación 2: 284/284 PASS. Cifra correcta, pero la suite no cubría la corrección de origen en
  estado `REVISADA`, que es justamente la ventana desprotegida.
- Generación 1: 280/280 PASS. Cifra correcta, pero la suite no cubría ninguno de los dos
  bloqueantes de esa generación.

Las tres cifras eran ciertas y las tres suites estaban verdes. Ninguna regresión verde sustituye a
una revisión independiente.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Escaneo heurístico de secretos: PASS; las únicas coincidencias están dentro del propio test de prohibición.
- Captura 1920×1080: PASS.

## FAIL preservados y corregidos durante la implementación

1. **Explicación del convenio desaparecía tras el cálculo.**
   `test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance` falló porque, al pasar
   a `CALCULADA`, el motivo mostrado dejaba de mencionar el convenio. La misión exige mostrar
   siempre por qué una venta recibió el descuento. Corregido: `breakdown()` antepone el motivo del
   convenio en todos sus estados. Prueba repetida: PASS.

2. **KPI «Cobros parciales» sin formato monetario.**
   La primera captura mostró `700000` en crudo. `partial_payments_amount` faltaba en `AMOUNT_KEYS`.
   Corregido y fijado por aserción en `test_full_hd_layout_keeps_every_control_visible`.

3. **Tabla principal recortada a 1920×1080.**
   La primera captura cortaba «Base comisionable» y ocultaba por completo la columna «Comisión»;
   el resumen por vendedora también se cortaba. Causa: el panel izquierdo tenía `minsize=980`
   frente a 1470 px de columnas. Corregido recalibrando anchos y paneles, y fijado con una guarda
   de regresión que compara la suma de anchos de columna contra el ancho visible de cada tabla.
   Evidencia visual regenerada tras la corrección.

## Reproducción

```
python -m pytest -q
python -m compileall -q modulos tools tests bc_gestion_central.py
git diff --check
python tools/capture_gestion_central_comisiones.py artifacts/BC-GESTION-CENTRAL-COMISIONES-001/screenshots/comisiones-1920x1080.png
```
