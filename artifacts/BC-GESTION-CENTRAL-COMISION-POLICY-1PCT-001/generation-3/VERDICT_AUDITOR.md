# VERDICT_AUDITOR — Generación 3

| Campo | Valor |
|---|---|
| **Runner** | AUDITOR-IND-COMISION-POLICY-1PCT-003 |
| **Rol** | Auditor independiente de invariantes económicos |
| **Misión** | BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 — generación 3 |
| **Snapshot revisado** | `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a` (verificado con `git rev-parse HEAD` al abrir y al cerrar) |
| **Timestamp UTC** | inicio `2026-08-18T00:48:52Z` — cierre `2026-08-18T00:59:06Z` |
| **Ficheros modificados por mí** | **Ninguno.** `git status --porcelain` vacío al empezar y al terminar. Sin commits, sin `git add`, sin `checkout`, sin `push`. |
| **Dónde escribí mis pruebas** | Directorio temporal fuera del repositorio: `scratchpad\auditor-gen3\` (`common.py`, `t1_arith.py`, `t2_migration.py`, `t3_legacy.py`, `t4_drift.py`, `t5_fuzz.py`, `t5b_cov.py`, `t6_conc.py`, `t7_idem.py`, `t8_claims.py`, `t9_final.py`). Bases SQLite temporales bajo `%TEMP%\aud3_*`. Cero escrituras dentro del worktree. |
| **Independencia** | No consulté verdicts de Librarian ni de QA de la generación 3 (el directorio `generation-3/` no existía en el snapshot). Todo por rutas públicas del código. |

---

## Cierre de los hallazgos de las generaciones invalidadas

| Gen | Hallazgo | Estado | Evidencia propia |
|---|---|---|---|
| **gen1 A1** | Invariante de traza falso sobre base migrada | **CERRADO** | `t2_migration.py` + fuzz `t5_fuzz.py` (I-B): sobre base de piloto migrada, la traza queda **completa** (`CANONICA_APROBADA`, `FUERA_DE_VIGENCIA`) o **vacía** (`POLITICA_HISTORICA_PREVIA`, `SIN_POLITICA_APLICADA`), nunca a medias. 1.680 operaciones aleatorias, 0 violaciones. |
| **gen1 A2** | Fuga: liquidación legada pagable al porcentaje retirado; el remedio destruía la comisión | **CERRADO en la parte de fuga; PARCIAL en el remedio** | `t3_legacy.py`: `e-appr` (legada, 7%) → `mark_paid` bloqueado (`no lleva la política oficial vigente (POLITICA_HISTORICA_PREVIA)`). Ya no es pagable. El remedio sí repara cuando el período está en vigencia (ver gen2 A2); **no** cuando es anterior a la vigencia → **B2**. |
| **gen2 A1** | Deriva de versión: la guarda comprobaba el sello grabado y no la política en vigor | **CERRADO** | `t4_drift.py` D1: aprobada a 1% v1, se publica v2 al 2% sobre el mismo período → `mark_paid` rechaza con `la política del período cambió desde el cálculo (v1 → v2)`. D3: publicar una versión con vigencia **futura** no bloquea ni mueve el período en curso (se paga correctamente al 2% v2). |
| **gen2 A2** | Liquidación legada sin porcentaje: impagable e irreparable | **CERRADO para períodos en vigencia** | `t3_legacy.py`: `e-norate` (período 2026-08, `SIN_POLITICA_APLICADA`, sin importe) → `recalculate` la lleva a `CALCULADA` 1% / 30.000 Gs con traza completa, y se recorre review → approve → mark_paid. Reparada y pagada al porcentaje oficial. **Sigue abierta para períodos anteriores a la vigencia** → **B2**. |
| **gen2 A3** | `paid_at IS NULL` colgaba de una rama y no del `WHERE` | **CERRADO** | `comisiones.py:778-780` lo tiene en el `WHERE` raíz. `t4_drift.py` D5: forzando por SQL `status='APROBADA'` con `paid_at` presente, `recalculate` devuelve `evaluated=0, changed=0` y no toca el importe. |

---

## Tabla de los diez invariantes

### Cinco heredados

| # | Invariante | Resultado | Prueba / salida |
|---|---|---|---|
| **I1** | Un solo porcentaje general tras migrar | **PASS** | `t2_migration.py`: base con `GENERAL`(3%), `VENDEDORA:ANA`(7%), `LOCAL:ASU`(4,5%) sintéticas → tras migrar queda **una** fila: `GENERAL / '' / 100 bp / CANONICA_APROBADA / COMISION_GENERAL_1PCT v1 / 2026-08-01`. Las de alcance se borran. Idempotente: 2ª corrida no duplica auditorías ni versiones. `t8_claims.py` R3: no existe API que escriba `scope<>'GENERAL'`. |
| **I2** | Traza de política inseparable del importe calculado | **PASS** | `t5_fuzz.py` I-A/I-B/I-C sobre 12 corridas × 140 pasos (alta, cobro, corrección de origen, anulación, reversa, recálculo, revisión, aprobación, pago, observación, reversión, publicación de tasa): 0 violaciones. `rate_bp` y `commission_amount` siempre nulos o presentes juntos; `FUERA_DE_VIGENCIA` nunca con porcentaje; una corrección de origen borra la traza junto con el importe. |
| **I3** | Idempotencia de `recalculate` incluyendo los cinco campos de política | **PASS** | `t7_idem.py`: 1ª `changed=4`, corridas 2ª–5ª `changed=0` con snapshot idéntico **incluido `updated_at`**. Alterando por SQL cada uno de los cinco campos (`policy_status`, `policy_code`, `policy_version`, `policy_effective_from`, `policy_scope`) por separado, `recalculate` detecta y restaura los cinco (`changed=1` en cada caso). |
| **I4** | Ninguna liquidación sin porcentaje alcanza el pago | **PASS** | `t3_legacy.py` + fuzz I-E: `review`/`approve`/`mark_paid` exigen importe, sello `CANONICA_APROBADA` **y** coincidencia de `(rate_bp, version)` con la política en vigor para el período. Ninguna entrada llegó a `PAGADA` sin porcentaje ni con política no canónica en 1.680 operaciones. |
| **I5** | Un cambio de política no mueve dinero ya liquidado | **PASS** | `t4_drift.py` D4: tras pagar a 2% v2, se publica 10% v4 y se recalcula → snapshot de la entrada **idéntico** (`INTACTO: True`). `recalculate` reporta `evaluated=0`. `t8_claims.py` R2: `set_general_rate` por sí solo no altera ninguna entrada, ni siquiera `updated_at`. |

### Cinco que agrega esta misión

| # | Invariante | Resultado | Prueba / salida |
|---|---|---|---|
| **I6** | Ausencia de floats en el cálculo monetario | **PASS** (con observación O1) | `t1_arith.py` D: escaneo AST de `comision_policy.py`, `comisiones.py`, `repository.py`, `comisiones_ui.py` → **0 literales float**, **0 llamadas a `float()` o `round()`**. Las divisiones verdaderas de `comision_policy.py:58,82` son sobre `Decimal`; las de `comisiones_ui.py:357,359` son operadores de `pathlib`. Única división float real: `comisiones.py:879`, sólo en una etiqueta de pantalla (O1). |
| **I7** | Exactitud de la aritmética `Decimal` y del único redondeo `HALF_UP` | **PASS** | `t1_arith.py` A/B/C: 26.000 casos (barrido 0–2999 × {1%, 5%} + 20.000 aleatorios hasta 10^12 con tasas 1/7/100/333/500/9999/10000 bp) contra un HALF_UP exacto implementado con `Fraction`: **0 discrepancias**. Medio guaraní sube y no redondea al par: `50×1%=1`, `150×1%=2`, `250×1%=3` (`HALF_EVEN` daría 0 y 2). Base de convenio `total − HALF_UP(5%)`: 0 discrepancias en 25.000 casos. |
| **I8** | La migración no escribe ningún importe | **PASS** | `t2_migration.py`: `rate_bp`, `commission_amount`, `gross_amount`, `commissionable_base` y `agreement_discount` de las tres entradas heredadas (pagada, aprobada, sin tasa) **idénticos** antes y después. Sólo cambia `policy_status`: `SINTETICA_PENDIENTE_APROBACION`→`POLITICA_HISTORICA_PREVIA` con importe, `SIN_POLITICA_CONFIGURADA`→`SIN_POLITICA_APLICADA` sin importe. Estable en la 2ª corrida. |
| **I9** | El retiro de políticas por alcance queda auditado con su valor previo | **PASS** | `t2_migration.py`: tres asientos `COMMISSION_POLICY_RETIRED` con `rate_bp` previo (300, 700, 450), `approval_status` previo y `replaced_by`. No se duplican en la 2ª corrida (3 → 3). |
| **I10** | Concurrencia sobre `mark_paid` y sobre `set_general_rate` | **PASS** | `t6_conc.py` con hilos reales y barrera de sincronización. **C1**: 12 hilos `mark_paid` sobre la misma aprobada × 5 reps → exactamente 1 éxito y 1 evento `COMMISSION_PAID` en cada rep, sin doble pago. **C2**: 30 reps × 8 hilos entrelazando `mark_paid`/`set_general_rate`/`recalculate` → 18 pagos, **0 inconsistencias** (importe = base×tasa, versión existente, sello canónico). **C3**: 16 hilos `set_general_rate` → 0 errores, versiones 1..17 únicas y consecutivas, fila vigente coherente con la última versión. **C4**: 12 hilos `register_payment` de 200.000 sobre saldo de 1.000.000 → exactamente 5 éxitos, libro = `paid_amount`, sin sobrecobro. **C5**: 20 reps de `recalculate` concurrente con `review`/`set_general_rate` → 0 desalineaciones. **C6** (`t7_idem.py`): carrera determinista con la guarda instrumentada para dormir 1,5 s dentro del `BEGIN IMMEDIATE` mientras otro hilo publica 50% → SQLite serializa: se paga al 1% vigente y la publicación commitea después. No existe ventana entre la lectura de política y el commit del pago. |

### Undécimo criterio del prompt de rol

| # | Criterio | Resultado |
|---|---|---|
| **I11** | Que ninguna afirmación de invariante del paquete sea falsa contra el código | **FAIL** — ver bloqueantes B1 y B2 |

---

## Bloqueantes

### B1 — El versionado no impide re-tarifar el pasado: un período ya liquidado y aprobado puede re-tarifarse al alza o a cero

**Invariante declarado (falso).**
- `COMMISSION_POLICY_1PCT.md:84` — «Se puede programar el futuro; **no se puede re-tarifar el pasado**. Una corrección hacia atrás no es un cambio de política.»
- `modulos/gestion_central/comisiones.py:696` — «no se puede re-tarifar el pasado, **que es lo que el versionado existe para impedir**.»

**Causa.** La guarda de `set_general_rate` (`comisiones.py:709-712`) es estrictamente `effective_from < latest`. Una vigencia **igual** a la última publicada se acepta. Como `in_force_for()` resuelve por `applicable[-1]` sobre `ORDER BY effective_from, version`, la versión nueva pasa a gobernar ese período **y todos los posteriores**, incluidos los ya calculados, revisados y aprobados. Mientras no exista una versión con vigencia posterior —el caso por defecto tras la migración, cuya única versión rige desde `2026-08-01`— la ventana retroactiva permanece abierta indefinidamente.

**Reproducción — al alza** (`t9_final.py`, sección B1-bis):

```
aprobada: {'commission_amount': 100000, 'rate_bp': 100, 'policy_version': 1}
set_general_rate(4000 bp, '2026-08-01') -> (2, True)
recalculate -> {'evaluated': 1, 'changed': 1}
PAGADA: {'status':'PAGADA','rate_bp':4000,'commission_amount':4000000,'policy_version':2}
   (1 pct eran 100.000 Gs; se pagaron 4.000.000 Gs por una política publicada DESPUÉS del período)
