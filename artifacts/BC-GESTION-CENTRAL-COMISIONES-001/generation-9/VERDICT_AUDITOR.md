# Auditor independiente — Generación 9

- RUNNER_ID: `AUDITOR-IND-COMISIONES-009`
- SNAPSHOT_COMMIT: `114aee84745aa82293509f4d76be3c0bac381827`
- SNAPSHOT_TREE: `cdf46c8bac5c877aa1d7d8ba2a2c561581a213d6`
- TIMESTAMP_UTC: 2026-08-16T02:22:08Z
- SCOPE_DIFF vs base: 52 archivos, 5244 inserciones, **0 deleciones**. vs generación 8: 13 archivos.
- ISOLATION / MAIN_UNTOUCHED / FORCE_PUSH / REMOTE_SYNC: OK / OK / NO / OK

## VERDICT: PASS

**BLOCKERS: NONE.**

### Invariantes sostenidos por ejecución propia

- **PAID_INVARIANT.** **Seis rutas** atacadas sobre liquidaciones realmente pagadas: `revert()`
  directo, `observe()`+`revert()`, `revert_payment()`, `void_sale()`, corrección de origen y
  `recalculate()`. Ninguna produjo `REVERTIDA`. Consulta al motor tras cada ruta:
  `WHERE status='REVERTIDA' AND paid_at IS NOT NULL` = 0 filas, siempre.
- **DOUBLE_PAYMENT_POSSIBLE: NO**, en API y en motor. Misma clave en otra venta sí se acepta: no hay
  colisión cruzada.
- **SOURCE_CORRECTION_INVARIANT.** Cinco estados verificados valor a valor.
  `COMÚN→CONVENIO→COMÚN` conserva el cobro previo y reabre el saldo correcto — exactamente el
  contraejemplo que el backlog 16 documenta.
- **PAYMENT_LEDGER_INTEGRITY.** Fuzz propio de 600 pasos sobre 12 ventas con 11 operaciones
  aleatorias, revalidando 7 invariantes duros tras cada paso: **0 violaciones**. Migración aditiva
  sobre esquema anterior con datos: preserva e idempotente.
- **INGESTION_RESILIENCE.** `AccessDenied` propaga y corta la sincronización, al inicio y a mitad de
  lote. Con 7 filas (una válida al final tras todas las rotas) el lote no se trunca y los contadores
  cubren las 7. Salvedad ya registrada como hallazgo 17, verificada no alcanzable.
- **PACKAGE_TRUTHFULNESS: VERAZ.** «No encontré una sola afirmación falsa contra el código.» Los 24
  verdicts leídos uno por uno coinciden exactamente con la tabla de `SAFE_CLOSURE_EVIDENCE.md`.
- **Integridad monetaria**: `base + descuento == total` exacto en 5.000 casos; `typeof=integer` en
  todos los importes tras 600 pasos.

### Estado de sus observaciones de la generación 8: las cuatro atendidas o registradas

Verificadas contra el código y no sólo contra el documento. Destaca que la retirada del ítem de
backlog obsoleto «es legítima y no un encubrimiento».

## Observaciones no bloqueantes

1. **Orden no determinista del libro**: `utc_now()` trunca a segundos y `payments()` ordena por
   `recorded_at, id` con `id` aleatorio, de modo que una `REVERSA` puede listarse antes del `COBRO`
   que revierte. Sin efecto monetario; degrada la lectura cronológica.
2. **`sync_review_sales` no tiene guarda de autorización propia**: la autorización llega desde
   `list_sales` y `register_sale`. El efecto es correcto, pero con un lote vacío el método retorna
   sin evaluar permisos. Defensa en profundidad, no un agujero.
3. El hallazgo 17 sigue abierto y correctamente documentado, misma severidad que en la generación 8.
