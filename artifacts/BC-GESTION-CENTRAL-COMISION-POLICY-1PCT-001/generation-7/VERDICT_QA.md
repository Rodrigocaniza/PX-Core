# Verdict — QA, generación 7
Runner: QA-IND-COMISION-POLICY-1PCT-007
Snapshot: 41131a6a111be6e33ad1d47497bf22b128faf6e3
Veredicto: PASS

## Escenarios propios ejecutados

Escribí cuatro suites nuevas en el scratchpad de sesión (`qa7_seq.py`, `qa7_mig.py`, `qa7_adv.py`, `qa7_ui.py`, `qa7_last.py`), sobre bases sqlite temporales, sin reusar una sola prueba del paquete ni ningún verdict de generaciones 1–6. 91 comprobaciones. Además `python -m pytest -q`: **418 passed en 48,49 s**.

**Matriz temporal (fijar → retirar → refijar), punto por punto: dinero / evidencia / rótulo**

| Punto de la secuencia | Dinero observado | Evidencia (libro del período) | Rótulo observado |
|---|---|---|---|
| Venta común 400.000 Gs aprobada | 4.000 Gs | `PINNED` @100bp, origen `APROBADA` | `pinned=True`; pantalla «fijada al aprobarse o pagarse» |
| Dos aprobadas (400.000 → 4.000 y 1.000.000 → 10.000), revierto la primera | ambos importes intactos | sigue un solo `PINNED`, sin `UNPINNED` prematuro | `pinned=True` |
| Revierto también la segunda | importes intactos en las revertidas | `PINNED → UNPINNED` | `pinned=False`, «todavía sin tasa fijada: el período sigue siendo corregible» |
| Pagada 2.500.000 → 25.000 Gs, luego observada, luego venta anulada | 25.000 Gs y `paid_at=2099-09-30` intactos | `PINNED` solo, **sin** `UNPINNED` | `pinned=True` |
| Aprobada 1.000.000 → 10.000 Gs y después cheque de 600.000 rechazado (`revert_payment`) | — | `PINNED → UNPINNED` origen `PAYMENT_REVERTED` | `pinned=False` |
| `void_sale` tras aprobar | — | `PINNED → UNPINNED` origen `SALE_VOIDED` | `pinned=False` |
| `observe` tras aprobar, luego `revert` | — | `observe` ya suelta; el `revert` posterior **no** duplica el `UNPINNED` | `pinned=False` |
| Corrección de origen sobre una aprobada (400.000 → 1.200.000) | liquidación a `OBSERVADA` | `PINNED → UNPINNED` origen `SOURCE_UPDATED_AFTER_CLOSE` | `pinned=False` |
| Convenio 500.000 (base 475.000 → 4.750 Gs) aprobado y luego corregido a 400.000 | 4.750 Gs correctos antes de corregir | `PINNED → UNPINNED` | `pinned=False` |
| Provisionales entre medio (`CALCULADA`, `REVISADA`) tras soltar | 100.000 Gs calculados | libro sin eventos nuevos | `pinned=False` en ambos |
| Nuevo hecho oficial posterior (aprobar / pagar) | 100.000 Gs y 8.000 Gs según el caso | `PINNED → UNPINNED → PINNED`, tasas 10000 → 10000 → 100 bp | vuelve a «fijada al aprobarse o pagarse» |

**Escenario del Auditor, cifra exacta.** Tasa errónea 100% publicada, venta de 10.000.000 aprobada (comisión 10.000.000 Gs), aprobación revertida, corrección a 1% publicada: una venta nueva de 10.000.000 Gs del mismo mes liquida **100.000 Gs**, no 10.000.000. Sobrepago de **9.900.000 Gs por venta eliminado**.

**PAGADA viva: cinco rutas contra un pago de 9.000.000 → 90.000 Gs.** `observe` (aplicada), `revert` (rechazada por pago), `void_sale` (aplicada), corrección de origen (rechazada), `recalculate` (aplicada). En las cinco el período siguió fijado, el libro quedó con un único `PINNED` y los 90.000 Gs no se movieron.

