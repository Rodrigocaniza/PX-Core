# Verdict — Auditor, generación 6
Runner: AUDITOR-IND-COMISION-POLICY-1PCT-006
Snapshot: a5d6955828850b322c7ea00f5b46e3b5e7f3d7e4
Veredicto: FAIL

## Ataques ejecutados

Todo el trabajo se hizo con scripts propios en `…\scratchpad\aud6`, sobre bases sqlite temporales, importando el módulo con `sys.path.insert` al worktree. No se modificó ningún archivo del repositorio ni se hizo ningún commit (`git status --porcelain` sólo muestra los tres `PROMPT_*.txt` que el orquestador de la misión reescribió antes de arrancar; ningún archivo de código o de artefacto fue tocado por mí).

Regresión completa del repositorio: `python -m pytest -q` → **395 passed in 37.46s**.

**1. Boundary de fijación (`RATING_BOUNDARY_STATES`, `_pin_rated_period`, `_transition`).** Recorrí a mano todas las rutas de escritura de `commission_rated_periods`: `grep` sobre `modulos/` confirma exactamente **dos `INSERT` y ningún `UPDATE` ni `DELETE`** en todo el código (`comisiones.py:681`, `repository.py:340`). La fijación es literalmente irreversible: no existe ninguna sentencia en el sistema capaz de corregirla. Verifiqué que `APROBADA` sólo se alcanza por `approve()` y `PAGADA` sólo por `mark_paid()`, ambos con `guard=_require_current_policy`, y que `_set_status` sólo se usa para `OBSERVADA`/`REVERTIDA` desde `_revert_commission_effect`, `void_sale` y `_apply_source_update`. El boundary de *entrada* está bien cerrado; lo que está abierto es el de *salida* (bloqueante AB1-g6).

**2. Matriz B1-g4/B1-g3 (`t11_b1g4.py`).** Sobre un período fijado al 1 % publiqué la misma vigencia con 100 % y con 0 %, después de once transiciones distintas: sin transición, `observe`, `revert`, `observe+revert`, `void_sale`, corrección de origen, reversa de cobro, pago completo, pagada+observe, pagada+void_sale y `recalculate` ×3. **Las once devuelven 100 bp / 40.000 Gs.** Retirar la fijación de `recalculate()` no reabrió B1, B2, B1-g4 ni B2-g4.

**3. Concurrencia real (`t04_conc.py`), cinco escenarios con `threading.Barrier`:**

| Escenario | Rondas | Resultado |
|---|---|---|
| A — dos `approve` simultáneos de dos liquidaciones del **mismo** período | 40 | 0 errores; un solo pin (100 bp, `origin=APROBADA`); ambas quedan `APROBADA` a la tasa fijada |
| B — dos `approve` simultáneos de la **misma** liquidación | 40 | 40 × `transición inválida: APROBADA → APROBADA`; **un solo** asiento `APROBADA` en el historial; un solo `approved_by` |
| C — `approve` ‖ `set_general_rate` | 60 | 31 rechazos `la política del período cambió desde el cálculo (v1 → v2)`; nunca una aprobación a tasa vieja con catálogo nuevo |
| D — `approve` ‖ `recalculate` ‖ `approve` ‖ `set_general_rate` (4 hilos) | 40 | 18 errores, todos `ValueError` de dominio; pin único; ninguna liquidación con tasa distinta del pin |
| E — `mark_paid` ‖ `set_general_rate` | 60 | 0 errores; el pago sale siempre a la tasa fijada |

Ni un `OperationalError`, ni un `database is locked`, ni una doble aprobación, ni un pago a tasa distinta de la fijada. `BEGIN IMMEDIATE` serializa correctamente las tres operaciones. Añadí además `void_sale ‖ approve` y `void_sale ‖ mark_paid` (60 rondas cada una): **0 estados peligrosos** — no hay ventana en la que una venta anulada quede con liquidación pagable.

**4. Siembra reescrita de la migración (`t03_mig.py`, `t09_ab1g5_aprob.py`), con bases legadas construidas a mano por SQL plano:**

