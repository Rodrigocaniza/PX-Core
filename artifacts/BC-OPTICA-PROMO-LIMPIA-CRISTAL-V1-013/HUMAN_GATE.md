# HUMAN_GATE — retirar el obsequio ficticio

**Nada escrito en producción.** Dry-run **PASS, 0 fallas** sobre copia de la base
real; 14 pruebas dirigidas verdes; producción con el mismo `sha256` `d307e017…`.

## Lo primero que hay que decir

**El mecanismo de la promoción ya funcionaba. No hizo falta cambiar una línea de
código de producto para que funcione.**

- `SaleItem.subtotal` devuelve **0** cuando `no_cost` está marcado
- `_lineas_con_stock` decide qué descuenta mirando **la naturaleza del artículo**,
  no `no_cost` — así que una línea bonificada con `article_id` **sí descuenta**
- el buscador de la línea de venta ya excluye artículos inactivos
- la verificación de stock ya impide que un obsequio deje el depósito en negativo
- la UI ya tenía la casilla «Artículo sin costo»

Lo que faltaba no era capacidad: era **usarla**, y sacar de en medio el artículo
inventado.

## 1. Stock de `000037` antes

| Sucursal | Unidades ficticias |
| --- | ---: |
| ASUNCION | **210** |
| PILAR | **516** |
| **total** | **726** |

Los dos únicos movimientos que tiene son de la carga inicial de V1-008.
**Ninguna venta histórica lo referencia** — 0 líneas.

## 2. Compensaciones exactas

Dos `AJUSTE_NEGATIVO` con causa
`RECONCILIACION_STOCK_FICTICIO / PROMO_OBSEQUIO_LEGACY`: **−210** en Asunción y
**−516** en Pilar.

Cada nota deja escrito que esas unidades **no eran frascos** sino la ficción de un
artículo creado para poder poner precio cero, y que **no se trasladan a `000010`
ni a ningún otro**.

## 3. Stock final de `000037` = **0** en las dos sucursales

Verificado antes de retirarlo, y verificado después: **stock operativo en
artículos retirados = 0**.

## 4. Cómo queda retirado

`active = 0`. **No se borra nada**: el artículo sigue existiendo, sus dos
movimientos originales siguen donde estaban, y la compensación es un hecho nuevo
al lado. Deja de aparecer en el buscador de la línea de venta —verificado— así
que no se puede vender por accidente.

Queda además una entrada en `admin_audit_log` con acción
`PROMO_OBSEQUIO_LEGACY_RETIRED` que guarda las unidades compensadas por sucursal,
la causa, que no se trasladó a `000010`, cuántas ventas lo referenciaban, y qué
lo reemplaza.

## 5. Stock de `000010` — intacto

| Sucursal | Unidades |
| --- | ---: |
| ASUNCION | **100** *(estimadas, de V1-010)* |
| PILAR | **10** |

**Las 726 unidades ficticias no se le sumaron.** Verificado explícitamente.

## 6. Una venta bonificada, demostrada

Sobre la copia, con datos reales:

```
línea 1: Armazón + cristal          280.000 + 250.000
línea 2: Limpia Cristal — obsequio PROMO_CRISTAL_ARMAZON_LIMPIA
         no_cost, article_id = 000010
total cobrado: 530.000        (el regalo no suma)
000010 en ASUNCION: 100 → 99  (el regalo sí sale del depósito)
000010 en PILAR:    10 → 10   (no se mezclan sucursales)
```

El movimiento de stock lleva `PROMO_CRISTAL_ARMAZON_LIMPIA` en su nota, así que
dentro de un año se puede saber por qué faltaba ese frasco. La línea queda
marcada `no_cost = 1` con el artículo real vinculado.

## 7. Anulación

Anular la venta **devuelve el frasco**: `000010` vuelve de 99 a 100. Y lo hace
como corresponde — el movimiento `VENTA` original **no se borra**, se agrega un
`AJUSTE_POSITIVO` compensatorio. Verificado.

## Controles verificados

| Control | Resultado |
| --- | --- |
| regalar sin stock | ✔ rechazado (`StockInsuficiente`) |
| dos regalos con una sola unidad | ✔ rechazado |
| venta sin promoción no mueve el limpia-cristal | ✔ |
| `000037` retirado no aparece para vender | ✔ |
| vender `000010` cobrando normalmente sigue funcionando | ✔ |
| retirar `000037` con stock encima | ✔ el producto lo impide |
| repetir el retiro | ✔ se rechaza en las guardas, no escribe |

## 8. Impacto exacto en producción

**Lo único que se escribiría es el retiro.** Las ventas del dry-run son de la
copia y no van a ningún lado.

| | antes | después |
| --- | ---: | ---: |
| artículos | 3.595 | 3.595 *(no se borra ninguno)* |
| activos | 2.829 | **2.828** |
| movimientos | 4.439 | **4.441** |
| stock ASUNCION | 6.376 | **6.166** |
| stock PILAR | 2.776 | **2.260** |
| **stock total** | 9.152 | **8.426** |

Las 726 unidades que desaparecen del total **nunca fueron frascos**. El inventario
no pierde nada: deja de contar algo que no existía.

Caja histórica intacta · V1-008 intacta (3.583 movimientos) · los movimientos de
V1-010 intactos.

## 9. Backup y rollback

El script hace su propio backup verificable antes de escribir —contenido
comparado contra la base— y si algo falla dice cómo volver: cerrar BC Caja,
borrar la base con su `-wal` y `-shm`, y copiar el backup encima.

## La UI

Se agregó **un botón**: `Limpia-cristal de regalo`, al lado de «Buscar artículo».
Busca `000010`, verifica que haya stock en la sucursal de esa caja, avisa si ya
hay un obsequio en la misma venta, y agrega la línea con `no_cost`, precio 0 y el
artículo real vinculado. Si no hay stock, no deja. Si la caja no está ligada a una
sucursal, tampoco.

No se tocó nada más de Caja. No se construyó un motor de promociones.

## Gates

pruebas dirigidas **14 PASS** · suite comercial **268 PASS** · ciclo de ventana de
Caja **OK** · dry-run **PASS** · idempotencia **PASS** · `integrity_check` **ok** ·
FK **0** · negativos **0** · huérfanos **0** · efectos sin hecho **0** · Librarian ·
QA · Auditor · Artifact Consistency **PASS**.

## Para autorizar

> **Autorizo el retiro de `000037`.**

Se compensan las 726 unidades ficticias y se desactiva. **Nada se escribe hasta
que lo digas.**
