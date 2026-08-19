# Categorías → `nature`

Propuesta **por categoría**, nunca fila por fila. Cubre las 15 categorías que
aparecen en los dos archivos. Sólo se justifican las que no son obvias.

## Resueltas — se aplican sin decisión humana

| Categoría | PC | P2 | `nature` | Confianza |
| --- | ---: | ---: | --- | --- |
| Armazones | 2179 | 825 | `PRODUCTO_STOCKEABLE` | alta |
| Lentes de Sol | 241 | 59 | `PRODUCTO_STOCKEABLE` | alta |
| Lente de contacto | 100 | 78 | `PRODUCTO_STOCKEABLE` | alta |
| Sujetadores | 27 | 20 | `PRODUCTO_STOCKEABLE` | alta |
| Accesorios | 13 | 10 | `PRODUCTO_STOCKEABLE` | alta |
| Líquidos Multipropósitos | 12 | 9 | `PRODUCTO_STOCKEABLE` | alta |
| Estuches | 2 | — | `PRODUCTO_STOCKEABLE` | alta |
| Estuche LC | — | 2 | `PRODUCTO_STOCKEABLE` | alta |
| Limpia Cristales | 2 | 2 | `PRODUCTO_STOCKEABLE` | alta |
| Marcadores | 1 | — | `PRODUCTO_STOCKEABLE` | alta |
| Medicamentos | 1 | — | `PRODUCTO_STOCKEABLE` | alta |
| Organizadores | 1 | 2 | `PRODUCTO_STOCKEABLE` | alta |
| Paños | 1 | 1 | `PRODUCTO_STOCKEABLE` | alta |
| **Cristales** | — | 23 | `TRABAJO_BAJO_PEDIDO` | alta |

**Equivalentes agrupados.** `Estuches` (PC) y `Estuche LC` (P2) son la misma
naturaleza y quedan como dos categorías con el mismo tratamiento; no se
fusionan los nombres porque el archivo distingue estuche de anteojo de estuche
de lente de contacto y esa distinción es del negocio, no ruido.

### Por qué `Cristales` no es stockeable

Las 23 filas son tipos de cristal — Multiblue, Progresivo OP, Futurex Protec,
Policarbonato AR, Kto.AR, Multifocal Foto AR. La columna «Marca» no trae un
fabricante de producto: trae **el laboratorio que lo fabrica**, Optilab y Servi
Opti. Un cristal así no está en la góndola: se pide cuando entra la receta. Eso
es exactamente `TRABAJO_BAJO_PEDIDO`.

Lo confirma el propio dato: los stocks declarados son 949, 967, 974, 984, 994,
999, 1971. No son conteos, son el número que pone un sistema para que algo no se
acabe nunca. **12.272 unidades declaradas que no entran al depósito**, y no
entran porque un cristal recetado nunca estuvo ahí.

## Resueltas fila por fila — `Compostura` y `(sin categoría)`

Ver `EXCEPCIONES_RESUELTAS.md` para la evidencia de cada una. El resumen:

### `Compostura` — 21 filas en P2

Decisión humana del 19/08/2026: la categoría se abre en tres.

| Grupo | Filas | `nature` |
| --- | ---: | --- |
| Servicios | 9 | `SERVICIO_NO_STOCKEABLE` |
| Tipos de cristal | 7 | `TRABAJO_BAJO_PEDIDO` |
| Repuestos físicos — Hilo, Tornillo, Plaqueta | 3 | `PRODUCTO_STOCKEABLE` |
| `000005 Mostacillas` — resuelto por evidencia | 1 | `PRODUCTO_STOCKEABLE` |
| `2000056 Par de patillas` — **sin resolver** | 1 | — |

> **Corrección de una afirmación de este mismo artefacto.** La versión anterior
> decía que los ocho valores de ~99.900 caían todos en el grupo de servicios.
> Es falso: `Hilo` (99.981) y `Tornillo` (99.425) son dos de esos ocho, y están
> en el grupo de repuestos físicos. La naturaleza que se les aprobó es correcta
> — un hilo y un tornillo son cosas —, pero su **cantidad** es un centinela, no
> un conteo. Por eso los tres repuestos entran al catálogo con las unidades en
> suspenso. El error importa: sin corregirlo, la carga habría metido 108.799
> unidades fantasma en el depósito de Pilar.

### `(sin categoría)` — 4 filas normalizables en PC

Las cuatro quedaron en `PRODUCTO_STOCKEABLE` sin intervención humana, porque la
evidencia lo determina: las **3.065** filas del universo cuya descripción empieza
con `AC PAT` / `AC APT` / `AC PAC` son `Armazones` (2.773) o `Lentes de Sol`
(289). No hay una tercera posibilidad, y **las dos categorías son
`PRODUCTO_STOCKEABLE`**: la naturaleza no depende de cuál sea.

La categoría sí se pudo determinar en dos de ellas y en dos no:

| Código | Categoría | Evidencia |
| --- | --- | --- |
| `100093` | Armazones | marca Steffani, en `Armazones` en las 585 filas donde aparece |
| `100240` | Armazones | marca Betania, en `Armazones` en las 357 filas donde aparece |
| `101181` | *(vacía)* | sin marca; `AC PAT` se reparte 2.773/289 entre las dos |
| `108004` | *(vacía)* | ídem |

Las dos sin categoría entran con la categoría vacía en vez de inventada. Un dato
ausente se completa después; uno inventado no se detecta nunca. No cambia nada
del stock: la naturaleza, que es lo que decide si el artículo se mueve, está
determinada en las cuatro.

## Cómo se hizo, y cómo no

- La naturaleza sale **de la categoría**. Donde la categoría no informaba —
  porque no había, o porque era un cajón de sastre — se resolvió fila por fila
  con decisión humana o con evidencia del propio universo de datos, y quedó
  escrito cuál de las dos fue en cada caso.
- Ninguna categoría quedó sin cubrir, y ya no queda ninguna en
  `REQUIRES_POLICY_DECISION`.
- Lo que sigue sin resolverse es **una fila** (`2000056 Par de patillas`) y
  **cuatro cantidades**, no cuatro naturalezas. La diferencia importa: una
  naturaleza equivocada rompe el comportamiento del sistema; una cantidad en
  suspenso sólo espera que alguien cuente.
