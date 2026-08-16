# QA independiente — Generación 6

- RUNNER_ID: `QA-IND-COMISIONES-006`
- SNAPSHOT_COMMIT: `aed7bb2e4b370aeaa884008efab31dec16a965b2`
- SNAPSHOT_TREE: `f4f8aead7692f81cecd3ee9b466263d2745f1823`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T01:24:53Z
- REGRESSION: 297 passed / 0 failed (38.19 s) · DOMAIN 42/42 · UI 4/4
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS

## VERDICT: FAIL

### Los doce bloqueantes históricos: 12/12 CERRADOS, verificados por ejecución propia

### LEDGER_CONSISTENCY: 7.184 controles, 0 desvíos

5.184 controles del invariante (1.296 secuencias de 4 operaciones) + 2.000 escenarios aleatorios.
En cada paso: `paid_amount` == libro, no negativo, ≤ total, `balance == total − paid` y ≥ 0,
ninguna fila revertida dos veces, a lo sumo una liquidación activa por venta, ninguna venta común
con convenios vivos, y ninguna venta con saldo en estado pagable.

### CURRENT_FIX_RISKS: los cuatro riesgos verificados, todos OK

Ciclos CONVENIO→COMÚN→CONVENIO (6 iteraciones): el libro crece 2 filas por ciclo pero el neto es
exacto y queda **siempre exactamente un convenio vivo**. Descenso sobre liquidación ya PAGADA: el
invariante del dinero pagado se respeta (OBSERVADA conservando `paid_at`, `revert` bloqueado).

### BLOQUEANTE — corregir a la baja el total de un convenio se rechaza para siempre, y trunca el lote

`_apply_source_update` sólo revertía el convenio cuando la venta *dejaba* de serlo. En una
corrección CONVENIO→CONVENIO no se revertía nada, así que `settled` seguía valiendo el total viejo
y la guarda disparaba. Evidencia: convenio de 1.000.000 corregido a 900.000 →
`ValueError('el total corregido es menor a lo ya cobrado')`, con `dinero_real_cliente = 0` — el
mensaje afirmaba un cobro que nunca existió. La venta quedaba clavada en 1.000.000 y el reporte
informaba base 950.000 en lugar de 855.000: **95.000 Gs. de base sobrevaluada por venta afectada**,
sin vía automática de corrección.

**Agravante**: alcanzable por la integración documentada. `sync_review_sales` no capturaba la
excepción, de modo que un total corregido en el origen **propagaba el `ValueError` fuera de
`sync_review_sales` y salteaba todas las filas posteriores del lote**. Verificado con las filas
`antes/malo/después`: `antes` se actualizó, `después` **no**, y el llamador no recibía ningún
reporte — ingesta parcial y silenciosamente truncada de toda la bandeja.

## Observaciones no bloqueantes

- Atribución obsoleta en el KPI tras el descenso de un convenio ya PAGADO: el entry conserva la
  foto del convenio mientras la venta ya es común. No mueve dinero.
- Si el cliente después paga de verdad, la venta no genera base comisionable en su período por
  quedar la entry en OBSERVADA. Coherente con el contrato, conviene documentarlo.
- Una corrección sobre una liquidación OBSERVADA **no pagada** sí recalcula su base en silencio,
  a diferencia de REVISADA/APROBADA/PAGADA. Asimetría menor, sin efecto sobre dinero.
- El libro crece 2 filas por ciclo CONVENIO↔COMÚN sin poda. Correcto para un append-only.
- `VISUAL_EVIDENCE.md` documenta sólo una de las dos bandas de piloto de la captura.
