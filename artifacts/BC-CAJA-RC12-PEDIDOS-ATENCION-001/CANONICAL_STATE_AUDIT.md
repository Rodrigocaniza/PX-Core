# CANONICAL_STATE_AUDIT — BC-CAJA-RC12-PEDIDOS-ATENCION-001

Auditoría de estado canónico real ejecutada al reanudar la misión.
**Regla aplicada: estado canónico real > handoff, memoria o mensajes anteriores.**

## 1. Estado verificado del repositorio

| Ítem | Valor real |
| --- | --- |
| Repositorio | PX-Core (`https://github.com/Rodrigocaniza/PX-Core.git`) |
| git-common-dir | `.git` (worktree principal: `PX-Core`, en `feature/caja-operator-ux-001` @ `0f6195e`) |
| Worktree de la misión | `PX-Core/rc12` |
| Rama | `feature/bc-caja-rc12-pedidos-atencion-001` |
| HEAD | `41ee4ce` — *feat(caja): focus pedidos on what needs attention* |
| Working tree | Limpio, sin cambios pendientes |
| Push | `origin/feature/bc-caja-rc12-pedidos-atencion-001` = `41ee4ce` (sincronizada, sin force-push) |
| `origin/main` | `098a9fb` — *docs(gestion-central): record safe pilot closure* |
| Merge-base con main | `098b150` (BC Caja rc.11) |
| Divergencia | main **+15 commits** que rc12 no tiene; rc12 **+1 commit** propio |
| Leases activos | Ninguno para misiones de Caja (`.bc-command-center/missions` sólo tiene misiones BC-Remote) |
| Pruebas focalizadas | **36 passed** (`test_rc12_pedidos_atencion`, `orders_v1`, `rc10`, `rc5`, `operator_fixes_003`, `rc11`) |
| Hashes MANIFEST | **15/15 OK** — 12 fuentes + 3 capturas, sin drift |
| Empaquetado | `packaged: false`, bloqueado por `HUMAN_GATE-RC12-PEDIDOS-001` |

## 2. Hallazgo crítico: la línea canónica de BC Caja ya no es esta rama

`origin/main` avanzó **15 commits** desde el punto de fork (`098b150` = rc.11) y contiene
otra línea de release de BC Caja:

```
df1d3ed feat(caja): integrate cash count modal for rc12     <- rc.12 canónico = ARQUEO
5c51547 feat(caja): add protected administrator v1
4367f70 feat(caja): require audited opening and closing counts
9f04865 feat(caja): queue private close reports by email
5cf6e8e chore(caja): release rc13
42b8df2 fix(caja): recover configured close notifications    <- rc.14
a8240ed feat(gestion-central): implement isolated four-unit pilot
... (+ pilot Gestión Central, outbox de sincronización)
```

Artifacts presentes en `main`: `BC-CAJA-RC12-ARQUEO-EN-CAJA-DIARIA-001`,
`BC-CAJA-RC13-ADMIN-ARQUEO-EMAIL-001`, `BC-CAJA-RC14-MAIL-OPS-FIX-001`
(199 pruebas, SMTP/TLS simulado, smoke visual 1366×768).

Consecuencias verificadas:

1. **El nombre `rc.12` está tomado.** En la línea canónica, rc.12 es *Arqueo en Caja
   diaria*; esta rama es un rc.12 paralelo de *Pedidos*. La versión canónica instalable
   hoy es **rc.14**, no rc.11 como afirma `SAFE_PAUSE_EVIDENCE.md`.
2. **El trabajo de Pedidos-atención no está en `main`.** Verificado: `main` conserva los
   filtros viejos `("Hoy", "Atrasados", "Próximos", "Todos")` y no tiene
   `tests/caja_diaria/test_rc12_pedidos_atencion.py`.
3. **La rama no integra limpio.** `git merge-tree origin/main <rama>` da conflicto de
   contenido en `CajaDiaria.py` y en `.bc-command-center/verification.json`
   (auto-merge OK en `services.py`, `controller.py` y `test_rc5_operational_ux.py`).
4. **El HUMAN_GATE es inválido tal como está.** Pide observar en la Óptica una pantalla
   construida sobre rc.11; el equipo tiene instalada la línea rc.13/rc.14. Un PASS humano
   sobre esa captura no certificaría lo que hoy corre en producción.

## 3. Qué NO se hizo, y por qué

- **No se empaquetó rc.12-pedidos.** El gate humano sigue sin resolver y, además, el
  paquete saldría de una base superada (rc.11). Empaquetar produciría un artefacto
  engañoso.
- **No se registró PASS humano.** No hay evidencia humana; sólo evidencia visual
  automática (3 capturas verificadas por hash).
- **No se rebasó ni se mergeó nada.** Resolver el conflicto de `CajaDiaria.py` entre dos
  reescrituras divergentes de UI es una decisión de producto, no una decisión segura y
  reversible que Command Center pueda tomar solo.
- **No se tocó `main`, no hubo force-push, no se borró evidencia.** Los worktrees rc9,
  rc10, rc11 y las ramas ajenas (incluida
  `origin/feature/bc-caja-rc12-arqueo-en-caja-diaria-001`) quedaron intactos.

## 4. Clasificación de la validación (sin inventar PASS)

| Tipo | Estado |
| --- | --- |
| Validación automática | **PASS** — 36 pruebas focalizadas verdes, hashes MANIFEST 15/15 |
| Validación visual automatizada | **PASS con reserva** — 3 capturas reproducibles y verificadas por hash, generadas sobre base rc.11 |
| Validación humana real | **NO EJECUTADA** — y actualmente **no ejecutable de forma válida** sobre esta base |

## 5. Decisión pendiente (única, de producto)

`BC-CAJA-RC12-PEDIDOS-ATENCION-001` queda en `BLOCKED_ON_PRODUCT_DECISION`:

- **A — Portar:** reabrir el slice como `BC-CAJA-PEDIDOS-ATENCION-002` sobre `origin/main`
  (rc.14), resolviendo el conflicto de `CajaDiaria.py`, y emitir un HUMAN_GATE nuevo,
  válido contra la UI real actual.
- **B — Archivar:** marcar esta rama como superada. Se conserva como evidencia; el trabajo
  de Pedidos vuelve a la cola como slice futuro sobre rc.14.

Ninguna de las dos se ejecutó automáticamente: cambian qué software recibe la Óptica.
