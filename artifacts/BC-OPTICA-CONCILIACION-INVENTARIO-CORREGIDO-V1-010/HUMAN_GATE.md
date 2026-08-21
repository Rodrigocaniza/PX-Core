# HUMAN_GATE FINAL — conciliación recalculada

Las tres decisiones están incorporadas. El plan anterior (42 altas, +47/−65, ASU
6.904, PIL 2.892) **quedó obsoleto y no se reutilizó**: se recalculó entero.

**Nada escrito en producción.** Dry-run **PASS, 0 fallas**, base con el mismo
`sha256` `25cd7d04…`.

## 1. Altas definitivas

**41 artículos**, de 45 registros — 4 son el mismo SKU global en las dos
sucursales y se consolidan en uno. **1.064 unidades** de stock inicial.

Crear el catálogo no movió una sola unidad; el stock entra por separado.

## 2. Retiros

| | |
| --- | ---: |
| ausentes declarados por la comparación | 775 |
| — el mismo código renumerado con un cero adelante | **−1** |
| — una fila que nunca fue artículo | **−1** |
| **ausentes reales** | **773** |
| **retirados del catálogo activo** | **766** |
| no retirados por seguir vivos en la otra sucursal | **5** |

Artículos activos: **3.554 → 2.829**.

### 3. Retiros que requieren compensación: **773 de 773**

Todos tenían stock de la V1-008 — ninguno era una baja «limpia».

| Sucursal | Unidades compensadas |
| --- | ---: |
| **ASUNCION** | **645** |
| **PILAR** | **128** |
| total | **773** |

Entran como `AJUSTE_NEGATIVO` con la nota
`RECONCILIACION_INVENTARIO_CORREGIDO / ARTICULO_RETIRADO`, cada una con el stock
que dejaba la 008, el archivo y la fila. **Primero se lleva el stock a cero,
después se retira** — nunca queda stock fantasma en un artículo inactivo. Los
movimientos originales de la 008 no se tocan.

### Dos correcciones que evitaron retirar de más

**Un código renumerado.** El archivo corregido normaliza algunos códigos de barra
a 13 dígitos con un cero adelante: `300653145470` «desaparece» y `0300653145470`
«aparece». Es el mismo Opti Free Express. No se da de baja ni de alta — es un
cambio de cantidad, 3 → 2. Busqué el patrón en los 775 y **es el único caso**, no
es sistémico.

**Cinco que siguen vivos.** Un artículo puede faltar en el archivo de una
sucursal y tener stock en la otra: cuatro Acuvue y un Opti Free. Se compensa el
depósito que los declara ausentes, pero **el artículo no se retira**. El propio
sistema lo impide —desactivar algo con stock lo sacaría de las búsquedas dejando
unidades que nadie mira— y la guarda es correcta.

**Y uno que nunca existió.** `ASU-101814` era la fila sin descripción que la 008
rechazó. No es una baja: nunca fue un artículo.

## 6. Cambios de `nature`: **4**

| Código | Artículo | Antes | Ahora |
| --- | --- | --- | --- |
| `2000056` | Par de patillas | `PRODUCTO_STOCKEABLE` | **`SERVICIO_NO_STOCKEABLE`** |
| `2000070` | Hilo | `PRODUCTO_STOCKEABLE` | **`SERVICIO_NO_STOCKEABLE`** |
| `2000071` | Tornillo | `PRODUCTO_STOCKEABLE` | **`SERVICIO_NO_STOCKEABLE`** |
| `2000072` | Plaqueta | `PRODUCTO_STOCKEABLE` | **`SERVICIO_NO_STOCKEABLE`** |

Buscados otros equivalentes de compostura mal clasificados: **no queda ninguno**.
`000039 LINTERNA O LUZ CHICA CON SUJETADOR PARA PATILLA` aparece por el patrón
pero es una linterna física de la categoría Accesorios, no un servicio; no se
tocó.

## 7. Estado final de los cuatro

Los cuatro quedan en `SERVICIO_NO_STOCKEABLE` con **stock 0**, y los cuatro tenían
**0 unidades desde el principio**: no hubo nada que compensar. Sus cifras
—99.981, 99.423, 9.391, 524— quedan escritas en las notas del artículo **sólo
como evidencia histórica de la fuente**, con la aclaración de que eran centinelas
y no conteos. Sus pendientes de la V1-008 siguen registrados, cerrados por
`NATURE_CORRECTION` y no por conteo. **Ninguno requiere que nadie cuente nada.**

## 8, 9, 10. Limpia cristal — verificado explícitamente

| | |
| --- | --- |
| `000010` **ASUNCION** | **0 unidades, sin ajuste**, conserva su `STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION`. Ni 2.860 ni 2.857 |
| `000010` **PILAR** | **10 unidades, intactas** |
| `000037` OBSEQUIO | sin stock ficticio nuevo (210 ASU / 516 PIL, como estaban), **sigue activo** |

`000037` se retira en `BC-OPTICA-PROMO-LIMPIA-CRISTAL-V1-013`, junto con la
migración a `000010 + no_cost + salida de stock real`.

## 11. Stock total antes / después

| | antes | después |
| --- | ---: | ---: |
| artículos | 3.554 | **3.595** |
| activos | 3.554 | **2.829** |
| movimientos | 3.583 | **4.438** |
| stock ASUNCION | 5.849 | **6.276** |
| stock PILAR | 2.899 | **2.776** |
| **total** | **8.748** | **9.052** |

El neto (+304) cierra: +1.064 de altas − 773 de retiros + 47 − 34 de ajustes.

Ajustes de cantidad de los que sí siguen: **37** — `AJUSTE_POSITIVO` 47 unidades
en 8 artículos, `AJUSTE_NEGATIVO` 34 en 29.

## 12. Excepciones reales

1. **Los 5 que siguen vivos** en la otra sucursal: se compensa el depósito
   ausente y el artículo queda activo. No es un problema, es la forma correcta.
2. **`000010` en Asunción sigue sin cantidad.** Ninguna de las dos cifras fuente
   se acepta y no se inventó cero. Cuando alguien cuente, entra por V1-009, que
   quedó pausada y lista.
3. **`000037` y sus 726 unidades ficticias** siguen en producción hasta el slice
   013. No se cargó ni una unidad nueva.
4. **Los 28 centinelas** siguen declarados en los archivos y **ninguno entró al
   ledger**. Los del lado Compostura ya son servicios; los de Cristales ya eran
   trabajo bajo pedido.

## Gates

dry-run **PASS** · idempotencia **PASS** (0 duplicación en artículos,
movimientos, unidades, corridas y bitácora) · `integrity_check` **ok** · FK **0** ·
stock negativo **0** · huérfanos **0** · efectos sin hecho **0** · Caja histórica
**intacta** · movimientos de la V1-008 **intactos** (3.583 y sus 8.748 unidades,
verificado por `document_id`) · Librarian · QA · Auditor · Artifact Consistency
**PASS**.

*Nota honesta sobre la idempotencia:* al reaplicar, **no se escribió una sola
fila** —artículos, movimientos, unidades, corridas y bitácora quedaron idénticos—
pero el archivo no sale byte a byte igual, porque abrir SQLite en modo escritura
reorganiza páginas internas. La verificación es por contenido, no por hash.

## Para autorizar

> **Autorizo la conciliación.**

Se aplican las 41 altas, los 766 retiros con sus 773 unidades compensadas, los 37
ajustes y los 4 cambios de naturaleza. **Nada se escribe hasta que lo digas.**
