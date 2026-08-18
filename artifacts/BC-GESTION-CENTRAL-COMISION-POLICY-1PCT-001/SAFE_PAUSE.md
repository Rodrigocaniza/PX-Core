# Safe Pause — Auto-Resume desde la PC de la Óptica

> **El estado canónico manda sobre este documento.** Si algo de aquí no coincide con `git`,
> `WORKFLOW.json` o `MISSION_LEASE.json`, gana el estado real. Este resumen existe para no
> reconstruir contexto, no para sustituirlo.

## Identidad

| | |
|---|---|
| **Misión** | `BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001` |
| **Generación actual** | **5 — INVALIDATED** (snapshot `2ac9f5c93ec99ed506133310ee6cd19f6779b971`) |
| **Generación siguiente** | **6 — PENDING_REMEDIATION**, sin snapshot |
| **Branch** | `mission/bc-gestion-central-comision-policy-1pct-001` |
| **HEAD en la pausa** | `998037f924cdeb0c88565cc4618a85f9a0c92477` |
| **Remoto** | `origin` — **0 ahead / 0 behind**, publicada |
| **Working tree** | limpio |
| **Worktree del host pausado** | `.worktrees/gc-comision-policy-1pct-001` |
| **Safe Pause** | `SAFE_PAUSED` |
| **Safe Closure** | `PENDING` |
| **Mission Lease** | `RELEASED_FOR_SAFE_PAUSE` — **hay que readquirirlo antes de tocar nada** |

Base de la misión: `e7732603d9eb098867a272598e6d30803a4f1ac3`.

## Cómo retomar

```
git fetch origin
git checkout mission/bc-gestion-central-comision-policy-1pct-001
git rev-parse HEAD          # debe dar 998037f924cdeb0c88565cc4618a85f9a0c92477
git status --porcelain      # debe estar vacío
```

Después: adquirir el Mission Lease y arrancar `BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001-GEN6`.
No hace falta reconstruir nada más: los artifacts y los quince verdicts están en la branch.

## Recorrido de las cinco generaciones

| Gen | Snapshot | Librarian | QA | Auditor | Qué dejó |
|---|---|---|---|---|---|
| 1 | `578bf8b` | FAIL | PASS | FAIL | fuga: una liquidación legada era pagable al porcentaje retirado |
| 2 | `7abc30e` | FAIL | FAIL | FAIL | deriva de versión; la reparación cubría una sola etiqueta |
| 3 | `75f5c57` | FAIL | PASS | FAIL | **B1** re-tarifado retroactivo; **B2** importe retirado sin asiento |
| 4 | `5652e46` | PASS | PASS | FAIL | **B1-g4** la guarda por estado se desarmaba con `observe`/`revert`/`void_sale`; **B2-g4** `_apply_source_update` sin asiento |
| 5 | `2ac9f5c` | FAIL | FAIL | FAIL | **AB1-g5** y **AB2-g5** económicos; **QB1/QB2-g5** rotulado; L1-g5…L6-g5 documentales (cerrados) |

Los quince verdicts viven íntegros y sin retocar en `generation-1/` … `generation-5/`.

## Bloqueantes: cerrados y abiertos

**Cerrados y verificados**

| ID | Qué era | Estado |
|---|---|---|
| `B1` | vigencia *igual* re-tarifaba un período liquidado | cerrado en ruta directa · sucedido por `B1-g4` |
| `B2` | `replaced` sólo en las ramas `REVISADA`/`APROBADA` | cerrado en `recalculate` · sucedido por `B2-g4` |
| `B1-g4` | la guarda miraba el estado actual | **cerrado — verificado por los tres runners de la generación 5** |
| `B2-g4` | `_apply_source_update` anulaba sin asiento | **cerrado — verificado por los tres** |
| `L1`, `L2`, `L1-g5…L6-g5` | documentales | cerrados en sus commits de registro |

En la generación 5 los tres runners confirmaron, cada uno por su cuenta, que **no existe transición
pública que devuelva un período tarifado al catálogo**: QA con matriz propia de 18 transiciones y 7
cadenas, el Librarian ejecutando la matriz y comprobando que ninguna sentencia hace `UPDATE`/`DELETE`
sobre la evidencia, el Auditor con 10 transiciones, 30 semillas × 120 pasos de fuzz y concurrencia
real. Los diez invariantes económicos pasan sobre bases frescas.

**Abiertos — son el alcance de GEN6**

| ID | Tipo | Qué es | Decisión |
|---|---|---|---|
| `AB1-g5` | **económico** | La siembra de la migración fija el período con la tasa de la liquidación **más antigua**, aunque esté `REVERTIDA` y su venta anulada, y aunque el mes se haya pagado dos veces a otra tasa. Baja una `APROBADA` de 500.000 → 100.000 Gs y le borra el aval, **sin una sola fila de auditoría**. | resuelta abajo |
| `AB2-g5` | **económico** | Un tipeo de fecha fija un mes lejano **para siempre**; el pin sobrevive a la corrección de origen y a la anulación que el propio sistema registra, y ese mes paga mal en silencio. | resuelta abajo |
| `QB1-g5` | rotulado | En un período sin tasa en vigor la cabecera cae a la política global y la declara oficial de ese mes («Comisión oficial 10,00%» donde no rige nada). | sin bifurcación |
| `QB2-g5` | rotulado | El `policy_disclaimer` del export `contract_version: 3` emite «Comisión oficial **None%**». | sin bifurcación |

