# HUMAN_GATE FINAL — `AUTORIZAR IMPORTACIÓN PRODUCTIVA`

Todo está resuelto, el dry-run volvió a dar **PASS con 0 fallas** y el backup ya
está hecho. **Producción sigue intacta**: 0 artículos, 0 movimientos, sha256
`aa13f36e…`.

Falta una sola cosa: que autorices.

---

## CATÁLOGO — 3.554 artículos a crear

| | |
| --- | ---: |
| **total a crear** | **3.554** |
| con identificador global (código de barras o catálogo interno) | 247 |
| propios de ASUNCION (`ASU-…`) | 2.425 |
| propios de PILAR (`PIL-…`) | 882 |
| de los globales, presentes en las dos sucursales | 73 |

Por naturaleza:

| `nature` | artículos |
| --- | ---: |
| `PRODUCTO_STOCKEABLE` | 3.515 |
| `TRABAJO_BAJO_PEDIDO` | 30 |
| `SERVICIO_NO_STOCKEABLE` | 9 |

Además se crean **14 categorías** y **136 marcas**, todas por nombre y tomadas
del archivo. Dos artículos entran sin categoría, a propósito: son los dos
armazones sin marca cuya categoría no se pudo determinar, y un dato ausente se
completa después mientras que uno inventado no se detecta nunca.

---

## INVENTARIO INICIAL

### `CONFIRMED_INITIAL_STOCK`

| | ASUNCION | PILAR | total |
| --- | ---: | ---: | ---: |
| líneas de recuento | 2.575 | 1.008 | 3.583 |
| **unidades** | **5.849** | **2.899** | **8.748** |
| movimientos `INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL` | 2.575 | 1.008 | 3.583 |
| fecha de corte grabada | **2026-08-03** | **2026-08-10** | |

Cada movimiento lleva actor, motivo `INVENTARIO_INICIAL`, la explicación escrita
de qué recuento y de qué planilla salió, el documento `CARGA_INICIAL` y la fila
física del XLSX de origen. Ninguna compra falseada. Ni un guaraní movido.

### `PENDING_PHYSICAL_VERIFICATION`

**5 artículos · 212.185 unidades declaradas por la fuente que NO entran al
ledger.**

| Sucursal | Código | Artículo | La fuente declara | Por qué no entra |
| --- | --- | --- | ---: | --- |
| ASUNCION | `000010` | Limpia Cristal | **2.860** | decisión humana: las fuentes que lo repiten comparten origen, no es confirmación física independiente |
| PILAR | `2000056` | Par de patillas | **526** | 526 el 10/08 y 616 el 04/08 — dos cifras del mismo mes, ninguna verificada |
| PILAR | `2000070` | Hilo | **99.981** | centinela; valía 949 seis días antes |
| PILAR | `2000071` | Tornillo | **99.425** | centinela; valía 708 seis días antes |
| PILAR | `2000072` | Plaqueta | **9.393** | centinela; valía 575 seis días antes |

Los cinco **existen en el catálogo** y son `PRODUCTO_STOCKEABLE`: pueden llevar
unidades, sólo que todavía nadie las contó.

**Y esto no es cargar cero.** `stock_actual` es la suma de los movimientos
agrupada por artículo y depósito, así que un artículo sin movimientos **no tiene
fila en la vista** y `stock_por_destino()` devuelve vacío. El sistema no dice
«hay cero»: no dice nada, que es exactamente lo que corresponde. La cifra que la
fuente declaró queda guardada como `SOURCE_REPORTED_QUANTITY` en las notas del
artículo y en `admin_audit_log` con acción
`STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION`.

`000010` es un código global: **Pilar sí lo contó (10 unidades, y entran)**;
lo que espera son los 2.860 de Asunción. Un mismo artículo puede tener stock
confirmado en un depósito y ninguna afirmación en el otro.

### Filas que no llegan al catálogo

**11 rechazadas**, todas de origen: 9 tienen descripción pero ningún código, y 2
tienen código pero ningún nombre. No se inventó ninguno de los dos.

---

## SEGURIDAD PRODUCTIVA

**Backup ya hecho y verificado**, por la API de backup de SQLite:

```
C:\Users\Striker\AppData\Local\BC\Caja\Backups\
    bc-caja-preimport-catalogo-20260819-135805.sqlite3
  sha256  eec36a5d62ed5a375d74291bcb359351a746bfb11ddeb5a720f59ecb7d80a139
  733.184 bytes
```

Verificado contra la base fila por fila: mismas 12 entradas, mismos 6.400.000,
mismas 10 líneas, 2 días, 8 pedidos, `integrity_check` ok, 0 FK.

**Hash pre-importación de la base productiva:**
`aa13f36e0105bef7ca9ced5e258132cf5a247232d192f652f62268b45b8e60de`

**Secuencia exacta:**

```
python tools/carga_inicial_optica_importar.py --entrada <artifacts> --confirmar
```

1. backup verificable + hash *(vuelve a hacerlo, no reusa el de arriba)*
2. paso 1 — planificar el catálogo; si hay un solo rechazo, se detiene
3. paso 1b — aplicar el catálogo: 3.554 artículos, **ni una unidad**
4. paso 2 — inventario inicial por sucursal, con la fecha de cada recuento y
   `run_id` fijo
5. anotar los 5 artículos con cantidad pendiente en `admin_audit_log`
6. verificación post-import
7. hash final

**Verificación post-import** (el script la corre solo): unidades por sucursal
contra lo esperado, 3.583 movimientos, `integrity_check`, `foreign_key_check`,
stock negativo, huérfanos, efectos sin hecho, y que Caja siga con sus 12
entradas, 6.400.000, 10 líneas, 2 días y 8 pedidos.

**Si falla cualquier paso:** el script se detiene, marca la falla y escribe cómo
volver atrás — cerrar BC Caja, borrar `bc_caja.sqlite3` con su `-wal` y `-shm`, y
copiar el backup encima. Vuelve al estado exacto de antes.

**Repetir la importación no duplica nada.** El catálogo se rechaza por sha256 del
archivo y cada recuento tiene `run_id` fijo, así que volver a correrlo devuelve la
misma corrida. Probado en el dry-run.

---

## GATES

| | |
| --- | --- |
| dry-run | **PASS**, 0 fallas |
| idempotencia | **PASS** |
| `integrity_check` | **PASS** |
| foreign keys | **PASS**, 0 |
| stock negativo | **0** |
| huérfanos | **0** |
| efectos sin hecho | **0** |
| Librarian | **PASS** |
| QA | **PASS** |
| Auditor | **PASS** |
| Artifact Consistency | **PASS** |

---

## PARA AUTORIZAR

> **Autorizo la importación productiva.**

Con eso corro la secuencia de arriba sobre la base real y devuelvo la evidencia
post-import. **No se ejecuta nada hasta que lo digas.**
