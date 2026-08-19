# Las excepciones, una por una, con la evidencia que las resolvió

Se buscó evidencia real antes de volver a preguntar. Apareció una tercera fuente
de inventario que no se había usado.

## La tercera fuente

`BC-Inventario-Control/data/inventario_base.xlsx`, corte **2026-08-04**, 2.710
filas, mismo formato que P2.

**No es un conteo independiente.** De los 2.577 códigos que comparte con
`PC - Inventario.xlsx`, los **2.577 traen exactamente el mismo stock**. Es otra
extracción del mismo sistema, no otra persona contando. Sirve para confirmar que
un número está bien transcripto; **no** sirve para confirmar que sea cierto.

Donde sí aporta es en las filas de Pilar: trae 227 códigos de P2, con valores de
otra fecha.

---

## A. `Compostura` — las dos que quedaban

### `000005 Mostacillas` → **RESUELTO** · `PRODUCTO_STOCKEABLE` · `Sujetadores`

| Fuente | Categoría | Marca | Stock |
| --- | --- | --- | ---: |
| P2 fila 853 | Compostura | Proray | 2 |
| `inventario_base` | *no aparece* | | |

Los otros tres artículos del universo que se llaman «Mostacilla*»:

| | Código | Categoría | Marca | Stock |
| --- | --- | --- | --- | ---: |
| PC 8454 / P2 1037 | `000012 Mostacilla` | **Sujetadores** | **Proray** | 130 / 13 |
| PC 18 / P2 7 | `000040 Mostacilla Hanis` | Accesorios | Hanis | 7 / 1 |

Los tres son bienes físicos, y el más cercano — `000012 Mostacilla` — comparte
la marca **Proray** y está en `Sujetadores` en **los dos** archivos. Una
mostacilla es una cuenta: una cosa. Su stock, 2, tiene forma de conteo real, no
de centinela.

La única evidencia en contra era la categoría del propio archivo, y esa
categoría ya está probada como cajón de sastre. **Resuelto sin intervención.**

### `2000056 Par de patillas` → **SIN RESOLVER**

| Fuente | Categoría | Marca | Stock |
| --- | --- | --- | ---: |
| P2 fila 842 @2026-08-10 | Compostura | Óptica San Cayetano | 526 |
| `inventario_base` @2026-08-04 | Composturas | Óptica San Cayetano | 616 |
| PC | *no aparece* | | |

Lo que se buscó y lo que dio:

- **Filas vecinas.** 2000054 y 2000055 son `Compostura de Patilla Izquierda` y
  `Derecha`, las dos servicios. Que la mano de obra ya esté cubierta por esas dos
  sugiere que 2000056 es la pieza — pero es una inferencia por vecindad, no una
  prueba.
- **La cantidad no discrimina.** Cambió de 616 a 526 entre el 4 y el 10 de
  agosto. Parecería consumo, salvo que en esos mismos seis días
  `Fotocromático (AR)` pasó de 625 a 707, `Multifocal (OP)` de 714 a 934 y
  `Kripto` de 402 a 9.480. Los números de esta categoría se mueven en las dos
  direcciones y a saltos: no son conteos, así que no dicen nada sobre si el ítem
  es físico.
- **La marca no discrimina.** `Óptica San Cayetano` aparece en `Compostura` (11)
  y en `Sujetadores` (2).
- **Otras fuentes.** No aparece en PC ni en ningún otro archivo de inventario
  local.

`Par de patillas` puede ser el repuesto que se entrega o el servicio de
cambiarlo. La evidencia disponible no lo determina, así que **queda afuera del
catálogo** hasta que se decida. Es una fila.

### Y una corrección que la investigación destapó

La decisión humana aprobó `Hilo`, `Tornillo` y `Plaqueta` como
`PRODUCTO_STOCKEABLE`, sobre un artefacto que decía que los ocho valores de
~99.900 eran todos servicios. **Eso era falso**, y es un error de este mismo
análisis:

| Artículo | Stock en P2 | Stock en `inventario_base` |
| --- | ---: | ---: |
| `2000070 Hilo` | **99.981** | 949 |
| `2000071 Tornillo` | **99.425** | 708 |
| `2000072 Plaqueta` | **9.393** | 575 |

`Hilo` y `Tornillo` son dos de los ocho ~99.900. Y el salto de 949 a 99.981 en
seis días termina de mostrar qué son esos valores: entre el 4 y el 10 de agosto
alguien puso los ítems en «no se acaba nunca». Nadie compró 99.000 hilos.

**La naturaleza aprobada sigue siendo correcta** — un hilo y un tornillo son
cosas físicas y se venden. Lo que no sirve es la **cantidad**. Los tres entran al
catálogo con las unidades en suspenso, esperando un recuento real. Sin esta
corrección, la carga habría metido **108.799 unidades fantasma** en Pilar.

---

## B. Las 4 filas sin categoría de PC → **RESUELTAS**

