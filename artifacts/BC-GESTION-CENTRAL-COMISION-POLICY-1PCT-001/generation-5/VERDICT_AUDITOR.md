# VERDICT — AUDITOR INDEPENDIENTE (generación 5)

| Campo | Valor |
|---|---|
| Rol | AUDITOR-IND-COMISION-POLICY-1PCT-005 |
| Misión | BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 |
| Generación | 5 |
| Snapshot auditado | `2ac9f5c93ec99ed506133310ee6cd19f6779b971` (verificado con `git rev-parse HEAD`) |
| Árbol al empezar / al terminar | limpio / limpio (`git status --porcelain` vacío en ambos momentos) |
| Archivos del repositorio modificados | ninguno; todas las pruebas viven en `…\scratchpad\aud-gen5` |
| Independencia | trabajo solo; no leí ni busqué los verdicts de Librarian ni de QA de esta generación |
| Timestamp UTC | **2026-08-18T02:38:49+00:00** |
| **VEREDICTO** | **FAIL — 2 bloqueantes** |

---

## 1. Alcance y método

Se auditó el código, no el paquete: `modulos/gestion_central/comisiones.py`, `comision_policy.py` y `repository.py`, contrastados contra las afirmaciones de `ARCHITECTURE_DELTA.md`, `COMMISSION_POLICY_1PCT.md`, `MIGRATION.md` y `HANDOFF.md`.

Pruebas propias escritas para esta auditoría (todas en `…\scratchpad\aud-gen5`):

| Script | Qué hace |
|---|---|
| `harness.py` | arranque de repositorio/servicio sobre base temporal, acceso SQL directo |
| `t01_base.py` | camino feliz + fuga exacta de la generación 3 (misma vigencia, otra tasa, al alza y a cero) |
| `t02_fuzz.py` | fuzz aleatorio de 12 operaciones públicas, 90 pasos, invariantes de tasa/pin, aritmética y libro |
| `t03_hist.py` | mismo fuzz + invariante histórica reconstruida desde `commission_entry_history` (un período nunca visto con dos tasas), 120 pasos, semillas 100–129 |
| `t04_mig.py` | piloto real construido con el **código de la generación 4** (`git show a7ea6a4:…`) y migrado después a la generación 5 |
| `t05_typo.py` | error de tipeo de fecha sobre base fresca, corregido en el origen y anulado |
| `t06_inv.py` | batería de los invariantes declarados, ambas rutas de `replaced`, aritmética Decimal / HALF_UP |
| `t07_misc.py` | auditoría de `protected_periods`, export y disclaimer |
| `t08_conc.py` | concurrencia real de 6 hilos entre `set_general_rate`, `recalculate` y `mark_paid` |
| `t09_seed_min.py` | repro mínimo y determinista de la siembra de la migración |
| `t10_heredados.py` | reglas económicas heredadas (convenio, saldo, anulación, libro append-only) |
| `t11_b1g4.py` | matriz de 10 transiciones desde un período tarifado (cierre de B1-g4) |
| `t12_aprob.py` | impacto de la siembra sobre una liquidación ya aprobada |

---

## 2. Cierre de los bloqueantes de la generación 4

### B1-g4 — la guarda de período liquidado se desarmaba con `observe` / `void_sale` / `revert` / corrección de origen

**CERRADO en bases frescas.** Reproduje la fuga exacta que reporté: sobre un período tarifado al 1 % se publica la misma vigencia con 100 % y luego con 0 %, después de aplicar cada transición que antes desarmaba la marca. `t11_b1g4.py`:

```
  sin transicion                     venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  observe                            venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  revert                             venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  observe+revert                     venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  void_sale                          venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  correccion de origen               venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  correccion reabre saldo            venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  review+approve+pay                 venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  pagada + observe                   venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
  pagada + void_sale                 venta nueva de 2026-08 -> 100bp / 400000 Gs  OK
```