| Base legada | Resultado |
|---|---|
| sólo `REVERTIDA` @100 | **no siembra**, sin asiento |
| `APROBADA` @100 con venta `voided=1` | **no siembra**, sin asiento |
| sólo provisional (`CALCULADA`/`REVISADA`/`ELEGIBLE`) | **no inventa tasa**; ningún pin |
| discrepante: `APROBADA`@100 + `PAGADA`@500 | **no desempata**; asiento `COMMISSION_PERIOD_RATE_SEED_SKIPPED` con `reason=EVIDENCIA_DISCREPANTE` y ambos `entries` |
| coincidente `APROBADA`@500 + `PAGADA`@500 | siembra 500, `boundary=PAGADA`, con asiento `COMMISSION_PERIOD_RATE_SEEDED` |
| etiqueta retirada `SINTETICA_PENDIENTE_APROBACION` | relabelada a `POLITICA_HISTORICA_PREVIA`, **no siembra** |
| `policy_version`/`code`/`eff` NULL en la evidencia | siembra con los valores canónicos por COALESCE |

**No escribe nunca sobre `commission_entries`:** hash SHA-256 de la tabla completa idéntico tras **cinco** reaperturas de una base viva con una `PAGADA` y una `CALCULADA` (`t06_targeted.py` T1); ni importe, ni tasa, ni aprobación, ni pago. **Su auditoría no se duplica:** cuatro reaperturas de la base discrepante dejan **1** fila `SEED_SKIPPED`; cuatro reaperturas de la sembrada dejan **1** fila `SEED_SEEDED`.

**5. Fuzz encadenado (`t02_fuzz.py`, `t05_fuzz2.py`).** 16 operaciones públicas (`register_sale`, corrección de origen, `register_payment`, `revert_payment`, `recalculate`, `set_general_rate`, `review`, `approve`, `mark_paid`, `observe`, `revert`, `void_sale`, reapertura de la base —que vuelve a correr la migración—), períodos `2026-08…2027-01`, importes `{3, 50, 100000, 400000, 999999, 1234567, 7777777}`, tasas `{0, 100, 250, 500, 900, 10000}`, ambos tipos de venta.

- `t02_fuzz.py`: semillas 0–24 × 120 pasos.
- `t05_fuzz2.py`: semillas 0–59 × 200 pasos, con invariantes reforzados verificados **después de cada paso**: (B1) todo pin `RATED` tiene un hecho oficial en el historial del período; (B2) todo hecho oficial deja el período fijado; (B3) ninguna `APROBADA`/`PAGADA` cobra distinto del pin de su período; (B4) ninguna `CALCULADA`/`REVISADA` canónica cobra distinto del pin; (B5) el pin nunca cambia y el asiento coincide con la tabla; venta anulada nunca comisiona; aritmética `commission_for(base, rate)` exacta en toda fila; `paid_amount == Σ` libro append-only; ningún importe cambia entre asientos sin bloque `replaced`.

**Cero fallos en las 85 corridas.** Declaro explícitamente el límite: mi invariante B1 valida el pin contra el **historial**, y el historial sigue conteniendo la aprobación después de revertirla — por eso el fuzz **no** detecta AB1-g6. Lo encontré leyendo el código, no fuzzeando.

**6. Aritmética y estructura (`t10_inv.py`).** `git diff 71c4893 HEAD -- comision_policy.py` y `git diff b90a5db HEAD -- comision_policy.py` → **vacíos: el módulo no cambió desde la generación 3**. `grep` de `float(`/`round(` sobre `comision_policy.py` + `comisiones.py`: cero. La única división por flotante del paquete está en `comisiones.py:1061`, dentro de la **etiqueta de texto** del desglose (`AGREEMENT_DISCOUNT_BP / 100:.0f`), no en ningún cálculo monetario. `ROUND_HALF_UP` aparece sólo en `comision_policy.py` (import, y el único `quantize` en `quantize_guarani`), con `prec = 60`. Tabla verificada: `50×1%→1`, `150×1%→2`, `49×1%→0`, `1×1%→0`, `1234567×1%→12346`, `999999×5%→50000`, `2500000000000×1%→25000000000`, `1×100%→1`.

