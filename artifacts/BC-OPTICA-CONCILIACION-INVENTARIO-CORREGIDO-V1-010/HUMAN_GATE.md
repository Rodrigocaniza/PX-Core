# HUMAN_GATE — conciliación con los inventarios corregidos

**Nada escrito en producción.** Dry-run PASS, idempotencia PASS, base con el mismo
`sha256`.

Lo primero que hay que decir es incómodo: **los archivos «corregidos» no
corrigieron lo que más importaba.**

## 1. Qué cambió entre el inventario original y el corregido

Los dos archivos son del **2026-08-19**, contra el 03/08 y el 10/08 de los
anteriores. Traen tres columnas nuevas —`Cod. Barra`, `CostoA`, `PrecioA`— y
pierden `Casilla`, `Zona` y `Observacion`, que de todos modos venían vacías.

| | antes | ahora |
| --- | ---: | ---: |
| filas con artículo, Asunción | 2.586 | **1.974** |
| filas con artículo, Pilar | 1.052 | **938** |

| Clasificación | Cantidad |
| --- | ---: |
| `UNCHANGED` | 2.800 |
| `QUANTITY_CHANGED` | 54 |
| `NEW_ARTICLE` (registros) | 58 → **42 artículos** |
| `REMOVED_OR_NOT_PRESENT` | **775** |
| `DESCRIPTION_CHANGED` | 147 |
| `CATEGORY_CHANGED` | 37 |
| `BRAND_CHANGED` | 31 |
| `SOURCE_SENTINEL` | **28** |

## 2. Los centinelas siguen ahí — y ahora también en Asunción

**28 artículos, 842.497 unidades declaradas.** Hilo sigue en 99.981, Adaptación de
cristal en 99.916, Compostura Flex en 99.884.

Y algo nuevo: el archivo corregido de **Asunción trae 7 centinelas que antes no
tenía**, incluido `2000058 Compostura Flex` con 9.222. La corrección no limpió el
problema: lo propagó a la otra sucursal.

**No se convierte ninguno en stock.** Ninguno entra al ledger.

## 3. Cuántas naturalezas cambian: **una**

Y es la que pediste: `2000056 Par de patillas` pasa de `PRODUCTO_STOCKEABLE` a
`SERVICIO_NO_STOCKEABLE` por definición operativa. **No requiere conteo físico.**

Todo lo demás ya estaba bien:

| Regla | Estado |
| --- | --- |
| A — Cristales sin stock | ✔ ya son `TRABAJO_BAJO_PEDIDO`, **30 artículos, 0 movimientos** |
| C — Composturas son servicios | ✔ ya son `SERVICIO_NO_STOCKEABLE`, 9 artículos, 0 movimientos |
| D — Adaptación de cristal | ✔ ya es `SERVICIO_NO_STOCKEABLE` |

**No hay un solo movimiento de stock para ningún artículo no stockeable.** La
regla A pedía preparar compensaciones si producción tenía movimientos por
interpretación anterior: **no hay nada que compensar.** La cautela de la misión
008 —dejar en suspenso todo lo que no fuera un conteo— dejó producción limpia.

## 4. Lo que el dry-run aplicaría

| | |
| --- | ---: |
| artículos nuevos a crear | **42** (de 46 registros; 4 son el mismo SKU global en las dos sucursales) |
| stock inicial de esas altas | 46 líneas, **1.066 unidades** |
| `AJUSTE_POSITIVO` | **47 unidades**, 8 artículos |
| `AJUSTE_NEGATIVO` | **65 unidades**, 32 artículos |
| corrección de naturaleza | 1 |

Resultado: artículos 3.554 → **3.596** · ASUNCION 5.849 → **6.904** · PILAR 2.899 → **2.892**

Los ajustes entran como `AJUSTE_POSITIVO`/`AJUSTE_NEGATIVO` con motivo
`ERROR_INVENTARIO` —el código canónico que ya existe—, cada uno con el stock
anterior, la cifra corregida, el delta, el archivo, la fila y la sucursal en la
nota. **Los 3.583 movimientos de la 008 quedan intactos**, verificado por sus dos
`document_id`.

## 5. Las cuatro cosas que necesitan tu decisión

### A. 775 artículos desaparecieron del archivo — **776 unidades**

647 de Asunción y 128 de Pilar. **641 son armazones**, y 774 de los 775 tenían
stock 1.

Los dos informes listan **sólo lo que tiene stock > 0** —ni el viejo ni el nuevo
traen una sola fila en cero—, así que «ausente» significa *el sistema viejo dice
que ya no hay*, no *no existe*.

