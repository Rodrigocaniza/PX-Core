# Auditor independiente — Generación 2

- RUNNER_ID: `AUDITOR-IND-COMISIONES-002`
- ROLE: AUDITOR
- SNAPSHOT_COMMIT: `5ba11bdbdbaaa826f16510fb07d08ffdbce17097`
- SNAPSHOT_TREE: `a03e20ed29ea0d583e89259013775f1de26b668c`
- TIMESTAMP_UTC: 2026-08-16T00:02:53Z
- SCOPE_DIFF vs base `eb6d082`: 31 archivos, +2665/-0, nada fuera del alcance de la misión.
- SCOPE_DIFF vs generación 1: 19 archivos, +569/-111; código sólo en `comisiones.py` (+53/-8);
  `comisiones_ui.py` no tocado; 3 renames `git mv` con 0 cambios de contenido.
- ISOLATION / MAIN_UNTOUCHED / FORCE_PUSH / REMOTE_SYNC: OK / OK / NO / 0 ahead · 0 behind

## VERDICT: FAIL

### PAID_INVARIANT: SE CUMPLE

Verificado por ejecución real, no por lectura. Enumeradas por `grep` las 3 —y únicas— sentencias
que producen `REVERTIDA`, y atacadas las tres con una liquidación pagada. **12 rutas probadas**:
`revert()` directo, `observe()` + `revert()`, `revert_payment()` tras el pago, `void_sale()` tras
el pago, `void_sale()` sobre OBSERVADA-ex-PAGADA, corrección de origen tras el pago, corrección
que reabre saldo, la misma sobre OBSERVADA-ex-PAGADA, `revert_payment()` sobre OBSERVADA-ex-PAGADA,
y la cadena pago → reversa → recobro → intento de segundo pago. En ninguna apareció una fila con
`status='REVERTIDA'` y `paid_at` no nulo. `paid_at` no se limpia en ninguna sentencia del módulo.

### DOUBLE_PAYMENT_POSSIBLE: NO

Ninguna de las 12 rutas libera el índice parcial; un `INSERT` directo de una segunda entrada
activa en SQL crudo es rechazado con `UNIQUE constraint failed`; y `OBSERVADA` no tiene transición
de retorno, por lo que la entrada pagada-y-observada es terminal. Máximo de entradas con `paid_at`
por venta observado: 1.

### BLOQUEANTE B1 — el ZIP transportaba un `ARTIFACT_CONSISTENCY.md` auto-certificado falso

Comparación miembro a miembro de los 30 archivos del ZIP contra el worktree: 29 byte-idénticos,
uno distinto. El empaquetado era idéntico al de `c24b4f19` y declaraba «PASS», «21 archivos»,
«21/21 OK», «25 miembros», `HUMAN_GATE_PENDING`, «280/280», «25 de dominio» y «no hay ningún
artifact que declare Safe Closure ni independencia»: **siete afirmaciones falsas** contra el
snapshot. Agravante: el archivo estaba deliberadamente excluido del manifest, de modo que la
verificación de integridad declarada era estructuralmente incapaz de detectarlo.

### BLOQUEANTE B2 — `INDEPENDENCE.md` afirmaba en pasado una revisión de generación 2 inexistente

Contradecía a `WORKFLOW.json`, a `SAFE_CLOSURE_EVIDENCE.md` y falsificaba la afirmación de
`ARTIFACT_CONSISTENCY.md` de que ningún artifact declaraba verdicts de generación 2.

## ARTIFACT_TRUTHFULNESS

Todas las afirmaciones sobre el **código** verificadas como ciertas: las tres únicas rutas a
`REVERTIDA`, `_was_paid` aplicado en las tres, imposibilidad de doble pago, `mark_paid` sólo desde
`APROBADA`, enteros y puntos básicos sin floats, manifest 28/28, captura 1920×1080 con hash
coincidente, 284/284 y línea base 251. Falsas sólo las dos afirmaciones del paquete sobre sí mismo.

## Observaciones no bloqueantes

- **O1** — `_apply_source_update` usaba `status in FROZEN_STATES or == "APROBADA"` en vez de
  `_was_paid`: una entrada OBSERVADA por haber sido PAGADA podía ver reescritos `saleswoman` y
  `gross_amount`, reagrupando bajo otra vendedora una comisión ya desembolsada. No silencioso ni
  habilitante de doble pago.
- **O2** — `report()` calcula `paid_entries`/`paid_amount` por `status == 'PAGADA'` en vez de por
  `paid_at`: al observar una liquidación pagada, el reporte subdeclara lo desembolsado.
- **O3** — `test_state_contract_and_append_only_history` ejecuta `DELETE` + `rollback()`: demuestra
  que el rollback de SQLite funciona, no que exista una restricción append-only. La propiedad real
  se cumple (verificada por grep), pero la suite no la protege ante regresiones.
- **O4** — «quedan fuera del manifest sólo dos archivos»; eran tres.
- **O5** — El `MISSION_LEASE` se mantuvo `HELD` entre generaciones, justificado explícitamente en
  `WORKFLOW.json`. Razonable y documentado; registrado, no objetado.
