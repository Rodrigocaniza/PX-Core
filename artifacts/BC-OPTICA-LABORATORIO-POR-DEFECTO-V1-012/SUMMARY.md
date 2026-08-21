# BC-OPTICA-LABORATORIO-POR-DEFECTO-V1-012

Cada cristal ya sabe a qué laboratorio se lo suele mandar, y elegirlo en la venta
llena el campo solo.

## El problema, tal como estaba

En las diez líneas de venta que existen hasta hoy, el campo «Laboratorio»
contiene `''`, `'Optilab'`, `'optilab'`, `'SI'`, `'asd'` y `'asasa'`. No es
distracción: el dato no vivía en ninguna parte y había que acordarse y
retipearlo en cada venta.

## Lo que se hizo

Una preferencia, no una identidad. El cristal no *es* de Optilab: se le *suele
pedir* a Optilab. Esa diferencia decide todo el diseño — la sugerencia vive en el
artículo (`articles.default_laboratory_id`) y el hecho vive en la línea
(`sale_items.laboratory`, intacto). Por eso cambiar mañana a dónde va un cristal
no puede reescribir lo que se mandó en agosto, y hay una prueba dedicada a eso.

El catálogo de laboratorios **ya existía**: lo creó la migración 003 para el
circuito de seguimiento, con los teléfonos a los que se llama cuando un trabajo
se atrasa. Estaba vacío. No se hizo uno nuevo: el laboratorio al que se le pide
un cristal y el laboratorio al que se le reclama son el mismo, y dos listas
serían dos verdades.

Un laboratorio tampoco se convirtió en marca. Ni una marca nueva: siguen siendo
136.

## El catálogo del brief no coincidía con producción

Esto es lo más importante del informe, porque cambia lo que se pudo hacer.

**Siete de los 32 códigos no existen** — ni activos, ni inactivos, ni en ningún
backup: `2000124`, `2000139`, `2000077`, `2000078`, `2000090`, `2000231`,
`2000235`. No se les puede poner laboratorio a artículos que no están, y no se
los creó.

**Cinco tienen otro nombre** con el mismo código: `2000125` es «FUTUREX STEEL» y
no «Futurex Still»; `2000066` es «Solamax»; `2000062` es «Multifocal (OP)»; y
`2000060`/`2000063` difieren sólo en la tilde. Se asignaron igual — mismo código,
misma categoría, misma naturaleza, activos — y quedan listados uno por uno.

**`2000212 ST Fotocromatico` no es un cristal en producción**: es
`PRODUCTO_STOCKEABLE` en la categoría *Armazones*. Sea lo que sea, el resultado
pedido es el mismo y se cumplió: **sin laboratorio por defecto**, y sin
inventarle uno.

**Seis cristales activos que el brief no menciona** quedaron sin default:
`2000127 Green AR`, `2000210 Multifocal Foto AR`, `2000211 Multifocal AR`,
`2000219 Multiblue Foto Ar`, `2000227 Progresivo Rodensto`, `2000239 POLIBLUE`.
La pantalla no les sugiere nada, que es exactamente lo que corresponde mientras
nadie diga a dónde van.

Un detalle que vale la pena: el `2000078 Multiblue Foto Ar` del brief no existe,
pero **ese nombre exacto sí existe en producción con el código `2000219`**. No se
asignó por nombre. El código es la identidad del catálogo, y esa es justamente la
regla que evitó fusionar armazones distintos en V1-008.

## Resultado

24 cristales con laboratorio: **16 a Optilab, 7 a ServiOptica, 1 a Laboratorio
Cristal**. Tres laboratorios creados. 28 migraciones.

Stock y movimientos idénticos: ASUNCION 6.166, PILAR 2.260, total 8.426, 4.441
movimientos. Caja histórica intacta: 12 entradas, 6.400.000, 10 líneas idénticas
al carácter. En toda la tabla `articles`, el único campo que cambió es
`default_laboratory_id`, en 24 filas.

## `2000070 Hilo`: investigado, no tocado

La marca «Laboratorio Optilab» **sí es un arrastre**, y hay evidencia de las dos
puntas:

- en la fuente original `P2 - Inventario.xlsx`, fila 854, la columna «Marca» dice
  «Laboratorio Optilab»; esa columna, para los cristales, trae el laboratorio —
  es como la Óptica lleva sus planillas, y el normalizador de V1-008 ya lo
  documentaba;
- Hilo cae dentro de un bloque de filas de cristales que quedaron bajo la
  categoría *Compostura*, que en esa planilla mezcla servicios, tipos de cristal
  y repuestos físicos.

Pero **no se limpió a NULL**, y el motivo es que la orden condiciona esa limpieza
a que *no exista marca real*. Existe: en las fuentes **corregidas** del 19/08,
las dos sucursales le dan a Hilo la marca «Óptica Puppilent\`s». Poner NULL
descartaría un dato que el dueño ya corrigió, y poner «Óptica Puppilent\`s» es
una decisión de catálogo que nadie autorizó.

Además no es un caso aislado, y por eso arreglarlo solo a él sería arbitrario: en
las fuentes corregidas **las 21 filas de Compostura** pasaron a «Óptica
Puppilent\`s», y producción todavía tiene las viejas porque V1-010 no tocaba
marcas. Y en *Cristales* la «Marca» sigue siendo el laboratorio en 20 artículos.
Va al HUMAN_GATE completo, no como parche de una fila.

## Pruebas

22 dirigidas —los 12 escenarios obligatorios más 10 propios— y la suite completa
en **1.003**. La migración se probó sobre una base real de rc.32 y correrla dos
veces no hace nada. El circuito se verificó sobre copia con datos reales: la
venta cobra 530.000, el armazón baja de 100 a 99, el cristal no mueve una sola
unidad ni crea fila en `stock_actual`, y la línea guarda «ServiOptica»; después
se cambia el default a Optilab y la venta **sigue diciendo ServiOptica**.

No se creó una venta de prueba en producción: sería un hecho sin causa.