versiones publicadas: [(1, 100, '2026-08-01'), (2, 4000, '2026-08-01')]
```

**Reproducción — a cero** (`t8_claims.py`, sección R1): tres liquidaciones de agosto aprobadas a 1% (100.000 Gs cada una) → `set_general_rate(0 bp, '2026-08-01')` aceptado → `recalculate` las lleva a `rate_bp=0, commission_amount=0, CANONICA_APROBADA v2`, y la primera se revisa, aprueba y **paga a 0**. Un mes entero de comisiones aprobadas se anula por una publicación posterior al período.

**Por qué es económico y no sólo documental.** El sello queda `CANONICA_APROBADA` y la cadena de pago lo acepta: el dinero efectivamente sale al porcentaje impuesto retroactivamente. Es la forma inversa de la fuga de gen1/gen2 — allí se pagaba a una política superada; aquí se paga a una política que **no regía cuando se generó la comisión**. Los mitigantes (versión auditada, retiro de revisión y aprobación, `paid_at` intocable) limitan el daño a lo aún no pagado, pero no impiden el movimiento que el paquete declara imposible.

**Cierre esperable.** O bien la guarda pasa a comparar contra el período liquidable en curso (rechazar toda vigencia que gobierne un período ya cerrado o ya con liquidaciones calculadas), o bien el paquete retira la afirmación y documenta el re-tarifado retroactivo como operación admitida, con su control explícito.

---

### B2 — «`recalculate` repara cualquier liquidación no pagada y no destruye la comisión, con el importe reemplazado asentado en el historial» es falso en dos sub-casos

**Invariante declarado (falso).** `COMMISSION_POLICY_1PCT.md:110-114` — «Cualquier liquidación **no pagada** cuyo importe no sea el oficial **tiene salida, y no destruye la comisión**: `recalculate` la repara, sea cual sea la causa […] con el importe reemplazado asentado en el historial como `COMMISSION_POLICY_REPAIRED`.»

**Sub-caso (a) — período anterior a la vigencia: no hay salida y sí se destruye.** Una liquidación legada de `2026-07` con 7% / 560.000 Gs entra a `recalculate`, que la deja en `FUERA_DE_VIGENCIA` con `rate_bp=NULL` y `commission_amount=NULL`. No es pagable, y `set_general_rate('2026-07-01')` queda bloqueado por la propia guarda de retroceso, de modo que la comisión es irrecuperable por toda ruta pública. Es literalmente el hallazgo A2 de gen2 —«impagable, irreparable, y el único remedio destruía la comisión»— **no cerrado** para períodos anteriores a `2026-08-01`. La sección «Vigencia» del mismo documento describe correctamente este comportamiento, así que el paquete se contradice a sí mismo.

**Sub-caso (b) — el valor previo no queda asentado.** El bloque `replaced` sólo se escribe cuando `repairing`, es decir cuando el estado es `REVISADA` o `APROBADA` (`comisiones.py:812-817`). Una liquidación legada en `ELEGIBLE` o `CALCULADA` toma la otra rama: se registra `COMMISSION_RECALCULATED` **sin** `replaced`, y el importe anterior desaparece de toda ruta pública.

**Reproducción** (`t9_final.py`, sección B2-bis):

```
migrada:     {'status':'ELEGIBLE','rate_bp':700,'commission_amount':560000,'policy_status':'POLITICA_HISTORICA_PREVIA'}
recalculada: {'status':'CALCULADA','rate_bp':None,'commission_amount':None,'policy_status':'FUERA_DE_VIGENCIA'}
 historial: COMMISSION_RECALCULATED | 'replaced' presente: False
 los 560.000 previos en alguna ruta publica? central_audit: []
 segunda recalculate (ya no queda ni rastro): {'evaluated': 1, 'changed': 0}
 breakdown publico: [{"label":"Total de la venta","amount":8000000},{"label":"Base comisionable","amount":8000000}]