**Idempotencia y no duplicación.** Reintentos de `revert`, transiciones adicionales del mismo mes ya suelto y un tercer ciclo completo no agregaron ni un evento ni un asiento en `central_audit`: 2 eventos y 2 asientos antes y después. Los tres eventos de la secuencia completa tienen causa, actor y fecha, y hay exactamente un asiento de auditoría por evento.

**Dinero intacto al soltar.** Con una `PAGADA` de 3.000.000 → 30.000 Gs y una `APROBADA` de 700.000 → 7.000 Gs en el mismo mes, retirar la segunda no tocó ni el importe ni el `paid_at` ni el `approved_by` de la primera, y el mes siguió fijado.

**Aislamiento y no re-tarifado.** Soltar 2099-09 no tocó 2099-10 (su libro no creció). Con el mes fijado a 1% y una publicación posterior al 50%, una venta nueva de 1.000.000 del mes fijado liquidó 10.000 Gs y no 500.000. Una fecha mal tipeada (2999-01) no fijó nada y no impidió publicar.

**Tasa retirada no pagable.** Tras soltar, una `REVISADA` de 10.000 Gs calculada con la tasa vieja fue rechazada al aprobar («la política del período cambió desde el cálculo (v1 → v2)»), el período siguió suelto tras el rechazo, el recálculo la llevó a 20.000 Gs (2%) y sólo entonces refijó a 200 bp.

**Migración vs. código en caliente.** Cinco construcciones operadas, borrando después el libro y reabriendo: aprobada (100 → 100), aprobada revertida (None → None), pagada observada y anulada (100 → 100), sólo calculada (None → None), pin-unpin-repin (100 → 100). Coinciden en las cinco. La migración no escribió un solo `UNPINNED` y no sembró nada sin hecho vivo.

**Bases legadas construidas a mano** (filas crudas inyectadas en sqlite): `APROBADA` viva → siembra `PINNED` @100; `APROBADA` con venta anulada → no siembra; `PAGADA` con venta anulada → sí siembra (el dinero salió); dos `APROBADA` a 100 y 500 bp → no desempata, deja asiento `EVIDENCIA_DISCREPANTE` con las dos tasas y los dos ids; pin heredado de la generación 5 sin hecho vivo → no se arrastra y queda asentado `SIN_HECHO_ECONOMICO_VIVO`.

**Reapertura.** Abrir la base 200 veces dejó exactamente 1 evento y 1 asiento; sobre una base con `PINNED → UNPINNED`, 50 reaperturas no reescribieron ni un byte del libro y el período siguió suelto.

**Rotulado real de pantalla (1920x1080, Tk headless, tres puntos de la secuencia)** — venta de 4.000.000 → 40.000 Gs:
- provisional: «Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde 2026-08-01 · **todavía sin tasa fijada: el período sigue siendo corregible**», KPI «COMISIÓN OFICIAL 1,00%», 40.000 Gs.
- fijado: «… · **fijada al aprobarse o pagarse** …», 40.000 Gs.
- soltado: vuelve a «todavía sin tasa fijada…», KPI 0 Gs.
- refijado con venta nueva: vuelve a «fijada al aprobarse o pagarse», 40.000 Gs.

En ningún estado apareció `None`, ningún porcentaje inventado, y **ninguna variante del rótulo afirma que nadie aprobó** —ni en pantalla ni en el `policy_disclaimer` del export—: la rama describe la ausencia de fijación, no la ausencia de aprobaciones. Esto cierra mi observación 1 sobre la generación 6. Export `contract_version 3` con bloque `policy` y `pinned` correcto en los tres puntos.

**Alcance de la publicación.** Con el mes fijado, la publicación asienta `protected_periods: ["2099-09"]`; después de soltarlo, la publicación siguiente asienta `protected_periods: []`. El rótulo de alcance sigue a la secuencia.

## Bloqueantes

Ninguno.

## Observaciones no bloqueantes

