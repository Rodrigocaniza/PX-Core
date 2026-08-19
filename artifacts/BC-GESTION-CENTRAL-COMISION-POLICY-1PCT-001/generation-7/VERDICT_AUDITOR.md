# Verdict — Auditor, generación 7
Runner: AUDITOR-IND-COMISION-POLICY-1PCT-007
Snapshot: 41131a6a111be6e33ad1d47497bf22b128faf6e3
Veredicto: FAIL

## Ataques ejecutados

Todo el trabajo se hizo con scripts propios en `…\scratchpad\aud7`, sobre bases sqlite temporales, importando el módulo con `sys.path.insert` al worktree. No modifiqué ningún archivo del repositorio ni hice ningún commit: `git status --porcelain` sólo muestra los tres `PROMPT_*.txt` que el orquestador reescribió antes de arrancar.

Regresión completa del repositorio: `python -m pytest -q` → **418 passed in 49.74s** (corrida dos veces, antes y después de todos los ataques).

**1. Arnés reescrito contra hechos VIVOS, en las dos direcciones (`common.py::check_symmetry`).** El invariante que valida ahora es exactamente el que la generación 6 no podía expresar: para cada período, `fijado ⟺ existe al menos una APROBADA/PAGADA sobre venta no anulada, o un paid_at`. Comprueba las dos direcciones —`PINNED_SIN_HECHO_VIVO` y `HECHO_VIVO_SIN_PIN`— y añade una tercera condición que la 6 tampoco tenía: `PIN_INCOHERENTE_CON_HECHOS_VIVOS`, que la tasa del último evento sea una de las que efectivamente llevan los hechos vivos. Esa tercera condición es la que destapó el bloqueante.

**2. Reproducción de `AB1-g6` y sus cuatro rutas sobre base fresca (`t01_ab1g6.py`).** Cerradas. Detalle en la sección siguiente.

**3. La `PAGADA` viva jamás suelta (`t02_pagada.py`), once rutas y órdenes.** Sobre un período fijado al 100 % por una liquidación **pagada**: `observe`, `void_sale`, `revert_payment`, `observe+revert`, `void+observe`, `observe+void`, `revpay+observe`, `revpay+void`, `recalculate`, `publish+recalculate` y `revert`. **Las once dejan el pin en `PINNED@10000`**, el importe en 10.000.000 Gs, `paid_at` y `payment_reference` intactos, y el arnés no reporta nada. `revert` sobre la pagada se rechaza (`transición inválida: PAGADA → REVERTIDA`) y `revert` tras `observe` se rechaza por `_reject_paid`. El dinero que salió nunca suelta su mes.

**4. Regresión B1/B1-g3/B1-g4 (`t12_b1.py`).** Sobre un período sostenido por dinero pagado publiqué 100 %, 0 % y 2,5 % tras ocho transiciones distintas (sin transición, `observe`, `void_sale`, `revert_payment`, `observe+void`, `recalculate` ×3, corrección de origen, reapertura de la base). **Las ocho devuelven 100 bp y `pinned=True`.** Retirar la fijación no reabrió ninguna fuga de las generaciones 1 a 5.

**5. Secuencias largas fijar/soltar/refijar con tasa distinta en cada ciclo (`t07_long.py`).** Ocho ciclos completos con tasas `100, 900, 0, 2500, 10000, 350, 100, 5000`. Los 16 eventos alternan `PINNED`/`UNPINNED` sin excepción, los `id` son estrictamente crecientes, la auditoría deja 8 `COMMISSION_PERIOD_RATE_PINNED` y 8 `COMMISSION_PERIOD_RATE_UNPINNED`, y **en cada ciclo el snapshot completo de `commission_entries` —tasa, importe, base, bruto, descuento, `reviewed_by`, `approved_by`, `paid_at`, `payment_reference`— es byte a byte idéntico antes y después de soltar**. Soltar no altera ningún importe ni aval.