**7. Invariantes heredados.** I1 (un solo porcentaje `GENERAL` tras migrar, alcances por vendedora y local retirados **con su `rate_bp` previo en la auditoría**: 900 y 700), I2 (traza completa o vacía), I3 (idempotencia de `recalculate`, `changed==0`), I4 (una liquidación `FUERA_DE_VIGENCIA` sin tasa es rechazada en `review`), I8 (importe heredado de 700.000 Gs retirado por la rama `FUERA_DE_VIGENCIA` queda en el bloque `replaced`), I10 (`paid_amount == Σ` libro). Todos pasan.

## Reproducción de AB1-g5 y AB2-g5

**AB2-g5 — el tipeo de fecha que fijaba un mes lejano para siempre: CERRADO.** Escenario exacto de la generación 5 (`t01_ab_g5.py`): venta de 10.000.000 Gs con fecha `2036-08-04` en vez de `2026-08-04`.

```
entry: 2036-08 100bp 100000 CALCULADA
pins tras recalcular: []            <-- la 5 dejaba aquí {'2036-08': 100, origin 'RATED'}
pins tras anular:     []
publish 5% eff 2027-01-01: (2, True)
venta real de 2036-08 cobra: 500bp / 500000 Gs     (la 5 pagaba 100000)
policy_for_period 2036-08: rate_bp 500, pinned False
```

El cálculo provisional ya no fija nada. El mes lejano vuelve a resolverse por catálogo y la venta real de 2036-08 cobra sus 500.000 Gs. Los 400.000 Gs de diferencia que reportaba la generación 5 desaparecen.

**AB1-g5 — la siembra desde la liquidación más antigua, revertida y con venta anulada: CERRADO.** Escenario exacto: base legada con `eA` `REVERTIDA` @100 bp sobre venta `voided=1` (la de `created_at` más antiguo) y `eB` `PAGADA` @500 bp de 500.000 Gs.

```
SIEMBRA: [{'period':'2026-09','rate_bp':500,'origin':'BACKFILL','policy_version':2}]
auditoria: COMMISSION_PERIOD_RATE_SEEDED 2026-09 {"boundary":"PAGADA","entry_id":"eB",...}
policy_for_period 2026-09: rate_bp 500, pinned True
venta nueva de 2026-09 cobra: 500bp / 500000 Gs     (la 5 cobraba 100000)
```

La siembra ya no depende del orden de creación sino del boundary: ignora la `REVERTIDA` y la venta anulada, y toma la tasa a la que el mes **se pagó**. Los 400.000 Gs por venta que perdía la generación 5 dejan de perderse.

Y la segunda mitad de AB1-g5, el `t12_aprob` de la generación 5 —la migración bajaba una `APROBADA` de 500.000 → 100.000 Gs y le borraba el aval sin una sola fila de auditoría— **también está cerrada** (`t09_ab1g5_aprob.py`): tras migrar la misma forma de base, `eB` sigue en `APROBADA` con 500.000 Gs y `approved_by='Resp'`; `recalculate` devuelve `{'evaluated': 1, 'changed': 0}`; `mark_paid` paga los **500.000 Gs** correctos. Los 400.000 Gs que la migración se llevaba ya no se van, y la siembra deja asiento.

## Bloqueantes

### AB1-g6 — deshacer una aprobación no deshace la fijación del período: el mes queda tarifado para siempre por un hecho económico que el propio sistema anuló

**Dónde.** `modulos/gestion_central/comisiones.py`: `_pin_rated_period` (líneas 665-695) escribe `commission_rated_periods` con `INSERT OR IGNORE` y **jamás se borra ni se actualiza** — verificado por `grep` sobre todo `modulos/`: dos `INSERT`, cero `UPDATE`, cero `DELETE`. `revert()` (línea 758) admite `APROBADA` porque `OPEN_STATES` la incluye, es decir **deshacer una aprobación equivocada es una operación pública de primera clase**, y no toca el pin. `CanonicalCommissionPolicy.decide()` (línea 218) consulta el pin **antes** que el catálogo, sin ruta de corrección.

**Reproducción — `t07_ab1g6.py`, base fresca de la generación 6, sólo API pública, sin migración, sin SQL, sin concurrencia:**

