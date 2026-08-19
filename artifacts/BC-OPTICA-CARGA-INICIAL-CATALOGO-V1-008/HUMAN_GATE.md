# HUMAN_GATE mínimo — quedan dos cosas

Todo lo demás está resuelto y el dry-run volvió a dar **PASS con 0 fallas**.
Producción sigue intacta: 0 artículos, 0 movimientos.

Las decisiones de Compostura y las 4 filas sin categoría ya están aplicadas. La
evidencia de cada una está en `EXCEPCIONES_RESUELTAS.md`.

---

## A. `2000056 Par de patillas` — sigue ambigua

| Código | Descripción | Marca | Stock | Recomendación | Evidencia |
| --- | --- | --- | ---: | --- | --- |
| `2000056` | Par de patillas | Óptica San Cayetano | 526 (P2) · 616 (base 08-04) | **sin recomendación** | las vecinas 2000054/55 ya son los servicios de cambiar patilla, lo que sugiere que ésta es la pieza; pero la cantidad no discrimina (en esta categoría los números saltan en las dos direcciones sin ser conteos), la marca aparece en Compostura y en Sujetadores, y no está en ningún otro archivo |

**Lo que hace falta:** ¿es el repuesto físico que se entrega, o el servicio de
cambiar las patillas?

- **repuesto** → `PRODUCTO_STOCKEABLE`, y hará falta un conteo real (los 526 no
  son un conteo)
- **servicio** → `SERVICIO_NO_STOCKEABLE`, sin unidades

Mientras tanto queda afuera del catálogo. Es una fila.

---

## B. `000010 Limpia Cristal = 2.860` — `LIKELY_REAL_BUT_REQUIRES_HUMAN_CONFIRMATION`

**Valor fuente exacto:** celda `C8397` de `PC - Inventario.xlsx`, entero literal
`2860`. Sin fórmula, sin merge, sin subtotal, sin arrastre, sin observación. La
hoja no tiene un solo rango combinado.

**Interpretación:** es un número capturado, no un artefacto de planilla.
`inventario_base.xlsx` (corte 08-04) trae el mismo 2.860 — pero los 2.577 códigos
comunes con PC coinciden **todos**, así que eso confirma transcripción fiel del
sistema, no que el depósito los tenga.

**Evidencia encontrada:**

- a favor — no tiene forma de centinela (los de este juego de datos son ~99.900 o
  ~999); es marca propia, un consumible de bulto; y el vecino
  `000037 LIMPIA CRISTAL OBSEQUIO` llega a 516 en Pilar, así que los cientos son
  normales en esta familia
- en contra — es **2,9×** el segundo valor más alto de todo Asunción
  (`Goma Niño`, 978); son **el 33% de todo el inventario de la sucursal**; Pilar
  declara **10** del mismo artículo; y ningún archivo dice si son frascos,
  sachets o mililitros

**Recomendación concreta:** `CONFIRMAR 2860` **o** `NO IMPORTAR 2860`.

No se propone una corrección: no existe evidencia documental de otro valor, y
cambiarlo a ojo sería inventar un conteo.

---

## Y algo que la investigación destapó, para que lo sepas

`Hilo` y `Tornillo` — dos de los tres repuestos que aprobaste como
`PRODUCTO_STOCKEABLE` — resultaron ser **dos de los ocho valores de ~99.900**. Un
artefacto anterior de esta misión decía que los ocho eran servicios; era falso y
quedó corregido.

**La naturaleza que aprobaste sigue siendo correcta**: un hilo y un tornillo son
cosas y se venden. Lo que no sirve es la cantidad. `inventario_base` los tenía en
949 y 708 el 4 de agosto; el 10 aparecen en 99.981 y 99.425. Nadie compró 99.000
hilos: alguien los puso en «no se acaba nunca».

Los tres entran al catálogo con **las unidades en suspenso**. Sin eso, la carga
habría metido 108.799 unidades fantasma en Pilar. No hace falta que decidas nada:
esperan un recuento real, como cualquier artículo sin contar.

---

## Estado si respondés sólo esto

| | ASUNCION | PILAR |
| --- | ---: | ---: |
| líneas de recuento | 2.575 | 1.008 |
| unidades | **5.849** | **2.899** |

3.553 artículos · 3.583 movimientos `INVENTARIO_INICIAL` · dry-run **PASS**.

Con `Par de patillas` resuelta y `Limpia Cristal` confirmada o descartada, se
regenera, se vuelve a correr el dry-run y se te devuelve el **HUMAN_GATE final de
importación** con el impacto exacto, el backup previsto y el rollback.
