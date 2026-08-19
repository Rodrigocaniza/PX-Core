# Artifact Consistency — BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008

Cada afirmación de los artefactos contra lo que el repositorio, los archivos y
las corridas dicen. Lo que no se verificó está declarado como tal.

## Base canónica

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `origin/main` = `7db56a0` | `git rev-parse origin/main` tras `fetch --all --prune` | ✔ |
| Slice 6 = `5bc1540` | `git rev-parse origin/feature/…-006` | ✔ |
| Misión 007 = `a7b685c` | `git rev-parse origin/feature/…-007` | ✔ |
| `a7b685c` contiene `5bc1540` | `git merge-base --is-ancestor` | ✔ |
| `a7b685c` **no** está en `main` | `git merge-base --is-ancestor …-007 origin/main` | ✔ no está |
| Producción está por delante de `main` | rc.32/27 migraciones instaladas vs rc.31/21 en main | ✔ |
| Worktree creado desde `a7b685c` | `git rev-parse HEAD` en el worktree | ✔ |

## Estado productivo

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| rc.32 instalada | `VERSION.txt` del ejecutable | ✔ |
| 27 migraciones | `schema_migrations` | ✔ |
| 12 entradas / 6.400.000 / 10 líneas / 2 días / 8 pedidos | consultas sobre la base real | ✔ |
| Catálogo vacío | `articles`, `stock_movements`, `domain_events` en 0 | ✔ |
| Integridad y FK limpias | `PRAGMA integrity_check`, `PRAGMA foreign_key_check` | ✔ |

## Mapping de sucursales

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `PC → ASUNCION` no es hipótesis | fila `('PC','ASUNCION','MIGRACION-018', …)` en `cash_register_branches` | ✔ |
| `P2 → PILAR` | fila `('P2','PILAR','MIGRACION-020', …)` | ✔ |
| Esta instalación opera como PC | `orders.branch` = `PC` en los 8 pedidos reales | ✔ |

La orden autorizaba `PC → ASUNCION` sólo como hipótesis. Dejó de serlo porque el
vínculo ya existía en el estado canónico, que manda sobre la suposición.

## Perfil de los archivos

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| PC: 8.459 físicas, 5.871 vacías, 2.586 con artículo | conteo sobre la hoja | ✔ |
| P2: 1.054 físicas, 0 vacías, 1.052 con artículo | ídem | ✔ |
| 0 duplicados exactos y normalizados en ambos | `Counter` sobre nombre y sobre nombre normalizado | ✔ |
| 0 códigos repetidos dentro de cada archivo | `Counter` sobre el código embebido | ✔ |
| 0 filas de total/subtotal/encabezado repetido | búsqueda de `total|subtotal|suma|resumen` y de la palabra `articulo` | ✔ |
| `Casilla`, `Zona`, `Observacion` vacías en las 2.586 filas de PC | conteo de poblado por columna | ✔ |
| Los ~99.900 son todos de `Compostura` | listado de los 8 mayores con su categoría | ✔ |
| 11 filas concentran 818.867 de 837.403 | suma por tramo | ✔ |

## Identidad del artículo

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| 180 códigos en los dos archivos | intersección de códigos | ✔ |
| 42/42 códigos de barras son el mismo producto | inspección de los 16 que difieren: mismo producto, texto más flojo | ✔ |
| 29/31 del catálogo interno tienen descripción idéntica | similitud de secuencia | ✔ |
| Sólo 1 de 107 armazones compartidos describe lo mismo | similitud ≥ 0.80 sobre los 107 | ✔ |
| La regla produce 3.529 artículos, 226 globales | conteo tras aplicarla | ✔ |

## Naturaleza

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Las 15 categorías están cubiertas | cada categoría del universo tiene entrada en el mapeo | ✔ |
| Las 4 naturalezas usadas existen en el dominio | `ArticleNature` en `modulos/comercial/domain/models.py` | ✔ |
| `REQUIRES_POLICY_DECISION` no llega al catálogo | 25 registros excluidos, 0 en el CSV | ✔ |
| La naturaleza sale de la categoría, no del texto | el normalizador sólo lee `categoria` para decidirla | ✔ |

## Dry-run

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Corrió sobre copia, no sobre producción | `sha256` de la base real idéntico antes y después | ✔ |
| Usó el mecanismo real | `planificar_carga_de_articulos` → `aplicar_carga_de_articulos` → `cargar_stock_inicial` | ✔ |
| Plan sin rechazos | 3.529 altas, 0 rechazadas | ✔ |
| Catálogo no crea stock | 3.529 artículos y 0 movimientos | ✔ |
| 3.579 movimientos, 8.705 + 2.897 | conteo y suma por `destination` | ✔ |
| Todo `INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL` | `group by kind`, `group by reason_code` | ✔ |
| Fecha del recuento, no la de hoy | `group by substr(occurred_at,1,10)` → 2026-08-03 y 2026-08-10 | ✔ |
| Ningún movimiento sin nota ni sin actor | conteo de vacíos | ✔ 0 |
| Idempotencia del catálogo | reaplicar el mismo archivo se rechaza por sha256 | ✔ |
| Idempotencia del recuento | repetir devuelve la misma corrida; 0 duplicados | ✔ |
| Integridad, FK, negativos, huérfanos | consultas sobre la copia final | ✔ 0 |
| Caja intacta | 12 / 6.400.000 / 10 sin cambios | ✔ |

## Lo que NO se verificó, y hay que decirlo

- **No se cargó nada sobre producción**, por prohibición explícita de la orden.
  Todo lo anterior describe lo que *pasaría*, medido sobre una copia real, no lo
  que pasó.
- **Los 2.860 limpia-cristales de Asunción no se validaron contra la realidad
  física.** No tienen forma de centinela y por eso entrarían tal cual. Es una
  confirmación pendiente, no un defecto detectado.
- **`Compostura` y las 4 filas sin categoría quedaron sin naturaleza.** Se
  desglosaron en grupos con evidencia, pero no se asignó ninguna: hacerlo sería
  deducir la naturaleza del texto.
- **La descripción canónica de los 139 códigos con texto distinto se resolvió
  por regla** — gana la más informativa, la otra queda anotada en el artículo con
  su archivo y su fila. Es una regla defendible, no una verdad verificada.
- **Las 11 filas rechazadas no se recuperaron.** Nueve no tienen código y dos no
  tienen descripción. No se inventó ninguno de los dos.
- **La suite completa no se re-corrió**: la misión no toca código de producto.
  Sí se corrió la suite comercial en esta máquina: **254 passed**.