```
1) publish 10000bp eff 2026-09-01 -> (2, True)          [promoción con un cero de más]
2) venta 2026-09 de 10.000.000 Gs -> recalculate/review/approve
   aprobada: APROBADA 10000bp 10000000 Gs
   pin: [{'period':'2026-09','rate_bp':10000,'origin':'APROBADA','first_rated_by':'sol'}]
3) revert(entry, "aprobación equivocada: la tasa promocional era un tipeo")
   estado: REVERTIDA, paid_at None
   pin tras revertir: [{'period':'2026-09','rate_bp':10000,...}]   <-- SIGUE AHÍ
   hechos economicos vivos en 2026-09: 0
4) publish 100bp eff 2026-09-01 -> (3, True)            [corrección al 1% oficial]
   policy_for_period 2026-09: {'rate_bp': 10000, 'version': 2, 'pinned': True}
5) tres ventas REALES de 2026-09, de 10.000.000 Gs cada una, aprobadas y pagadas:
   venta real 0: pagada 10000000 Gs   (oficial 1% = 100000 Gs)
   venta real 1: pagada 10000000 Gs
   venta real 2: pagada 10000000 Gs
   TOTAL pagado: 30.000.000 Gs | correcto: 300.000 Gs | SOBREPAGO: 29.700.000 Gs
```

**Daño: 9.900.000 Gs de sobrepago por cada venta de 10.000.000 Gs del mes, sin techo, indefinidamente.** En la dirección contraria —pin al 1 % y política corregida al 10 %— el daño es un **subpago de 900.000 Gs por venta de 10.000.000 Gs**, verificado en `t06_targeted.py` T4.

**No hay ninguna ruta pública de corrección.** Todas fracasan silenciosamente:

```
publish 100bp  eff 2026-09-01 -> (3, False); pin sigue: 10000
publish 0bp    eff 2026-09-01 -> (4, True);  pin sigue: 10000
publish 250bp  eff 2026-09-01 -> (5, True);  pin sigue: 10000
recalculate(period='2026-09') -> {'evaluated': 0, 'changed': 0}
pin final: [{'period':'2026-09','rate_bp':10000,'origin':'APROBADA'}]
```

**Son cuatro rutas independientes, no una (`t08_variants.py`).** Todas dejan el período fijado al 100 % con **cero** hechos económicos vivos y todas hacen que la venta real posterior pague 10.000.000 Gs en vez de 100.000:

| Ruta que retira el hecho económico | Estado final | Hechos vivos en 2026-09 | Pin | Venta real paga | Sobrepago |
|---|---|---|---|---|---|
| `revert` de la aprobación | `REVERTIDA` | 0 | 10000 bp | 10.000.000 Gs | 9.900.000 Gs |
| `void_sale` (**regla aprobada 8**: una venta anulada no genera comisión) | `REVERTIDA` | 0 | 10000 bp | 10.000.000 Gs | 9.900.000 Gs |
| `revert_payment` (cheque del cliente rechazado) | `REVERTIDA` + `PENDIENTE_SALDO` | 0 | 10000 bp | 10.000.000 Gs | 9.900.000 Gs |
| `observe` + `revert` | `REVERTIDA` | 0 | 10000 bp | 10.000.000 Gs | 9.900.000 Gs |

**Por qué es bloqueante y no la consecuencia aceptada por el propietario.** La decisión del propietario, tal como la fija `SAFE_PAUSE.md` líneas 78-90, es que el período se fije «cuando existe un hecho económico oficial», y su justificación literal es: *«un tipeo que será anulado nunca alcanza `APROBADA` ni `PAGADA`, así que no puede fijar un mes»*. **Esa frase es falsa contra el código.** Un tipeo que **sí** llega a `APROBADA` y **después** se anula —por `revert`, por `void_sale`, o porque el cobro del cliente se revirtió— fija el mes exactamente igual de para siempre que en la generación 5. El boundary de entrada se movió de `CALCULADA` a `APROBADA`; el defecto estructural no se movió: **la evidencia se crea con un hecho y no se retira cuando el hecho se retira.**

La tercera ruta es la que hace que esto no sea un caso de laboratorio: `revert_payment` no requiere ningún error humano. Es el flujo normal cuando un cheque rebota. Basta con que la aprobación de la comisión ocurra antes de que el cobro se caiga —cosa que el propio ciclo `ELEGIBLE → CALCULADA → REVISADA → APROBADA` favorece, porque aprobar es rápido y un rechazo bancario llega días después— para que un mes quede tarifado por un cobro que nunca existió. En ese momento **no se pagó un solo guaraní de comisión** por esa venta: no hay absolutamente nada que proteger, y sin embargo el mes entero queda inmovilizado.