Ni los 400.000 Gs donde el 1 % eran 40.000, ni el mes anulado a cero. Además `t01_base.py` confirma que la liquidación ya pagada conserva su importe tras publicar 10 % y 0 % sobre su propia vigencia, y `t03_hist.py` no encontró en 30 semillas × 120 pasos ni un solo período con dos tasas distintas en su historial. El cambio de estrategia —evidencia durable en vez de predicado sobre el estado— es correcto y resiste todo lo que rompí en la generación 4.

**Retirar la guarda por estado no reabrió ninguna fuga de las generaciones 1 a 4** sobre bases frescas. Lo que sí abrió es una superficie nueva, que es el objeto de los bloqueantes de abajo: la evidencia se puede **fijar mal**, y una evidencia mal fijada es peor que una guarda floja, porque es irreversible.

### B2-g4 — `_apply_source_update` anulaba un importe heredado sin asiento

**CERRADO.** Las dos rutas que anulan importes escriben el mismo bloque `replaced`, con el mismo nombre y los mismos tres campos. `t06_inv.py`:

```
  recalculate replaced:    [{'commission_amount': 25000, 'policy_status': 'CANONICA_APROBADA', 'rate_bp': 250}]
  source_update replaced:  [{'commission_amount': 10000, 'policy_status': 'CANONICA_APROBADA', 'rate_bp': 100}]
```

La rama sin salida —período anterior a la vigencia, `FUERA_DE_VIGENCIA` sin porcentaje— deja el importe retirado en el asiento, y como `recalculate` es idempotente (`changed == 0` en la segunda pasada) el asiento no se repite. `t12_aprob.py` confirma que incluso la rebaja de una `APROBADA` de 500.000 a 100.000 Gs deja su `replaced`. **Ningún importe puede desaparecer sin asiento por ninguna de las dos rutas.**

---

## 3. Tabla de invariantes

Dos columnas porque el resultado difiere según el origen de la base: es exactamente ahí donde está el daño.

| # | Invariante | Base fresca | Base migrada desde gen ≤ 4 | Evidencia |
|---|---|---|---|---|
| 1 | Un solo porcentaje general tras migrar (`GENERAL`, sin alcance por vendedora ni local, retiro auditado con su valor previo) | **PASA** | **PASA** | `t06_inv.py` — quedan sólo `GENERAL/''`, con dos filas `COMMISSION_POLICY_RETIRED` que conservan `rate_bp` 900 y 700 |
| 2 | Traza de política inseparable del importe: completa o vacía, nunca a medias | **PASA** | **PASA** | `t06_inv.py` — los cinco campos viajan juntos con el importe |
| 3 | Idempotencia de `recalculate` incluyendo los cinco campos de política | **PASA** | **PASA** | `t06_inv.py` — `{'evaluated': 1, 'changed': 0}` en la 2.ª y 3.ª pasada |
| 4 | Ninguna liquidación sin porcentaje oficial alcanza el pago | **PASA** | **PASA** (rechaza, pero por la razón equivocada — ver B-1) | `t06_inv.py`, `t12_aprob.py` |
| 5 | Un cambio de política no mueve dinero ya liquidado | **PASA** | **FALLA** | `t12_aprob.py` — la migración baja una `APROBADA` de **500.000 → 100.000 Gs** y le borra el aval |
| 6 | Un período ya tarifado conserva su tasa, con protección durable e independiente del estado | **PASA** | **FALLA en el fondo**: el período conserva una tasa, pero **no la que se le aplicó** | `t11_b1g4.py` vs. `t04_mig.py` / `t09_seed_min.py` |
| 7 | Resolución por período, no por «última publicada»; nada de `MAX(period)` global | **PASA** | **PASA** | `t06_inv.py` — 2026-08 → 100 bp, 2026-09 → 300 bp; verificado además que no existe `MAX(period)` en el código |
| 8 | Todo importe retirado queda asentado, por las dos rutas | **PASA** | **PASA** | `t06_inv.py`, `t12_aprob.py` |
| 9 | La comisión oficial no se mezcla con la no oficial en ningún agregado | **PASA** | **PASA** | `t07_misc.py`, `t10_heredados.py` |
| 10 | Reglas económicas heredadas: convenio finaliza y descuenta 5 % antes de la base, convenio sin saldo cliente, sólo la venta cancelada comisiona, venta anulada no comisiona, `paid_amount` = libro append-only | **PASA** | **PASA** | `t10_heredados.py` — descuento 50.000 / base 950.000; cobro y convenio parcial rechazados; anulada sale del KPI; `paid_amount == Σ libro` en todas las ventas |

