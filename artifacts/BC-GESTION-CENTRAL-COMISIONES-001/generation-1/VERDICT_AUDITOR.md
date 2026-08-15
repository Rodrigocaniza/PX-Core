# Auditor independiente — Generación 1

- RUNNER_ID: `AUDITOR-IND-COMISIONES-001`
- ROLE: AUDITOR
- SNAPSHOT_COMMIT: `c24b4f19c66dc685d1679ed266eb887f2dbfe773`
- SNAPSHOT_TREE: `d296c6384885176399dceeeda103a4acb397e43d`
- TIMESTAMP_UTC: 2026-08-15T23:34:18Z
- SCOPE_DIFF: 27 archivos, +2207/-0, sin borrados. Cero archivos bajo `modulos/caja_diaria/**`.
- ISOLATION: gc-sol-001 = c87d857, gc-outbox-ack-001 = 74470d7, gc-factufacil-001 = eb6d082 (intactos)
- MAIN_UNTOUCHED: YES (main = `d88f5956a65c2521ad707eab0117ac88c8dfdd04`; el commit no está contenido en main)
- FORCE_PUSH: NO (reflog remoto de una sola entrada; rama de creación limpia)
- BASE_IS_ANCESTOR: YES
- REMOTE_SYNC: 0 ahead / 0 behind
- Regresión reproducida por el propio auditor: 280/280 PASS

## VERDICT: FAIL

### BLOQUEANTE A1 — Existe una ruta real PAGADA → OBSERVADA → REVERTIDA

`modulos/gestion_central/comisiones.py:492` y `:499`. `observe()` admitía
`OPEN_STATES | {"PAGADA"}` → OBSERVADA y `revert()` admitía `OPEN_STATES | {"OBSERVADA"}` →
REVERTIDA, sin ninguna comprobación de `paid_at`. Reproducido por ejecución real: historial final
`APROBADA → PAGADA → OBSERVADA → REVERTIDA`, conservando `paid_at` y `payment_reference`.
Alcanzable desde la interfaz: los botones «Observar» y «Revertir» están siempre habilitados sobre
la fila seleccionada.

### BLOQUEANTE A2 — Consecuencia financiera: doble pago de la misma venta

Una vez la entrada pagada queda REVERTIDA, el índice único parcial
`idx_commission_entry_active ... WHERE status<>'REVERTIDA'` deja de bloquear y una corrección de
origen crea una entrada nueva que recorre otra vez ELEGIBLE → CALCULADA → REVISADA → APROBADA →
PAGADA. Reproducido: entrada 1 REVERTIDA con comisión 23.750 y referencia TR-1; entrada 2 PAGADA
con 28.500 y referencia TR-2 sobre la misma `sale_id`. Agravante: `report()` excluye REVERTIDA del
conjunto contable, de modo que los KPI informan `paid_entries=1 / paid_amount=28.500` y **ocultan
por completo los 23.750 ya pagados bajo TR-1**.

### BLOQUEANTE A3 — Afirmaciones de artifacts no respaldadas por el código

`ARCHITECTURE.md:43` declaraba «**`PAGADA` nunca pasa a `REVERTIDA`**» y `AUDIT_REPORT.md:28`
«Ninguna ruta lleva `PAGADA` a `REVERTIDA`». Ambas falsas contra el snapshot de generación 1.
Ningún test cubría la secuencia observe → revert desde PAGADA:
`test_paid_settlement_is_never_modified_silently` sólo verificaba que la reversión de *cobro* deja
OBSERVADA, y `test_observation_and_motivated_reversal_require_reason` recorría observe → revert
partiendo de una entrada **no pagada**.

## Observaciones no bloqueantes registradas

- Ninguna transición es *silenciosa*: ambos pasos exigen motivo obligatorio y dejan historial
  append-only con actor. El defecto es la existencia del destino REVERTIDA para una liquidación
  pagada y la pérdida contable que provoca, no la falta de auditoría.
- `assert "float(" not in source` es una comprobación más débil que la propiedad declarada; las
  divisiones `/100` de las líneas 619 y 623 la eluden aunque sean sólo de presentación. El mismo
  test lee una ruta relativa, por lo que depende del directorio de trabajo.
- `_create_entry` fija `eligible_date = sale["cancelled_date"]` también al crear en
  PENDIENTE_SALDO (NULL en ese caso); correcto pero poco explícito.

## Checklist verificado OK

Aislamiento, main intacto y sin merge, base ancestro real, sin force-push, sincronía remota,
alcance restringido a la misión, permisos por rol, historial append-only, integridad monetaria
entera, política sintética correctamente identificada, ausencia de red, proveedor externo, nómina
y bancos, protección de datos sensibles, y captura 1920×1080 con hash idéntico al registrado.