La segunda ruta es peor aún en su lectura de negocio: `void_sale` implementa la **regla aprobada 8**, «una venta anulada no genera comisión». El sistema declara formalmente que esa comisión no existe —pone la liquidación en `REVERTIDA` y la saca del KPI— y al mismo tiempo conserva su tasa como la verdad económica del mes. El mes queda fijado por una comisión que el propio sistema afirma que no debe existir.

El comentario de `set_general_rate` (líneas 812-816) dice: *«es deliberado que la protección no dependa del estado posterior de la liquidación: observar, revertir, anular o corregir el origen cambian el estado, y la evidencia sigue ahí»*. Esa deliberación es correcta **para proteger dinero que salió** —una `PAGADA` observada después sigue teniendo su pago— pero se aplica indiscriminadamente al caso en que **no salió nada y ya no puede salir**. El invariante 9 declarado en `ARCHITECTURE_DELTA.md` («lo provisional es corregible; lo avalado, no») esconde que «lo avalado» incluye un aval que fue retirado por la misma persona que lo dio, minutos después, con la operación que el sistema le ofrece para retirarlo.

**Mitigación parcial que reconozco.** El pin queda asentado en `central_audit` como `COMMISSION_PERIOD_RATE_PINNED` con `boundary`, `entry_id` y `sale_id`, y cada publicación posterior asienta `protected_periods` —verificado: `{"protected_periods": ["2026-09"], "protected_periods_count": 1, ...}`—. La pantalla rotula « · fijada al aprobarse o pagarse». Un auditor **puede** enterarse. Pero `set_general_rate` devuelve `(3, True)` —éxito liso— y no existe ninguna operación, en ninguna capa, capaz de deshacerlo.

**Qué haría falta, como mínimo.** Que retirar el último hecho económico oficial vivo de un período retire también su fijación, con asiento propio (`COMMISSION_PERIOD_RATE_UNPINNED` con la tasa previa y el motivo), y que la fijación se vuelva a escribir cuando aparezca el siguiente hecho; o, si el propietario prefiere que el pin sea inmutable por diseño, que exista de una vez el flujo de corrección explícita y auditada que la propia documentación admite que no existe (`set_general_rate`, líneas 838-841). Sin uno de los dos, la primera aprobación equivocada de cada mes —o el primer cheque rechazado después de una aprobación— es definitiva.

## Observaciones no bloqueantes

1. **`recalculate`, `review`, `approve` y `mark_paid` no consultan `commission_sales.voided`.** No encontré ninguna ruta pública que produzca una liquidación no revertida sobre una venta anulada —`void_sale` es idéntico en las cuatro generaciones (`git show` de `71c4893`, `a7ea6a4`, `2ac9f5c`, `a5d6955`), las carreras `void_sale ‖ approve` y `void_sale ‖ mark_paid` dan 0 estados peligrosos en 60 rondas cada una, y 85 corridas de fuzz no lo produjeron—, pero sobre una base legada de procedencia externa que **sí** contenga esa fila, el código actual la recalcula, la revisa, la aprueba, la **paga** (100.000 Gs en mi repro `t06_targeted.py` T2) **y fija el período con ella**. La migración hace bien su parte —no siembra desde ventas anuladas— pero no marca ni bloquea la fila. La regla aprobada 8 no tiene defensa en el punto de pago.

2. **`INSERT OR IGNORE` en `_pin_rated_period` traga silenciosamente violaciones `NOT NULL`, no sólo la colisión de clave.** Verificado con sqlite directamente: `INSERT OR IGNORE` con `NULL` en una columna `NOT NULL` devuelve `rowcount == 0` sin error. `_pin_rated_period` interpreta ese `rowcount == 0` como «el período ya estaba fijado» y devuelve `False` **sin auditar nada**. `policy_version` es la única de las nueve columnas que no lleva `COALESCE`; hoy no puede ser `NULL` porque `_require_current_policy` compara contra `decision.version`, que siempre es `int`, pero es un fallo silencioso latente en el punto exacto donde se compromete dinero. Un `INSERT … ON CONFLICT(period) DO NOTHING` diría lo mismo sin ocultar el resto de las violaciones.

