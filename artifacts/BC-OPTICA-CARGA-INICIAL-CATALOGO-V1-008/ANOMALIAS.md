# Anomalías de los dos inventarios, explicadas

Nada de esto se «arregló» en silencio. Cada anomalía tiene su regla, y cada
regla está escrita.

## 1. Las 8.459 filas de PC — resuelto, no era una anomalía de datos

| | |
| --- | --- |
| filas físicas | 8.459 |
| **filas totalmente vacías** | **5.871** |
| filas con artículo | 2.586 |

La hoja tiene 5.871 filas en blanco intercaladas — rastro de cómo se exportó,
no artículos. Los artículos reales son **2.586**, que es lo que
`docs/CARGA_INICIAL_DE_ARTICULOS.md` esperaba de Asunción («unos 2.000»).

No hay filas de total, ni de subtotal, ni encabezados repetidos, ni históricos:
0 de cada uno. Tampoco duplicados: los 2.586 nombres son distintos entre sí, y
los 2.573 códigos también. Las columnas `Casilla`, `Zona` y `Observacion` vienen
enteramente vacías en las 2.586 filas.

## 2. Los 837.403 «unidades» de P2 — no eran unidades

Ocho filas declaran entre 99.425 y 99.981 unidades. Todas son de la categoría
`Compostura` y todas son servicios: *Hilo, Tornillo, CENTRADO, Compostura
Simple, Compostura Flex, Compostura de Patilla Izq/Der, Adaptación de cristal*.
Es el valor centinela de un sistema que modela un servicio como un producto que
nunca se agota.

Otras 23 filas de `Cristales` declaran entre 949 y 1.971 por la misma razón.

**Once filas concentran 818.867 de las 837.403 unidades. Las otras 1.041 filas
suman 18.536.**

Esto no se corrigió a mano: se resuelve solo cuando la naturaleza es la
correcta. Un `SERVICIO_NO_STOCKEABLE` y un `TRABAJO_BAJO_PEDIDO` no pueden
llevar stock — el ledger los rechaza. De ahí que Pilar entre con **2.897**
unidades y no con 837.403.

## 3. El código NO es el mismo artículo en las dos sucursales

La anomalía más peligrosa, y la que habría hecho daño real.

180 códigos aparecen en los dos archivos. Al mirarlos:

| Rango de código | Compartidos | Describen lo mismo |
| --- | ---: | ---: |
| 11–13 dígitos (código de barras) | 42 | 42 |
| `00xxxx` y `2000xxx` (catálogo interno) | 31 | 29 |
| **`10xxxx` y demás de 4–6 dígitos (armazones)** | **107** | **1** |

Ejemplos del último grupo:

```
104627  ASUNCION 'AC PAT FIJA ROJO TH 1771 C9A 145'
        PILAR    'AC PAT FLEX DORADO HA26017 52-18-145 C.B2'
102123  ASUNCION 'Terminado +1.00'
        PILAR    'AH PAT FLEX ROJO G-8254 C3 52-18-140'
```

No son variantes del mismo marco: son marcos distintos. Cada sucursal numera sus
armazones por su cuenta. Tratar el código como SKU global habría **pegado dos
armazones distintos en un solo artículo** y después el stock de Asunción se
habría sumado al de Pilar sobre algo que no existe.

**Regla aplicada:** identificador global sólo para códigos de barras de
fabricante (11–13 dígitos) y para el catálogo interno compartido (`00xxxx`,
`2000xxx`). Todo lo demás lleva prefijo de sucursal: `ASU-104627`, `PIL-104627`.

Los 16 códigos de barras que difieren en el texto difieren en prolijidad, no en
producto: `Air Optix Hydraglyde -3.75` vs `Air Optix -3.75`. Son el mismo
producto y quedan como un artículo, con la variante anotada.

## 4. Once filas que no se pueden cargar

De 3.638 filas con artículo, **11** no producen un artículo:

| Archivo | Fila | Motivo | Texto |
| --- | ---: | --- | --- |
| PC | 8 | sin código | `AC PAC FIJA AZUL` |
| PC | 9 | sin código | `Armazon` |
| PC | 2544 | sin código | `AC PAT FIJA TRANSPARENTE 66008 55-18-150 C6` |
| PC | 2548 | sin código | `AC PAT FLEX ROJO TL 53-16-140 C3` |
| PC | 4212 | sin código | `AC PAT FLEX NARANJA RGE026 51-16-140 C4` |
| PC | 4215 | sin código | `AC PAT FIJA AZUL G7071 54-16-145 C3` |
| PC | 4241 | sin código | `AC PAT FLEX AZUL` |
| PC | 8074 | código sin descripción | `101814` |
| PC | 8114 | sin código | `AC PAT FIJA NEGRO 140 145 COL.B1` |
| PC | 8116 | sin código | `AC PAT FIJA ROSA 54-20-140 COL.BCT6` |
| P2 | 105 | código sin descripción | `104561` |

Nueve tienen descripción pero no código: no hay SKU. Dos tienen código pero
ningún nombre: no hay artículo que crear.

Son 11 unidades de stock en total. No se inventó un código para ninguna.

## 5. Valores altos que sí parecen reales, y conviene mirar

Después de sacar los centinelas quedan algunos números grandes que **no** tienen
forma de centinela y entran tal cual al depósito si se confirma la carga:

| Unidades | Artículo | Sucursal |
| ---: | --- | --- |
| 2.860 | `000010 Limpia Cristal` | ASUNCION |
| 978 | `000006 Goma Niño` | ASUNCION |
| 953 | `2000146 Capuchon` | ASUNCION |
| 835 | `2000140 Estuches para Anteojos` | PILAR |
| 516 | `000010 LIMPIA CRISTAL` | PILAR |

Los cinco son insumos que se compran por bulto, así que son plausibles. Pero
2.860 limpia-cristales es mucho limpia-cristales: **conviene confirmarlo antes
de asentarlo**, porque una vez asentado sólo se corrige compensando, nunca
borrando. No bloquea: es una confirmación, no un arreglo.

## 6. Diferencias de categoría entre sucursales — no bloquean

19 códigos compartidos tienen distinta categoría en cada archivo: `Armazones` en
una y `Lentes de Sol` en la otra, `Estuches` y `Estuche LC`, `Accesorios` y
`Sujetadores`.

**Los 19 tienen la misma naturaleza en las dos.** Conflictos de naturaleza entre
sucursales: **0**. Por eso no bloquean: se toma la categoría del registro con la
descripción más informativa y la otra queda anotada en el artículo.
