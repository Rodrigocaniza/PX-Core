# HUMAN_GATE — sólo faltan cinco números

Está todo preparado y probado. Lo único que no puede salir de ningún archivo es
cuántos hay realmente en el estante.

| Sucursal | Código | Artículo | Cantidad fuente anterior | Cantidad física real |
| --- | --- | --- | ---: | ---: |
| ASUNCION | `000010` | Limpia Cristal | 2.860 | |
| PILAR | `2000056` | Par de patillas | 526 | |
| PILAR | `2000070` | Hilo | 99.981 | |
| PILAR | `2000071` | Tornillo | 99.425 | |
| PILAR | `2000072` | Plaqueta | 9.393 | |

## Dónde contar cada uno

Ninguna de las tres planillas trae ubicación: `PC - Inventario.xlsx` tiene
columnas `Casilla` y `Zona` pero vienen vacías en las 2.586 filas, y `P2` no las
tiene. Así que lo único que la evidencia permite decir es la sucursal y en qué
familia está archivado:

- `000010 Limpia Cristal` — **Asunción**, categoría *Limpia Cristales*, marca
  propia (`Óptica Puppilent's`). Es el consumible que se vende en mostrador.
  *Pilar ya contó los suyos: 10 unidades, y no se tocan.*
- `2000056 Par de patillas` — **Pilar**, categoría *Compostura*, proveedor
  *Óptica San Cayetano*. Es la pieza, no el servicio de colocarla.
- `2000070 Hilo` — **Pilar**, *Compostura*, *Laboratorio Optilab*.
- `2000071 Tornillo` — **Pilar**, *Compostura*, *Óptica San Cayetano*.
- `2000072 Plaqueta` — **Pilar**, *Compostura*, *Óptica San Cayetano*.

Los cuatro de Pilar son el cajón de repuestos del taller.

## Si alguno da cero

Decilo igual. **Contar y que dé cero no es lo mismo que no haber contado**, y el
sistema los va a distinguir: el que dé cero queda registrado como
`PHYSICAL_COUNT_CONFIRMED = 0`, sin movimiento —porque no hubo nada que
ingresar— y con la cifra vieja al lado. El que nunca se cuenta se queda como
está.

## Cómo responder

Alcanza con cinco números en el orden de la tabla. Por ejemplo:

> 143, 12, 0, 37, 0

O nombrando el que quieras y dejando los demás para después: los que no cuentes
siguen pendientes y no pasa nada.

---

## Lo que ya está hecho, para que no lo tengas que mirar

- **Los cinco salieron de la base**, no de una lista escrita a mano: se leen de
  `admin_audit_log` con acción `STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION`.
  Verificado que los cinco siguen sin movimiento en su sucursal y que `000010`
  conserva sus 10 unidades en Pilar.
- **Dry-run completo sobre copia de la base real: PASS, 0 fallas.** Se probaron
  los dos caminos —cantidad mayor que cero y cantidad cero—, que Asunción no
  toque Pilar, que repetirlo no duplique nada, integridad, FK, stock negativo,
  huérfanos, efectos sin hecho y que Caja quede intacta.
- **Backup verificable ya tomado:**
  `bc-caja-prerecuento-20260819-142306.sqlite3`, sha256 `71580fc8…`, equivalente
  a la base fila por fila. El paso productivo vuelve a hacer el suyo igual.
- **El movimiento llevará la fecha del recuento de hoy**, no la de los XLSX de
  agosto, y quedará como `INGRESO_ADMINISTRATIVO` / `INVENTARIO_INICIAL` con el
  vínculo explícito entre la cifra que declaró la planilla, lo que se contó y el
  movimiento creado. La cifra vieja no se borra ni se reescribe.

**No se escribe nada en producción hasta que estén los números.**