**6. El libro como fuente de verdad.** `grep` sobre `modulos/`: **dos `INSERT` y cero `UPDATE` y cero `DELETE`** sobre `commission_period_rate_events` (`comisiones.py:766`, `repository.py:388`). El fuzz verifica además, después de **cada paso**, que el prefijo del libro leído en el paso anterior sigue siendo idéntico (ningún evento se reescribe) y que un período nunca encadena dos eventos iguales consecutivos.

**7. Concurrencia real (`t06_conc.py`, `t08_danger.py`), con `threading.Barrier`, 480 rondas y 1.080 operaciones concurrentes:**

| Escenario | Rondas | Resultado |
|---|---|---|
| A — `revert` (soltar) ‖ `approve` (fijar), mismo período | 30 | 60 ok, 0 estados malos |
| B — `void_sale` ‖ `mark_paid` | 30 | 39 ok / 21 `ValueError`, 0 |
| C — dos reversiones simultáneas del **mismo** período | 30 | 60 ok, 0 |
| D — `revert` ‖ `set_general_rate` | 30 | 60 ok, 0 |
| E — `revert` ‖ `recalculate` | 30 | 60 ok, 0 |
| F — `revert_payment` ‖ `approve` | 30 | 36 ok / 24 `ValueError`, 0 |
| G — `revert` ‖ `void_sale`, mismo período | 30 | 60 ok, 0 |
| H — `approve` ‖ `set_general_rate` (publicar) | 30 | 39 ok / 21 `ValueError`, 0 |
| I — 4 hilos: `revert` ‖ `approve` ‖ `void_sale` ‖ `recalculate` | 30 | 120 ok, 0 |
| J — `observe` de una pagada ‖ `void_sale` | 30 | 46 ok / 14 `ValueError`, 0 |
| `void_sale` ‖ `mark_paid` (estados peligrosos) | 60 | 0 peligrosos |
| `void_sale` ‖ `approve` | 60 | 0 peligrosos |
| `revert_payment` ‖ `mark_paid` | 60 | 0 peligrosos |

Ni un `OperationalError`, ni un `database is locked`, ni un pin duplicado, ni una `APROBADA`/`PAGADA` sobre venta anulada, ni una `PAGADA` con saldo abierto. `BEGIN IMMEDIATE` serializa correctamente soltar contra fijar.

**8. Fuzz encadenado con el invariante nuevo.** Dos arneses, 140 corridas:
- `t05_fuzz.py`: 13 operaciones públicas (`register_sale`, corrección de origen, `register_payment`, `revert_payment`, `recalculate`, `set_general_rate`, `review`, `approve`, `mark_paid`, `observe`, `revert`, `void_sale`, reapertura de la base), períodos `2026-08…2027-01`, importes `{3, 50, 100000, 400000, 999999, 1234567, 7777777, 10000000}`, tasas `{0, 100, 250, 500, 900, 2000, 10000}`, ambos tipos de venta. **Semillas 0–79 × 250 pasos = 20.000 pasos, 0 fallos.** Invariantes por paso: simetría en las dos direcciones, coherencia del pin con las tasas vivas, alternancia del libro, inmutabilidad del prefijo del libro, aritmética `commission_for(base, rate)` exacta en toda fila, y que ninguna `APROBADA`/`PAGADA` canónica viva cobre distinto del pin de su período.
- `t09_fuzz2.py`: mismo invariante, sesgado a churn de fijar/soltar y con invariantes estructurales añadidos (una sola liquidación no `REVERTIDA` por venta, ninguna `REVERTIDA` con `paid_at`, `paid_amount == Σ` del libro append-only). **Semillas 0–59 × 200 pasos = 12.000 pasos, 0 fallos.**

**Declaro el límite de mi propio fuzz, igual que hizo el auditor anterior con el suyo: las 140 corridas arrancan de bases frescas, donde toda liquidación nace con política canónica, y por eso no podían encontrar `AB1-g7`.** Lo encontré leyendo el SQL de los dos predicados de vitalidad uno junto al otro. Cuando reescribí el arnés para que la base arranque **migrada desde un piloto con una comisión ya pagada** (`t16_fuzz3.py`), el invariante se viola en **25 de 25 corridas, en el paso 0**: la base migrada nace ya en violación.