```

560.000 Gs de comisión heredada se anulan sin que ni `commission_entry_history`, ni `central_audit`, ni `breakdown`, ni el export conserven el valor retirado. La migración sí audita el porcentaje previo de la **política** (I9), pero nadie audita el importe previo de la **liquidación**.

**Cierre esperable.** Escribir `replaced` en toda rama de `recalculate` que anule o modifique un `commission_amount` previo, y corregir la afirmación de `COMMISSION_POLICY_1PCT.md:110` para que no prometa reparación donde el período es anterior a la vigencia.

---

## Observaciones no bloqueantes

1. **O1 — Único float del módulo, en una etiqueta.** `comisiones.py:879`: `f"Descuento de convenio ({AGREEMENT_DISCOUNT_BP / 100:.0f}%)"` evalúa `500 / 100 = 5.0` en coma flotante. No toca ningún importe (el monto sale de `entry["agreement_discount"]`, entero), pero la afirmación «no se usan floats en ningún punto» es literalmente inexacta. La línea 903 del mismo fichero ya usa `//` para lo mismo. Coste de cierre: un carácter.

2. **O2 — `mark_paid` no lleva la guarda `_reject_paid`.** `recalculate` se blindó explícitamente con `paid_at IS NULL` sobre el `WHERE` (gen2 A3), pero `mark_paid` confía sólo en la máquina de estados (`allowed={"APROBADA"}`). Verifiqué que **no existe ruta pública** que devuelva una entrada con `paid_at` a `APROBADA`: desde `PAGADA` sólo se sale a `OBSERVADA`; desde `OBSERVADA`, `revert` está guardado por `_reject_paid` y `recalculate` la excluye. Forzando `status='APROBADA'` por SQL directo con `paid_at` presente sí se repaga (`t4_drift.py` D6), lo cual no constituye hallazgo. Añadir `_reject_paid` a `mark_paid` cerraría la asimetría de defensa en profundidad por una línea.