### Aritmética

Sin regresión. `grep` sobre `comision_policy.py` + `comisiones.py` devuelve **tres apariciones de `ROUND_HALF_UP` y cero de `float(` o `round(`**. `apply_basis_points` sigue con `prec = 60` y un único `quantize` final:

```
   50x1%            -> 1              OK      (medio hacia arriba)
   150x1%           -> 2              OK
   49x1%            -> 0              OK
   1234567x1%       -> 12346          OK
   0x1% / 1x1%      -> 0 / 0          OK
   2500000000000x1% -> 25000000000    OK      (sin pérdida en magnitud grande)
```

**La aritmética Decimal y el único HALF_UP no cambiaron.**

### Concurrencia

`t08_conc.py`, 6 hilos × 20 iteraciones cruzando `set_general_rate`, `recalculate` y `mark_paid` sobre 30 liquidaciones: **51 errores, todos `ValueError` de dominio** (vigencia que retrocede, transición inválida). Ni un `OperationalError`, ni un `database is locked`, ni una liquidación pagada con tasa distinta del pin. Las tres operaciones serializan bien por `BEGIN IMMEDIATE`.

---

## 4. Bloqueantes

### BLOQUEANTE 1 — la siembra de la migración fija el período con la tasa de la liquidación **más antigua**, aunque esté anulada y aunque contradiga el dinero ya pagado ese mes; es silenciosa e irreversible

**Dónde.** `modulos/gestion_central/repository.py`, `_backfill_rated_periods` (líneas 280-312):

```sql
SELECT period, rate_bp, ... , MIN(created_at), 'BACKFILL'
  FROM commission_entries
 WHERE period IS NOT NULL AND rate_bp IS NOT NULL AND policy_status=?
 GROUP BY period
```

`rate_bp` es una columna desnuda bajo `GROUP BY` con **un único agregado `MIN()`**: SQLite la toma de la fila con el `created_at` más antiguo. La elección de qué tasa fija a un período —una decisión de dinero, definitiva— la resuelve el orden de creación, sin mirar el estado de la liquidación, sin mirar si esa tasa sigue siendo la oficial del período, y sin mirar a qué tasa se pagó realmente ese mes. El filtro `policy_status = CANONICA_APROBADA` sólo descarta la etiqueta del piloto retirado; **no** distingue una tasa canónica vigente de una canónica superada.

**Por qué importa ahora.** Una base con dos tasas canónicas en un mismo período es exactamente el estado que produce B1-g4, es decir el estado en el que están las bases que esta generación viene a arreglar. La migración es el único camino de esas bases hacia la generación 5.

**Reproducción — `t04_mig.py`.** El piloto se construye con el **código real de la generación 4** (`git show a7ea6a4:modulos/gestion_central/*`) y luego se abre la misma base con el código de la generación 5:

```
== GEN 4 pilot ==
A1 entry: 2026-09 100 100000 CALCULADA
A1 tras anular: [{'status': 'REVERTIDA', 'rate_bp': 100, 'period': '2026-09', ...}]
publish 5% eff 2026-09-01: (3, True)
A2 PAGADA: 500 500000
A3 PAGADA: 500 500000
tabla rated_periods existe en gen4?: []

== GEN 5 tras migrar la misma base ==
SIEMBRA commission_rated_periods: [{'period': '2026-09', 'rate_bp': 100, 'policy_version': 2,
                                    'first_rated_by': 'MIGRACION', 'origin': 'BACKFILL'}]
policy_for_period 2026-09: {... 'rate_bp': 100, 'rate_percent': '1.00', 'pinned': True}
venta nueva de 2026-09 cobra: 100 bp -> 100000 Gs (las pagadas del mes cobraron 500 bp -> 500000 Gs)
politica vigente publicada: {... 'version': 3, 'rate_bp': 500, 'rate_percent': '5.00'}
```