**Pero 647 armazones vendidos en 16 días son 40 por día.** Eso no parece una
óptica vendiendo: parece una limpieza, un filtro distinto, o artículos dados de
baja. **No los toqué.** Descontarlos sería sacar 776 unidades del depósito por una
ausencia que no entiendo.

*¿Se vendieron, se dieron de baja, o el informe cambió de criterio?*

### B. Los cuatro pendientes de Pilar

| Código | Artículo | 10/08 | 19/08 | Precio |
| --- | --- | ---: | ---: | ---: |
| `2000056` | Par de patillas | 526 | 524 | 80.000 |
| `2000070` | Hilo | 99.981 | 99.981 | 20.000 |
| `2000071` | Tornillo | 99.425 | 99.423 | 5.000 |
| `2000072` | Plaqueta | 9.393 | 9.391 | 15.000 |

`Par de patillas` **ya está resuelto**: es servicio, no se cuenta.

Los otros tres siguen siendo centinelas que bajan de a uno cuando se usan —un
contador de «no se acaba nunca», no un conteo. *¿Hilo, Tornillo y Plaqueta son
repuestos físicos que hay que contar, o son parte del servicio de compostura y
tampoco llevan stock?* Si es lo segundo, se cierran como `NATURE_CORRECTION`,
igual que las patillas, y no hay nada que contar.

### C. `000010 Limpia Cristal` en Asunción: **2.860 → 2.857**

Ahora hay evidencia que antes no existía: bajó **3 unidades en 16 días**, y el
archivo trae precio 15.000 y costo 1.000. Un centinela no se mueve; esto se mueve
despacio, como un consumible real que se vende de a poco.

Sigue siendo el mismo sistema fuente, así que no lo asenté solo. Pero la pregunta
ya no es «¿será real?» sino **«¿confirmás 2.857?»**.

### D. `000037 LIMPIA CRISTAL OBSEQUIO` — el SKU ficticio de la regla F

Existe, y es exactamente lo que describiste:

| | Asunción | Pilar |
| --- | ---: | ---: |
| stock cargado en producción | 210 | 516 |
| stock en el corregido | 191 | 507 |
| **precio de venta** | **0** | **0** |
| costo | 4.740 | 4.740 |

Precio 0 clavado en el catálogo, y un costo **4,7 veces** el del limpia-cristal
real (`000010`, costo 1.000). No es otro producto: es el mismo producto con una
ficción encima. **726 unidades de stock ficticio en el ledger.**

La buena noticia: **el modelo ya soporta la forma correcta.** `sale_items` tiene
`no_cost` y `article_id`, así que una línea de venta puede apuntar al
limpia-cristal real con precio cobrado 0. Hoy hay **0 líneas** usando `no_cost`.

*No lo toqué.* Retirar `000037` significa sacar 726 unidades del depósito y
migrar la práctica a `000010 + no_cost`, y eso merece decisión propia.

## 6. Lo que quedó fuera de alcance, como slices separados

| Regla | Estado | Por qué |
| --- | --- | --- |
| **B — laboratorio por defecto** | falta soporte | la tabla `laboratories` existe pero está **vacía**, y `sale_items.laboratory` es texto libre. No hay campo de laboratorio por defecto en el artículo. `2000212 ST Fotocromatico` sigue sin laboratorio y no se le inventó ninguno |
| **E — Delivery / Envío** | no existe | no hay ningún artículo de envío en el catálogo. Crearlo como `SERVICIO_NO_STOCKEABLE` con precio editable por venta necesita decidir dónde vive el precio orientativo de 20.000 |
| **F — motor promocional** | modelo listo, práctica no | `no_cost` ya existe; falta el motivo promocional (`PROMO_CRISTAL_ARMAZON_LIMPIA`) y la transición de `000037` |

Ninguno se empezó: la orden pedía conciliación, no rediseño.

## 7. Gates

dry-run **PASS** · idempotencia **PASS** (copia byte a byte igual al reaplicar) ·
`integrity_check` **ok** · FK **0** · stock negativo **0** · huérfanos **0** ·
efectos sin hecho **0** · Caja histórica **intacta** · movimientos de la 008
**intactos** (3.583 y sus 8.748 unidades) · Librarian **PASS** · QA **PASS** ·
Auditor **PASS** · Artifact Consistency **PASS**.

## Para autorizar

Se puede aplicar **la parte limpia** —42 altas, 1.066 unidades, los 40 ajustes y
la corrección de `Par de patillas`— y dejar los cuatro puntos del §5 para después.
O esperar a resolverlos y aplicar todo junto.

**Nada se escribe hasta que lo digas.**
