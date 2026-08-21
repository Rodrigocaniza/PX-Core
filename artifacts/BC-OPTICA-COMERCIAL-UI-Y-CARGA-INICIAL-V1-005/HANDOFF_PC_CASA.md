# HANDOFF — de la PC de la Óptica a PC Casa

Safe Pause del 2026-08-18. Todo lo que hace falta para retomar sin reconstruir contexto a
mano está acá y en el repositorio. **No hay que copiar rutas, SHAs ni archivos.**

## Cómo retomar

Desde PC Casa, en PX-Core:

```
git fetch --all --prune
git worktree add .worktrees/venta-reversible-006 \
    -b feature/bc-optica-venta-reversible-y-release-gate-v1-006 \
    origin/feature/bc-optica-comercial-ui-carga-inicial-v1-005
```

Ese es el único comando que importa: **el slice 6 sale del 5**, porque necesita los cinco
dominios. Todo lo demás se lee del repositorio.

## Estado canónico verificado al pausar

| Qué | Valor |
| --- | --- |
| `origin/main` | `7db56a0` — BC Caja 1.0.0-rc.31, **sin tocar** |
| Slice 1 · Catálogo canónico | `ed0dbba` · migración **022** |
| Slice 2 · Event Spine + Ledger | `54f5f06` · migración **023** |
| Slice 3 · Proveedores + Compras | `ecc0c7b` · migración **024** |
| Slice 4 · Venta ↔ Artículo ↔ Stock | `b580e50` · migración **025** |
| Slice 5 · UI Comercial + Carga inicial | `91071c5` · migración **026** |

Los cinco: pusheados, limpios, `0/0` contra su upstream. Ninguno mergeado a `main`. Sin PR,
sin rebase, sin force-push.

Cada rama contiene los artefactos completos de su misión (8 archivos cada una):
`IMPLEMENTATION_PACKET.md`, `SUMMARY.md`, `ARTIFACT_CONSISTENCY.md`, `MANIFEST.json`,
`WORKFLOW.json`, `NEXT_ACTION.json`, `QA_SUITE.txt` y la evidencia de migración sobre copia
productiva.

## Producción — no se tocó

| Qué | Estado |
| --- | --- |
| Ejecutable instalado | BC Caja **1.0.0-rc.31**, `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` |
| Cadena instalada | **21 migraciones** (001–021) |
| 022–026 instaladas | **ninguna** |
| Tablas del núcleo comercial en producción | **0** |
| `cash_entries` / `sale_items` | 12 / 10, intactos |
| `SUM(cash_entries.total)` | 6.400.000, sin cambios |
| sha256 de la base real | `1c4fcc406904fe3eebc62e209a56c4e273192a27912331a43dbd0e4d9fde98ec` |

Todas las verificaciones sobre la base real fueron **de sólo lectura** (`mode=ro`); las
migraciones y los escenarios corrieron siempre sobre copias.

## Lo siguiente: `BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006`

El orden **no es negociable**, y la razón es una sola: instalar sin poder corregir una venta
dejaría a la Óptica con errores que sólo un técnico puede arreglar.

1. Reversión / anulación / corrección compensatoria segura de una venta que ya movió stock.
2. Validar que ninguna corrección reescriba historia.
3. Recién entonces, el release/migration gate acumulado de **022–026**.
4. Backup.
5. Upgrade sobre copia real.
6. Rollback probado.
7. Packaging.
8. Smoke.
9. Sólo después, evaluar la instalación productiva.

### Por qué la reversión primero

Hoy, por diseño del slice 4: una venta que movió stock **no se puede anular ni editar en sus
líneas**. Cuatro triggers lo impiden para cualquier escritor. Fue deliberado —media reversión
improvisada es peor que ninguna— pero es el único boundary abierto que la operación real toca
todos los días.

La pieza que falta no es el mecanismo: `StockLedgerService.compensar()` existe desde el slice
2 y ya se usa para corregir un recuento mal hecho. Lo que falta es el **circuito de negocio**
que lo dispare desde una venta anulada, y la decisión de qué pasa con el hecho económico de
Caja cuando eso ocurre.

## Decisiones arquitectónicas que conviene no reabrir

- **El stock es la suma del ledger**, nunca un contador editable.
- **El signo lo decide el tipo de movimiento**; no hay columna de signo que pueda
  contradecirlo.
- **`tracks_stock` se deriva de la naturaleza del artículo**, nunca del texto, del código ni
  del laboratorio.
- **El costo no es columna del artículo**: se deriva de la última compra confirmada, y sin
  compras se declara `PENDIENTE_DE_CONCILIACION`.
- **No hay `tax_rate` por artículo**: el IVA es 10% uniforme y no hay evidencia de
  excepciones.
- **Una factura real se registra una sola vez**, a nivel empresa; lo que se reparte es la
  mercadería.
- **El vencimiento se deriva** de fecha + plazo; pasarlo a mano es `TypeError`.
- **Catálogo no es stock**: cargar el archivo crea artículos y cero unidades.
- **La línea de venta óptica es una fila con dos componentes** (armazón + cristal), no dos
  filas.
- **Un hecho es durable aunque no produzca efectos**: una venta de puros servicios emite
  `SALE_COMPLETED` igual.
- **La UI no tiene reglas**: pregunta al controlador, que pregunta al dominio.
- **Nada se infiere**: la naturaleza que falta en un archivo rechaza la fila.

## Deuda registrada, sin resolver

| Deuda | Estado |
| --- | --- |
| Reversión / anulación de ventas | **bloqueante para producción** — es el slice 6 |
| Release gate de 022–026 | **bloqueante para producción** — es el slice 6 |
| Notas de crédito y anulación de compras | boundary abierto desde el slice 3 |
| Cuentas por Pagar | sólo se guarda e indexa el vencimiento |
| IVA más completo | 10% uniforme, sin desglose |
| Transferencias entre sucursales | vocabulario declarado desde el slice 2, sin usar |
| Cantidad arbitraria por línea de venta | hoy una línea es una unidad |
| `BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001` | flake heredado, no apareció en el slice 5 |
| **Archivo real de ~3.000 artículos** | **no localizado ni cargado** — ver abajo |
| `CajaDiaria.py:3253` | hallazgo anotado, no corregido |
| BC-Core local sin Headless Executor | por eso no se usó en ninguno de los 5 slices |
| `admin_users = 0` en producción | decisión del dueño, preexistente a rc.31 |
| `main` local 147 commits atrás | referencia vieja sin worktree, inofensiva |

### Sobre el archivo de artículos

**No hay que buscarlo ni producirlo ahora.** Cuando se retome, la secuencia es: primero
inspeccionar automáticamente cualquier fuente ya existente —planillas, exportes, el sistema
que la Óptica use hoy— y recién pedir trabajo manual si no aparece ninguna.

El mecanismo y el contrato ya están listos y probados en la rama del slice 5:
`docs/PLANTILLA_ARTICULOS.csv` y `docs/CARGA_INICIAL_DE_ARTICULOS.md`. La columna crítica es
`nature`: es la única que el sistema se niega a adivinar, y la que decide si el artículo
descuenta stock.

## Worktrees

Los cinco worktrees de los slices quedan **en su lugar, a propósito**: son la política de
reanudación de este repositorio y no ocupan nada que no esté ya publicado. Desde PC Casa no
hacen falta —todo está en `origin`— pero en la PC de la Óptica se conservan por si el trabajo
vuelve acá.

No se borró ninguna evidencia. No se retiró ningún worktree.
