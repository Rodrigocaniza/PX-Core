# Verdict — QA, generación 6
Runner: QA-IND-COMISION-POLICY-1PCT-006
Snapshot: a5d6955828850b322c7ea00f5b46e3b5e7f3d7e4
Veredicto: PASS

## Escenarios propios ejecutados

Todos los escenarios son míos, escritos desde cero en el scratchpad de sesión (`qa6_matrix.py`, `qa6_probe.py`, `qa6_probe2.py`), importando el módulo con `sys.path.insert` al worktree y usando bases sqlite temporales. No reutilicé ninguna prueba del paquete ni ningún verdict de las generaciones 1 a 5. Política de partida en toda base nueva: `COMISION_GENERAL_1PCT` v1, 1,00%, vigente desde 2026-08-01. Período de trabajo: 2026-09.

### A. Matriz de dos ejes (estado de la liquidación × período fijado o no)

Once celdas, cada una sobre una base limpia con una venta común de 400.000 Gs cancelada el 2026-09-15. En cada celda comprobé simultáneamente el dinero (base comisionable, `rate_bp`, importe), la evidencia durable (`commission_rated_periods`), el rótulo (`policy_for_period.pinned`) y el `policy_disclaimer` del export.

| Estado | Base / tasa / comisión | ¿Período fijado? | Rótulo observado |
|---|---|---|---|
| PENDIENTE_SALDO (cobro 100.000, saldo 300.000) | 0 / None / None | No | "todavía provisional: ninguna liquidación del período fue aprobada ni pagada" |
| ELEGIBLE | 400.000 / None / None | No | provisional |
| CALCULADA | 400.000 / 100 bp / 4.000 Gs | No | provisional |
| REVISADA | 400.000 / 100 bp / 4.000 Gs | No | provisional |
| OBSERVADA (antes de aprobar) | 400.000 / 100 bp / 4.000 Gs | No | provisional |
| REVERTIDA (antes de aprobar) | 400.000 / 100 bp / 4.000 Gs | No | provisional |
| APROBADA | 400.000 / 100 bp / 4.000 Gs | Sí, 100 bp, `origin=APROBADA` | "tasa ya fijada por un hecho económico oficial (aprobación o pago)" |
| PAGADA | 400.000 / 100 bp / 4.000 Gs | Sí, 100 bp | fijada |
| OBSERVADA después de aprobar | 400.000 / 100 bp / 4.000 Gs | Sí (no desfija) | fijada |
| REVERTIDA después de aprobar | 400.000 / 100 bp / 4.000 Gs | Sí (no desfija) | fijada |
| OBSERVADA después de pagar | 400.000 / 100 bp / 4.000 Gs | Sí | fijada |

En las once celdas el dinero y el rótulo coinciden: `policy_for_period.pinned` es exactamente igual a la existencia de fila en `commission_rated_periods`, y ningún disclaimer emite la cadena "None".

### B. Los provisionales siguen siendo corregibles

- Mes sólo CALCULADA: 400.000 Gs comisionaban 4.000 Gs al 1%. Publiqué 2,50% con vigencia 2026-09-01 y recalculé: la liquidación pasa a 10.000 Gs y el mes sigue sin fijar (`commission_rated_periods` vacía).
- Mes REVISADA: no fija nada. Tras publicar 2,50% y recalcular, vuelve a CALCULADA con 10.000 Gs y pierde el aval (`reviewed_by=None`).

### C. Errores que no deben congelar nada

- Fecha mal tipeada: venta de 400.000 Gs cargada como 2036-09-15. El mes 2036-09 no queda fijado; publicar 3,00% con vigencia 2026-10-01 sigue siendo posible (no se bloquea por el typo); recalculando el mes tipeado toma la tasa nueva, es decir sigue corregible.
- Anular tras calcular: venta calculada al 1% y luego anulada; `commission_rated_periods` queda vacía.

### D. Un período fijado no se re-tarifa por ninguna vía

- Aprobación fija 2026-09 a 100 bp. Publiqué 9,00% con vigencia 2026-09-01 y recalculé: la APROBADA conserva estado, 100 bp, 4.000 Gs y `approved_by=Gerencia`; la fila de fijación no cambió.
- Venta nueva de 1.000.000 Gs en el mes fijado (2026-09-28): comisiona 10.000 Gs al 1%, no 90.000 Gs al 9%. Se revisó, aprobó y pagó: se pagan 10.000 Gs y la fijación no se duplica.
- Mes posterior no fijado (2026-10-04, 1.000.000 Gs): sí toma la tasa nueva, 90.000 Gs al 9%. La protección es por período, no global.
- Observar y revertir después de aprobar: en ambos casos la fijación sobrevive y una venta nueva del mes sigue cobrando 10.000 Gs al 1% aunque la política vigente sea 9%.
- Tasas divergentes dentro del mismo mes antes de fijar: A (Local A) a 90.000 Gs al 9% y B (Local B) a 10.000 Gs al 1% conviven sin fijar. Al aprobar A el mes queda fijado a 900 bp, y B ya no puede revisarse ("la política del período cambió desde el cálculo (v1 → v2): recalcule antes de continuar"). Recalculando, B pasa a 90.000 Gs. Nunca se pudo llevar a pago un importe a una tasa distinta de la fijada.

