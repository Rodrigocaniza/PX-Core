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

## Sin resolver — `REQUIRES_POLICY_DECISION`

### 1. `Compostura` — 21 filas en P2, 822.233 unidades declaradas

No hay una sola naturaleza honesta para esta categoría: adentro hay tres cosas
distintas.

**(a) Servicios puros — 11 filas.** CENTRADO, Compostura Simple, Compostura
Flex, Compostura de Patilla Izquierda / Derecha, Compostura del Aro / del Puente
/ de Porta Plaquetas, Adaptación de cristal. Aquí caen **los ocho valores de
~99.900**: son servicios marcados como inagotables por el sistema viejo.
→ correspondería `SERVICIO_NO_STOCKEABLE`.

**(b) Tipos de cristal — 7 filas.** Organico UVX, Fotocromático (AR),
Multifocal (OP), Kripto (Kto) Organico UVX, Blue Ar, Solamax, Bifocal (ST). Son
lo mismo que la categoría `Cristales`, sólo que archivadas en otro lado.
→ correspondería `TRABAJO_BAJO_PEDIDO`.

**(c) Repuestos físicos — 3 filas.** Hilo, Tornillo, Plaqueta. Y `Par de
patillas`, que puede ser repuesto o el servicio de cambiarlas.
→ correspondería `PRODUCTO_STOCKEABLE`, salvo Par de patillas.

**(d) Una fila mal archivada.** `000005 Mostacillas`, marca Proray, stock 2. En
el otro archivo el mismo tipo de artículo está en `Sujetadores`.

**Qué se necesita:** una sola decisión — *«Compostura se abre en estos tres
grupos»* — y el sistema reclasifica las 21 filas. No hay que mirar fila por fila:
los tres grupos están listados arriba.

### 2. `(sin categoría)` — 6 filas en PC, 6 unidades

Las seis dicen `AC PAT FLEX …`, `AC PAC FIJA …` o directamente `Armazon`, así
que **parecen** armazones. Pero deducir la naturaleza del texto de la
descripción es precisamente lo que el sistema prohíbe: el día que alguien
escriba «armazón de cristal», el cristal se pondría a descontar stock.

Dos de las seis además no tienen código y ya están rechazadas por eso.

**Qué se necesita:** decir «esas cuatro son Armazones». No es una inferencia si
lo dice una persona.

## Cómo se hizo, y cómo no

- La naturaleza sale **de la categoría**, no de la descripción.
- Ninguna categoría se dejó sin cubrir: 13 resueltas, 1 resuelta con
  justificación, 2 explícitamente sin resolver.
- Ninguna categoría ambigua se resolvió «para que cierre». Las 822.237 unidades
  en suspenso son el precio de no adivinar, y se recuperan en cuanto haya
  decisión.
