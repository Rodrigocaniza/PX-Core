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
