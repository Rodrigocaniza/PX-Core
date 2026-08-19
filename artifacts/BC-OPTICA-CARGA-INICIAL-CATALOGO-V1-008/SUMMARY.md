# BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008

**Los dos inventarios reales están entendidos, limpios, normalizados y
simulados. Producción no fue tocada: sigue con 0 artículos y 0 movimientos.**

## Base canónica elegida

`a7b685c`, tip de `feature/bc-optica-instalacion-productiva-v1-007`.

No se salió de `origin/main`. `main` está en `7db56a0` = rc.31 con 21
migraciones, y **producción está por delante**: corre rc.32 con 27 migraciones
desde la rama del slice 6. Crear esta misión desde `main` habría borrado las
seis migraciones comerciales que la Óptica ya usa — no habría existido ni la
tabla `articles`. La cadena verificada es
`7db56a0 → ed0dbba → 54f5f06 → ecc0c7b → b580e50 → a8443a3 → 5bc1540 → a7b685c`.

## Lo que resultó de mirar los archivos

**Las 8.459 filas de PC eran 2.586 artículos.** 5.871 filas vienen vacías.
Coincide con los «unos 2.000 de Asunción» que ya decía la documentación.

**Los 837.403 «unidades» de Pilar no eran unidades.** Ocho filas de `Compostura`
declaran ~99.900 cada una: es el centinela con que un sistema viejo modela un
servicio que no se agota. Once filas concentran 818.867 de las 837.403. No se
corrigió a mano: cuando la naturaleza es la correcta, un servicio no puede
llevar stock y el número desaparece solo. Pilar entra con **2.897**.

**El código no identifica al mismo artículo en las dos sucursales.** De 107
códigos de armazón compartidos, uno solo describe el mismo marco. `104627` es un
rojo fijo en Asunción y un dorado flex en Pilar. Tratarlo como SKU global habría
pegado dos marcos distintos en un artículo y sumado stock sobre algo inexistente.
Sólo son globales los códigos de barras de fabricante y el catálogo interno
compartido; el resto lleva prefijo de sucursal.

**Las sucursales no hubo que suponerlas.** `cash_register_branches`, sembrada por
las migraciones 018 y 020, ya dice `PC → ASUNCION` y `P2 → PILAR`. Los 8 pedidos
reales de esta instalación están en `PC`. `PC → ASUNCION` dejó de ser hipótesis.

## Naturaleza

13 categorías directas a `PRODUCTO_STOCKEABLE`. `Cristales` a
`TRABAJO_BAJO_PEDIDO`, justificada: la «marca» es el laboratorio que los fabrica
y el stock declarado son centinelas.

Dos quedan en `REQUIRES_POLICY_DECISION` y no se adivinaron: `Compostura`, que
mezcla servicios, cristales y repuestos en una sola categoría, y las 4 filas sin
categoría de Asunción, que parecen armazones — pero deducir la naturaleza del
texto es exactamente lo que el sistema prohíbe.

## Dry-run — PASS, 0 fallas

Sobre copia consistente de la base productiva, con el mecanismo real de dos
pasos, sin ningún atajo:

- catálogo: 3.529 altas, 0 rechazos, plan aplicable entero
- tras aplicarlo: 3.529 artículos y **0 movimientos** — catálogo no es stock
- inventario inicial: 3.579 movimientos `INGRESO_ADMINISTRATIVO` /
  `INVENTARIO_INICIAL`, 8.705 unidades a Asunción y 2.897 a Pilar
- cada movimiento con actor, motivo, explicación escrita, documento de origen y
  **la fecha del recuento, no la de hoy**: 2026-08-03 y 2026-08-10
- idempotencia: reaplicar el archivo se rechaza por sha256; repetir el recuento
  devuelve la misma corrida; 0 movimientos duplicados
- `integrity_check` ok, 0 violaciones de FK, 0 stock negativo, 0 huérfanos, 0
  efectos sin hecho
- Caja intacta: 12 entradas, 6.400.000, 10 líneas
- la base productiva quedó con el mismo sha256: nunca se abrió para escribir

## Generación 2 — decisiones aplicadas, excepciones investigadas

La decisión humana sobre `Compostura` entró tal cual: 9 servicios, 7 tipos de
cristal, 3 repuestos físicos. Las dos que quedaban se investigaron con evidencia
y apareció una tercera fuente que nadie había usado,
`BC-Inventario-Control/data/inventario_base.xlsx`, del 4 de agosto.

**`000005 Mostacillas` quedó resuelto sin preguntar.** Los otros tres artículos
del universo llamados «Mostacilla\*» son bienes físicos, y el más cercano
comparte marca y está en `Sujetadores` en los dos archivos.

**Las 4 filas sin categoría también.** Las 3.065 filas del universo que empiezan
con `AC PAT` / `AC APT` / `AC PAC` son `Armazones` o `Lentes de Sol`, y las dos
son `PRODUCTO_STOCKEABLE`: la naturaleza no depende de cuál sea. La categoría se
determinó por marca en dos y quedó vacía en las otras dos, en vez de inventada.

**Y la investigación destapó un error propio.** Este análisis había afirmado que
los ocho valores de ~99.900 eran todos servicios. No: `Hilo` y `Tornillo` son dos
de esos ocho, y son dos de los tres repuestos que se aprobaron como stockeables.
La naturaleza aprobada es correcta; la cantidad no. `inventario_base` los tenía
en 949 y 708 el 4 de agosto y aparecen en 99.981 y 99.425 el 10: nadie compró
99.000 hilos. Los tres entran al catálogo con **las unidades en suspenso**. Sin
esa corrección, la carga metía 108.799 unidades fantasma en Pilar.

## Estado actual

| | ASUNCION | PILAR |
| --- | ---: | ---: |
| líneas de recuento | 2.575 | 1.008 |
| unidades | 5.849 | 2.899 |

3.553 artículos · 3.583 movimientos · dry-run **PASS, 0 fallas** · producción con
el mismo sha256 · **0 filas en `REQUIRES_POLICY_DECISION`**.

## Lo que falta y por qué se para acá

Dos cosas, y ninguna es una naturaleza:

- **`2000056 Par de patillas`** — repuesto o servicio. La vecindad sugiere que es
  la pieza; sugerir no es determinar. Queda afuera del catálogo hasta que se
  decida. Es una fila.
- **`000010 Limpia Cristal = 2.860`** —
  `LIKELY_REAL_BUT_REQUIRES_HUMAN_CONFIRMATION`. Es un entero literal, sin
  fórmula ni merge ni subtotal: no hay error de planilla. Pero son el 33% de todo
  el inventario de Asunción y Pilar declara 10 del mismo artículo. El artículo
  entra; sus unidades esperan.

Están en `HUMAN_GATE.md`. **No se carga nada sobre producción hasta que estén
respondidas.**
