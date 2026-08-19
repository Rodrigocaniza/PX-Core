# Artifact Consistency — BC-OPTICA-RECUENTO-FISICO-PENDIENTES-V1-009

Cada afirmación contra lo que la base, el repositorio y las corridas dicen. Lo
que no se verificó está declarado como tal.

## Base canónica

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `origin/main` = `7db56a0` | `git rev-parse` tras `fetch --all --prune` | ✔ |
| Misión 008 = `f5a55b7` | `git rev-parse origin/feature/…-008` | ✔ |
| La 008 **no** está en `main` | `git merge-base --is-ancestor` | ✔ no está |
| `f5a55b7` desciende del código de rc.32 y de la instalación | ancestros `5bc1540` y `a7b685c` | ✔ |
| Worktree creado desde `f5a55b7` | `git rev-parse HEAD` | ✔ |

Ramificar desde `main` habría eliminado Commercial Core entero: `main` está en
rc.31 con 21 migraciones y ni siquiera existe la tabla `articles`.

## Estado productivo

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| rc.32, 27 migraciones | `VERSION.txt`, `schema_migrations` | ✔ |
| 3.554 artículos, 3.583 movimientos | conteos | ✔ |
| 5.849 + 2.899 = 8.748 unidades | suma por `destination` | ✔ |
| Caja histórica | 12 / 6.400.000 / 10 / 2 / 8 | ✔ |
| Integridad, FK, negativos | `PRAGMA` y `stock_actual` | ✔ 0 |
| `sha256` | `25cd7d04…` | ✔ |

## Los cinco pendientes

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Salen de la base, no de una lista escrita a mano | `admin_audit_log`, acción `STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION` | ✔ 5 |
| Cada uno trae artículo, código, sucursal y `nature` | join contra `articles` | ✔ |
| Los cinco siguen sin movimiento en su sucursal | consulta por artículo y destino | ✔ 0 |
| `000010` conserva 10 unidades en PILAR | suma por destino | ✔ |
| ASUNCION sigue sin movimiento por sus 2.860 | ídem | ✔ 0 |
| Ninguno estaba ya cerrado | ausencia de `PHYSICAL_COUNT_CONFIRMED` | ✔ |

## Dónde contar — lo que la evidencia NO permite decir

`PC - Inventario.xlsx` tiene columnas `Casilla` y `Zona`, pero vienen **vacías en
las 2.586 filas**; `P2` no las tiene; y `articles.location` está vacío en los
cinco. **No hay dato de ubicación**, así que el gate dice sucursal, categoría y
marca, y nada más. Inventar un estante sería exactamente el tipo de dato que esta
misión existe para evitar.

## Mecanismo

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| El hecho es `INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL` | vía `cargar_stock_inicial`, el camino que ya usa Commercial Core | ✔ |
| La fecha es la del recuento, no la del XLSX | `occurred_at` del movimiento en el dry-run | ✔ 2026-08-19 |
| La cifra vieja no se borra ni se reescribe | el cierre guarda `source_reported_quantity`, `fuente_anterior` y `corte_anterior` | ✔ |
| Vínculo explícito reportado → contado → movimiento | `run_id` en el registro de cierre | ✔ |
| Cantidad cero no inventa un movimiento | `PHYSICAL_COUNT_CONFIRMED` con `physical_count = 0` y `movimiento_creado = false` | ✔ |
| Las filas de `PENDIENTE` no se borran | conteo antes y después | ✔ |

## Dry-run — PASS, 0 fallas

Sobre copia consistente de la base real, con cantidades de ensayo elegidas para
ejercitar los dos caminos (143, 12, **0**, 37, **0**):

| Afirmación | Resultado |
| --- | --- |
| 3 movimientos nuevos, uno por cada cantidad > 0 | ✔ |
| ASUNCION 5.849 → 5.992, PILAR 2.899 → 2.948 | ✔ |
| Los dos ceros quedaron registrados y sin unidades | ✔ |
| `000010` quedó en 143 en ASUNCION y siguió en 10 en PILAR | ✔ |
| Repetir el conteo no escribe nada | ✔ |
| Integridad, FK, negativos, huérfanos, efectos sin hecho | ✔ 0 |
| Caja histórica intacta | ✔ |
| La base productiva quedó con el mismo `sha256` | ✔ |

### Un detalle de legibilidad que se corrigió

La primera versión del mecanismo, al reintentar un conteo ya asentado, lo
reportaba como **falla** («de más»). No lo era: reaplicar algo ya hecho es no
tener nada que hacer. Se separó el caso «ya estaba cerrado» del caso «no lo
reconozco», porque la evidencia de una corrida idempotente no debería leerse como
un error.

## Seguridad productiva

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Backup tomado por la API de backup de SQLite | `bc-caja-prerecuento-20260819-142306.sqlite3` | ✔ 5.906.432 bytes |
| Equivalente a la base | artículos, movimientos, unidades, pendientes, Caja, integridad, FK | ✔ |
| Tomarlo no tocó producción | `sha256` idéntico antes y después | ✔ |
| El paso productivo hace su propio backup | está en el código, probado en el dry-run | ✔ |

## Lo que NO se verificó, y hay que decirlo

- **No se escribió nada en producción.** Todo lo anterior es lo que pasaría.
- **Las cantidades del dry-run son inventadas a propósito** para probar el
  mecanismo. No son un conteo ni pretenden serlo, y no se parecen a las cifras
  de las planillas para que nadie las confunda.
- **No hay forma de verificar desde acá cuántos hay en el estante.** Esa es la
  única cosa irreducible de esta misión, y es exactamente por lo que existe.
- **La suite completa no se re-corrió.** La misión no toca código de producto:
  agrega una herramienta que usa el camino existente. El dry-run lo ejercita de
  punta a punta.
