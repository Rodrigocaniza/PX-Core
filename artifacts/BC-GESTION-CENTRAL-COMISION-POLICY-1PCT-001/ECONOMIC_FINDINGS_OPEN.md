# Hallazgos económicos abiertos — registro separado y priorizado

> Este documento existe por decisión explícita del propietario en la Safe Pause del 2026-08-19:
> **los hallazgos económicos nuevos no se absorben dentro de una generación**. Ninguno de los que
> siguen está corregido. Ninguno se convirtió en remediación esa noche. Están aquí para que la
> próxima sesión decida el orden, no para que lo herede en silencio.

Producidos por `AUDITOR-IND-COMISION-POLICY-1PCT-011` sobre el snapshot
`75d7f1b6d0ff090abe9f1c063388c38b3f2f4ab0`, con fuzz desde bases migradas (13.862 pasos),
concurrencia (25 rondas × 6 hilos) y construcción manual de bases. Los tres se hallaron **leyendo y
construyendo a mano**, no fuzzeando: el propio Auditor deja dicho que su arnés no podía encontrarlos
porque parte de bases que el sistema sabe producir.

Todos son **no bloqueantes** según el criterio del Auditor y ninguno invalidó la generación 11. Los
tres tienen el mismo perfil de alcanzabilidad: **no son alcanzables desde ninguna ruta pública**, y
sólo se manifiestan sobre filas incoherentes de procedencia externa o sobre estados que el propio
sistema declara pendientes de resolución manual.

---

## P1 · `O15-g11` — la base comisionable no se contrasta contra la venta

**Daño medido: 8.900.000 Gs de sobrepago** sobre una venta de 10.000.000 Gs. Es la cifra íntegra de
`O8-g10`.

«¿Este importe es el oficial de hoy?» sigue contestándose en dos sitios con dos criterios.
`recalculate` compara diez campos y **re-deriva** `gross_amount`, `agreement_discount` y
`commissionable_base` desde `commission_sales`. `_require_current_policy` —la guarda de `review`,
`approve` y `mark_paid`— comprueba tasa, versión, `policy_status` y, desde la generación 11, que el
importe sea `commission_for(base, tasa)`; pero **nunca re-deriva la base ni el bruto desde la venta**.
Su criterio sigue siendo un subconjunto estricto del de `recalculate`.

Reproducción: `gross_amount=10.000.000`, `commissionable_base=900.000.000`,
`commission_amount=9.000.000` a 100 bp — aritméticamente coherente entre sí, incoherente con la
venta. Las tres puertas se abren, se pagan 9.000.000 Gs, y el mes queda `PINNED@100`: el libro
afirma el 1% mientras el importe pagado es el 90%. Variante acotada: un convenio sin su descuento
del 5% cobra 100.000 en vez de 95.000, y el desglose muestra «Descuento de convenio (5%): 0» sin
objetar nada.

El invariante `gross_amount = commissionable_base + agreement_discount` **no lo comprueba nadie**.

**Por qué es P1.** Es el único de los tres que mueve dinero, y es la séptima aparición del patrón
estructural que costó `AB1-g6`, `AB1-g7` y `AB1-g8`: la misma pregunta contestada en dos sitios. La
generación 11 cerró la mitad que estaba reportada y no la mitad contigua, que es literalmente lo que
ocurrió en las tres generaciones anteriores. El Auditor lo dejó por escrito «para que el propietario
pueda discrepar con datos delante».

**Corrección natural:** una línea al lado de la que se añadió — recomputar
`commissionable_base(sale_kind, total)` desde la venta y exigir que coincida, junto con
`gross_amount == total`. Cubrir las tres puertas, no sólo `review`.

---

## P2 · `O17-g11` — una traza de política inventada entra al libro de tasas

**Daño: no monetario directo. Contamina la evidencia durable y resucita un alcance abolido.**

La guarda compara `(rate_bp, policy_version)`. `policy_code`, `policy_effective_from` y
`policy_scope` **no los mira nadie**. Una fila de procedencia externa con
`policy_code='INVENTADO'` y `policy_scope='VENDEDORA'`, pero tasa y versión correctas, pasa la
guarda; `approve` escribe entonces `PINNED … 'INVENTADO','VENDEDORA'` en
`commission_period_rate_events`, **resucitando en el libro append-only el alcance por vendedora que
la misión abolió en su primera generación**.

El libro es append-only por diseño: esa fila no se puede corregir después, sólo suceder. Y el export
la publica: `policy.scope="VENDEDORA"` conviviendo con un disclaimer que dice «igual para toda
vendedora y local».

**Por qué es P2.** No mueve dinero, pero ensucia de forma permanente la evidencia sobre la que se
apoya toda la política económica, y contradice el invariante 1 de la misión —«después de migrar,
`commission_policies` contiene exactamente una fila, de alcance `GENERAL`»— en el único sitio donde
esa contradicción queda escrita para siempre.

**Corrección natural:** que la guarda compare la traza completa contra la decisión, no sólo tasa y
versión; o que el escritor del libro derive la traza de `decide()` en vez de copiarla de la
liquidación.

---

## P3 · `O16-g11` — el KPI de pagados pierde una comisión que sí se pagó

**Daño: no monetario. Descuadra el informe mensual con el que se concilia.**

«¿Ya movió dinero?» tiene **tres textos distintos** en el módulo:

| Sitio | Criterio |
|---|---|
| `_was_paid` | `status == 'PAGADA' or paid_at` |
| `LIVE_OFFICIAL_FACT_SQL` | `paid_at IS NOT NULL OR (status IN boundary AND venta no anulada)` |
| KPI `paid_amount` del reporte | **sólo** `status == 'PAGADA'` |

Reproducción: comisión pagada de 100.000 Gs, después se anula la venta. La liquidación queda
`OBSERVADA` conservando su `paid_at`; `revert` la sigue rechazando por pagada —correcto, el dinero
salió— y sin embargo `paid_amount` del reporte **pasa de 100.000 a 0**. El mes deja de contar como
pagado un dinero que efectivamente salió.

Es la misma familia que el hallazgo abierto 26 del backlog (`AUDITOR-004 O2`), que lleva abierto
desde la generación 4 y que esta reproducción confirma y amplía.

**Por qué es P3.** No mueve dinero y no altera ninguna decisión económica; sólo el informe. Pero el
informe es con lo que se concilia, y un «pagado» que baja solo es exactamente el tipo de cifra que
hace desconfiar de todo lo demás.

**Corrección natural:** que el KPI use el mismo predicado que el resto del módulo —`paid_at`— en vez
del estado actual.

---

## Nota sobre lo que **no** está en esta lista

`O1` no es un hallazgo: es la **decisión de propietario** de la generación 9, tomada y escrita. Un
mes con una `PAGADA` viva al 7% cobra el 7% a las ventas registradas después —600.000 Gs por venta
de 10.000.000 Gs—. El Auditor la señala en cada verdict porque la justificación escrita es «no
reescribir historia» y el efecto observable es que la historia gobierna dinero futuro. **Merece una
confirmación explícita antes de producción**, pero no es un defecto del código.