El período 2026-09 queda fijado al **1 %** tomado de una liquidación de una **venta anulada** (`voided=1`, entrada `REVERTIDA`), mientras el mes se pagó dos veces al **5 %** oficial. Una venta nueva de ese mes cobra **100.000 Gs donde le corresponden 500.000 Gs**, y se paga:

```
  la nueva liquidación es pagable? SÍ, pagada por 100000 Gs
```

**No hay corrección posible por ninguna ruta pública.** Publicar de nuevo es idempotente o inocuo, porque `decide()` consulta el pin antes que el catálogo:

```
  publicar 600bp  eff 2026-09-01 -> version 4; la venta nueva sigue en 100 bp / 100000 Gs
  publicar 900bp  eff 2026-09-01 -> version 5; la venta nueva sigue en 100 bp / 100000 Gs
  publicar 10000bp eff 2026-09-01 -> version 6; la venta nueva sigue en 100 bp / 100000 Gs
  publicar 0bp    eff 2026-09-01 -> version 7; la venta nueva sigue en 100 bp / 100000 Gs
  pin final: [{'period': '2026-09', 'rate_bp': 100, 'origin': 'BACKFILL'}]
```

**El daño alcanza dinero ya avalado.** `t12_aprob.py`, sobre la misma forma de base, con una `APROBADA` legítima al 5 %:

```
pin: [{'period': '2026-09', 'rate_bp': 100}]
mark_paid de la APROBADA al 5%: la política del período cambió desde el cálculo (v3 → v2): recalcule antes de continuar
recalculate: {'evaluated': 1, 'changed': 1}
e2 ahora: [{'status': 'CALCULADA', 'rate_bp': 100, 'commission_amount': 100000, 'approved_by': None}]
asiento replaced: [{'commission_amount': 500000, 'policy_status': 'CANONICA_APROBADA', 'rate_bp': 500}]
```

La migración —no una publicación, no una operación del usuario— **baja una comisión aprobada de 500.000 a 100.000 Gs y le borra la aprobación**. Eso es literalmente el invariante 5 de la misión («un cambio de política no mueve dinero ya liquidado») roto por el propio paso de migración, y el asiento `replaced` sólo documenta la pérdida: no la evita ni la revierte.

**Es silenciosa.** `t09_seed_min.py`, repro mínimo y determinista sobre una base construida con SQL plano:

```
pin sembrado: [{'period': '2026-09', 'rate_bp': 100, 'policy_version': 2, 'origin': 'BACKFILL'}]
pagado realmente en 2026-09: 500 bp / 500000 Gs (entrada e2)
filas de auditoria nuevas por la siembra: 0
```

**Cero filas de auditoría.** `_migrate_commission_policy` audita cada retiro de política «así nada desaparece en silencio»; la siembra, que fija dinero para siempre, no audita nada.

**Afirmación falsa del paquete.** `MIGRATION.md` línea 89 y `ARCHITECTURE_DELTA.md` línea 52 sostienen: *«un importe heredado no oficial no fija nada, porque fijarlo lo volvería incorregible»*. Es falso en el sentido que importa. La comprobación implementada mira la **etiqueta** `POLITICA_HISTORICA_PREVIA`, no si la tasa sigue siendo la oficial del período; una tasa canónica **superada**, tomada además de una liquidación anulada, sí fija, y sí lo vuelve incorregible. Es la condición que el propietario declaró explícitamente como inaceptable para esta generación.

**Qué haría falta, como mínimo:** que la siembra sólo fije un período cuando todas sus liquidaciones canónicas con tasa coinciden en la misma tasa; que ante discrepancia no fije nada y lo asiente en `central_audit` para resolución explícita; que ignore las liquidaciones `REVERTIDA` y las de ventas con `voided=1`; que prefiera la tasa a la que se pagó (`paid_at IS NOT NULL`) sobre cualquier otra; y que la siembra deje asiento de auditoría fila por fila.

---

