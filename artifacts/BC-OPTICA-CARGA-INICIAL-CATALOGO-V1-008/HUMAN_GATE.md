# HUMAN_GATE FINAL — **AUTORIZADO Y EJECUTADO**

Autorizado el 2026-08-19. La importación corrió, dio **PASS con 0 fallas** y el
rollback **no** hizo falta.

Este documento queda como registro de lo que se autorizó y de lo que pasó. No hay
ningún gate abierto.

---

## Pre-guard — PASS en los seis puntos

| Guarda | Esperado | Encontrado |
| --- | --- | --- |
| base productiva, sha256 | `aa13f36e…` | `aa13f36e…` ✔ |
| backup disponible e íntegro | `bc-caja-preimport-catalogo-20260819-135805.sqlite3` | presente, 733.184 bytes ✔ |
| backup, sha256 | `eec36a5d…` | `eec36a5d…` ✔ |
| branch / HEAD | `feature/bc-optica-carga-inicial-catalogo-v1-008` @ `e64c180` | ídem, worktree limpio ✔ |
| artefactos sin drift | 4 sha256 de la generación 3 | los 4 coinciden ✔ |
| plan = dry-run 3 | 12 cifras + los 5 prohibidos | verificado campo por campo ✔ |

BC Caja no estaba corriendo y el WAL estaba en 0 bytes.

---

## Lo que se ejecutó

**Backup de la corrida:** `bc-caja-preimport-catalogo-20260819-140624.sqlite3`,
sha256 `eec36a5d…` — idéntico al preparado, porque la base no había cambiado
entre uno y otro.

| paso | resultado |
| --- | --- |
| planificación | 3.554 altas, 0 rechazadas |
| catálogo | 3.554 artículos, **0 movimientos** |
| inventario inicial ASUNCION | 2.575 líneas, corte 2026-08-03 |
| inventario inicial PILAR | 1.008 líneas, corte 2026-08-10 |
| stock pendiente | 5 artículos anotados |
| verificación post-import | PASS |

`sha256` de la base: `aa13f36e…` → **`25cd7d04025dac867c05cb3a178f6c7ea4a132b6f50e264ae20351dedb2ca658`**

**Rollback usado: NO.**

---

## Resultado

### Catálogo — 3.554 artículos

`PRODUCTO_STOCKEABLE` 3.515 · `TRABAJO_BAJO_PEDIDO` 30 ·
`SERVICIO_NO_STOCKEABLE` 9. Globales 247, `ASU-` 2.425, `PIL-` 882. 14 categorías
y 136 marcas. 0 SKU duplicados. Las 11 filas rechazadas siguen fuera —verificado
por procedencia, no por nombre.

### Inventario inicial

| | ASUNCION | PILAR | total |
| --- | ---: | ---: | ---: |
| líneas | 2.575 | 1.008 | 3.583 |
| **unidades** | **5.849** | **2.899** | **8.748** |

Los 3.583 movimientos son `INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL`, con
documento `CARGA_INICIAL`, ninguno sin actor y ninguno sin explicación escrita.
Los cortes quedaron grabados como 2026-08-03 (2.575) y 2026-08-10 (1.008), no la
fecha de hoy.

### Las 5 cantidades prohibidas — efectivamente excluidas

| Sucursal | Código | Artículo | Declarado | En el ledger |
| --- | --- | --- | ---: | --- |
| ASUNCION | `000010` | Limpia Cristal | 2.860 | **0 movimientos** |
| PILAR | `2000056` | Par de patillas | 526 | **0 movimientos** |
| PILAR | `2000070` | Hilo | 99.981 | **0 movimientos** |
| PILAR | `2000071` | Tornillo | 99.425 | **0 movimientos** |
| PILAR | `2000072` | Plaqueta | 9.393 | **0 movimientos** |

Ninguno figura en `stock_actual` para su sucursal: el sistema **no afirma cero**,
no afirma nada. Los cinco existen en el catálogo, conservan
`SOURCE_REPORTED_QUANTITY` en sus notas y tienen su fila en `admin_audit_log` con
acción `STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION`.

**Y `000010` conserva sus 10 unidades confirmadas en PILAR**, como pedía la
autorización.

### Caja histórica — intacta

| | antes | después |
| --- | ---: | ---: |
| entradas | 12 | 12 |
| dinero registrado | 6.400.000 | 6.400.000 |
| líneas de venta | 10 | 10 |
| días de caja | 2 | 2 |
| pedidos | 8 | 8 |

0 ventas históricas integradas al stock: la carga no tocó ninguna operación
anterior.

### Integridad

`integrity_check` **ok** · foreign keys **0** · stock negativo **0** · huérfanos
**0** · efectos sin hecho **0** · líneas de venta huérfanas **0**.

### Idempotencia sobre producción

Reaplicar el catálogo se rechaza por sha256. Los dos recuentos con el mismo
`run_id` devuelven la misma corrida. Después del replay la base quedó **byte a
byte igual**: `25cd7d04…`.

### Smoke

BC Caja abre sobre la base cargada (ventana `Caja diaria - Óptica`) y la UI
Comercial —Artículos, Proveedores, Compras y el buscador de la línea de venta—
funciona contra una copia de la base ya cargada. Abrir y cerrar la app no cambió
el sha256.
