# VERDICT_AUDITOR — Generación 4

| Campo | Valor |
|---|---|
| **Rol** | AUDITOR-IND-COMISION-POLICY-1PCT-004 — auditor independiente de invariantes económicos |
| **Misión** | BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 — generación 4 |
| **Snapshot revisado** | `5652e46ce7127060ed50d96e464e732809351550` (verificado con `git rev-parse HEAD` al abrir y al cerrar) |
| **Timestamp UTC** | inicio `2026-08-18T01:35:10Z` — cierre `2026-08-18T01:45:21Z` |
| **Ficheros modificados por mí** | **Ninguno.** `git status --porcelain` vacío al empezar y al terminar. Sin commits, sin `git add`, sin `checkout`, sin `push`. |
| **Dónde escribí mis pruebas** | Fuera del repositorio: `scratchpad\aud-gen4\` (`harness.py`, `t_b1.py`, `t_evasion.py`, `t_evasion2.py`, `t_evasion4.py`, `t_block.py`, `t_conc.py`, `t_conc2.py`, `t_b2.py`, `t_inv.py`, `t_inv2.py`, `t_final.py`). Bases SQLite temporales bajo `%TEMP%\aud4-*`. Cero escrituras dentro del worktree. |
| **Independencia** | No consulté los verdicts de Librarian ni de QA de la generación 4 (el directorio `generation-4/` no existía en el snapshot). Todo por rutas públicas del código, salvo donde indico explícitamente una inyección SQL para reconstruir un estado migrado. |
| **Suite del proyecto** | `tests/gestion_central/test_comisiones.py` — 88 passed (corrida propia, `-p no:cacheprovider`, árbol intacto). |
| **VEREDICTO** | **FAIL** — 2 bloqueantes |

---

## Cierre de B1 y B2 (generación 3)

| Gen3 | Hallazgo | Estado | Evidencia propia |
|---|---|---|---|
| **B1** | Guarda `effective_from < latest`: una vigencia *igual* re-tarifaba un período ya liquidado | **CERRADO en la ruta directa; ABIERTO por ruta indirecta** | `t_b1.py`: sobre una liquidación de 2026-08 pagada al 1% (40.000 Gs), `set_general_rate(1000, "2026-08-01")` y `set_general_rate(0, "2026-08-01")` son **rechazados** con «la vigencia 2026-08-01 gobernaría el período 2026-08, que ya fue liquidado». Igual rechazo con la entrada en `CALCULADA`, `REVISADA` y `APROBADA`. El retroceso estricto sigue bloqueado. **Pero** la marca de «período liquidado» se borra con `observe()` / `void_sale()` y la fuga vuelve completa → **bloqueante B1-g4**. |
| **B2** | `replaced` sólo se escribía al reparar `REVISADA`/`APROBADA` | **CERRADO dentro de `recalculate`** | `t_b2.py`: base de piloto migrada, entrada legada 2% / 80.000 Gs con período previo a la vigencia, en los cuatro estados alcanzables. `recalculate` la deja `FUERA_DE_VIGENCIA` sin importe y **siempre** escribe `replaced={'rate_bp':200,'commission_amount':80000,'policy_status':'POLITICA_HISTORICA_PREVIA'}` — en `ELEGIBLE` y `CALCULADA` con acción `COMMISSION_RECALCULATED`, en `REVISADA` y `APROBADA` con `COMMISSION_POLICY_REPAIRED`. Idempotente: la 2ª y 3ª corrida dan `changed=0` y no repiten el asiento. **Pero** la misma anulación por `_apply_source_update` no deja asiento → **bloqueante B2-g4**. |

La decisión del propietario —opción (a), endurecer la guarda, sin flujo de corrección explícita— **está correctamente declarada** en el paquete: `COMMISSION_POLICY_1PCT.md:90-92`, `SUMMARY.md:66-71` y `HANDOFF.md:124-129` dicen que el flujo separado de corrección «hoy no existe» y que un período liquidado con tasa equivocada no tiene corrección por ruta pública. Esa declaración es cierta y suficiente.

---

## Tabla de los diez invariantes

### Cinco heredados

| # | Invariante | Resultado | Prueba / salida |
|---|---|---|---|
| **I1** | Un solo porcentaje general tras migrar | **PASS** | `t_inv.py`: base con `GENERAL`(sintética), `VENDEDORA:ANA`(7%), `LOCAL:ASU`(4,5%) → tras migrar queda **una** fila: `GENERAL / '' / 100 bp / CANONICA_APROBADA / COMISION_GENERAL_1PCT v1 / 2026-08-01`. Estable en la 2ª migración. Ninguna ruta pública escribe `scope<>'GENERAL'`. |
| **I2** | Traza de política inseparable del importe calculado | **PASS** | `t_inv.py`, fuzz de 10 corridas × 120 pasos (alta, corrección de origen, anulación, recálculo, revisión, aprobación, pago, observación, reversión, publicación de tasa) = **1.200 operaciones, 0 violaciones**: `rate_bp` y `commission_amount` siempre nulos o presentes juntos; `FUERA_DE_VIGENCIA` nunca con porcentaje; `CANONICA_APROBADA` nunca sin él; e importe siempre `= base × tasa`. |
| **I3** | Idempotencia de `recalculate` incluyendo los cinco campos de política | **PASS** | `t_inv2.py`: 1ª `changed=4`; corridas 2ª–5ª `changed=0` con snapshot **idéntico incluido `updated_at`**. Alterando por SQL cada uno de los cinco campos (`policy_status`, `policy_code`, `policy_version`, `policy_effective_from`, `policy_scope`) por separado: `changed=1` y restauración exacta en los cinco casos. |
| **I4** | Ninguna liquidación sin porcentaje alcanza el pago | **PASS** | `t_inv2.py`: sin calcular, `review`/`approve`/`mark_paid` rechazan por transición. Período pre-vigencia → `FUERA_DE_VIGENCIA` sin importe → `review` rechaza («no tiene la política oficial aplicada»). Deriva de versión (sello canónico, v1 vs v2 en vigor) → `mark_paid` rechaza («la política del período cambió desde el cálculo (v1 → v2)») y `recalculate` repara retirando los avales y asentando `replaced`. |
| **I5** | Un cambio de política no mueve dinero ya liquidado | **PASS** | `t_inv2.py`: tras pagar al 1%, publicar 10% desde 2027-01-01 deja el snapshot completo de entradas **idéntico**; `recalculate` posterior devuelve `evaluated=0`. Forzando por SQL `status='APROBADA'` con `paid_at` presente, `recalculate` sigue en `evaluated=0` (`paid_at IS NULL` cuelga del `WHERE` raíz, `comisiones.py:800-802`). |

### Cinco que agrega esta misión

| # | Invariante | Resultado | Prueba / salida |
|---|---|---|---|
| **I6** | Ausencia de floats en el cálculo monetario | **PASS** (con observación O3) | `t_inv.py`, escaneo AST de `comision_policy.py`, `comisiones.py`, `repository.py`, `comisiones_ui.py`: **0 literales float**, **0 llamadas a `float()` o `round()`**. Las divisiones de `comision_policy.py:58,82` son sobre `Decimal`; las de `comisiones_ui.py:357,359` son operadores de `pathlib`. Única división float real: `comisiones.py:919`, en una etiqueta de pantalla (O3). |
| **I7** | Exactitud de la aritmética `Decimal` y del único redondeo `HALF_UP` | **PASS** | `t_inv.py`: **161.000 casos** (barrido 0–2999 + 20.000 aleatorios hasta 10^12 × tasas 1/7/100/333/500/9999/10000 bp) contra un HALF_UP exacto con `Fraction`: **0 discrepancias**. Medio guaraní sube y no redondea al par: `50×1%=1`, `150×1%=2`, `250×1%=3`, `350×1%=4`. Base de convenio `total − HALF_UP(5%)`: 0 discrepancias en 25.000 casos. |
| **I8** | La migración no escribe ningún importe | **PASS** | `t_inv.py`: `rate_bp`, `commission_amount`, `gross_amount`, `commissionable_base` y `agreement_discount` **idénticos** antes y después de dos migraciones consecutivas. Sólo cambia la etiqueta de política. |
| **I9** | El retiro de políticas por alcance queda auditado con su valor previo | **PASS** | `t_inv.py`: tres asientos `COMMISSION_POLICY_RETIRED` con `rate_bp` previo (100, 700, 450), `approval_status` previo y `replaced_by`. Tras dos migraciones siguen siendo **3**, no se duplican. |
| **I10** | Concurrencia sobre `mark_paid` y sobre `set_general_rate` | **PASS** | `t_conc.py` / `t_conc2.py`, hilos reales y barreras. **C1**: 8 hilos `mark_paid` sobre la misma aprobada → exactamente **1 éxito** y **1** asiento `COMMISSION_PAID`. **C2**: 12 cadenas review→approve→mark_paid entrelazadas con `set_general_rate` y `recalculate` → 12 pagos, **0 anomalías**; total pagado 193.333 Gs = suma exacta al 1%. **C3**: 10 hilos publicando la misma versión → 1 `True` + 9 `False`, **sin versiones duplicadas**. **C4**: 40 rondas de carrera `set_general_rate(2026-08)` contra dos `recalculate(2026-08)` → **0 rondas con tasas mezcladas** en un mismo período. **C5**: 40 rondas de `mark_paid` contra publicación sobre el mismo mes → 0 casos de publicación sobre período liquidado. `BEGIN IMMEDIATE` serializa correctamente; no encontré ventana TOCTOU entre la lectura de política (conexión aparte) y el commit. |

### Undécimo criterio del prompt de rol

| # | Criterio | Resultado |
|---|---|---|
| **I11** | Que ninguna afirmación de invariante del paquete sea falsa contra el código | **FAIL** — ver B1-g4 y B2-g4 |

---

## Bloqueantes

### B1-g4 — La guarda nueva se desarma con `observe()` o `void_sale()`: la fuga de re-tarifado retroactivo sigue abierta

**Invariante declarado (falso).**
- `ARCHITECTURE_DELTA.md:72` — «Con las dos, el re-tarifado retroactivo **no tiene ruta pública, ni directa ni indirecta**.»
- `COMMISSION_POLICY_1PCT.md:90` — «Un período ya liquidado **no se re-tarifa** por esta vía, ni al alza ni a la baja.»
- `SUMMARY.md:66-70` — misma afirmación.

**Causa.** La guarda de `comisiones.py:737-745` decide si un período «ya fue liquidado» consultando el **estado actual** de las entradas:

```sql
SELECT MAX(substr(period,1,7)) FROM commission_entries
 WHERE period IS NOT NULL AND status IN ('CALCULADA','REVISADA','APROBADA','PAGADA')
