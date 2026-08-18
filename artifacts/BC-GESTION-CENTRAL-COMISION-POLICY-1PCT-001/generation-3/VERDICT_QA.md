# VERDICT_QA — generación 3

| Campo | Valor |
|---|---|
| **Runner** | QA-IND-COMISION-POLICY-1PCT-003 |
| **Rol** | Revisor INDEPENDIENTE de calidad funcional (gen 3) |
| **Misión** | BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 |
| **Snapshot** | `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a` (verificado con `git rev-parse HEAD` al iniciar y al cerrar) |
| **Worktree** | `.worktrees/gc-comision-policy-1pct-001` |
| **Timestamp UTC** | 2026-08-18T00:58:35Z |
| **Ficheros modificados por mí** | **Ninguno.** `git status --porcelain` vacío al iniciar y al terminar. Sin commits, sin `add`, sin `checkout`, sin `push`. |
| **Dónde escribí mis escenarios** | Directorio temporal fuera del repositorio: `scratchpad\qa-gen3\` |

## Método

Escribí **mis propios escenarios**, con mis propios importes, fechas y actores, sin reusar las fixtures ni las aserciones de `tests/gestion_central/test_comisiones.py`. Todo estado se reconstruyó **ejecutando el código** (`register_sale`, `register_payment`, `recalculate`, `review/approve/mark_paid`, `set_general_rate`, `report`, `export_summary`, panel Tk real). El único SQL directo está en el escenario D, para *envejecer* una base al estado del piloto sintético (`SINTETICA_PENDIENTE_APROBACION` / `SIN_POLITICA_CONFIGURADA`): ningún código produce ya esas etiquetas, así que no hay forma de generarlas ejecutando; y en G3, para simular una corrupción de estado deliberada.

| Script | Cobertura | Checks | Fallidos |
|---|---|---|---|
| `harness.py` | arranque propio (repo temporal fuera del worktree) | — | — |
| `a_economia.py` | 400.000 cancelada → 4.000; saldo no comisiona; parcial informativo; convenio 500.000 → 25.000 / 475.000 / 4.750; orden 5%→1%; mismo 1% para toda vendedora y local; venta anulada | 29 | 0 |
| `b_redondeo.py` | HALF_UP en bordes, medio guaraní exacto (1%, 5% y extremo a extremo), 2^53+1 sin floats | 32 | 0 |
| `c_politica_estados.py` | cierre Q1 y Q2; PAGADA/REVISADA/APROBADA frente a `recalculate`; período previo a la vigencia; reversión y auditoría | 35 | 0 |
| `d_migracion_q3.py` | migración desde base sintética, reapertura sin duplicar; cierre Q3 (grilla/resumen/KPI/desglose/export); contrato v2 | 30 | 0 |
| `e_versionado_persistencia.py` | `set_general_rate` append-only e idempotente, entradas inválidas, recálculo idempotente, persistencia y reapertura, control de acceso | 36 | 0 |
| `f_ui_1920.py` | panel Tk real a 1920×1080: base, 1%, comisión oficial, aviso, desglose, export | 28 | 0 |
| `g_adversario.py` | sondeo adversario: bordes de vigencia, guarda de pago, corrupción de estado, corrección de origen, **vigencia a mitad de mes** | 13 | 1 (ver O1) |
| **Total propio** | | **203** | **1** |
| Regresión del paquete | `pytest tests/gestion_central` → 131 passed · `pytest tests` → 331 passed | | 0 |

## Cierre de los bloqueantes de la generación 2

### Q1 — «la reparación cubría sólo `POLITICA_HISTORICA_PREVIA` y dejaba varada la liquidación SIN porcentaje» — **CERRADO**

`recalculate` ya no discrimina por etiqueta: compara la **tupla completa** (importes + `rate_bp` + `commission_amount` + los cinco campos de traza) contra la decisión de política del período, así que cualquier divergencia se repara, venga de donde venga.

Verificado ejecutando (`c_politica_estados.py`):

```
OK  Q1 recien creada nace SIN_POLITICA_APLICADA  :: SIN_POLITICA_APLICADA
OK  Q1 recien creada sin rate
OK  Q1 review rechaza la ELEGIBLE sin politica :: transición inválida: ELEGIBLE → REVISADA; requiere CALCULADA
OK  Q1 mark_paid rechaza sin politica          :: transición inválida: ELEGIBLE → PAGADA; requiere APROBADA
OK  Q1 recalculate repara la SIN_POLITICA      :: ('CANONICA_APROBADA', 100, 4000, 'CALCULADA')
```

Y en la base migrada (`d_migracion_q3.py`), conviven las tres etiquetas y las tres se resuelven bien: la heredada abierta y la que estaba sin porcentaje pasan a la comisión oficial (`E2 tras recalcular, lo abierto pasa a oficial :: 17000`), mientras la pagada queda intacta.

Además, la cadena de pago rechaza *cualquier* liquidación sin porcentaje oficial aplicado, no sólo la de etiqueta ausente: `C4 review rechaza fuera de vigencia :: la liquidación no tiene la política oficial aplicada: recalcule antes de continuar`.

### Q2 — «publicar la vigencia siguiente destruía la comisión del mes en curso» — **CERRADO** (con la salvedad O1)

`CanonicalCommissionPolicy.in_force_for(period)` resuelve **por período**, tomando la versión de vigencia más reciente que no lo supera, y `_require_current_policy` compara `(rate_bp, version)` contra esa decisión, no contra «la última publicada». La migración además siembra `commission_policy_versions` con v1, de modo que el catálogo nunca está vacío y la resolución por período está siempre disponible.

Verificado ejecutando la secuencia completa del piloto:

```
OK  Q2 pre-publicacion APROBADA 4.000                    :: ('APROBADA', 4000)
OK  Q2 publica v2                                        :: (2, True)      # 2% desde 2026-09-01
OK  Q2 el mes en curso conserva 4.000 al 1%              :: (100, 4000)
OK  Q2 conserva su aval APROBADA                         :: APROBADA
OK  Q2 policy_version sigue 1                            :: 1
OK  Q2 recalculate no la modifico                        :: {'evaluated': 1, 'changed': 0}
OK  Q2 pagable tras publicar la vigencia siguiente       :: ('PAGADA', 4000)
OK  Q2 septiembre toma v2 al 2% = 8.000                  :: ('2026-09', 200, 8000, 2)
```

El mes en curso conserva importe, versión y aval, y **sigue siendo pagable**; septiembre toma la versión nueva. Refuerzo en `g_adversario.py`: publicar 3% desde octubre no toca la PAGADA de agosto (`G3 recalculate no toca nada con paid_at :: evaluated 0`), y una APROBADA cuya política del propio período sí cambió no se puede pagar (`G2 :: la política del período cambió desde el cálculo (v1 → v2)`).

### Q3 — «grilla, resumen, KPI y export rotulaban "oficial 1,00%" un importe calculado con la política retirada» — **CERRADO**

Verificado sobre una base migrada con importes heredados reales (5%) y sobre el panel Tk:

```
OK  Q3 KPI comision oficial excluye lo heredado            :: 0
OK  Q3 KPI informa aparte lo no oficial                    :: 150000
OK  Q3 KPI cuenta 2 liquidaciones no oficiales             :: 2
OK  Q3 resumen por vendedora separa oficial de no oficial  :: (0, 150000)
OK  Q3 desglose no llama oficial al importe heredado
    :: ['Comisión con política anterior (no pagable) (5,00% de la base)']