**9. La migración, con bases legadas construidas a mano por SQL plano (`t03_mig.py`), diez formas distintas:**

| Base legada | Resultado |
|---|---|
| sólo `REVERTIDA` @100 | no siembra; `SEED_SKIPPED` |
| `APROBADA` @100 con venta `voided=1` | no siembra; `SEED_SKIPPED` |
| `PAGADA` @500 con venta `voided=1` | siembra 500 (el dinero salió); `SEED_SEEDED` |
| sólo provisional (`CALCULADA`) | no inventa tasa; ningún pin |
| discrepante `APROBADA`@100 + `PAGADA`@500 | no desempata; `SEED_SKIPPED` con `EVIDENCIA_DISCREPANTE` |
| coincidente `APROBADA`@500 + `PAGADA`@500 | siembra 500, `boundary=PAGADA` |
| `OBSERVADA` con `paid_at` @700 | siembra 700 |
| `APROBADA` con política legada @300 | **no siembra** — y es la mitad del bloqueante |
| legada @300 + canónica @100 | siembra 100 — la otra mitad |
| etiqueta retirada `SINTETICA_PENDIENTE_APROBACION` | relabelada, no siembra |

**No escribe un solo `UNPINNED`** en ninguna de las diez formas. **La siembra no toca `commission_entries`**: SHA-256 de la tabla completa idéntico tras **cinco** reaperturas de una base con una `PAGADA` y una `CALCULADA`. **Es idempotente**: cuatro reaperturas dejan exactamente 1 fila `SEED_SEEDED` o 1 `SEED_SKIPPED` y el mismo número de eventos. **Migrar y operar coinciden** en el caso limpio (`t11_inv.py`: una `PAGADA` canónica @500 da `PINNED@500` por las dos vías) y **divergen** en cuanto la política de la evidencia no es canónica, que es el bloqueante.

**10. Invariantes declarados del paquete verificados contra el código (`t11_inv.py`).** I1 (una sola fila `GENERAL` tras migrar, alcances `VENDEDORA`@900 y `LOCAL`@700 retirados con su `rate_bp` previo en `COMMISSION_POLICY_RETIRED`): cierto. I12 (la siembra no escribe `commission_entries`, no escribe `UNPINNED`): cierto. I13 (asientos idempotentes): cierto. **I14 (una venta anulada no llega al pago), que era la observación no bloqueante 1 de la generación 6: CERRADA** — sobre una base legada con la venta `voided=1`, `review` y `mark_paid` responden `la venta de origen está anulada: no genera comisión`. **I11 (migrar y operar dan el mismo resultado): FALSA**, y es el bloqueante.

**11. Aritmética y estructura.** `git diff 71c4893 HEAD -- comision_policy.py`: el único cambio desde la generación 3 son las dos constantes nuevas `RATING_BOUNDARY_STATES` y `BOUNDARY_SQL_IN` y sus comentarios; **ni una línea de aritmética cambió** pese a que el módulo ahora aloja el boundary compartido. Tabla verificada idéntica a la de la generación 6: `50×1%→1`, `150×1%→2`, `49×1%→0`, `1×1%→0`, `1234567×1%→12346`, `999999×5%→50000`, `2500000000000×1%→25000000000`, `1×100%→1`; `commissionable_base('CONVENIO', 1000000)→950000`. Cero `float(` y cero `round(` en `comision_policy.py` y en `comisiones.py`; el único `ROUND_HALF_UP` sigue en `quantize_guarani` con `prec = 60`. El diff de `comisiones_ui.py` es un cambio de rótulo, sin aritmética.

## Reproducción de AB1-g6

**Las cuatro rutas están CERRADAS sobre base fresca** (`t01_ab1g6.py`, escenario exacto de la generación 6: publicar 100 % con un cero de más, aprobar una venta de 10.000.000 Gs, retirar el hecho, corregir al 1 %, y pagar tres ventas reales del mes).

