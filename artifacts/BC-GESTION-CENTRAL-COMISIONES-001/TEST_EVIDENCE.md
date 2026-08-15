# Evidencia de pruebas

## Generación 2 (vigente)

- Dominio de comisiones: **29/29 PASS**.
- Interacción Tk y Full HD: **4/4 PASS**.
- Regresión completa: **284/284 PASS** en 24.77 s.
- Línea base heredada: 251 pruebas; esta misión suma 33 sin romper ninguna existente.

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

## Generación 1 (histórica, invalidada)

- Regresión: 280/280 PASS. Cifra correcta, pero la suite no cubría ninguno de los dos bloqueantes.
- Línea base heredada: 251; la misión sumaba 29.
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