### E. Exactitud monetaria

- Convenio de 500.000 Gs: descuento 25.000 Gs, base 475.000 Gs, comisión 4.750 Gs.
- Borde de redondeo: venta de 50 Gs, 1% = 0,5 Gs exacto, HALF_UP a 1 Gs.

### F. Rotulado

- Mes anterior a la vigencia (2026-07, venta de 400.000 Gs): la liquidación queda `FUERA_DE_VIGENCIA` sin tasa ni importe; `policy_for_period` devuelve `rate_bp=None`, `rate_percent=None`, `pinned=False`; el KPI de comisión oficial es 0 con base informada de 400.000 Gs; el disclaimer dice "Sin tasa de comisión en vigor para 2026-07: la tasa del período se fija cuando una liquidación alcanza APROBADA o PAGADA…" sin emitir None ni ningún porcentaje de comisión. Export `contract_version` 3.
- UI real con Tk (1920x1080, `CommissionsPanel` instanciada de verdad):
  - Mes provisional: cabecera "Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde 2026-08-01 · provisional: aún sin aprobación ni pago en el período · redondeo HALF_UP a Gs. enteros"; KPI "COMISIÓN OFICIAL 1,00%".
  - Tras aprobar: cabecera "… · fijada al aprobarse o pagarse · …".
  - Mes sin tasa en vigor: cabecera "Sin tasa oficial en vigor para 2026-07 · se fija cuando una liquidación se aprueba o se paga · se informa sólo la base comisionable · redondeo HALF_UP a Gs. enteros" (ni None ni porcentaje de comisión); KPI "COMISIÓN OFICIAL — SIN TASA EN VIGOR".

### G. Migración de bases legadas construidas a mano

Nueve bases construidas por SQL directo (ventas y liquidaciones insertadas a mano en estados y tasas arbitrarios) y reabiertas con el repositorio:

- Sólo CALCULADA y REVISADA a 7,00%: no se inventa tasa, `commission_rated_periods` vacía.
- APROBADA viva a 7,00%: siembra el período con 700 bp, `origin=BACKFILL`, `first_rated_by=MIGRACION`.
- APROBADA de venta anulada: no siembra.
- REVERTIDA con tasa: no siembra.
- APROBADA con `POLITICA_HISTORICA_PREVIA`: no siembra.
- Evidencia discrepante (APROBADA a 7,00% y PAGADA a 3,00% en el mismo mes): no se fija nada y queda asiento `COMMISSION_PERIOD_RATE_SEED_SKIPPED` con `{"reason": "EVIDENCIA_DISCREPANTE", "rates_bp": [300, 700]}`.
- Evidencia concordante APROBADA + PAGADA a 5,00%: una sola fila a 500 bp.
- Idempotencia: base con cuatro liquidaciones legadas (2026-09, 2026-11 concordantes; 2026-12 discrepante) abierta 1.000 veces. `commission_rated_periods`, `central_audit` (3 filas) y `commission_entries` quedan byte a byte idénticos a la primera apertura; 2026-12 nunca se fija.
- Fijación preexistente a 100 bp con evidencia legada a 700 bp: la migración no la pisa, queda 100 bp.
- Base viva (no legada) con un período ya fijado, reabierta 1.000 veces: `commission_rated_periods`, liquidaciones, auditoría (1 fila) e historial (4 filas) sin un solo cambio.
- Borrando por SQL la evidencia durable de una base cuya única liquidación quedó OBSERVADA: la migración no reinventa la tasa y no toca el importe (sigue 100 bp / 4.000 Gs).

### H. Guardas e invariantes de contrato

- `review` rechaza una liquidación sin política aplicada ("la liquidación no tiene la política oficial aplicada: recalcule antes de continuar").
- PAGADA intacta tras publicar 9,00% y recalcular: sigue en 4.000 Gs y `recalculate` ni siquiera la evalúa (`evaluated=0`).
- Recalcular cinco veces no reasienta historial (2 filas antes y después).
- Republicar el mismo porcentaje y vigencia no crea versión; una vigencia que retrocede se rechaza.
- Corrección de origen sobre una APROBADA (400.000 → 900.000 Gs): el importe y la tasa aprobados no cambian (4.000 Gs, 100 bp); queda OBSERVADA con "Origen corregido tras la revisión, aprobación o pago: requiere corrección manual".
- Trazabilidad: la fijación deja `COMMISSION_PERIOD_RATE_PINNED` en `central_audit` con `boundary=APROBADA`, `rate_bp=100`, `entry_id` y `sale_id`; el historial de la liquidación recoge las cinco transiciones (SALE_REGISTERED, COMMISSION_RECALCULATED, CALCULATION_REVIEWED, COMMISSION_APPROVED, SOURCE_UPDATED_AFTER_CLOSE).