OK  Q3 la pagada se conserva por auditoria
    :: "... Ya fue pagado: se conserva tal cual por auditoría."
OK  Q3 review rechaza la politica retirada
    :: la liquidación no lleva la política oficial vigente (POLITICA_HISTORICA_PREVIA)
OK  E1 la entrada heredada exporta su etiqueta real        :: ('POLITICA_HISTORICA_PREVIA', 500)
OK  E1 KPI exportado no declara oficial lo heredado        :: 0
```

En pantalla (`f_ui_1920.py`), el `1,00%` aparece exactamente donde el importe *sí* es oficial y en ningún otro sitio:

```
OK  F2 KPI rotulado COMISION OFICIAL 1,00%     :: COMISIÓN OFICIAL 1,00%
OK  F3 la columna de comision NO se rotula 1,00% :: Comisión
OK  F5 aparece el aviso de politica anterior
OK  F5 el aviso cifra lo no oficial
    :: 1 liquidación(es) por 23.750 Gs. con política anterior, fuera de la comisión oficial.
OK  F5 el KPI oficial deja de sumarlo          :: 4.000 Gs.
OK  F5 el desglose no lo llama oficial
OK  F6 tras recalcular el aviso desaparece / KPI oficial vuelve a 8.750 Gs.
```

La cabecera nombra el porcentaje vigente sin rotular filas: `Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde 2026-08-01 · redondeo HALF_UP a Gs. enteros`.

## Resto del prompt de rol — evidencia

**Economía aprobada.** 400.000 cancelada → base 400.000, `rate_bp` 100, comisión **4.000**, `CANONICA_APROBADA`, período 2026-08. Venta común con saldo → `PENDIENTE_SALDO`, base 0, sin comisión, sin período, y `recalculate` no la alcanza. Cobro parcial → estado intacto y asiento `PARTIAL_PAYMENT_INFORMATIVE`; al cancelar el saldo comisiona 4.000. Convenio 500.000 → descuento **25.000**, base **475.000**, comisión **4.750**, sin saldo cliente. Orden 5%→1% verificado por definición y por valor. Mismo 1% para tres combinaciones distintas de local y vendedora (`{100}` / `{10.000}`). Venta anulada → `REVERTIDA` y fuera del KPI, con la suma del KPI reconciliada a mano (42.750 = 42.750).

**Redondeo.** `quantize_guarani` en 0,5 / 1,5 / 2,5 / −0,5 y en 0,4999 / 0,50001. 1% con medio guaraní exacto: 150→2, 250→3, 350→4, 450→5, 50→1; y los no-medios 149→1, 151→2, 49→0. 5% con medio exacto: 10→1, 30→2, 50→3, 70→4, 90→5, 110→6. Extremo a extremo: venta común de 150 persiste **2**; convenio de 10 → descuento 1, base 9, comisión 0; convenio de 5.000 → base 4.750, comisión **48** (47,5 HALF_UP). Sin floats: 1% de 2^53+1 coincide con el `Decimal` exacto.

**Estados frente a `recalculate`.** `PAGADA` nunca se evalúa —ni siquiera con el estado corrompido a `APROBADA` con `paid_at` puesto (`G3`, `evaluated: 0`)—. `REVISADA` y `APROBADA` **correctas** conservan estado y aval (`changed: 0`, `approved_by` intacto). `REVISADA`/`APROBADA` **obsoletas** caen a `CALCULADA`, pierden `reviewed_*` y `approved_*`, y asientan `COMMISSION_POLICY_REPAIRED`. Ninguna liquidación queda *en* `REVISADA`/`APROBADA`/`PAGADA` como resultado de un recálculo, y ninguna con dinero movido se toca. `OBSERVADA` y `REVERTIDA` quedan fuera.

**`review` / `mark_paid` sin política.** Rechazan por la guarda `_require_current_policy` (sin importe, con etiqueta no canónica, o con versión desfasada) y por la propia máquina de estados. Los tres mensajes son distintos y accionables.

**Período anterior a la vigencia.** Julio 2026 → `FUERA_DE_VIGENCIA`, sin `rate_bp` ni comisión, **con la base informada** (600.000); el desglose omite la línea de comisión; el KPI oficial es 0 pero la base comisionable se informa. Borde mensual limpio: 2026-07-31 fuera, 2026-08-01 comisiona 1.000.

**Reversión y auditoría.** La liquidación revertida conserva su importe histórico (3.000), se abre una nueva `PENDIENTE_SALDO`, el KPI del período cae a 0, y el historial de la venta es exactamente `SALE_REGISTERED → SALE_CANCELLED → COMMISSION_RECALCULATED → PAYMENT_REVERTED → PENDING_AFTER_REVERSAL`.

**Corrección de origen.** Antes de la revisión recalcula la base completa y **cae la traza de política** (`ELEGIBLE`, `rate_bp` NULL); después de la revisión deja `OBSERVADA` conservando el importe, y `recalculate` no la reabre.

**Recálculo idempotente.** Primera pasada `changed: 1`; tres pasadas siguientes `changed: 0`; el historial no crece (2 asientos antes y después); una sola liquidación activa; importe estable. Alta de venta y cobro con `idempotency_key` no duplican.

**Versionado `set_general_rate`.** Republicar idéntico devuelve `(1, False)` sin crear versión; v2 se añade dejando v1 **íntegra**; el reintento de v2 es idempotente. Rechaza vigencia hacia atrás, `rate_bp` inválido (−1, 10001, `True`, `1.5`, `"100"`) y fechas inválidas (`2026-13-01`, `01/09/2026`, `""`, `2026-09-31`) sin crear versión ni asiento de auditoría espurio: una publicación auditada por versión real.

**Migración desde base sintética.** Sobre una base envejecida con política 5% `SINTETICA_PENDIENTE_APROBACION`, una política por vendedora 7% `SIN_POLITICA_CONFIGURADA`, y liquidaciones pagada / abierta / sin importe: la migración **no altera un solo importe ni estado** (comparación exhaustiva de todas las filas antes/después), reetiqueta a `POLITICA_HISTORICA_PREVIA` lo que tiene importe y a `SIN_POLITICA_APLICADA` lo que no, borra el alcance por vendedora, instala la canónica 1% v1 vigente 2026-08-01, siembra el historial de versiones, y asienta **dos** auditorías `COMMISSION_POLICY_RETIRED` con los valores previos (500 y 700). Reabrir dos veces más no duplica versiones, ni políticas, ni auditorías, ni altera importes.

**Persistencia y reapertura.** Los datos, los importes y el reporte completo son idénticos tras reabrir la base; `recalculate` tras reabrir devuelve `changed: 0`.

**Export contrato v2.** `contract_version: 2`; bloque `policy` con `rate_bp` 100, `rate_percent` `"1.00"`, `version` 1, `effective_from` 2026-08-01, `rounding` `HALF_UP`, `currency` `GS`; **traza por entrada** (`policy_status`, `policy_code`, `policy_version`, `policy_effective_from`, `policy_scope`, `rate_bp`, base e importe) que refleja la política real de cada liquidación, no la vigente; `policy_disclaimer` coherente. El export desde la UI escribe `Comisiones/comisiones-2026-08.local.json`.

**UI 1920×1080.** Ventana real de 1920 de ancho; la grilla de detalle suma 1271 px sobre un panel mínimo de 1310 y el resumen 1275, así que **base, descuento y comisión entran sin recorte**; 1310 + 500 + sashes caben en 1920. Fila común cancelada `400.000 Gs. … 400.000 Gs. … 4.000 Gs.`; fila con saldo `300.000 Gs.` de saldo y comisión `—`; convenio `25.000 / 475.000 / 4.750`. Desglose: `Total de la venta / − Descuento de convenio (5%) / = Base comisionable / = Comisión oficial (1,00% de la base)` con `500.000 / 25.000 / 475.000 / 4.750`.

**Control de acceso.** Auditor lee pero no recalcula ni publica política; operador local no accede a comisiones ni al reporte.

**Regresión.** `pytest tests/gestion_central` → **131 passed**. `pytest tests` (suite completa del repo) → **331 passed**. Sin ficheros nuevos ni modificados en el worktree.

## Bloqueantes

**Ninguno.**

## Observaciones no bloqueantes

**O1 (prioridad alta) — una vigencia que no es día 1 de mes se publica como una fecha y se aplica como otra.** `set_general_rate` acepta cualquier `effective_from` válido ≥ la última publicada, pero la resolución es mensual (`is_in_effect` compara `period[:7] >= effective_from[:7]`). Publicar «3% desde 2026-08-20» aplica el 3% a **todo agosto**, incluida una venta cancelada el 5 de agosto ya aprobada, que vuelve a `CALCULADA` a 30.000 y pierde su aval — el síntoma que Q2 cerró para las vigencias de día 1 reaparece para las de mitad de mes. Reproducido en `g_adversario.py`:

```
OK    G6 aprobada el 5 de agosto con 10.000 al 1%   :: ('APROBADA', 10000, 1)
OK    G6 el sistema acepta una vigencia a mitad de mes :: (2, True)
FAIL  G6 la venta del 5 de agosto NO deberia re-tarifarse a 3%
      :: (30000, 'CALCULADA', 2, {'evaluated': 1, 'changed': 1})