### BLOQUEANTE 2 — un error de carga de fecha fija para siempre la tasa de un mes lejano, incluso después de que el propio sistema registre que fue un error

**Dónde.** `modulos/gestion_central/comisiones.py`, `recalculate`, líneas 921-929: el `INSERT OR IGNORE` en `commission_rated_periods` se dispara con el primer recálculo de cualquier liquidación con período y decisión canónica, sin ninguna condición sobre si esa liquidación llegará a producir dinero. Y `CanonicalCommissionPolicy.decide()` consulta ese pin antes que el catálogo, sin ruta de corrección.

**Reproducción — `t05_typo.py`, base fresca de la generación 5, sólo API pública, sin migración:**

```
entry errónea: 2036-08 100 100000
pin sembrado por el error: [{'period': '2036-08', 'rate_bp': 100, 'origin': 'RATED', 'first_rated_by': 'admin'}]
tras corregir y anular, pin: [{'period': '2036-08', 'rate_bp': 100, 'origin': 'RATED'}]
publicar 5% eff 2027-01-01: (2, True)
venta real de 2036-08 cobra: 100 bp -> 100000 Gs; oficial publicada = 500 bp -> 500000 Gs
policy_for_period 2036-08: {... 'rate_bp': 100, 'rate_percent': '1.00', 'pinned': True}
policy_for_period 2035-12: {... 'rate_bp': 500, 'rate_percent': '5.00', 'pinned': False}
PAGADA por: 100000
```

Un operador tipea `2036-08-04` en vez de `2026-08-04`. El recálculo fija 2036-08 al 1 %. **Después el sistema reconoce el error por dos vías propias**: una corrección de origen mueve la venta a `2026-08-04` y la venta se anula (`void_sale`). El pin sobrevive a ambas. Nueve años más tarde, con el 5 % publicado y vigente desde 2027-01, una venta real de agosto de 2036 cobra **100.000 Gs en vez de 500.000 Gs** y se paga — mientras el mes inmediatamente anterior, 2035-12, cobra el 5 % correcto. No existe ruta pública que corrija 2036-08.

**Por qué es bloqueante y no una consecuencia aceptada.** La evidencia durable se justifica como «proteger un período al que ya se le aplicó una tasa», y el propietario aceptó que corregir un período **tarifado** exija un flujo aparte. Pero aquí no hay nada que proteger: en 2036-08 nunca hubo un hecho económico. El sistema mismo asentó que la venta pertenecía a otro mes y que además fue anulada, y aun así ese mes queda tarifado por un tipeo. La protección no está resguardando dinero: está inmovilizando un mes al azar. Además el paquete presenta este caso concreto —el «`2036` en lugar de un `2026`»— como **resuelto** (`comisiones.py` líneas 795-800, `COMMISSION_POLICY_1PCT.md` línea 94, `ARCHITECTURE_DELTA.md` invariante 5: *«una fecha errónea protege su propio mes y no congela ningún otro»*). Es cierto que ya no congela la publicación; lo que no se dice es que ahora ese mes **paga mal, en silencio y sin retorno**. La generación 4 convertía la fecha errónea en un bloqueo visible y reversible; la 5 la convierte en una liquidación equivocada e irreversible. Para el dinero, eso es un retroceso.

**Mitigación parcial que reconozco.** Toda publicación posterior asienta la lista de períodos que quedan fuera de su alcance (`t07_misc.py`):

```
COMISION_GENERAL_1PCT:v2 {"effective_from": "2027-01-01", "protected_periods": ["2036-08"],
                          "protected_periods_count": 1, "rate_bp": 500}
```

El operador **puede** enterarse, si lee `central_audit`. Pero `set_general_rate` devuelve `(2, True)` —éxito liso— y ni el valor de retorno ni la interfaz señalan que la publicación no rige para ese mes. Un asiento en una tabla de auditoría no es un control sobre dinero que se va a pagar mal.

**Qué haría falta, como mínimo:** no fijar el período desde una liquidación de venta anulada ni desde una cuyo período fue después corregido; o exigir que el pin lo confirme un hecho económico real (liquidación revisada/aprobada/pagada); o —de mantenerse el fijado en el primer recálculo— entregar el flujo de corrección explícita y auditada que la propia documentación admite que hoy no existe, porque sin él la primera equivocación de cada mes es definitiva.