## Decisión de propietario para GEN6

**La tasa del período NO se fija en el primer cálculo.** Queda fijada únicamente cuando existe un
**hecho económico oficial**.

- **Boundary: `APROBADA` o `PAGADA`.**
- Los estados provisionales anteriores —`ELEGIBLE`, `CALCULADA`, `REVISADA`— **siguen siendo
  corregibles** y no fijan nada.
- **La migración no puede sembrar** desde una venta anulada, ni desde un primer cálculo arbitrario,
  ni desde evidencia ambigua.
- **Una migración nunca puede modificar silenciosamente dinero aprobado o pagado**, ni retirar una
  aprobación o un pago.

Por qué cierra los dos: un tipeo que será anulado nunca alcanza `APROBADA` ni `PAGADA`, así que no
puede fijar un mes (`AB2-g5`); y la siembra deja de depender del orden de creación para depender del
mismo hecho económico (`AB1-g5`).

## Artifacts que deben reutilizarse — no regenerar

- `generation-1/` … `generation-5/` — **quince verdicts, íntegros y sin retocar**. No se reutilizan
  como aprobación: la generación 6 relanza los tres runners desde cero.
- `WORKFLOW.json` — historial de generaciones, `blockers_open`, `policy_decision_b1`,
  `policy_decision_b1_g4`, `policy_decision_gen6`, backlog de 29 hallazgos, `safe_pause`.
- `HANDOFF.md` — los 29 hallazgos abiertos, con el 23 y el 25 ya corregidos.
- `INDEPENDENCE.md` — por qué falló cada generación y qué superficie no cubrió cada rol.
- `ARCHITECTURE_DELTA.md`, `COMMISSION_POLICY_1PCT.md`, `MIGRATION.md`, `SUMMARY.md` — contrato
  vigente. **Dos afirmaciones siguen demostradas falsas y se conservan a propósito** para que GEN6
  las corrija con la evidencia a la vista: la de `MIGRATION.md` / `ARCHITECTURE_DELTA.md` según la
  cual «un importe heredado no oficial no fija nada», y la lectura implícita de que la fecha errónea
  quedó resuelta.
- `PROMPT_LIBRARIAN.txt`, `PROMPT_QA.txt`, `PROMPT_AUDITOR.txt` — con sus secciones por generación.
- `TEST_EVIDENCE.md` — lleva la advertencia de que ninguna prueba cubre lo que pasa *después* de que
  un pin se graba mal.
- `MANIFEST.sha256` y el ZIP — **verifican en el worktree donde se generan**, no en un clon nuevo
  (hallazgo abierto 23: `core.autocrlf=true` sin `.gitattributes`).

**Debe regenerarse en GEN6:** `VISUAL_EVIDENCE.md` y su captura. El rótulo de pantalla cambió —ahora
incluye « · fijada al tarifarse»— y la captura de la generación 3 ya no coincide (`L6-g5`).

## Estado del código en la pausa

Sin cambios respecto del snapshot `2ac9f5c`. Regresión **371/371**, suite del módulo **171**,
dirigidas **114**. `comision_policy.py` intacto desde la generación 3: la aritmética `Decimal` y el
único `HALF_UP` canónico no se han tocado.

## NEXT_ACTION exacto

```
BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001-GEN6
```

1. Adquirir el Mission Lease sobre la branch ya publicada.
2. Cerrar `AB2-g5`: fijar el período **sólo** al alcanzar `APROBADA` o `PAGADA`.
3. Cerrar `AB1-g5`: la siembra ignora `REVERTIDA` y ventas anuladas, se apoya en el mismo boundary,
   no fija nada ante evidencia ambigua o discrepante, no toca importes ni avales, y audita cada
   período sembrado en `central_audit`.
4. Cerrar `QB1-g5`: rotular la ausencia de tasa en cabecera y KPI en vez de caer a la global.
5. Cerrar `QB2-g5`: `policy_disclaimer` propio cuando el período no tiene tasa en vigor.
6. Regenerar `VISUAL_EVIDENCE` y su captura.
7. Dirigidas → suite del módulo → regresión completa.
8. Publicar snapshot de la generación 6 y relanzar los tres runners independientes.
9. **No reutilizar verdicts de las generaciones 1 a 5.**

Con 3×PASS: protected commit/push, Safe Closure, liberar el lease y persistir NEXT_ACTION.
`BC-GESTION-CENTRAL-SOBRES-FACTURA-V1` sigue sin abrirse.

## Lo que no se toca

BC-Core. BC Caja rc.31 (`pedidos30-gate`). Los worktrees anteriores de Gestión Central. `main`. Sin
merge y sin force-push.
