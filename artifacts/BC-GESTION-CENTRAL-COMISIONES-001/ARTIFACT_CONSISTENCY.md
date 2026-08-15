# Artifact Consistency: PASS (generación 2)

- `MANIFEST.sha256` fija **28 archivos**: código, pruebas, capturador, captura, contrato económico,
  arquitectura, resumen, evidencia, workflow, lease, los tres `PROMPT_*.txt` y los seis documentos
  de la generación 1. Verificación `sha256sum -c`: **28/28 OK**.
- Respecto de la generación 1 el manifest incorpora los `PROMPT_*.txt`, que antes viajaban sin
  protección de integridad (observación 1 del Librarian independiente).
- Quedan deliberadamente fuera del manifest sólo dos archivos, por imposibilidad lógica:
  el propio ZIP —que contiene el manifest— y este documento, que describe el manifest.
- Captura 1920×1080 RGB: PASS, SHA-256 `dbf0462416eeb0184f3ca34438d5a9cfba0c1eae420cedebbb780f2733008467`,
  sin cambios respecto de la generación 1 porque la corrección no tocó la interfaz
  (`comisiones_ui.py` no fue modificado en la generación 2).
- ZIP `PX-Core-BC-GESTION-CENTRAL-COMISIONES-001.zip`: 30 miembros.
- Coherencia de estado en todos los artifacts: `WORKFLOW.json` = `REVIEW_PENDING_G2`,
  `MISSION_LEASE.json` = `HELD`, `SAFE_CLOSURE_EVIDENCE.md` = `NOT_EXECUTED`.
  Ningún artifact declara Safe Closure ni verdicts de generación 2 todavía.
- Cifras coherentes entre `TEST_EVIDENCE.md`, `SAFE_CLOSURE_EVIDENCE.md` y `WORKFLOW.json`:
  284/284 en generación 2, 280/280 en generación 1, línea base 251.
- Base declarada idéntica en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`:
  `eb6d082de4004d166379ffaae2b8f106fac10df1`.
- La evidencia de la generación 1 está preservada sin alterar contenido: los tres `SELF_REVIEW_*`
  se movieron con `git mv`, y `generation-1/README.md` documenta la errata de la afirmación que el
  auditor independiente refutó.
- Sin ventas reales, sin datos de clientes, sin secretos nuevos, sin proveedor externo, sin red
  y sin producción.