### Regresión completa

`python -m pytest -q` en el worktree: **395 passed en 39,21 s**, sin fallos ni errores.

## Bloqueantes

Ninguno.

## Observaciones no bloqueantes

1. **Base legada con evidencia discrepante: el rótulo afirma algo que en esa base es falso.** Construí a mano una base con una APROBADA de 28.000 Gs al 7,00% y una PAGADA de 12.000 Gs al 3,00% en 2026-09. La migración hace lo correcto: no desempata y asienta `EVIDENCIA_DISCREPANTE`. Pero el mes queda sin fijar, y entonces el disclaimer emite "todavía provisional: ninguna liquidación del período fue aprobada ni pagada" mientras el mes contiene una liquidación PAGADA, y el KPI "COMISIÓN OFICIAL 1,00%" suma 40.000 Gs formados por 28.000 Gs al 7% y 12.000 Gs al 3%. No es alcanzable por ninguna ruta pública (`mark_paid` siempre fija), sólo desde una base legada que el propio sistema declara pendiente de resolución manual, y ningún importe se altera. Sugiero suavizar la frase para que describa la ausencia de fijación ("el período aún no tiene tasa fijada") en lugar de afirmar que nadie aprobó ni pagó.

2. **Una aprobación posteriormente revertida deja el período fijado para siempre, y una migración de esos mismos datos no lo reproduciría.** Aprobar y luego anular la venta lleva la liquidación a REVERTIDA (el KPI de comisión oficial y el de pagado quedan en 0) pero el mes sigue fijado y rotulado como fijado. Es coherente con el contrato de la generación 6 ("revertir después de aprobar no desfija"), pero la siembra de la migración excluye las REVERTIDA, así que reconstruir la misma base desde cero daría un mes sin fijar. La divergencia sólo se nota en una reconstrucción; el dinero es el mismo en ambos casos.

3. **En una base legada discrepante, una APROBADA cuyo importe ya no es el oficial se repara y su importe cambia.** Recalcular llevó la APROBADA de 28.000 Gs (7,00%) a 4.000 Gs (1,00%) retirando el aval, con asiento `COMMISSION_POLICY_REPAIRED` y bloque `replaced`. No es silencioso y es el diseño heredado de las generaciones 4 y 5, pero conviene que quede dicho: en una base migrada sin fijación, un importe ya aprobado sí puede cambiar de valor por recálculo.

4. **Formato del porcentaje distinto entre export y pantalla.** El `policy_disclaimer` escribe "1.00%" (punto decimal) y la cabecera de la UI "1,00%" (coma). El export es contrato de datos y la pantalla es texto en español, así que probablemente sea deliberado, pero es una inconsistencia visible si alguien pega el disclaimer en un informe.

5. Falso positivo de mi propia aserción, que aclaro para que no se lea como hallazgo: mi comprobación "el disclaimer sin tasa no contiene ningún %" falló porque el texto incluye "Convenio: 5% de descuento antes de la base". No es un porcentaje de comisión; el disclaimer efectivamente no declara ninguna tasa de comisión ni emite None en ese caso.

## Superficie que mi revisión NO cubrió

- No revisé el paquete documental de la misión (SUMMARY, HANDOFF, MIGRATION, ARCHITECTURE_DELTA, ARTIFACT_CONSISTENCY, MANIFEST.sha256, WORKFLOW.json, el zip ni las capturas). No verifiqué hashes del manifiesto ni la coherencia entre lo escrito en la documentación y lo que hace el código; sólo validé el comportamiento del código.
- No revisé la captura `comision-1pct-1920x1080.png` como imagen; mi evidencia visual es el texto real de los widgets Tk instanciados, no un examen del PNG del paquete.
- No ejercité concurrencia: dos procesos aprobando el mismo período a la vez, ni el comportamiento de `BEGIN IMMEDIATE` bajo contención o bloqueo de sqlite.
- No probé bases corruptas a nivel de fichero, esquemas parcialmente migrados (tablas o columnas faltantes) ni versiones de sqlite distintas de la del intérprete local.
- No auditoré `sync_review_sales` contra un servicio de revisión real ni la integración con BC Caja; sólo trabajé con el libro de comisiones directamente.
- No evalué rendimiento ni volumen: mis bases tienen unidades de liquidaciones, no miles, y no medí el coste de la migración sobre una base grande.
- No revisé permisos y roles más allá de usar un ADMIN_CENTRAL; no probé auditor, operador local ni escalada de privilegios.
- No probé el flujo separado de corrección explícita de una tasa ya fijada, porque según el propio código no existe todavía.
- No revisé módulos ajenos a la política de comisión (caja diaria, RRHH, entregas, factufácil) más allá de que la regresión completa pasa.