3. **O3 — `set_general_rate` sin guarda de retroceso si `commission_policy_versions` queda vacía.** `latest` se calcula sobre esa tabla; si estuviera vacía con la fila de `commission_policies` ya canónica, `_migrate_commission_policy` no repuebla la versión (su condición es `current is None or approval_status != CANONICA`) y `set_general_rate` publicaría con `version=1` y cualquier vigencia, sin guarda. No encontré ruta pública que produzca ese estado —toda escritura inserta en ambas tablas—, así que lo dejo como endurecimiento: derivar `latest` también de `commission_policies.effective_from`.

4. **O4 — Vigencia a mitad de mes.** `is_in_effect` compara prefijos `AAAA-MM`, de modo que una vigencia fijada el día 15 rige el mes completo. El paquete lo documenta explícitamente como consecuencia conocida; lo confirmo y no lo cuento como defecto.

5. **O5 — `rate_bp=0` es un porcentaje válido.** `0 <= rate_bp <= 10000` admite una política oficial del 0%, cuyas liquidaciones quedan `CANONICA_APROBADA` con importe 0 y son pagables. Es coherente por sí mismo; sólo resulta problemático combinado con B1, que permite imponerlo hacia atrás.

6. **O6 — Separación de oficial y no oficial: correcta.** `t8_claims.py` R5: con una legada pagada de 350.000 Gs y una oficial de 10.000 Gs, el reporte devuelve `commission_amount=10000`, `non_official_amount=350000`, `non_official_entries=1` y `paid_amount=350000`. El export mantiene la traza propia de cada liquidación junto a la política vigente al exportar. Sin objeciones.

