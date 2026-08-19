# HUMAN_GATE — autorizar la carga inicial del catálogo

**Nada se cargó todavía.** Producción sigue con 0 artículos y 0 movimientos. Lo
que sigue es lo que entraría, y las tres decisiones que faltan.

## Lo que entraría si autorizás tal cual

| | ASUNCION (caja PC) | PILAR (caja P2) | Total |
| --- | ---: | ---: | ---: |
| filas en el archivo | 8.459 | 1.054 | 9.513 |
| filas con artículo | 2.586 | 1.052 | 3.638 |
| filas descartadas (vacías) | 5.871 | 0 | 5.871 |
| filas rechazadas | 10 | 1 | 11 |
| en espera de decisión | 4 | 21 | 25 |
| **artículos canónicos** | | | **3.529** |
| **líneas de recuento** | **2.572** | **1.007** | **3.579** |
| **unidades al depósito** | **8.705** | **2.897** | **11.602** |

De los 3.529 artículos, 226 tienen identificador global (código de barras o
catálogo interno) y 3.303 llevan prefijo de sucursal. 73 existen en las dos
sucursales y son **un** artículo con stock en los dos depósitos.

Además se crearían 13 categorías y 136 marcas, todas por nombre, todas tomadas
del archivo.

**Cómo entra el stock:** 3.579 movimientos `INGRESO_ADMINISTRATIVO` con motivo
`INVENTARIO_INICIAL`, cada uno con la fecha real de su recuento —
2026-08-03 para Asunción, 2026-08-10 para Pilar, no la fecha de hoy — con actor,
con la explicación escrita de qué recuento y de qué planilla salió, y con el
número de fila del XLSX de origen. Ninguna compra falseada. Ni un guaraní movido.

## Las tres decisiones que faltan

### 1. `Compostura` (Pilar, 21 filas) — cómo se abre

La categoría mezcla tres cosas. Alcanza con aprobar el corte, no hace falta
mirar fila por fila:

- **11 servicios** → `SERVICIO_NO_STOCKEABLE`
  CENTRADO · Compostura Simple · Compostura Flex · Compostura de Patilla
  Izquierda · Compostura de Patilla Derecha · Compostura del Aro · Compostura del
  Puente · Compostura de Porta Plaquetas · Adaptación de cristal
- **7 tipos de cristal** → `TRABAJO_BAJO_PEDIDO`
  Organico UVX · Fotocromático (AR) · Multifocal (OP) · Kripto (Kto) Organico
  UVX · Blue Ar · Solamax · Bifocal (ST)
- **3 repuestos físicos** → `PRODUCTO_STOCKEABLE`
  Hilo · Tornillo · Plaqueta
- **2 sueltas:** `Par de patillas` (¿repuesto o el servicio de cambiarlas?) y
  `000005 Mostacillas`, que en el otro archivo está en `Sujetadores`

Las 822.233 «unidades» de esta categoría son centinelas de servicio, no stock:
con esta clasificación entrarían a lo sumo las de los repuestos físicos.

### 2. `(sin categoría)` (Asunción, 4 filas) — confirmar que son armazones

Las cuatro dicen `AC PAT FLEX …` / `AC PAC FIJA …`. Parecen armazones, pero el
sistema no deduce la naturaleza del texto. Con que lo digas vos, entran.

### 3. `000010 Limpia Cristal` en Asunción: 2.860 unidades

No tiene forma de centinela, así que entraría tal cual. Es mucho: confirmalo o
corregilo antes, porque una vez asentado sólo se arregla compensando.

## Lo que ya está resuelto y no requiere nada tuyo

- **Sucursales.** No fue una hipótesis: producción ya lo dice. La tabla
  `cash_register_branches` (migraciones 018 y 020) liga `PC → ASUNCION` y
  `P2 → PILAR`, y los 8 pedidos reales de esta instalación están en `PC`.
- **Las 8.459 filas de PC.** 5.871 están vacías. Son 2.586 artículos.
- **Duplicados.** 0 nombres repetidos, 0 códigos repetidos dentro de cada
  archivo. Entre archivos, el código de armazón no significa lo mismo en las dos
  sucursales, así que lleva prefijo — ver `ANOMALIAS.md` §3.
- **Naturalezas.** 13 categorías directas, `Cristales` justificada, 2 en espera.
- **Dry-run.** PASS, 0 fallas, sobre copia de la base productiva real.
- **Idempotencia.** Repetir el archivo se rechaza por sha256; repetir el
  recuento devuelve la misma corrida. 0 duplicación.

## Para autorizar

Respondé con las tres decisiones. Por ejemplo:

> 1. Compostura: aprobado el corte propuesto. `Par de patillas` es servicio.
>    `000005 Mostacillas` va a Sujetadores.
> 2. Las 4 sin categoría son Armazones.
> 3. Limpia Cristal 2.860 confirmado / corregir a N.
> Autorizo la carga sobre producción.

Con eso Command Center regenera el catálogo con las 25 filas incorporadas,
vuelve a correr el dry-run completo sobre copia, y recién si vuelve a dar PASS
aplica sobre producción con backup previo.

Si preferís cargar sólo lo que ya está limpio y dejar las 25 para después,
también se puede: son 3.529 artículos y 11.602 unidades sin ninguna decisión
pendiente. Pero conviene lo primero — cargar dos veces deja dos hechos donde
hubo un solo recuento.
