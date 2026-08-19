# Artifact Consistency — BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008

Cada afirmación de los artefactos contra lo que el repositorio, los archivos y
las corridas dicen. Lo que no se verificó está declarado como tal.

> Este documento tiene dos partes. La primera es el registro de la **generación
> 1** y se deja tal como se escribió: sus cifras (3.529 artículos, 3.579
> movimientos, 25 filas en `REQUIRES_POLICY_DECISION`) son las de ese momento y
> quedaron superadas por la generación 2. La segunda parte, al final, es la
> vigente. No se reescribe la primera: un registro que se corrige a sí mismo hacia
> atrás deja de servir para auditar.

# Generación 1 — análisis, normalización y primer dry-run

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

---

# Generación 2 — decisiones aplicadas y excepciones investigadas

## Reanudación sin drift

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Se retomó, no se reinició | `git rev-parse HEAD` = `a21c304`, worktree limpio | ✔ |
| Los artefactos de la generación 1 estaban intactos | sha256 del catálogo `226a7245…` y de los dos recuentos | ✔ |
| Los XLSX no cambiaron | sha256 `388d4c51…` y `9be5ffcb…` | ✔ |
| Producción no cambió | sha256 `aa13f36e…`, 0 artículos, 0 movimientos, 0 `import_runs` | ✔ |
| No se repitió análisis válido | el perfil, la regla de identidad y el mapping se reusaron sin volver a correrlos | ✔ |

## Decisiones aplicadas

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Los 9 servicios quedaron `SERVICIO_NO_STOCKEABLE` | `articles.nature` en la base del dry-run | ✔ |
| Los 7 cristales quedaron `TRABAJO_BAJO_PEDIDO` | ídem | ✔ |
| Hilo, Tornillo y Plaqueta quedaron `PRODUCTO_STOCKEABLE` | ídem | ✔ |
| …y con **0 unidades** | `stock_movements` de esos tres artículos | ✔ 0 movimientos |
| `Par de patillas` no entró al catálogo | `SELECT … WHERE sku LIKE '%2000056%'` | ✔ 0 filas |
| Las 4 filas sin categoría entraron con 1 unidad cada una | `stock_movements` de `ASU-101181/100093/100240/108004` | ✔ |
| Cada excepción dejó escrito de dónde salió | `articles.notes` — «naturaleza por decisión humana» / «por evidencia: …» | ✔ |
| Ya no queda ninguna `REQUIRES_POLICY_DECISION` | salida del normalizador: `en espera de decision: 0` | ✔ |

## Evidencia de las investigaciones

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `inventario_base.xlsx` no es un conteo independiente | de 2.577 códigos comunes con PC, **2.577** traen el mismo stock | ✔ |
| Los ~99.900 aparecieron entre el 04 y el 10 de agosto | Hilo 949 → 99.981, Tornillo 708 → 99.425 | ✔ |
| Las 3.065 filas `AC PAT`/`AC APT`/`AC PAC` son todas stockeables | 2.773 `Armazones` + 289 `Lentes de Sol`, sin tercera categoría | ✔ |
| Steffani sólo aparece en `Armazones` | 585 de 585 | ✔ |
| Betania sólo aparece en `Armazones` | 357 de 357 | ✔ |
| Los otros «Mostacilla\*» son bienes físicos | `000012` en `Sujetadores` (PC y P2), `000040` en `Accesorios` | ✔ |
| `C8397` es un literal, no una fórmula | `data_type='n'`, fórmula `2860`, sin merge en toda la hoja | ✔ |
| 2.860 es el 33% del inventario de Asunción | 2.860 de 8.709 | ✔ 32,8% |

## Dry-run de la generación 2

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| 3.553 altas, 0 rechazos | plan del importador | ✔ |
| Catálogo sin stock | 3.553 artículos y 0 movimientos | ✔ |
| 5.849 + 2.899 unidades | suma por `destination` | ✔ |
| 3.583 movimientos | uno por línea de recuento | ✔ |
| Todo `INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL` | `group by` | ✔ |
| Fechas 2026-08-03 y 2026-08-10 | `group by substr(occurred_at,1,10)` | ✔ 2.575 / 1.008 |
| Idempotencia | archivo rechazado por sha256; corridas repetidas devuelven la misma | ✔ |
| Integridad, FK, negativos, huérfanos, efectos sin hecho | consultas sobre la copia | ✔ 0 |
| Caja intacta | 12 / 6.400.000 / 10 | ✔ |
| Producción intacta | sha256 idéntico antes y después | ✔ |

## Un error propio, corregido

`MAPPING_CATEGORIAS_NATURE.md` afirmaba que los ocho valores de ~99.900 caían
todos en el grupo de servicios. **Era falso**: `Hilo` (99.981) y `Tornillo`
(99.425) son dos de esos ocho y están en el grupo de repuestos físicos. La
decisión humana se tomó sobre esa afirmación.

La naturaleza aprobada sigue siendo correcta; lo que no servía era la cantidad.
Quedó corregido en el artefacto y resuelto poniendo las unidades en suspenso. Sin
detectarlo, la carga habría metido **108.799 unidades fantasma** en Pilar.

## Lo que NO se verificó en esta generación

- **Sigue sin cargarse nada sobre producción.** Todo lo anterior es lo que
  *pasaría*, medido sobre una copia real.
- **`Par de patillas` no se resolvió.** La vecindad sugiere que es la pieza; eso
  no es determinar, y la orden pedía no adivinar.
- **Los 2.860 limpia-cristales siguen sin validarse contra la realidad física.**
  Se descartó el error de planilla, que es lo único que un archivo puede probar.
- **Las cantidades de Hilo, Tornillo y Plaqueta no se reemplazaron por las de
  `inventario_base`** (949, 708, 575). Esos números son de la misma familia
  dudosa y tampoco son conteos: poner uno en lugar del otro sería elegir el error
  más pequeño, no la verdad.
- **La suite completa no se re-corrió.** Esta generación no toca código de
  producto: sólo las tablas de decisión del normalizador, y el dry-run ejercita
  ese camino de punta a punta. La corrida de la generación 1 (254 passed) sigue
  siendo la vigente.