```

`OBSERVADA` y `REVERTIDA` no están en `SETTLED_STATES` (`comisiones.py:45`), y **desde los cuatro estados liquidados se llega a ellas por rutas públicas y legítimas**:

- `observe()` acepta explícitamente `OPEN_STATES | {"PAGADA"}` (`comisiones.py:663`): observar un pago —una acción normal de control— borra la marca del período.
- `void_sale()` sobre una venta con comisión ya pagada pone la entrada en `OBSERVADA` **sin que el operador lo elija** (`comisiones.py:566-568`).
- `revert()` saca de la marca cualquier `CALCULADA`/`REVISADA`/`APROBADA` no pagada.
- Una **corrección cosmética de origen** (cambiar sólo el sobre) devuelve una `CALCULADA` a `ELEGIBLE` con `rate_bp=NULL` (`comisiones.py:390-400`), que tampoco es un estado liquidado.

La guarda no mira `paid_at`, ni `rate_bp`, ni el historial: la evidencia de que a ese período **se le aplicó un porcentaje y salió dinero** existe en la fila y se ignora.

**Reproducción — al alza** (`t_final.py`, salida literal):

```
### B1-RESIDUAL: observar una PAGADA borra la marca de 'periodo liquidado' ###
1) Ana, agosto: PAGADA al 1% = 40000 Gs
2) set_general_rate(10%, 2026-08-01) BLOQUEADO (guarda nueva, correcto)
3) observe(PAGADA) -> estado: OBSERVADA | paid_at: 2026-08-20
4) set_general_rate(10%, 2026-08-01) -> (2, True)
   politica que rige 2026-08 ahora: {'version': 2, 'rate_bp': 1000, 'effective_from': '2026-08-01', 'code': 'COMISION_GENERAL_1PCT'}
