# HUMAN_GATE — V1-015

**Una sola pregunta.** Treinta de los treinta y un casos se resuelven con
evidencia y no necesitan que mires nada. Queda uno.

---

## `2000212 ST Fotocromatico`

| | |
|---|---|
| categoría | Armazones |
| naturaleza | `PRODUCTO_STOCKEABLE` |
| marca hoy | `Laboratorio Optilab` |
| laboratorio por defecto | ninguno, y es a propósito (V1-012) |

El brief de V1-012 lo listaba entre los tipos de cristal. En producción no lo es:
es un armazón que se stockea. Un armazón **sí** tiene marca real —es un
fabricante— sólo que la que tiene no lo es: es un laboratorio.

No lo resuelvo solo porque las dos salidas son razonables y llevan a lugares
distintos:

- si la fuente corregida del 19/08 le da una marca real en el bloque de
  *Armazones*, esa marca gana y el caso se cierra sin decidir nada;
- si no le da ninguna, la marca queda en blanco como los 28 cristales;
- y si en realidad es un cristal mal categorizado, entonces lo que hay que
  corregir es la categoría, no la marca, y eso es otra misión.

**Qué necesito:** al volver a la Óptica, correr la herramienta con
`--fuente-corregida "C:\Users\Striker\Downloads\Inventario P2.xls"`. Si el
archivo trae una marca real para `2000212`, el caso se resuelve solo y este gate
se cierra sin que decidas nada. Si no la trae, ahí sí hace falta tu decisión
entre blanco y recategorizar.

---

## Lo que encontré de paso y no toqué

**`Óptica Puppilent\`s` y `Optica Puppilents` conviven** en el catálogo — siete
artículos con una grafía y uno con la otra. Es la misma óptica escrita de dos
maneras. Unificarlas tocaría artículos fuera de estos 31, así que no entra acá.

**«Laboratorio Servi Optical» y «ServiOptica»** siguen siendo la pregunta 3 del
gate de V1-012. Para limpiar la marca no hizo falta resolverla: alcanzaba con
saber que ese texto nombra un laboratorio y no un fabricante. Sigue abierta para
cuando haya que cargarles los teléfonos.

Los otros pendientes de V1-012 —los 7 códigos ausentes, el par
`2000078`/`2000219`, los 6 cristales sin laboratorio y los tres teléfonos—
quedaron donde estaban. Se leyeron como evidencia; ninguno se resolvió acá.
