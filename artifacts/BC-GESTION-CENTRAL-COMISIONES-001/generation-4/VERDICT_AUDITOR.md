# Auditor independiente — Generación 4

- RUNNER_ID: `AUDITOR-IND-COMISIONES-004`
- SNAPSHOT_COMMIT: `88a3f74e0d507f20917ef5d650dd92a3e56e8202`
- SNAPSHOT_TREE: `f58a3b7196ae8645360cfe5faa70a9656df50819`
- TIMESTAMP_UTC: 2026-08-16T00:42:13Z
- SCOPE_DIFF vs base: 37 archivos, +3376/-0. vs generación 3: 17 archivos, +452/-115.
- ISOLATION / MAIN_UNTOUCHED / FORCE_PUSH / REMOTE_SYNC: PASS / PASS / PASS / PASS

## VERDICT: FAIL

### PAID_INVARIANT: PASS por ejecución

Tres —y sólo tres— sentencias escriben `REVERTIDA`. **10 rutas ejecutadas**, todas con verificación
SQL de `status='REVERTIDA' AND paid_at IS NOT NULL` y de la historia: 0 filas en todos los casos.

### DOUBLE_PAYMENT_POSSIBLE: NO

El contrato nuevo sin deduplicación automática **no abrió ninguna vía**: el tope de cada cobro es
`balance_amount`, no la clave; tres ciclos reversa/recobro dejaron exactamente 1 transición
histórica a PAGADA; misma clave en ventas distintas no interfiere.

### SOURCE_CORRECTION_INVARIANT: PASS · MIGRACIÓN: PASS

La migración aditiva sobre una base con el esquema de la generación 3 conserva los datos byte a
byte, añade la columna una sola vez y es idempotente en tres invocaciones.

### BLOQUEANTE B1 — el contrato de idempotencia no cumplía lo que el paquete afirmaba

`ARCHITECTURE.md` afirmaba: «Con `idempotency_key`, el reintento de una integración se descarta con
`(None, False)`». Falso por ejecución: el chequeo `amount > balance_amount` **precedía** al de
idempotencia, de modo que el reintento del cobro que cancela la venta lanzaba
`ValueError("el cobro supera el saldo pendiente")` en vez de descartarse. El caso roto era
precisamente el más frecuente: el cobro que cancela la venta es el evento que la vuelve
comisionable. La prueba citada como cobertura usaba 50.000 sobre saldo 200.000 y estructuralmente
no podía alcanzar el caso.

### BLOQUEANTE B2 — `paid_amount` negativo por corrección a CONVENIO sin guarda

La rama COMÚN validaba «el total corregido es menor a lo ya cobrado»; la rama CONVENIO fijaba
`paid = total_amount` sin consultar el libro ni validar nada. Secuencia ejecutada: venta común de
400.000 totalmente cobrada → corrección a CONVENIO con total 100.000 (aceptada en silencio) →
`revert_payment` → fila persistida con **`paid_amount = -300.000`**, `balance = 400.000`,
`total = 100.000`, y el reporte informando `partial_payments_amount = 400.000` de un cobro ya
revertido. Alcanzable por la vía documentada: `sync_review_sales` deriva
`kind = CONVENIO if agreement >= total`. **Preexistente**, no introducido por la generación 4.

## Observaciones no bloqueantes

- **O1** — La clave de idempotencia ignora monto y fecha: reusar la clave con monto distinto
  descarta el segundo cobro en silencio.
- **O2** — La rama CONVENIO fijaba `paid_amount` sin escribir en el libro, divergiendo de
  `_settled_amount`.
- **O3** — `revert_payment()` seguía sin rechazar una venta anulada (observación no atendida de la
  generación 3).
- **O4** — División flotante en etiquetas de porcentaje; ningún importe es float.
- **O5** — Tras la migración, los cobros legados quedan con `client_key = NULL` y pierden la
  idempotencia derivada del contenido que tenían bajo el esquema anterior. Coherente con el
  contrato nuevo, pero es un cambio de comportamiento no documentado.
- **O6** — `main` local está 0 ahead / 82 behind `origin/main`: divergencia **preexistente**, ajena
  a la misión.
