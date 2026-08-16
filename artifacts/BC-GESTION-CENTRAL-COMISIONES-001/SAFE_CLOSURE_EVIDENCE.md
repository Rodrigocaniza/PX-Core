# Safe Closure

**Estado: `NOT_EXECUTED` en este snapshot.**

Este snapshot es la generación 6 y **todavía no fue revisado**. Las generaciones 1 a 5 fueron
invalidadas por FAIL de revisores independientes.

## Trazabilidad

| Generación | Snapshot | Librarian | QA | Auditor | Resultado |
|---|---|---|---|---|---|
| 1 | `c24b4f19` | PASS | **FAIL** | **FAIL** | INVALIDADA |
| 2 | `5ba11bd` | **FAIL** | **FAIL** | **FAIL** | INVALIDADA |
| 3 | `4c4cf54` | PASS | **FAIL** | PASS | INVALIDADA |
| 4 | `88a3f74` | PASS | **FAIL** | **FAIL** | INVALIDADA |
| 5 | `0f735f7` | **FAIL** | **FAIL** | **FAIL** | INVALIDADA |
| 6 | este snapshot | no ejecutado | no ejecutado | no ejecutado | pendiente |

## Lo verificado en la generación 6

- Regresión completa: 297/297 PASS (línea base 251 + 46 de la misión: 42 de dominio + 4 de interfaz).
- Los doce bloqueantes financieros acumulados, reproducidos con los escenarios exactos de cada
  revisor y verificados muertos.
- `compileall`, `git diff --check` y escaneo heurístico de secretos: PASS.
- `MANIFEST.sha256` verificado, cubriendo también `ARTIFACT_CONSISTENCY.md`.
- ZIP construido **después** de escribir todos los documentos y verificado miembro a miembro.
- Evidencia de las generaciones 1 a 5 preservada íntegra: quince verdicts independientes y las tres
  autorrevisiones originales.
- Sin merge a `main`, sin force-push, sin despliegue, sin tocar instalaciones productivas.

## Corrección de esta generación

La generación 5 hizo del libro append-only la única fuente de verdad de `paid_amount`, pero
introdujo un defecto propio: la fila `CONVENIO` sobrevivía a la conversión de la venta a común. La
generación 6 lo cierra revirtiendo esa liquidación en el libro cuando la venta deja de ser convenio
—exactamente lo que `COMMISSION_RULES.md` ya documentaba— y excluyendo del KPI los cobros
revertidos. No se inventó ninguna regla económica.

## Condición de cierre

Safe Closure se ejecutará y el Mission Lease se liberará **sólo si los tres revisores
independientes de la generación 6 emiten PASS** sobre este snapshot. Ningún documento de este
paquete afirma que eso haya ocurrido.