| Ruta que retira el hecho económico | Estado final | Vivos | Último evento | 3 ventas reales pagan | Sobrepago |
|---|---|---|---|---|---|
| `revert` de la aprobación | `REVERTIDA` | 0 | `UNPINNED@10000` origen `COMMISSION_REVERTED` | 300.000 Gs | **0 Gs** |
| `void_sale` | `REVERTIDA` | 0 | `UNPINNED@10000` origen `SALE_VOIDED` | 300.000 Gs | **0 Gs** |
| `revert_payment` (cheque rechazado) | `PENDIENTE_SALDO` | 0 | `UNPINNED@10000` origen `PAYMENT_REVERTED` | 300.000 Gs | **0 Gs** |
| `observe` + `revert` | `REVERTIDA` | 0 | `UNPINNED@10000` origen `COMMISSION_OBSERVED` | 300.000 Gs | **0 Gs** |

En las cuatro, `policy_for_period('2026-09')` devuelve `rate_bp=100, pinned=False` tras la corrección, y el libro queda con la secuencia completa `PINNED@10000 → UNPINNED@10000 → PINNED@100`: el rastro de que el mes estuvo fijado al 100 % no desaparece, y la tasa vuelve a resolverse por catálogo. **Los 29.700.000 Gs de sobrepago que medía la generación 6 desaparecen.** El arreglo del boundary de salida es correcto y está bien puesto: en el choke point de `_set_status`, no ruta por ruta.

Lo que no está cerrado es que ese boundary de salida **puede quedar permanentemente inhibido**, y entonces las mismas cuatro rutas vuelven a pagar mal con la misma cifra. Es `AB1-g7`.

## Bloqueantes

### AB1-g7 — la migración y el código en caliente siguen usando dos predicados distintos de «hecho vivo»: una comisión ya pagada del piloto bloquea el boundary de salida para siempre y `AB1-g6` reaparece completo

**Dónde.** Son dos SQL que la generación 7 declara idénticos y no lo son.

- `comisiones.py:746-751`, `_live_official_facts` — el predicado del boundary de **salida**:
  ```sql
  WHERE e.period=? AND (e.paid_at IS NOT NULL
        OR (e.status IN ('APROBADA','PAGADA') AND COALESCE(s.voided,0)=0))
  ```
- `repository.py:340-348`, `_backfill_period_rate_events` — el predicado de la **siembra**:
  ```sql
  WHERE e.period IS NOT NULL AND e.rate_bp IS NOT NULL AND e.policy_status=?   -- 'CANONICA_APROBADA'
    AND (e.paid_at IS NOT NULL
        OR (e.status IN ('APROBADA','PAGADA') AND COALESCE(s.voided,0)=0))
  ```

El segundo lleva `AND e.policy_status = 'CANONICA_APROBADA'`; el primero no. `BOUNDARY_SQL_IN` unificó la lista de estados, que era la parte que ya coincidía, y dejó divergente la parte que decide. El docstring de `_live_official_facts` (líneas 742-743) afirma: *«La migración usa esta misma definición, en SQL equivalente, para que migrar una base y reconstruirla operando den el mismo resultado»*. **Es falso contra el código**, y el invariante 11 de `ARCHITECTURE_DELTA.md` («Migrar y operar dan el mismo resultado… En la generación 6 no era así… y esa divergencia era media `AB1-g6`») repite la misma afirmación falsa. La divergencia no se cerró: se movió de columna.

**Por qué no es un caso de laboratorio.** La fila que la explota la produce la migración oficial, sobre cualquier base del piloto que ya haya pagado una comisión. `MIGRATION.md` lo declara en su propia tabla: `PAGADA` → *etiqueta → `POLITICA_HISTORICA_PREVIA`, importe intacto* → *primer `recalculate`: **no alcanzada**: ya movió dinero*. Es decir, **toda comisión ya pagada del piloto queda, por diseño y para siempre, con `policy_status = POLITICA_HISTORICA_PREVIA`**. Esa fila es invisible para la siembra —que exige política canónica— y es un hecho vivo de pleno derecho para `_live_official_facts` —que no mira la política y sí ve su `paid_at`—. Como nunca puede repararse (`recalculate` la excluye por `paid_at IS NULL`) ni revertirse (`_reject_paid`), **su mes no puede volver a soltarse jamás**.