| Fila | Código | Descripción | Marca | Stock | Resultado |
| ---: | --- | --- | --- | ---: | --- |
| 5 | `101181` | AC PAT FLEX NEGRO K9416 51-21-140 C206 | *(vacía)* | 1 | `PRODUCTO_STOCKEABLE`, categoría vacía |
| 6 | `100093` | AC PAT FLEX NEGRO K9771 53-17-143 C502 | Steffani | 1 | `PRODUCTO_STOCKEABLE` · `Armazones` |
| 7 | `100240` | AC APT FLEX ROSA 9151 44-20-130 C12 | Betania | 1 | `PRODUCTO_STOCKEABLE` · `Armazones` |
| 11 | `108004` | AC PAT FLEX NEGRO 28174 51-18-140 C.2 | *(vacía)* | 1 | `PRODUCTO_STOCKEABLE`, categoría vacía |

**La naturaleza está determinada en las cuatro, y no por parecido.** En los tres
archivos hay **3.065** filas cuya descripción empieza con `AC PAT` / `AC APT` /
`AC PAC`. De ésas, 2.773 son `Armazones` y 289 son `Lentes de Sol`. No existe una
tercera categoría con ese prefijo — y **las dos son `PRODUCTO_STOCKEABLE`**. Sea
cual sea, el artículo se comporta igual.

**La categoría** se determinó en dos por la marca: `Steffani` aparece en 585
filas y las 585 son `Armazones`; `Betania` en 357 y las 357 son `Armazones`.
Ninguna de las dos marcas aparece jamás en otra categoría.

Las otras dos no tienen marca, ni en PC ni en `inventario_base`, y ninguno de
sus códigos aparece en P2. `AC PAT` solo no alcanza para elegir entre `Armazones`
y `Lentes de Sol`, así que **la categoría queda vacía**. Un dato ausente se
completa después; uno inventado no se detecta nunca. No afecta el stock.

*(Las otras 2 de las 6 filas sin categoría siguen rechazadas por no tener código:
`AC PAC FIJA AZUL` y `Armazon`.)*

---

## C. `000010 Limpia Cristal = 2.860` → `LIKELY_REAL_BUT_REQUIRES_HUMAN_CONFIRMATION`

### La celda, mirada de cerca

```
PC, hoja «PC», celda C8397
  valor          : 2860   (entero literal)
  data_type      : 'n'    (numérico, no texto)
  fórmula        : ninguna — el archivo guarda 2860, no un cálculo
  number_format  : '#,##0.00'  (el mismo de toda la columna)
  merge          : la hoja no tiene ni un rango combinado
  Observacion    : vacía
  Casilla / Zona : vacías
  fila anterior  : 8395 y 8396 vacías
  fila siguiente : 8398 = «000037 LIMPIA CRISTAL OBSEQUIO», 210
```

**No es un arrastre, ni un subtotal, ni una fórmula, ni un merge.** Es un número
capturado.

### Contra las otras fuentes

| Fuente | Corte | Stock |
| --- | --- | ---: |
| `PC - Inventario.xlsx` | 2026-08-03 | **2.860** |
| `inventario_base.xlsx` | 2026-08-04 | **2.860** |
| `P2 - Inventario.xlsx` | 2026-08-10 | 10 |

El 2.860 se repite idéntico en la segunda extracción. Pero, como los 2.577
códigos comunes PC/BASE coinciden **todos**, eso prueba transcripción fiel del
sistema, **no** que el depósito tenga 2.860.

### Lo que juega a favor y en contra

**A favor de que sea real:**
- No tiene forma de centinela. Los centinelas de este juego de datos son
  ~99.900 o ~999; 2.860 no se parece a ninguno.
- El artículo es de marca propia (`Óptica Puppilent's`): un consumible que se
  compra por bulto, no una unidad cara.
- El sistema lo sostiene igual en dos extracciones.
- El vecino `000037 LIMPIA CRISTAL OBSEQUIO` tiene 210 en PC y **516 en P2**, así
  que en esta familia de productos los cientos de unidades son normales.

**En contra:**
- Es **2,9 veces** el segundo valor más alto de todo el archivo de Asunción
  (`Goma Niño`, 978).
- La misma sucursal declara 210 del «obsequio» y 2.860 del normal — trece veces
  más del que se vende que del que se regala.
- Pilar declara **10** del mismo artículo. Una diferencia de 286 a 1 entre
  sucursales del mismo consumible.
- No hay unidad ni presentación en ningún archivo: nada dice si 2.860 son
  frascos, sachets o mililitros.

### Recomendación

`LIKELY_REAL_BUT_REQUIRES_HUMAN_CONFIRMATION`.

No hay ningún indicio de error de planilla, así que **no corresponde corregir el
número**: no existe evidencia documental de otro valor, y cambiarlo a ojo sería
inventar un conteo. Pero tampoco corresponde asentarlo sin que alguien lo mire:
2.860 unidades es el 33% de todo el inventario de Asunción, y una vez asentado
sólo se corrige compensando.

**El artículo entra al catálogo; sus 2.860 unidades quedan en suspenso** hasta
que se confirme o se traiga el número real.
