# VERDICT_QA — Generación 5

| Campo | Valor |
|---|---|
| Rol | QA-IND-COMISION-POLICY-1PCT-005 (revisión independiente de calidad funcional) |
| Misión | BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 |
| Generación | 5 |
| Snapshot verificado | `2ac9f5c93ec99ed506133310ee6cd19f6779b971` (`git rev-parse HEAD`) |
| Árbol al iniciar / al terminar | limpio / limpio (`git status --porcelain` vacío en ambos extremos) |
| Escenarios propios | `…\scratchpad\qa-gen5\{matrix.py, checks.py, b2_and_econ.py, combos.py, ui_label.py}` |
| Suite del paquete (regresión) | `python -m pytest tests/gestion_central -q` → **171 passed** |
| Fecha UTC | 2026-08-18T02:30:34Z |
| **VEREDICTO** | **FAIL** (2 bloqueantes) |

---

## 1. Alcance y método

No reutilicé la matriz de 14 transiciones del paquete. Enumeré por mi cuenta las rutas públicas que mueven el estado de una liquidación leyendo `modulos/gestion_central/comisiones.py`, y construí **18 casos** (17 transiciones/combinaciones + un control). Superficie pública considerada:

- Transiciones directas de la liquidación: `review`, `approve`, `mark_paid`, `observe`, `revert`.
- Transiciones indirectas por la venta: `void_sale`, `revert_payment`, `register_payment` (parcial y cancelatorio), `register_sale` (alta, idempotente, y corrección de origen en sus cuatro ramas: total, reapertura de saldo, cambio de tipo, y posterior a la revisión).
- Transiciones de cálculo y de infraestructura: `recalculate` (repetido y con filtros), `set_general_rate`, `sync_review_sales`, y la **re-migración** que corre en cada `CentralRepository.__init__`.

La aserción de cada caso es **económica y no estructural**: tras aplicar la transición sobre un período ya tarifado al 1%, publico 10% con vigencia que abarca ese mismo mes, doy de alta una **venta nueva de ese mismo período** por 400.000 Gs cancelada, recalculo y exijo `rate_bp == 100` y `commission_amount == 4.000`. Es exactamente la fuga de B1-g4.

---

## 2. Matriz propia de transiciones (`matrix.py`)

Ancla: venta común 400.000 Gs cancelada en 2026-08, recalculada → `commission_rated_periods = {'2026-08': 100}`.
Sonda: `set_general_rate(1000 bp, 2026-08-01)` + venta nueva de 2026-08 + `recalculate`.

| # | Transición aplicada sobre el período tarifado | Publicar 10% | `rate_bp` venta nueva | Comisión | Veredicto |
|---|---|---|---|---|---|
| 00 | (control: sin transición posterior) | acepta v2 | 100 | 4.000 | OK |
| 01 | `review` → REVISADA | acepta | 100 | 4.000 | OK |
| 02 | `review`+`approve` → APROBADA | acepta | 100 | 4.000 | OK |
| 03 | `mark_paid` → PAGADA | acepta | 100 | 4.000 | OK |
| 04 | `observe` desde CALCULADA | acepta | 100 | 4.000 | OK |
| 05 | **`observe` sobre PAGADA** (flanco de B1-g4) | acepta | 100 | 4.000 | OK |
| 06 | `revert` desde CALCULADA | acepta | 100 | 4.000 | OK |
| 07 | `revert` vía OBSERVADA | acepta | 100 | 4.000 | OK |
| 08 | **`void_sale`** (flanco de B1-g4) | acepta | 100 | 4.000 | OK |
| 09 | `void_sale` tras PAGADA → OBSERVADA | acepta | 100 | 4.000 | OK |
| 10 | **`revert_payment`** (flanco de B1-g4, mi O2-g4) | acepta | 100 | 4.000 | OK |
| 11 | `revert_payment` tras PAGADA → OBSERVADA | acepta | 100 | 4.000 | OK |
| 12 | **Corrección de origen** (total 400.000→500.000) | acepta | 100 | 4.000 | OK |
| 13 | Corrección de origen que **reabre saldo** → REVERTIDA + PENDIENTE_SALDO | acepta | 100 | 4.000 | OK |
| 14 | Corrección de origen COMÚN→CONVENIO | acepta | 100 | 4.000 | OK |
| 15 | Corrección de origen tras REVISADA → OBSERVADA | acepta | 100 | 4.000 | OK |
| 16 | `recalculate` repetido (con y sin filtro de período) | acepta | 100 | 4.000 | OK |
| 17 | **Reapertura de la base** (re-migración + backfill) | acepta | 100 | 4.000 | OK |

**18/18.** En los 18 casos `commission_rated_periods` quedó en `{'2026-08': 100}` y `policy_for_period('2026-08')` devolvió `rate_bp=100, pinned=True`.

### 2.1 Combinaciones encadenadas adicionales (`combos.py`)