7. **O7 — Coste de las lecturas de política dentro de la transacción.** `recalculate` abre una conexión nueva por entrada (`policy.decide` → `catalogue()` → `repository.connection()`) mientras sostiene el `BEGIN IMMEDIATE`. Es correcto en WAL y no produjo bloqueos en las pruebas de concurrencia, pero escala mal con volúmenes grandes de período. Rendimiento, no corrección.

---

## Alcance de lo que probé

1.680 operaciones aleatorias sobre 12 bases independientes con verificación de cinco invariantes tras **cada** paso; 51.000 casos de aritmética contra un HALF_UP exacto con `Fraction`; escaneo AST de los cuatro ficheros del módulo; migración sobre base de piloto sintético con políticas por alcance y liquidaciones pagadas, aprobadas y sin tasa, corrida dos veces; y cinco escenarios de concurrencia con hilos reales y barrera, más una carrera determinista con la guarda instrumentada. La cobertura del fuzz no es vacía: alcanzó los ocho estados de liquidación y los tres `policy_status` productivos.

---

## VEREDICTO

# FAIL

**Fundamento.** Los diez invariantes económicos del enunciado —incluidos los cinco heredados que motivaron los FAIL de gen1 y gen2— **pasan**, y las cinco fugas previas están cerradas salvo un sub-caso. La aritmética es exacta, la migración no toca dinero, la traza es inseparable del importe, el recálculo es idempotente sobre los cinco campos de política, la deriva de versión ya se comprueba contra la política en vigor y no contra el sello grabado, y la concurrencia resiste hilos reales sobre `mark_paid`, `set_general_rate`, `register_payment` y `recalculate` sin un solo doble pago ni una sola inconsistencia.

Bloquea el undécimo criterio del prompt de rol: **dos afirmaciones de invariante del paquete son falsas contra el código, y ambas tienen consecuencia monetaria.** B1 permite re-tarifar retroactivamente un período ya liquidado y aprobado —al alza (pagué 4.000.000 Gs donde el 1% eran 100.000) o a cero—, precisamente lo que el código dice que «el versionado existe para impedir». B2 deja sin salida y sin rastro auditable la comisión legada de un período anterior a la vigencia, contradiciendo la promesa de que «tiene salida, y no destruye la comisión»; es el hallazgo A2 de gen2 sobreviviendo en su sub-caso pre-vigencia.

Ninguno de los dos bloqueantes es estructural. B1 se cierra endureciendo una comparación en `set_general_rate` o retirando la afirmación; B2, escribiendo `replaced` en toda rama de `recalculate` que anule un importe y corrigiendo la línea 110 de `COMMISSION_POLICY_1PCT.md`. Con eso, el módulo queda en condiciones de PASS.

---

*El worktree quedó exactamente como lo encontré — `git status --porcelain` vacío, HEAD en `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a`. Todas mis pruebas viven en el scratchpad, fuera del repo.*
