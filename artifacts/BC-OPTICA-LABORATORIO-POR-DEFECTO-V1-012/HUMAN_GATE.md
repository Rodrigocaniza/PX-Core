# HUMAN_GATE — V1-012

**No bloquea nada.** La misión está aplicada y cerrada: los 24 cristales que
existen tienen su laboratorio y la pantalla ya los sugiere. Lo que sigue son
decisiones de catálogo que no puedo tomar sin inventar datos.

---

## 1. Siete códigos del brief no existen en producción

Ni activos, ni inactivos, ni en ningún backup.

| código | nombre en el brief | laboratorio pedido |
|---|---|---|
| `2000124` | Foto Sunsenso | Laboratorio Optilab |
| `2000139` | Blue Light 1.60 | ServiOptica |
| `2000077` | Fotocromatico Blue Ar | Laboratorio Optilab |
| `2000078` | Multiblue Foto Ar | Laboratorio Optilab |
| `2000090` | Fotocromatico AR | Laboratorio Optilab |
| `2000231` | Multifocal Futurex | Laboratorio Optilab |
| `2000235` | Ultradelgado 1.67 AR | Laboratorio Optilab |

**Qué necesito saber:** ¿son cristales que la Óptica vende y que nunca entraron
al catálogo, o son códigos de otra planilla que ya no corresponden? Si son
reales, se dan de alta como `TRABAJO_BAJO_PEDIDO` en *Cristales* con su
laboratorio, en una misión aparte. Si no, se descartan y queda el registro.

## 2. `2000078` y `2000219` pueden ser el mismo cristal

`2000078 Multiblue Foto Ar` no existe. `2000219 Multiblue Foto Ar` sí, activo, y
el nombre coincide **exacto**. No lo asigné por nombre porque el código es la
identidad del catálogo, y esa regla es la que evitó fusionar armazones distintos
en V1-008.

**Qué necesito saber:** ¿es el mismo cristal renumerado? Si sí, `2000219` va a
Laboratorio Optilab y son 25 asignaciones.

## 3. Seis cristales activos sin laboratorio

El brief no los menciona. Hoy la pantalla no les sugiere nada.

`2000127 Green AR` · `2000210 Multifocal Foto AR` · `2000211 Multifocal AR` ·
`2000219 Multiblue Foto Ar` · `2000227 Progresivo Rodensto` · `2000239 POLIBLUE`

**Qué necesito saber:** a qué laboratorio va cada uno, o si se quedan sin
preferencia a propósito.

Dato útil, porque en esas planillas la «Marca» es el laboratorio: cinco de los
seis —`2000127`, `2000210`, `2000211`, `2000219` y `2000227`— tienen hoy marca
«Laboratorio Optilab». El sexto, `2000239 POLIBLUE`, tiene «FENIX», que no es
ninguno de los tres laboratorios del catálogo y aparece una sola vez en todo el
inventario. Es una pista, no una respuesta: no asigné nada a partir de ella.

## 4. Las marcas que en realidad son laboratorios

En las planillas de la Óptica la columna «Marca» de un cristal trae el
laboratorio, y así entró al catálogo:

- **20 cristales** con «Laboratorio Optilab» o «Laboratorio Servi Optical» como
  marca;
- **2 de Compostura**, `2000065 Adaptacion de cristal` y `2000070 Hilo`;
- **1 armazón**, `2000212 ST Fotocromatico`.

Ahora que el laboratorio tiene su lugar propio, esa marca dejó de ser el único
sitio donde el dato podía estar. Y las **fuentes corregidas del 19/08** ya dicen
otra cosa: las 21 filas de Compostura pasaron a «Óptica Puppilent\`s». Producción
tiene todavía las viejas porque V1-010 no tocaba marcas.

**Qué necesito saber**, y son tres preguntas distintas:

1. Las 21 filas de Compostura, ¿toman la marca de la fuente corregida («Óptica
   Puppilent\`s»)? Eso resolvería `2000070 Hilo` con evidencia y no por criterio
   mío.
2. Los cristales, ¿se les limpia la marca a NULL —el laboratorio ya está en su
   campo— o se les pone una marca real de fabricante?
3. «Laboratorio Servi Optical» y «ServiOptica» ¿son el mismo laboratorio con dos
   nombres? Si sí, conviene unificar antes de cargarle los teléfonos.

## 5. Los tres laboratorios quedaron sin teléfono

`Laboratorio Optilab`, `ServiOptica` y `Laboratorio Cristal` no tienen línea ni
WhatsApp. El circuito de seguimiento los usa para reclamar trabajos atrasados —
sin número, el botón «Contactar laboratorio» no tiene a quién llamar.

Se cargan desde el ABM de Laboratorios en la pantalla de Seguimiento, o los cargo
yo si me pasás los números.

---

**Nada de esto impide operar.** Desde ahora, elegir un cristal en la venta llena
el campo «Laboratorio» solo, y la operadora lo cambia cuando ese trabajo va a
otro lado.
