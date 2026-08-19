# Artifact Consistency — BC-OPTICA-CONCILIACION-INVENTARIO-CORREGIDO-V1-010

Cada afirmación contra lo que los archivos, la base y las corridas dicen.

## Base canónica y estado

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `main` = `7db56a0`, detrás de producción | `git rev-parse`, 008 no es ancestro de main | ✔ |
| Base elegida `f5a55b7` | tip de la 008, contiene el código de rc.32 | ✔ |
| Producción: 3.554 art / 3.583 mov / 5.849 + 2.899 | consultas | ✔ |
| `sha256` `25cd7d04…` | antes y después de todo | ✔ intacta |
| V1-009 en Safe Pause | `dceac1f`, `state = SAFE_PAUSE`, nada escrito | ✔ |

## Los archivos corregidos

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Se localizaron solos | búsqueda en Downloads/Desktop/Documents | ✔ |
| Son OLE2/BIFF legacy | magic `D0CF11E0A1B11AE1` | ✔ |
| Los originales no se modificaron | sha256 antes y después de convertir | ✔ |
| Conversión sin alterar datos | Excel COM en modo `ReadOnly`, `SaveAs` a copia | ✔ |
| PC: 1.974 filas, P2: 938 | conteo | ✔ |
| 0 merges, 0 fórmulas, 0 totales/subtotales | inspección celda a celda | ✔ |
| 0 códigos duplicados, 0 filas sin código | `Counter` sobre `Cod. Barra` | ✔ |
| Columnas nuevas: `Cod. Barra`, `CostoA`, `PrecioA` | encabezado | ✔ |
| Ningún archivo trae stock ≤ 0 | conteo | ✔ 0 en los dos, y también en los anteriores |

## Comparación

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| 3.687 pares (sucursal, sku) clasificados | unión de anterior y corregido | ✔ |
| 775 ausentes, 776 unidades | diferencia de conjuntos, suma de su stock anterior | ✔ |
| 641 de los ausentes son armazones, 774 tenían stock 1 | `Counter` | ✔ |
| «Ausente» = stock 0 en el sistema viejo | los dos informes filtran stock > 0 | ✔ |
| 28 centinelas, 842.497 unidades | umbral ≥9.000 o 890–1.000 | ✔ |
| Asunción ahora trae 7 centinelas que no tenía | `Composturas` no existía en el PC anterior | ✔ |
| 2.769 artículos coinciden con el ledger | comparación por (destino, sku) | ✔ |

## Reglas de negocio

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Cristales ya son `TRABAJO_BAJO_PEDIDO` | 30 artículos en el catálogo | ✔ |
| Composturas-servicio ya son `SERVICIO_NO_STOCKEABLE` | 9 artículos | ✔ |
| **Ningún artículo no stockeable tiene movimientos** | consulta sobre `stock_movements` | ✔ **0** |
| Por lo tanto no hay nada que compensar | corolario del anterior | ✔ |
| `Adaptación de cristal` ya es servicio | `articles.nature` | ✔ |
| `laboratories` está vacía | `SELECT COUNT(*)` | ✔ 0 |
| `sale_items.laboratory` es texto libre | `pragma table_info` | ✔ |
| No existe artículo de Delivery/Envío | búsqueda por nombre | ✔ 0 |
| `sale_items.no_cost` **existe** | `pragma table_info` | ✔ |
| 0 líneas lo usan hoy | conteo | ✔ |
| `000037` tiene precio 0 y costo 4.740 | archivo corregido | ✔ |
| `000037` tiene 726 unidades en el ledger | 210 ASU + 516 PIL | ✔ |
| `2000212 ST Fotocromatico` sin laboratorio | no se le asignó ninguno | ✔ declarado |

## Dry-run

| Afirmación | Resultado |
| --- | --- |
| Sobre copia, no sobre producción | ✔ `sha256` idéntico |
| 42 artículos de 46 registros | ✔ 4 SKU globales en las dos sucursales |
| Catálogo no crea stock | ✔ 0 movimientos tras las altas |
| `AJUSTE_POSITIVO` 47 / `AJUSTE_NEGATIVO` 65 | ✔ |
| `2000056` → `SERVICIO_NO_STOCKEABLE`, 0 movimientos que compensar | ✔ |
| Las dos corridas de la 008 enteras | ✔ 3.583 movimientos, 8.748 unidades |
| Los 5 pendientes siguen registrados | ✔ |
| Integridad, FK, negativos, huérfanos, efectos | ✔ 0 |
| Caja histórica | ✔ 12 / 6.400.000 / 10 |
| Idempotencia | ✔ copia byte a byte igual al reaplicar |

### Dos errores propios que el dry-run destapó

**Primero:** clasifiqué como «artículo nuevo» todo lo que no estaba en el archivo
anterior. Falso: un SKU global que antes sólo aparecía en Pilar **ya existe** en
el catálogo; lo nuevo es que ahora también se reporta en Asunción. Los 9
Composturas de Asunción son exactamente eso. La base lo rechazó con un `UNIQUE
constraint` y se corrigió clasificando contra el catálogo real, no contra el
archivo viejo.

**Segundo:** cuatro SKU globales nuevos aparecen en **las dos** sucursales, y el
primer intento creaba el artículo dos veces. Es la misma regla de identidad de la
008: un artículo, stock en dos depósitos.

**Y una comprobación mal formulada:** verificaba que hubiera exactamente 3.583
movimientos con `document_kind = 'CARGA_INICIAL'`, pero las altas nuevas entran
por el mismo camino y suman. Lo correcto es verificar las dos corridas de la 008
por su `document_id`, que es lo que ahora hace.

## Lo que NO se verificó, y hay que decirlo