1. **Export contradictorio en base legada fuera de vigencia.** Base construida a mano con dos `APROBADA` canónicas en `2026-01` (anterior a la vigencia) y evidencia discrepante: el `policy_disclaimer` dice «Sin tasa de comisión en vigor para 2026-01 … Se informa sólo la base comisionable», mientras `kpi.commission_amount` del mismo export informa **60.000 Gs**. El texto y las cifras del mismo documento no dicen lo mismo. Ninguna ruta pública produce esa base (el recálculo marcaría `FUERA_DE_VIGENCIA` y retiraría el importe), por eso no lo cuento como bloqueante, pero es exactamente el género de rótulo que la generación 2 pagó caro.
2. **La migración no reevalúa un período que ya tiene libro.** Inyecté a mano una `APROBADA` viva en un período cuyo último evento era `UNPINNED`: al reabrir, la siembra lo saltea (por diseño: sólo siembra períodos sin ningún evento) y el mes queda suelto, mientras el código en caliente sí habría fijado al aprobar. Converge en el siguiente hecho oficial real (verificado: el pago refija) y requiere editar la base a mano, pero es el único punto donde migración y caliente no coinciden.
3. **`observe` sobre una `APROBADA` ya suelta el período**, sin esperar al `revert`. Es correcto bajo la regla «cero hechos vivos» y así lo verifiqué, pero es más estricto que el enunciado «observe+revert suelta»: quien lea sólo el enunciado no espera que observar, por sí solo, devuelva el mes al catálogo.
4. **Evidencia discrepante se desempata de hecho con el primer pago.** En la base legada con 100 y 500 bp, la migración no elige —correcto—, pero la entrada cuya tasa coincide con el catálogo sí es pagable: pagarla fija el mes a 100 bp y deja la de 500 bp definitivamente impagable. El propietario nunca eligió explícitamente; la elección la hizo el orden de las operaciones.
5. **El `UNPINNED` no nombra al hecho que se retiró.** Graba período, tasa, origen (`COMMISSION_REVERTED`, `SALE_VOIDED`, `PAYMENT_REVERTED`, `SOURCE_UPDATED_AFTER_CLOSE`), actor, motivo y fecha, pero `entry_id` y `sale_id` van en `NULL`. Reconstruir *cuál* liquidación dejó de sostener el mes exige cruzar `central_audit` o el historial por fecha.

## Superficie que mi revisión NO cubrió

- **Concurrencia real.** Todo se ejecutó en un solo proceso y un solo hilo. No probé dos actores aprobando y revirtiendo el mismo período en paralelo, ni el comportamiento de `BEGIN IMMEDIATE` bajo contención, ni escrituras simultáneas desde dos instancias de la aplicación.
- **Los artefactos del paquete.** No verifiqué `MANIFEST.sha256`, el `.zip`, ni la consistencia interna de `SUMMARY.md`, `HANDOFF.md`, `MIGRATION.md`, `WORKFLOW.json` ni `TEST_EVIDENCE.md` con el código. Eso es superficie del Librarian.
- **La captura de pantalla entregada.** Comprobé los rótulos leyendo las etiquetas reales del panel Tk a 1920x1080, no el PNG `comision-1pct-1920x1080.png` del paquete: no puedo afirmar que la imagen entregada corresponda a este snapshot.
- **Bases reales de producción.** Sólo bases temporales creadas por el propio código y bases legadas que yo construí a mano. No hay migración probada sobre datos reales del piloto ni volumen (mi mayor prueba fue de unas pocas decenas de filas); tampoco medí rendimiento del libro de eventos con miles de períodos.
- **El resto del sistema fuera de comisiones.** Lo cubre la regresión (418 pruebas verdes) pero no lo revisé escenario por escenario: BC Caja, entregas, factufácil, alertas y la sincronización real de ventas quedaron fuera de mi diseño de casos.
- **Rutas de escritura no públicas.** Comprobé que toda transición pública pasa por el choke point, pero no audité línea por línea que ningún código futuro o externo escriba `commission_entries` o `commission_period_rate_events` por fuera de `_record_period_rate_event`.
- **Aritmética de bordes del redondeo.** No repetí los bordes HALF_UP ni el medio guaraní exacto de generaciones anteriores; asumo esa superficie cubierta por la regresión y por los verdicts previos, que por regla de independencia no reutilicé pero tampoco revalidé.