**Reproducción — `t14_realista.py`, sólo API pública sobre la base migrada, sin SQL, sin concurrencia. La base legada es la mínima posible: una única venta del piloto con su comisión ya pagada.**

```
base del piloto: eP = PAGADA 300bp / 30.000 Gs sobre venta de 1.000.000, etiqueta
                 SINTETICA_PENDIENTE_APROBACION, paid_at 2026-09-10
migracion oficial:
   etiqueta tras migrar: policy_status POLITICA_HISTORICA_PREVIA, importe 30.000 intacto
   pin sembrado: None            <-- la siembra no la ve
   hechos vivos 2026-09: [eP PAGADA 300]   <-- el codigo en caliente si la ve

1) publish 10000bp eff 2026-09-01 -> (2, True)      [promocion con un cero de mas]
2) venta 2026-09 de 10.000.000 Gs -> recalculate/review/approve
   pin tras aprobar: PINNED@10000  origin APROBADA
3) revert(entry, "aprobacion equivocada: la tasa promocional era un tipeo")
   estado: REVERTIDA
   hechos vivos CANONICOS en 2026-09: 0
   pin tras revertir: PINNED@10000     <-- NO SUELTA. eP lo sostiene.
4) publish 100bp eff 2026-09-01 -> (3, True)        [correccion al 1% oficial]
   recalculate(period='2026-09') -> {'evaluated': 0, 'changed': 0}; pin sigue 10000
   policy_for_period 2026-09: {'rate_bp': 10000, 'pinned': True}
5) tres ventas REALES de 2026-09, de 10.000.000 Gs cada una, aprobadas y pagadas:
   TOTAL pagado: 30.000.000 Gs | correcto al 1%: 300.000 Gs | SOBREPAGO: 29.700.000 Gs
   libro completo de 2026-09: [PINNED@10000]   <-- un solo evento, ningun UNPINNED jamas
```

**Las mismas cuatro rutas de `AB1-g6` vuelven a fallar, y por la misma causa.** Verificado en el mismo script: `revert` → `PINNED@10000` con 0 vivos canónicos; `void_sale` → `PINNED@10000`; `observe`+`revert` → `PINNED@10000`. La cuarta, `revert_payment`, cae igual porque el bloqueo no está en la ruta sino en `eP`.

**Daño: 29.700.000 Gs en el escenario reproducido; 9.900.000 Gs de sobrepago por cada venta de 10.000.000 Gs del mes, sin techo, indefinidamente.** En la dirección contraria —pin al 1 % y política corregida al 10 %— el daño es **900.000 Gs de subpago por venta de 10.000.000 Gs** (`t15_dir2.py`: la venta paga 100.000 Gs donde el oficial son 1.000.000 Gs). Es exactamente la misma cifra que reportó la generación 6, en las dos direcciones.

**No hay ninguna ruta pública de corrección** (`t15_dir2.py`), igual que en la generación 6:

```
publish 100bp eff 2026-09-01 -> (3, True); pin sigue 10000
publish   0bp eff 2026-09-01 -> (4, True); pin sigue 10000
publish 250bp eff 2026-09-01 -> (5, True); pin sigue 10000
recalculate(period='2026-09')  -> {'evaluated': 0, 'changed': 0}; pin sigue 10000
3 reaperturas de la base       -> pin 10000; 1 solo evento en el libro
observe(eP)                    -> OK, pero paid_at sobrevive; pin sigue 10000
revert(eP)                     -> RECHAZADO: liquidacion ya pagada
void_sale(venta de eP)         -> True, pero eP conserva paid_at: sigue viva; pin sigue 10000
```

**Segunda cara del mismo defecto, y peor de leer.** Antes incluso de que nadie apruebe nada, la base migrada **nace violando el invariante declarado**: `2026-09` tiene un hecho vivo (`eP`, `PAGADA`) y **ningún** evento en el libro, es decir no está fijado. Es la dirección «hecho vivo sin pin» del invariante de la generación 7. Mi fuzz sobre bases migradas (`t16_fuzz3.py`) lo detecta en **25 de 25 corridas, en el paso 0**. La consecuencia operativa es la que ya describí: la primera aprobación de ese mes fija la tasa **para siempre**, porque el hecho que la sostiene a partir de entonces ya no es la aprobación sino `eP`.