- **No se escribió nada en producción.**
- **No se sabe qué pasó con los 775 ausentes.** Se descartó que sean filas en
  cero —ningún informe las trae— pero 647 armazones en 16 días no se explica con
  ventas. No se descontaron.
- **Los 2.857 limpia-cristales siguen sin conteo físico independiente.** La
  evidencia mejoró mucho (se mueve −3 en 16 días, tiene precio y costo) pero es
  la misma fuente que dijo 2.860.
- **No se verificó que los archivos corregidos sean «más correctos».** Se
  verificó que son posteriores, mejor estructurados y con más columnas. Que sus
  cantidades sean ciertas es otra cosa, y los centinelas demuestran que no todas
  lo son.
- **La suite completa no se re-corrió.** La misión no toca código de producto.

---

# Generación 2 — decisiones humanas incorporadas, plan recalculado

El plan de la generación 1 **quedó obsoleto y no se reutilizó**: se recalculó
entero. Sus cifras (42 altas, +47/−65, ASU 6.904, PIL 2.892) quedan sólo como
registro.

## Sin drift

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| HEAD `e146893`, worktree limpio | `git rev-parse`, `git status` | ✔ |
| Los dos `.xls` sin cambios | sha256 `13f62244…` y `a866551f…` | ✔ |
| Producción sin cambios | `25cd7d04…`, 3.554 art, 3.583 mov | ✔ |
| Perfil y comparación reutilizados | no se volvieron a correr | ✔ |

## Decisiones aplicadas

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| Los 4 conceptos pasan a `SERVICIO_NO_STOCKEABLE` | `articles.nature` en la copia | ✔ |
| Los 4 tenían 0 unidades: nada que compensar | suma de movimientos por artículo | ✔ 0 |
| No queda ningún `Compostura` como producto | consulta por categoría y naturaleza | ✔ 0 |
| Las cifras viejas quedan sólo como evidencia | escritas en `articles.notes` | ✔ |
| `000010` ASUNCION sin ajuste y con su pendiente | 0 unidades, 1 fila de `PENDING` | ✔ |
| `000010` PILAR intacto en 10 | suma por destino | ✔ |
| `000037` sin stock nuevo y activo | 210 / 516, `active = 1` | ✔ |

## Los retiros

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| 773 ausentes reales de 775 declarados | descontados el renumerado y el que nunca existió | ✔ |
| Los 773 tenían stock: ninguno era baja limpia | consulta por artículo y destino | ✔ |
| 645 + 128 = 773 unidades compensadas | suma por sucursal | ✔ |
| Se compensa **antes** de retirar | orden del script; ningún inactivo con stock | ✔ |
| 766 retirados, 5 no retirables | los 5 viven en la otra sucursal | ✔ |
| Los movimientos originales no se tocan | las dos corridas de la 008 enteras | ✔ 3.583 / 8.748 |

## Tres errores que el recálculo destapó, y que habrían hecho daño

**1. Un código renumerado.** El archivo corregido normaliza algunos códigos de
barra a 13 dígitos con un cero adelante: `300653145470` figuraba como baja y
`0300653145470` como alta, siendo el mismo Opti Free Express. Se buscó el patrón
en los 775 y **es el único caso** — no es sistémico, pero de no verlo se habría
retirado un artículo vivo y creado un duplicado.

**2. El retiro es por artículo; la ausencia, por sucursal.** El primer intento
falló con `ArticuloEnUso`: el producto **impide** desactivar algo que todavía
tiene stock, «porque quedaría sin nadie que lo mire». La guarda es correcta y el
error era mío. Cinco artículos faltan en el archivo de una sucursal y viven en la
otra: se compensa el depósito ausente y el artículo sigue activo.

**3. Una fila que nunca fue un artículo.** `ASU-101814` era la fila sin
descripción que la 008 rechazó. Contarla como baja habría inflado el número.

## Dry-run e invariantes

| Afirmación | Resultado |
| --- | --- |
| Sobre copia, no sobre producción | ✔ `sha256` idéntico |
| 41 artículos de 45 registros | ✔ 4 SKU globales consolidados |
| Catálogo no crea stock | ✔ 0 movimientos tras las altas |
| Stock total 8.748 → 9.052 | ✔ cierra: +1.064 − 773 + 47 − 34 |
| Integridad, FK, negativos, huérfanos, efectos | ✔ 0 |
| Caja histórica | ✔ 12 / 6.400.000 / 10 |
| Historia de la V1-008 | ✔ intacta |

### Idempotencia — una precisión honesta

Al reaplicar **no se escribió una sola fila**: artículos, activos, movimientos,
unidades por sucursal, corridas y bitácora quedaron idénticos, y la última entrada
de auditoría sigue siendo la de la corrida original. Pero el archivo **no** sale
byte a byte igual, porque abrir SQLite en modo escritura reorganiza páginas
internas. En misiones anteriores sí salía idéntico porque el camino de replay ni
llegaba a abrir la base para escribir. La verificación aquí es por contenido, y
así queda dicho en vez de afirmar un «byte a byte» que no se cumple.

## Lo que NO se verificó

- **No se escribió nada en producción.**
- **No se sabe por qué desaparecieron 773 artículos.** El dueño confirmó que el
  corregido es la versión correcta y que corresponde retirarlos; eso es una
  decisión de negocio, no una verificación. Lo que sí se verificó es que ninguno
  se borra: se compensa y se desactiva, conservando la historia.
- **`000010` en Asunción sigue sin cantidad**, por decisión explícita.
- **Los 28 centinelas siguen declarados en los archivos.** Ninguno entró al
  ledger, pero los archivos los seguirán trayendo mientras el sistema viejo los
  genere.