5) Cyn, MISMO mes agosto: PAGADA al 10% = 400000 Gs
   sobrepago frente al 1% que regia el periodo: 360000 Gs
```

Dinero real: **400.000 Gs pagados por el período 2026-08, donde el 1% eran 40.000 Gs**, en el mismo mes en que otra vendedora cobró al 1%. Rompe además I1 en su sentido económico: dos porcentajes distintos conviviendo en un mismo período bajo el único alcance `GENERAL`.

**Reproducción — a cero, mes completo** (`t_evasion2.py`): tres liquidaciones de agosto (una `PAGADA` de 40.000, dos `APROBADA` de 90.000 y 70.000), todas observadas; `set_general_rate(0, "2026-08-01")` → `(2, True)`; la política que rige 2026-08 pasa a `rate_bp: 0`. El mes queda anulado a cero.

**Reproducción — sin tocar la observación de la pagada** (`t_evasion2.py`, EVASION 3): `void_sale` sobre la venta ya pagada → la entrada pasa sola a `OBSERVADA` → `set_general_rate(1000, "2026-08-01")` → `(2, True)`.

**Reproducción — con corrección cosmética de origen** (`t_evasion4.py`): la `CALCULADA` de Bea vuelve a `ELEGIBLE` sólo por cambiar el sobre; publicado el 10%, Bea cobra **400.000 Gs** por agosto contra los 40.000 de Ana.

**Cierre.** La guarda debe apoyarse en evidencia de tarifación, no en el estado actual. Basta con ampliar el `WHERE` a algo como `status IN (...) OR paid_at IS NOT NULL OR rate_bp IS NOT NULL` (o resolver el máximo período liquidado contra `commission_entry_history`), de modo que `OBSERVADA` y `REVERTIDA` con porcentaje grabado sigan protegiendo su período. Alternativamente, retirar las afirmaciones de `ARCHITECTURE_DELTA.md:72`, `COMMISSION_POLICY_1PCT.md:90` y `SUMMARY.md:66-70`. No es estructural.

---

### B2-g4 — `_apply_source_update` anula un importe heredado sin dejar asiento en ninguna ruta pública

**Invariante declarado (falso en su enunciado general).**
- `ARCHITECTURE_DELTA.md:76` — «**Todo importe retirado queda asentado.**»
- `SUMMARY.md:74-76` — «lo que sí queda garantizado es que el valor retirado se asienta en `replaced`».

La garantía sólo se cumple dentro de `recalculate`. La otra ruta que anula importes —`_apply_source_update`, `comisiones.py:390-402`— pone `rate_bp=NULL, commission_amount=NULL` y escribe una historia `SOURCE_UPDATED` cuyos `details` llevan `total`, `balance`, hashes, base y descuento, pero **no el porcentaje ni el importe anulados**. Para un importe que ya pasó por `recalculate` el valor sobrevive en el asiento anterior; para un **importe heredado de una base migrada** —exactamente el caso que motiva esta misión— no existe ningún asiento previo y el valor desaparece del sistema.

**Reproducción** (`t_final.py`, salida literal):

```
### B2-RESIDUAL: la correccion de origen anula un importe heredado sin asiento ###
1) tras migrar: CALCULADA rate 200 monto 80000 POLITICA_HISTORICA_PREVIA
2) tras corregir solo el sobre: ELEGIBLE rate None monto None
3) asientos: [('SALE_REGISTERED', None), ('SOURCE_UPDATED', None)]
4) el importe 80000 sobrevive en alguna ruta publica?: False
```

La corrección de origen es **cosmética** (sólo cambia el sobre) y no requiere ningún permiso especial más allá de `reviews.manage`. Los 80.000 Gs de comisión legada se pierden sin rastro en `commission_entry_history`, en `central_audit` y en la base.

**Cierre.** Añadir el bloque `replaced` a los `details` de `SOURCE_UPDATED` cuando `entry["commission_amount"]` o `entry["rate_bp"]` no son nulos, exactamente como hace `recalculate` en `comisiones.py:861-868`. Una línea de código. Alternativamente, restringir la afirmación de `ARCHITECTURE_DELTA.md:76` a `recalculate`, aunque eso deja el importe perdido igual.

---

## Observaciones no bloqueantes

**O1 — Una sola venta con fecha futura mal tipeada congela la programación de la tasa durante años.** La guarda usa `MAX(period)` sobre **toda** la tabla, incluidos períodos futuros, y nada valida que una fecha de venta no esté en el futuro. `t_block.py`:

```
entrada con tipeo: 2036-08 CALCULADA
  2026-09-01: BLOQUEADO -> la vigencia 2026-09-01 gobernaria el periodo 2036-08, que ya fue liquidado
  2027-01-01: BLOQUEADO -> ... 2036-08 ...
  2030-01-01: BLOQUEADO -> ... 2036-08 ...
  2036-09-01: publicado (2, True)