**Y una tercera cara, la que mi tercera condición de invariante destapó.** Tras el paso 3 el sistema afirma dos cosas incompatibles a la vez: el libro dice que `2026-09` está fijado **al 100 %**, y el único hecho económico vivo de ese mes es una comisión pagada **al 3 %**. Ningún hecho vivo del período lleva la tasa que el período declara. Es literalmente lo que el encargo pide comprobar —«que el último evento sea siempre coherente con los hechos vivos»— y no lo es.

**Qué haría falta, como mínimo.** Que los dos predicados sean **uno solo**, del mismo modo que `BOUNDARY_SQL_IN` ya unificó la lista de estados: extraer el `WHERE` completo de vitalidad a `comision_policy.py` y que lo usen `_live_official_facts` y la siembra sin añadidos por ninguno de los dos lados. Si el propietario decide que una liquidación con política legada **no** es un hecho vivo —defendible: nadie avaló ese importe bajo la regla aprobada—, entonces el filtro `policy_status` debe estar en **los dos**; si decide que **sí** lo es —también defendible: el dinero salió—, debe estar en **ninguno**, y la siembra tendrá que fijar el mes con la tasa a la que se pagó. Cualquiera de las dos cierra el agujero. Lo que no puede sostenerse es que la fila cuente para retener y no para sembrar, porque eso es exactamente un pin que ningún hecho justifica y que nada puede retirar.

## Observaciones no bloqueantes

1. **`recalculate` no es coherente consigo mismo en una sola pasada.** `decide()` resuelve el pin abriendo **su propia conexión** (`pinned_for` → `self.repository.connection()`) mientras `recalculate` mantiene su `BEGIN IMMEDIATE`. En WAL, esa conexión no ve lo que la transacción todavía no confirmó, así que un `UNPINNED` escrito por la reparación de una liquidación **es invisible** para las liquidaciones que el mismo bucle evalúa después: se calculan con la tasa que se acaba de retirar. Verificado (`t04b.py`): `recalc#1` deja la liquidación nueva en 100 bp / 100.000 Gs con `policy_version=1` pese a que el período quedó suelto y el catálogo rige a 200 bp; `review` la rechaza (`la política del período cambió desde el cálculo (v1 → v2)`) y `recalc#2` la corrige a 200 bp / 200.000 Gs. **No mueve dinero mal** —la guarda de `_require_current_policy` lo impide— pero exige dos pasadas para converger y deja un rechazo inexplicable en medio. Es la observación 7 de la generación 6, que allí era teórica y ahora es reproducible.

2. **La siembra agrupa por `period[:7]` y el predicado en caliente compara `e.period = ?` exacto.** Sobre una base de procedencia externa con un `period` de diez caracteres (`'2026-09-04'`), la migración siembra `PINNED@900` bajo la clave `'2026-09'` y `_live_official_facts('2026-09')` devuelve **cero** hechos vivos. Verificado (`t10_period_fmt.py`): la **primera transición cualquiera** de otra liquidación del mes —un simple `review`— escribe un `UNPINNED` y suelta un período que sí tiene una `APROBADA` viva al 9 %; el siguiente `recalculate` la reprecia de 900.000 a 100.000 Gs. `_month()` sólo produce `AAAA-MM`, así que ninguna ruta pública genera esa fila: es la misma clase de riesgo que la observación 1 de la generación 6, sobre datos de procedencia ajena. Bastaría comparar `substr(e.period,1,7)=?` en el predicado en caliente.

3. **«No desempata» deja períodos con hechos vivos y sin pin, y eso ahora tiene consecuencia.** La siembra descarta correctamente el período con evidencia discrepante (`APROBADA`@100 + `PAGADA`@500 → `SEED_SKIPPED / EVIDENCIA_DISCREPANTE`), y la decisión de no elegir por el propietario es la correcta. Pero combinada con `AB1-g7` el efecto es que la primera aprobación posterior de ese mes queda fijada para siempre, sostenida por la `PAGADA`@500 discrepante. Mientras `AB1-g7` esté abierto, este descarte es una fuente adicional de meses irrecuperables.

