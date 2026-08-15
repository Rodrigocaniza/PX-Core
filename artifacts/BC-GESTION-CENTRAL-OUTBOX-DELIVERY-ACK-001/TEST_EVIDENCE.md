# Evidencia de pruebas

- Dominio dirigido inicial: 17/17 PASS.
- Bandeja Tk corregida: 2/2 PASS.
- Regresión de falso positivo horario + UI heredada: 6/6 PASS.
- Contrato envelope anidado exacto: 6/6 PASS.
- Atomicidad/fault injection/reconciliación: 8/8 PASS.
- Regresión completa final regenerada: 241/241 PASS en 22.72s.
- `python -m compileall`: PASS.
- `git diff --check`: PASS.
- Escaneo heurístico: PASS; coincidencias limitadas a términos de prohibición en pruebas/documentos, sin valores secretos.
- FAIL preservados y corregidos: medición de ventana oculta/doble fixture Tcl; falso `LATE_OPEN`; divergencia de envelope/Workflow; inestabilidad de raíces Tk; ventana no atómica mensaje→delivery señalada por Auditor. La cola ahora confirma mensaje, outbox, delivery, historial y auditoría en una transacción, con fault injection y reconciliación heredada probadas.
- Warning no funcional: `.pytest_cache` sin permiso; `--basetemp` aislado sí funcionó.