```

Un `2036` en lugar de `2026` deja la política inmutable durante diez años, y el mensaje de error nombra un período que el operador no reconoce. No mueve dinero, por eso no es bloqueante, pero sí es un bloqueo indebido de la programación legítima hacia adelante. La programación normal sí funciona (verificado en `t_b1.py` B1-d y `t_block.py`: con agosto pagado se publica 2% desde 2026-09-01, septiembre cobra al 2%, agosto queda intacto, y republicar lo idéntico devuelve `(2, False)`).

**O2 — Observar una liquidación pagada retira su importe del KPI `paid_amount`.** `report()` calcula `paid_amount` sobre `status == "PAGADA"`, así que los 40.000 Gs efectivamente pagados desaparecen del reporte del período en cuanto la entrada pasa a `OBSERVADA` (`t_evasion4.py`: `KPI pagado 2026-08: 400000`, sin los 40.000 de Ana). Es dinero que salió y que el reporte oficial deja de mostrar; además es lo que vuelve invisible la fuga B1-g4 en pantalla.

**O3 — Único float del módulo.** `comisiones.py:919`, `AGREEMENT_DISCOUNT_BP / 100:.0f`, en una etiqueta de pantalla del desglose. No participa de ningún cálculo monetario. Heredada de la generación 3, sin cambios.

---

## Fundamento del veredicto

La aritmética es exacta (161.000 casos contra `Fraction`, cero discrepancias), la migración no toca un solo guaraní, la traza es inseparable del importe en 1.200 operaciones de fuzz, el recálculo es idempotente sobre los cinco campos de política, la deriva de versión se sigue comprobando contra la política en vigor y no contra el sello grabado, y la concurrencia resiste hilos reales sobre `mark_paid`, `set_general_rate` y `recalculate` sin un doble pago ni una tasa mezclada en 80 rondas de carrera. **Los diez invariantes económicos pasan y la guarda nueva no introdujo ninguna regresión** ni bloquea la programación legítima hacia adelante en su uso normal.

Bloquea el undécimo criterio. La guarda nueva cierra la puerta que yo derribé en la generación 3 —la vigencia igual sobre un período liquidado— pero se apoya en el **estado actual** de las entradas en lugar de en la evidencia de que a ese período ya se le aplicó un porcentaje. `observe()` sobre una liquidación pagada, que es una operación pública, normal y explícitamente permitida, borra esa marca y devuelve la fuga entera: **400.000 Gs pagados donde el 1% eran 40.000**, o el mes completo anulado a cero. La afirmación de que «no tiene ruta pública, ni directa ni indirecta» es falsa contra el código. Y la promesa de que «todo importe retirado queda asentado» tampoco se sostiene fuera de `recalculate`: una corrección cosmética de origen borra 80.000 Gs de comisión heredada sin dejar rastro.

Ninguno de los dos bloqueantes es estructural. B1-g4 se cierra ampliando una cláusula `WHERE` en `comisiones.py:737-740`; B2-g4, replicando en `SOURCE_UPDATED` el bloque `replaced` que `recalculate` ya escribe. Con eso —y con O1 atendida— el módulo queda en condiciones de PASS.

---

# VEREDICTO: **FAIL**

**Bloqueantes: 2** (B1-g4, B2-g4). **Observaciones no bloqueantes: 3** (O1, O2, O3).

---

*El worktree quedó exactamente como lo encontré — `git status --porcelain` vacío, HEAD en `5652e46ce7127060ed50d96e464e732809351550`. Todas mis pruebas viven en el scratchpad, fuera del repositorio.*