4. **El invariante 12 de `ARCHITECTURE_DELTA.md` afirma «No escribe una sola vez sobre `commission_entries`» en un párrafo que empieza hablando de la migración entera.** Es cierto de la **siembra** —lo verifiqué con SHA-256 sobre cinco reaperturas— pero no de `_migrate_commission_policy`, cuyo paso 4 sí ejecuta dos `UPDATE commission_entries SET policy_status=?` (`repository.py:298` y `:302`). `MIGRATION.md` lo documenta correctamente y aclara que `rate_bp` y `commission_amount` no se tocan, cosa que confirmé. Es ambigüedad de redacción en el delta, no una pérdida.

5. **`recalculate` sigue evaluando liquidaciones cuya venta está anulada** (`evaluated: 1` sobre una base legada con `voided=1`). Ya no es pagable —I14 cerró esa puerta en `review`/`approve`/`mark_paid`— pero la fila sigue consumiendo trabajo y apareciendo como recalculable.

6. **La única división por flotante del paquete sigue en `comisiones.py:1215`**, dentro de la etiqueta de texto del desglose de convenio (`AGREEMENT_DISCOUNT_BP / 100:.0f`). No participa de ningún cálculo monetario —las otras dos ocurrencias, en `:1239` y `:1398`, ya usan `//`— pero convive con la afirmación «no se usan floats en ningún punto» de la cabecera de `comision_policy.py`.

7. **`_reject_voided_sale` abre una conexión propia dentro del `BEGIN IMMEDIATE` de `_transition`**, igual que `pinned_for`. No produjo ni un `OperationalError` en 660 rondas concurrentes, pero es el mismo acoplamiento que la observación 1 y la 7 de la generación 6 ya señalaban, ahora en una guarda que decide si se paga.

## Superficie que mi auditoría NO cubrió

- **No auditó la interfaz gráfica ejecutándose.** Leí el diff de `comisiones_ui.py` —un solo cambio de rótulo, sin aritmética— y confirmé por `grep` que el panel no calcula dinero, pero no abrí la ventana ni verifiqué las capturas de `screenshots/`.
- **No verifiqué el `MANIFEST.sha256` ni el contenido del `.zip` del paquete.** Es trabajo del Librarian; me limité a contrastar las afirmaciones de invariantes de `ARCHITECTURE_DELTA.md` y `MIGRATION.md` contra el código.
- **Mi fuzz sobre bases frescas no puede encontrar defectos que sólo existen en bases migradas.** Lo digo explícitamente porque es el mismo tipo de punto ciego que declaró la generación 6: 32.000 pasos de fuzz limpio no significan nada sobre `AB1-g7`, que aparece en el paso 0 de cualquier base migrada desde un piloto que pagó. La corrida `t16_fuzz3.py` (25 × 60 pasos desde base migrada) es preliminar y debería ampliarse mucho más una vez cerrado el bloqueante.
- **No exploré combinaciones de política legada con `CONVENIO`, ni con períodos anteriores a la vigencia (`FUERA_DE_VIGENCIA`), sobre bases migradas.** El bloqueante apareció antes y no seguí ramificando; puede haber más superficie ahí.
- **No probé corrupción del fichero sqlite, fallos de disco a mitad de transacción, ni relojes que retroceden.** `recorded_at` y `created_at` vienen de `_now()` y ordenan la siembra por `created_at`; no ataqué esa dependencia.
- **No audité `sync_review_sales` ni el resto del módulo de gestión central fuera de comisiones**, ni el impacto del `commission_rated_periods` congelado sobre consumidores externos de la base.
- **No medí rendimiento.** El libro append-only crece sin poda y `_last_period_rate_event` hace un `ORDER BY id DESC LIMIT 1` por período apoyado en el índice, pero no probé con volúmenes grandes.