| Cadena | Resultado |
|---|---|
| `observe` → `revert` del ancla, luego publicar y vender | 100 / 4.000 — OK |
| `revert_payment` → `register_payment` **en el mismo mes** (rehace el período) | 100 / 4.000 — OK |
| `revert_payment` → corrección de origen a 700.000 sin cobro → recobro → `recalculate` → `observe` | 100 / 4.000 — OK |
| `mark_paid` → `void_sale` → reapertura de la base | 100 / 4.000 — OK |
| Ancla CONVENIO corregida a COMÚN | 100 / 4.000 — OK |
| Ingesta por `sync_review_sales` dentro del período fijado | 100 / 4.000 — OK |
| `recalculate` con filtro `branch` distinto del que fijó el período | 100 / 4.000 — OK |

No encontré ninguna ruta pública que devuelva un período tarifado al catálogo. Revisé además que **ninguna sentencia del código escribe `UPDATE` o `DELETE` sobre `commission_rated_periods`**: la única escritura es `INSERT OR IGNORE` en `recalculate` y en `_backfill_rated_periods`.

---

## 3. Cierre de los bloqueantes de la generación 4

### B1-g4 — **CERRADO**

La protección dejó de ser un predicado sobre `status` y pasó a ser una fila durable por período (`commission_rated_periods`, PK `period`), consultada por `CanonicalCommissionPolicy.pinned_for` **antes** que el catálogo dentro de `decide()`. Verifiqué las cuatro rutas que la generación 4 usó para desarmarla — `observe()` sobre PAGADA (caso 05), `void_sale()` (08), `revert()` (06/07) y la corrección de origen (12–15) — y las cuatro conservan la tasa. También el flanco que yo había rozado como observación O2-g4 y no elevé, `revert_payment` (10, 11), y su versión encadenada con recobro en el mismo mes.

Doy por cerrado el bloqueante y asumo el error de calificación de la generación 4: el flanco de `revert` era el mismo defecto por otra puerta, y correspondía elevarlo.

### B2-g4 — **CERRADO**

Escenario propio sobre **dato migrado** (`b2_and_econ.py`): liquidación con importe heredado `rate_bp=1000`, `commission_amount=40000`, `policy_status=POLITICA_HISTORICA_PREVIA`, reabierta la base para que corra la migración.

- **Importe previo distinto de cero**: `replaced = {"rate_bp": 1000, "commission_amount": 40000, "policy_status": "POLITICA_HISTORICA_PREVIA"}`.
- **Resultado cero**: la liquidación queda `rate_bp=None`, `commission_amount=None`, `policy_status=SIN_POLITICA_APLICADA`.
- **Auditable**: el asiento va en `commission_entry_history` con acción `SOURCE_UPDATED`, mismo bloque y mismo nombre que escribe `recalculate`.
- **Idempotente**: repetir la corrección idéntica no crea un segundo asiento.
- **No se inventa**: una tercera corrección, ya sin tasa previa, escribe `SOURCE_UPDATED` **sin** bloque `replaced`.
- **Rama de reapertura de saldo**: también asienta `replaced` antes de llevar la liquidación a REVERTIDA.

Confirmé además que la migración **no** siembra el período desde un importe heredado con etiqueta retirada.

---

## 4. Verificaciones exigidas por la decisión de propietario

| Criterio | Resultado |
|---|---|
| Publicar sigue siendo siempre posible | PASA — 5 publicaciones consecutivas, ninguna rechazada; la repetición idéntica devuelve `(4, False)` |
| Un período tarifado no bloquea períodos posteriores | PASA — 2026-09 → 3% (12.000), 2027-02 → 0,5% (2.000) |
| Sin `MAX(period)` global | PASA — `set_general_rate` sólo compara contra `MAX(effective_from)` |
| Una fecha lejana errónea no congela ningún período intermedio | PASA (ver O1) |
| Un período liquidado pero SIN tasa no protege nada | PASA — `commission_rated_periods` vacío, `pinned=False` |
| Corrección de origen asienta el importe retirado en datos migrados | PASA |
| El rótulo del período no declara oficial una tasa que en ese mes no rige | **FALLA → B1** |
| El export `contract_version` 3 no declara oficial una tasa que en ese mes no rige | **FALLA → B2** |
| Exactitud monetaria y HALF_UP canónico intactos | PASA — bordes `49→0, 50→1, 150→2, 250→3, 350→4, 99.950→1.000, 100.050→1.001` |

---

## 5. Bloqueantes

### B1 — La cabecera de la pantalla declara «Comisión oficial 10,00%» en un mes donde **ninguna** tasa rige

`modulos/gestion_central/comisiones_ui.py`, `_apply_policy_labels`, líneas 244-252:

```python
policy = self.service.policy_for_period(self.principal, self.report["period"])
if policy["rate_bp"] is None:
    policy = self.service.current_policy(self.principal)
percent = rate_percent_text(policy["rate_bp"])
```

Cuando el período no tiene tasa en vigor —`policy_for_period` devuelve `rate_bp=None`, `status=FUERA_DE_VIGENCIA`— la pantalla **cae de vuelta a la política global publicada** y la rotula como oficial de ese mes.

Reproducción (`ui_label.py`, panel real de Tk):