OK    G6 is_in_effect trata 2026-08-20 como todo agosto :: True
```

Contradice el propio contrato del método («se puede programar el futuro; no se puede re-tarifar el pasado») y hace que la cabecera muestre «vigente desde 2026-08-20» mientras se cobra desde el día 1. **No es bloqueante** porque: (a) `set_general_rate` no está cableado a ninguna pantalla ni entrypoint —sólo aparece en su definición y en los tests—, de modo que el piloto entregado no puede producirlo; (b) la política canónica entregada es día 1 (`2026-08-01`); y (c) la guarda de pago sigue impidiendo pagar un importe desfasado. Corrección sugerida cuando se exponga la publicación: rechazar en `normalize_effective_from` (o en `set_general_rate`) toda vigencia que no sea el primer día de un mes, que es la única granularidad que el modelo sabe representar.

**O2 (prioridad media) — `cancelled_date` viaja siempre nulo en el export v2.** `ENTRY_EXPORT_FIELDS` declara `cancelled_date`, pero `list_entries` proyecta esa columna como `sale_cancelled_date`, así que `row.get("cancelled_date")` devuelve `None` incluso para ventas canceladas. Comprobado: venta cancelada el 2026-08-10 → `cancelled_date exportado: None`, mientras `sale_cancelled_date` sí trae `'2026-08-10'`. El campo del contrato existe pero nunca lleva dato; ningún importe se ve afectado.

**O3 (prioridad baja) — el resumen por vendedora no expone la columna de importe no oficial.** `report()` calcula `non_official_amount` por vendedora, pero `SUMMARY_COLUMNS` no lo muestra: una vendedora con sólo importes heredados aparece con `Comisión 0` mientras la grilla de detalle sí muestra el importe. No es un rótulo falso (nada se llama «oficial»), y el aviso naranja global cubre el caso; aun así, añadir la columna evitaría que el dato quede sólo en el banner.

**O4 (informativo) — dos aserciones mías fallaron por error propio, no del producto.** En `a_economia.py` esperaba 1 cobro parcial de 100.000 olvidando el cobro inicial de 150.000 de la misma venta (lo correcto es 2 y 250.000), y en `f_ui_1920.py` comparé importes sin el sufijo `" Gs."` que añade `pyg`. Ambas corregidas y en verde; se dejan documentadas para que el registro sea reproducible.

---

# VEREDICTO: **PASS**

Los tres bloqueantes que emití en la generación 2 están **cerrados y verificados por ejecución**, cada uno con el escenario que antes los reproducía: la reparación alcanza hoy a la liquidación sin porcentaje —el estado por defecto del piloto— y no sólo a la etiqueta histórica; la política se resuelve por período, de modo que publicar la vigencia siguiente deja intactos importe, versión, aval y pagabilidad del mes en curso; y ni la grilla, ni el resumen, ni el KPI, ni el desglose, ni el export llaman «oficial 1,00%» a un importe calculado con la política retirada, que se informa aparte, se avisa en pantalla y se bloquea en la cadena de pago.

Las 203 verificaciones propias pasan salvo la que documenta O1, cuya única vía de acceso es una API no cableada al piloto y que no afecta a la política canónica entregada; la regresión completa del repositorio pasa (331 tests). No modifiqué ningún fichero del repositorio: el árbol quedó limpio, en el mismo snapshot `75f5c57`.