3. **Un período fijado atrae ventas nuevas por la fecha de cobro.** `_promote_to_eligible` deriva el período de `payment_date` y `register_payment` no valida esa fecha contra la de la venta. Verificado (`t06_targeted.py` T5): una venta de diciembre cuyo cobro se registra con fecha `2026-09-15` liquida en `2026-09` y cobra la tasa fijada de septiembre. Es entrada de datos, no un defecto del boundary, pero la fijación por período convierte una fecha mal puesta en una elección de tarifa.

4. **La corrección de origen nunca corrige el período.** `_apply_source_update` calcula `cancelled = row["cancelled_date"] or sale.sale_date`, de modo que el `cancelled_date` original sobrevive y `commission_entries.period` no se recalcula nunca. Una fecha mal cargada sólo puede enmendarse anulando la venta y dando de alta otra con distinto `source_sale_id`.

5. **Un `replaced` con `commission_amount` y `rate_bp` en `NULL`.** El bloque se escribe siempre que `repairing` sea cierto, aunque no hubiera importe previo que retirar. Es ruido en la auditoría, no una pérdida.

6. **KPI `commission_amount` del reporte suma también `OBSERVADA`**, y `paid_amount` deja de contar una liquidación que fue `PAGADA` y después observada, cuyo dinero sí salió. No es una regresión de esta generación.

7. **`decide()` lee el pin por una conexión propia, fuera de la transacción del llamador** (`pinned_for` abre `self.repository.connection()` mientras `_transition` mantiene su `BEGIN IMMEDIATE`). Hoy es inocuo —`BEGIN IMMEDIATE` serializa todas las escrituras y ninguna operación necesita ver un pin escrito en su propia transacción— pero es el mismo acoplamiento que ya señalaba la generación 5, y ahora la transacción que lo rodea sí escribe pines.

8. **La única división por flotante del módulo** está en `comisiones.py:1061`, dentro de la etiqueta de texto del desglose de convenio. No participa de ningún cálculo monetario, pero convive con la afirmación «no se usan floats en ningún punto» de la cabecera.

## Superficie que mi auditoría NO cubrió

- **No auditó la interfaz gráfica ejecutándose.** Leí el diff de `comisiones_ui.py` y confirmé por `grep` que no calcula dinero (sólo lee `policy_for_period` y llama a `rate_percent_text`), pero no abrí la ventana ni verifiqué las capturas de `screenshots/`.
- **No verifiqué el paquete entregable.** No comprobé `MANIFEST.sha256`, no abrí el `.zip`, no contrasté `WORKFLOW.json` ni `ARTIFACT_CONSISTENCY.md`. Sólo leí `SAFE_PAUSE.md` y `ARCHITECTURE_DELTA.md` para contrastar sus afirmaciones contra el código, y ahí encontré la falsedad citada en AB1-g6. Otras afirmaciones de esos documentos pueden ser falsas sin que yo lo haya notado.
- **No audité `sync_review_sales` ni `register_payment` contra un llamador productivo.** Siguen sin uno, como ya registraba el handoff; los ejercité sólo desde mis propios scripts.
- **No audité el resto del bounded context** —alertas, mensajería, entregas, factufácil, snapshots de caja— salvo por lo que toca la regresión completa de pytest.
- **Mi fuzz no puede detectar AB1-g6 por construcción**, porque valida el pin contra el historial y el historial conserva la aprobación revertida. Cualquier otro defecto de la misma familia —evidencia durable que sobrevive a la retirada del hecho que la creó— tampoco lo detectaría. Lo digo explícitamente porque significa que las 85 corridas limpias **no** son evidencia de ausencia en esa dirección.
- **No probé la concurrencia entre procesos**, sólo entre hilos del mismo proceso Python con conexiones sqlite independientes. No probé bases sobre red ni bloqueos de sistema de archivos.
- **No probé bases legadas producidas por las generaciones 1 y 2** con su código real; construí las mías por SQL plano, guiándome por el esquema, y reproduje la forma de la base de la generación 4/5 a partir de la descripción del verdict anterior en vez de correr `git show a7ea6a4` como hizo el auditor de la generación 5.
- **No estimé el daño agregado real** de AB1-g6 sobre el volumen del piloto; las cifras que doy son por venta y por escenario de laboratorio.
