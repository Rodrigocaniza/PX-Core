# QA independiente — Generación 10

- RUNNER_ID: `QA-IND-COMISIONES-010`
- SNAPSHOT_COMMIT: `c7a25a6a6439b555d1ea26a8f09ad1014a4f824c`
- SNAPSHOT_TREE: `11a13b26bb543125d0a0831489a7b66c3fe431da`
- WORKTREE_CLEAN_BEFORE / AFTER: YES / YES
- TIMESTAMP_UTC: 2026-08-16T02:49:19Z
- REGRESSION: 302 passed / 0 failed (24.95 s) · DOMAIN 47/47 · UI 4/4
- COMPILEALL / GIT_DIFF_CHECK / SECRET_SCAN: PASS / PASS / PASS

## VERDICT: PASS

**BLOCKERS: NONE.**

### DOMAIN_UNTOUCHED confirmado

`comisiones.py`, `comisiones_ui.py`, `repository.py`, `service.py` y `test_comisiones.py` son
**byte-idénticos y AST-idénticos** entre la generación 9 y la 10. El cambio es inerte respecto del
producto.

### Los quince bloqueantes financieros históricos: 15/15 CERRADOS

Cada uno con escenario propio ejecutado, sin apoyarse en ninguna suite ajena.

### LEDGER_CONSISTENCY: sin desvíos

**13 invariantes duros** evaluados en cada escenario y cada 25 pasos de fuzz.
**35.400 pasos de fuzz en 18 semillas, 0 violaciones.** Persistencia, reapertura y migración aditiva
sobre base legada verificadas. Total propio: **~30.500 aserciones**, sin una sola falla de dinero.

Incluye una sonda diseñada específicamente: excepción a mitad de `_apply_source_update` **después**
de insertar reversas — la transacción revierte y no queda ni una reversa huérfana ni divergencia
entre `paid_amount` y el libro.

### CONSISTENCY_CHECKER_EVALUATION: verificación real, probada por mutación

**27 inconsistencias inyectadas a mano** sobre una copia del paquete. Detecta las cinco clases que
declara y el paquete intacto pasa limpio; **detecta con precisión los dos bloqueantes reincidentes
de la generación 9**, que es su razón de ser. Sus límites (conteos en dígitos, afirmaciones en prosa,
hechos no verificables) quedan fuera de su alcance declarado.

## Observaciones no bloqueantes

1. El checker no tiene pruebas y la regresión no lo ejecuta; su uso antes de publicar es convención
   manual. Las 27 mutaciones son convertibles en suite.
2. Ante `HANDOFF.md` ausente o `WORKFLOW.json` corrupto muere con traceback en vez de reportar el
   problema. Mitigado porque el exit code 1 mantiene el gate.
3. Huecos de cobertura: conteos en dígitos, afirmación en prosa de una revisión no ocurrida, dos
   spans rotos que compensan paridad, y cualquier afirmación fáctica.
4. `ARTIFACT_CONSISTENCY.md` atribuye al checker cuatro generaciones; cubre las de la 9 y tres de
   las cuatro de la 7, no la de la 5 ni la de la 8.
5. El KPI «Comisión calculada» incluye las liquidaciones OBSERVADAS y no hay tarjeta «Observadas».
   Agregado informativo, no pagable.
