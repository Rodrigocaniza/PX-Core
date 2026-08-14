# BC-CAJA-PILOT-RELEASE-001

Estado: CLOSED
Versión: BC Caja 1.0.0-rc.1
Base canónica: origin/main f0ad079b8fc275385f844c6e76dbc452669c5e1c
Integración protegida: merge 08ecffa3f93ba431d5b8c4750f68212e66f48521, sin force y en worktree aislado.

## Pruebas

- Preflight y regresión completa: 151 passed.
- Edición de ventas y múltiples productos, Movimientos, backup/restore y migraciones: 34 passed.
- Smoke visual: contrato 1366×768 aprobado y evidencia canónica reutilizada; arranque del EXE final confirmado durante 5 segundos.
- Self-check del EXE: BC_CAJA_SELF_CHECK_OK con `BC_CAJA_DATA_DIR` externo.
- Paquete: contiene las 11 migraciones versionadas, 001–011.

## Gates

Verification PASS → Packaging PASS → Artifact Consistency PASS → Librarian PASS → QA PASS → Auditor PASS → Safe Closure PASS.

`BC-CAJA-MOVIMIENTOS-001` y `BC-CAJA-RECOVERY-DRILL-001` conservan su evidencia completa, commits de cierre y ramas publicadas/sincronizadas en origin.