```
PERIODO 2026-07
  header : Comisión oficial 10,00% de la base · COMISION_GENERAL_1PCT v2 · vigente desde 2026-08-01 · redondeo HALF_UP a Gs. enteros
  kpi cap: COMISIÓN OFICIAL 10,00%
  kpi val: 0 | entradas: [('CALCULADA', None, None, 'FUERA_DE_VIGENCIA')]

PERIODO 2026-08
  header : Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde 2026-08-01 · fijada al tarifarse · redondeo HALF_UP a Gs. enteros
  kpi val: 4000 | entradas: [('CALCULADA', 100, 4000, 'CANONICA_APROBADA')]
```

En 2026-07 no rige el 10%, no rige el 1%, no rige nada. Aun así la cabecera y el rótulo del KPI afirman que la comisión oficial de ese mes es del 10,00%, y el «vigente desde 2026-08-01» que la acompaña la contradice en la misma línea. Es el mismo error que el propio código condena en su comentario de `policy_for_period` y es el criterio de aceptación textual de la generación 5.

Agravante: el defecto es **proporcional a la brecha**. La suite del paquete no cubre el caso: `test_the_screen_names_the_official_one_percent_policy` sólo ejercita el período por defecto.

**Remediación sugerida:** cuando `policy_for_period` devuelve `rate_bp is None`, rotular el período como sin política en vigor en la cabecera y en el KPI, en vez de sustituirlo por la global.

### B2 — El `policy_disclaimer` del export `contract_version` 3 emite «Comisión oficial None%»

`comisiones.py`, `export_summary`. `policy_for_period` devuelve `rate_percent=None` para un período fuera de vigencia y la interpolación lo imprime crudo:

```
contract= 3
policy= {'status': 'FUERA_DE_VIGENCIA', 'version': 1, 'effective_from': '2026-08-01',
         'rate_bp': None, 'rate_percent': None, 'pinned': False}
disclaimer= 'Comisión oficial None% de la base comisionable (COMISION_GENERAL_1PCT v1,
             vigente desde 2026-08-01), igual para toda vendedora y local. …'
kpi commission= 0
```

El bloque `policy` estructurado es correcto; el `policy_disclaimer` es la línea que un consumidor imprime o pega en un correo, y afirma que existe una «Comisión oficial» para un mes sin política, con el porcentaje corrompido a `None%`. La aserción del paquete sólo mira el período vigente.

**Remediación sugerida:** emitir un `policy_disclaimer` distinto cuando `policy['rate_bp'] is None`.

---

## 6. Observaciones no bloqueantes

**O1 — Una fecha errónea deja un período fijado para siempre y no hay ruta pública que lo deshaga.** Una venta cargada con `2036-08-10` fija `2036-08` al 1%. Corregí el error por la única vía pública (`revert_payment` + `register_payment` con la fecha buena): la liquidación se mueve a 2026-09 y comisiona al 5%, pero **la fila de 2036-08 permanece**, ahora sin ninguna liquidación que la respalde. No lo elevo a bloqueante porque es la consecuencia declarada de la decisión de propietario y porque el criterio que se me pidió verificar —que no congele la publicación ni ningún período intermedio— se cumple. Recomiendo que el flujo de corrección explícita priorice el caso de un período fijado que ya no tiene ninguna liquidación asociada.

**O2 — `policy_for_period` no normaliza el período.** `policy_for_period(actor, "2026-8")` devuelve la global mientras `"2026-08"` devuelve el pin; `pinned_for` compara `substr(period,1,7)` contra la cadena cruda. No mueve dinero —el cálculo usa `entry["period"]`— pero puede producir un documento rotulado con una tasa que no es la del mes.

**O3 — El backfill depende de una regla específica de SQLite y no deja asiento.** Las columnas desnudas bajo `GROUP BY` toman el valor de la fila del `MIN(created_at)`; correcto pero no portable ni evidente, y sin ninguna entrada en `central_audit`.

**O4 — `set_general_rate` no está expuesto en ninguna interfaz.** Publicar una versión que resulta inerte para los períodos fijados sólo se descubre leyendo `central_audit`. Cuando se exponga, conviene devolver `protected_periods` al llamador.

---

## 7. VEREDICTO

# FAIL

La invariante histórica está bien construida y bien cerrada. B1-g4 y B2-g4 quedan **cerrados**: 18 transiciones propias y 7 cadenas adicionales, incluidos los cuatro flancos que la desarmaban en la generación 4 y el de `revert_payment` que yo había subestimado, conservan la tasa fijada y el dinero de una venta nueva del mismo mes.

Lo que impide el PASS no es la invariante sino cómo se **rotula** su ausencia, que es precisamente uno de los dos criterios de aceptación que se me pidió comprobar. En un período donde no rige ninguna tasa, la cabecera declara oficial la tasa global publicada (**B1**) y el export emite «Comisión oficial None%» (**B2**). Ambos son el mismo error que la misión viene corrigiendo desde la generación 2 —llamar oficial a un porcentaje que ahí no rige— sobreviviendo en las dos superficies que el usuario y los consumidores externos efectivamente leen, y ninguno está cubierto por la suite. Los dos se corrigen sin tocar la invariante.