---

## 5. Observaciones no bloqueantes

1. **`export_summary` imprime «Comisión oficial None%»** para un período anterior a la vigencia. `t07_misc.py`: `"Comisión oficial None% de la base comisionable (COMISION_GENERAL_1PCT v1, vigente desde 2026-08-01)…"`. El bloque `policy` es correcto (`FUERA_DE_VIGENCIA`, `rate_bp: None`); es el texto del disclaimer el que no contempla el caso sin tasa. Sale en un artefacto que se entrega.

2. **La siembra de la migración no deja auditoría.** Cero filas en `central_audit` (`t09_seed_min.py`), a diferencia de todos los demás pasos de migración. Aunque se corrija el bloqueante 1, la siembra debería asentar qué períodos fijó y con qué tasa.

3. **La regla de selección de fila de la siembra es un detalle de SQLite que nadie documenta.** `rate_bp` es columna desnuda bajo `GROUP BY` y su valor sale de la fila del `MIN(created_at)` por la regla especial de SQLite para un único agregado `min()`/`max()`. Es determinista, pero es una decisión de dinero apoyada en una particularidad del motor, sin `ORDER BY` explícito ni comentario que lo diga.

4. **Un período anterior a la vigencia más antigua publicada no puede comisionar nunca.** `set_general_rate` prohíbe que la vigencia retroceda, así que ningún mes previo a `2026-08-01` es alcanzable. Es coherente con el diseño heredado y no es una regresión de esta generación, pero conviene que quede dicho: no es una situación con salida.

5. **`decide()` lee el pin por una conexión propia, fuera de la transacción del llamador.** `pinned_for` abre `self.repository.connection()` mientras `recalculate` mantiene su `BEGIN IMMEDIATE`, de modo que nunca ve los pines escritos antes en esa misma transacción. Hoy es inocuo —todas las entradas de un mismo período resuelven el mismo valor del catálogo dentro de una corrida— pero es un acoplamiento no documentado que dejaría de ser inocuo si `decide()` pasara a depender de más estado escrito en la corrida.

6. **`register_payment` y `sync_review_sales` siguen sin llamador productivo**, tal como ya registraba el handoff. No lo reevalué; lo dejo anotado porque las rutas que más manipulan períodos cuelgan de ahí.

---

## 6. Veredicto

Lo que la generación 5 se propuso está bien elegido y, sobre bases frescas, bien ejecutado: la evidencia durable por período cierra B1-g4 en las diez transiciones que probé, cierra B2-g4 en las dos rutas que anulan importes, no usa `MAX(period)` global, no congela la programación hacia adelante, mantiene la aritmética `Decimal` con un único `HALF_UP` y aguanta la concurrencia entre `set_general_rate`, `recalculate` y `mark_paid`. Ocho de los diez invariantes pasan en todo escenario.

Pero el mecanismo cambió la naturaleza del riesgo sin cubrir el momento en que se crea la evidencia. Un pin es definitivo: si se graba mal, no hay ruta pública que lo enmiende, y el error deja de ser un bloqueo visible para volverse un pago equivocado silencioso. Encontré dos formas de grabarlo mal, ambas reproducibles y ambas con dinero mal pagado: la migración fija un mes con la tasa de la liquidación más antigua aunque esté anulada y aunque contradiga lo ya pagado y aprobado ese mes —bajando una comisión aprobada de 500.000 a 100.000 Gs sin una sola fila de auditoría—, y en base fresca un simple error de tipeo de fecha fija para siempre un mes lejano, incluso después de que el propio sistema registre por dos vías que fue un error.

Es la quinta generación consecutiva en que la fuga aparece en el mismo sitio conceptual: la afirmación de que un importe es oficial se apoya en algo que no verifica que lo sea. Antes era la etiqueta; ahora es la primera fila escrita.

**VEREDICTO: FAIL.** Bloqueantes 1 y 2 abiertos.
