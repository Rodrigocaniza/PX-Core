# BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006

Slice 6. Dos objetivos que ya no se podían separar: que una venta que movió stock
se pueda anular sin reescribir historia, y el gate de las seis migraciones
acumuladas. El orden no era negociable y se respetó: la reversión primero.

Reanudado desde PC Casa sobre el tip canónico del slice 5 (`a8443a3`), resuelto
automáticamente desde `origin`. Ninguna ruta, SHA ni archivo se pidió a mano.

## Objetivo A — reversión compensatoria segura

Hasta la 025, anular una venta integrada estaba prohibido por cuatro triggers.
Estaba bien que lo estuviera: media reversión improvisada es peor que ninguna. Lo
que faltaba no era el mecanismo —`compensar()` existe desde la 023— sino el
circuito de negocio que lo dispara.

El principio, hecho cumplir en la base y no sólo en la aplicación:

    el hecho original permanece
    -> se registra un hecho compensatorio
    -> que produce efectos compensatorios
    -> y el estado derivado queda correcto

### Qué ocurre al anular

| Paso | Qué queda |
| --- | --- |
| La venta | sigue en el día, con `status = VOIDED`, su motivo y su fecha |
| `SALE_COMPLETED` | intacto, byte por byte |
| Movimientos `VENTA` | intactos: mismo id, misma cantidad, mismo momento |
| Líneas de `sale_items` | intactas: el movimiento que sacó la unidad apunta a ellas |
| Hecho nuevo | `SALE_VOIDED`, con actor, motivo, fecha y payload propio |
| Efecto nuevo | un `AJUSTE_POSITIVO` por cada unidad que la venta descontó |
| Registro nuevo | una fila en `sale_void_compensations`, append-only |

El movimiento compensatorio reusa la clave `compensa:{movimiento}` de
`StockLedgerService.compensar`: una corrección manual del ledger y una anulación
de venta son dos caminos hacia la misma corrección, no dos correcciones.

### Corrección de una venta ya integrada

No se implementó una edición en el lugar y no fue por falta de tiempo: cambiar el
artículo de una línea dejaría el movimiento que sacó la unidad apuntando a una
fila que ya dice otra cosa. La corrección segura es **compensar y volver a
consecuenciar**: anular la venta equivocada y cargar la correcta. Las dos quedan,
el stock de los dos artículos termina donde tiene que terminar y no hay una sola
reversión parcial en el medio. Los campos que no deciden inventario —teléfono,
observaciones, cliente— se siguen editando como siempre.

### Migración 027

`027_sale_void_compensation.sql`. Aditiva salvo por el reemplazo de un trigger de
la 025, que pasa de **prohibir** la anulación a **exigir que esté compensada**.
Ninguna fila se modifica.

- `sale_void_compensations`: el espejo de `sale_stock_integrations`. Aquella dice
  que la mercadería salió; ésta dice que volvió.
- Motivo canónico `VENTA_ANULADA`, **reservado**: un trigger impide usarlo en
  cualquier movimiento que no compense una `VENTA`.
- `cash_entries_integrada_sin_anular`, reescrito: deja pasar el `VOIDED` sólo si
  la compensación ya está registrada.
- `cash_entries_anulada_no_revive`: revivir una venta anulada volvería a
  descontar sin un hecho que lo explique.
- `sale_void_compensations_sin_reversion_parcial`: si falta compensar un solo
  movimiento, la anulación entera se rechaza.
- `sale_void_compensations_cuenta_declarada_real`: `movement_count` no es un
  comentario, es una afirmación que el ledger confirma.
- Vista `stock_origen_anulacion`: el tercer lado del circuito, después de
  `stock_origen_compra` (024) y `stock_origen_venta` (025).

### Dónde corre

En la **misma transacción** del guardado de Caja y **antes** de escribir el
`VOIDED`, porque el trigger exige que la compensación ya esté. Si la devolución
falla no hay anulación; si la anulación falla no hay devolución.

## Objetivo B — release / migration gate 022 → 027

Tratado como release productivo, no como trámite. Seis migraciones, no cinco: la
027 se suma a las cinco acumuladas.

- Backup consistente por la API de backup de SQLite —copiar el archivo dejaría
  afuera lo que todavía está en el WAL.
- Upgrade secuencial 021 → 027 sobre una **copia**.
- `integrity_check` ok, `foreign_key_check` sin violaciones.
- Ninguna fila existente cambió, comparando **sobre las columnas que ya
  existían**: una migración aditiva agrega columnas y un `SELECT *` daría
  distinto sin que nada haya cambiado.
- Escenario completo sobre la copia migrada, incluida la reversión.
- Rollback probado: restaurar el backup devuelve la base byte a byte y la cadena
  vuelve a 021.
- Empaquetado `BC Caja 1.0.0-rc.32` y smoke real del ejecutable.
- Smoke de la UI Comercial contra la base ya migrada.

**No se instaló nada.** La instalación productiva necesita una autorización
separada.

## Sobre qué base corrió el gate

La base real de la Óptica **no está en PC Casa**. Lo que hay acá es la base local
del piloto de esta máquina: 21 migraciones, 8 entradas, 2 líneas de venta,
`SUM(total)` 2.115.000, sha256 `b38d9f27…c116`, con BC Caja 1.0.0-rc.27
instalado. Es una base real con la misma forma y la misma cadena, y sirve como
ensayo del gate; **no** es la base de la Óptica (12 entradas, 10 líneas,
6.400.000, sha256 `1c4fcc40…98ec`, rc.31).

Eso quiere decir dos cosas:

1. La producción real de la Óptica está intacta por construcción: no fue tocada
   ni alcanzada desde acá.
2. El gate sobre la base real de la Óptica **falta correrlo allá** antes de
   instalar. Está registrado como el próximo paso, no como algo ya hecho.

Todas las lecturas de la base local fueron en modo `ro`; migraciones y escenarios
corrieron siempre sobre copias, y su sha256 quedó idéntico.

## Pruebas

- Dirigidas primero: `tests/comercial/test_sale_void_compensation.py`, 31 casos.
- Suite completa una sola vez al cierre: **934 passed, 2 failed**.
- Las 2 fallas son `BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001`, heredado y
  verificado idéntico sobre el commit base `a8443a3` (903 passed, mismas 2
  fallas). No lo introduce este slice.
- Dos pruebas del slice 1 y una del slice 4 cambiaron de verdad con este slice y
  se actualizaron en vez de silenciarse: el motivo sembrado ahora es ocho, y
  «una venta integrada no se puede anular» pasó a ser «se anula compensando».
