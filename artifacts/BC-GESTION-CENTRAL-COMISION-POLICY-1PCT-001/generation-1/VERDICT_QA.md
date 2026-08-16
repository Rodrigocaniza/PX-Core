# QA independiente — Política de comisión 1% general (BC Gestión Central)

- **Runner:** QA-IND-COMISION-POLICY-1PCT-001
- **Rol:** revisor independiente de calidad funcional (trabajo aislado; sin conocimiento de Librarian ni Auditor)
- **Snapshot:** `578bf8b7205c857f9032581744f1e5818dab99fa` — worktree `c:\Users\Usuario\Desktop\Proyecto X\PX-Core\.worktrees\gc-comision-policy-1pct-001` (verificado limpio, `git status --porcelain` vacío antes y después)
- **Timestamp UTC:** 2026-08-16T03:28:35Z
- **Artefactos propios (scratchpad, no en el repo):** `test_qa_ind_comision.py` (35 pruebas nuevas, ninguna reusada del paquete) y `probe.py` (sondas + fuzz de estado de 1.500 operaciones)

---

## Escenarios ejecutados

**S1 — Venta común 400.000 cancelada comisiona exactamente 4.000.** Ruta distinta a la del paquete: alta con `initial_paid=0` → `PENDIENTE_SALDO`, luego dos cobros (137.000 el 2026-09-10 + 263.000 el 2026-09-22). Resultado: `ELEGIBLE` período `2026-09`, tras `recalculate` base 400.000, `rate_bp` 100, comisión **4.000**, `policy_status=CANONICA_APROBADA`. KPI del mes y fila por vendedora: 4.000.

**S2 — Saldo pendiente no genera comisión pagable; parcial informativo.** Venta 333.333 con cobro de 100.000. `recalculate` no la alcanza (`evaluated` la excluye), queda `PENDIENTE_SALDO`, base 0, `rate_bp=None`, `commission_amount=None`, `policy_status=SIN_POLITICA_APLICADA`, saldo 233.333. Historial exacto: `["SALE_REGISTERED", "PARTIAL_PAYMENT_INFORMATIVE"]`. KPI: `commission_amount=0`, `partial_payments_count=1`, `partial_payments_amount=100.000`. `review` y `mark_paid` rechazadas.

**S3 — Convenio 500.000 y orden 5%→1%.** Descuento 25.000, base 475.000, comisión **4.750**. Prueba de orden con totales discriminantes: en el rango 1..60.000 hay **4.760 totales** donde el orden inverso (1% y después −5%) da un número distinto; se corrieron 6 de ellos por el servicio completo y todos coincidieron con 5%→1%. Casos grandes verificados en el cálculo puro: 500.050 → desc 25.003, base 475.047, comisión **4.750** (orden inverso daría 4.751); 1.000.050 → **9.500** (inverso 9.501).

**S4 — Mismo 1% para toda vendedora y todo local.** 6 vendedoras × 4 locales (nombres con acentos, apóstrofos, espacios) × 1.000.000 → 24 liquidaciones, todas `rate_bp=100`, comisión 10.000, `policy_code=COMISION_GENERAL_1PCT`, `policy_scope=GENERAL`. Ruta de ataque: inyección directa en SQLite de políticas `VENDEDORA:Ana Benitez=9%`, `LOCAL:Local Centro=7,5%` y `GENERAL:Ana Benitez=5%` → el recálculo siguió dando 100 bp / 10.000 Gs y la migración borró los alcances no-GENERAL al reabrir. Grep de todo el árbol productivo: **una sola** instanciación de `CommissionService` (en `comisiones_ui.py:61`) y sin inyección del puerto `policy`, así que no hay ruta de aplicación a un porcentaje distinto por persona.

**S5 — Anulada sin comisión; reversión con auditoría.** Venta 600.000 calculada en 6.000, luego `void_sale` → única fila queda `REVERTIDA` conservando el importe histórico 6.000 (auditoría) y el KPI del mes cae a 0; `recalculate` devuelve `{evaluated: 0, changed: 0}`. Historial: `SALE_REGISTERED → COMMISSION_RECALCULATED → SALE_VOIDED` con `from_state=CALCULADA`. Reversión de cobro: historial `SALE_REGISTERED, SALE_CANCELLED, COMMISSION_RECALCULATED, PAYMENT_REVERTED, PENDING_AFTER_REVERSAL` y dos filas persistidas `["REVERTIDA","PENDIENTE_SALDO"]` — nada se borra.

**S6 — Redondeo HALF_UP en sus bordes.** Nueve bordes por el servicio completo: 49→0, **50→1** (truncamiento daría 0), 149→1, **150→2**, 151→2, **1.050→11** (HALF_EVEN daría 10), **1.150→12**, **1.250→13** (HALF_EVEN daría 12), 99.950→1.000. Barrido 1..40.000: se encontraron cientos de totales donde HALF_UP difiere de HALF_EVEN y/o del truncamiento; en los 18 probados por el servicio el resultado fue siempre el HALF_UP y **nunca** el HALF_EVEN ni el truncado. Medio guaraní en el descuento de convenio: total 1.010 → 5% = 50,5 exacto → **51** (HALF_EVEN daría 50), base 959, comisión 10. Fuzz de 4.011 totales contra una referencia independiente en `Fraction` (sin `Decimal`): coincidencia total en `apply_basis_points`, `agreement_discount`, `commissionable_base` y `commission_for`.

**S7 — Recálculo idempotente.** 10 ventas mixtas (común/convenio, con y sin saldo, 4 vendedoras, 3 locales), luego estados mezclados: REVISADA, APROBADA, PAGADA, OBSERVADA, REVERTIDA. **40 repeticiones** de `recalculate` + 8 recálculos filtrados por período y por local: `changed == 0` en todas. Conteo de `commission_entries` y de `commission_entry_history` idénticos antes y después, y el volcado fila-a-fila de toda la tabla (incluido `updated_at`) es bit a bit el mismo.

**S8 — Estados cerrados inalcanzables por recalculate, incluso con política nueva.** Cinco liquidaciones de 1.000.000 llevadas a PAGADA, APROBADA, REVISADA, OBSERVADA y REVERTIDA; snapshot completo de la tabla; luego `set_general_rate(250 bp)` (v2, `current_policy.rate_bp == 250`) y 5 recálculos. Volcado posterior **idéntico** al snapshot: las cinco conservan estado, `rate_bp=100`, comisión 10.000 y `policy_version=1`.

**S9 — `review` y `mark_paid` sin política aplicada.** `review` sobre una `CALCULADA` con `rate_bp IS NULL` (período fuera de vigencia) → `ValueError("...no tiene la política oficial aplicada...")`. Para `mark_paid` hubo que anular las columnas por SQL sobre una `APROBADA` (el camino público no lo permite): la guarda dispara y la liquidación sigue en `APROBADA`.

**S10 — Período anterior a la vigencia.** Venta 777.777 del 2026-07-31 → período `2026-07`, `rate_bp=None`, `commission_amount=None`, `policy_status=FUERA_DE_VIGENCIA`, base informativa 777.777, sin línea "Comisión oficial" en el desglose y nota que explica la vigencia. `review`, `approve` y `mark_paid` rechazadas; KPI de julio = 0. Borde: la misma venta el **2026-08-01** sí comisiona → 7.778 (HALF_UP de 7.777,77).

**S11 — `set_general_rate`.** Publicación 150 bp/2026-10-01 → v2; repetición idéntica 6 veces → `(2, False)` y ninguna versión nueva; 100 bp/2026-08-01 → v3. `commission_policy_versions` append-only con versiones 1..3 consecutivas y todas `CANONICA_APROBADA`. Rechazados: `-1`, `10001`, `True`, `False`, `1.5`, `"100"`, `None`, `10_000_000`; vigencias rechazadas: `2026-13-01`, `01/10/2026`, `""`, `"hoy"`, `2026-02-30`, `2026-8-1` — y ninguna publicó versión. Auditoría: exactamente 2 filas `COMMISSION_POLICY_VERSION_PUBLISHED` con `rate_bp` y `effective_from`. Permisos: `OPERADOR_LOCAL` y `AUDITOR` reciben `AccessDenied`; `SUPERVISOR` sí puede.

**S12 — Migración desde base con política sintética del piloto.** Base construida con una PAGADA de 1.234.567 al 3% (37.037 Gs) etiquetada `SINTETICA_PENDIENTE_APROBACION`, una abierta con `SIN_POLITICA_CONFIGURADA`, y políticas `VENDEDORA:450bp` y `LOCAL:275bp`. Seis reaperturas de `CentralRepository`: la auditoría `COMMISSION_POLICY_RETIRED` queda fija en **3** filas (no duplica), la tabla de políticas queda estable en una sola fila `GENERAL/''/100bp/CANONICA_APROBADA/v1/2026-08-01`, y `commission_policy_versions` tiene una sola fila. El volcado de importes (`gross`, `descuento`, `base`, `rate_bp`, `commission_amount`, `status`) es idéntico antes y después: la PAGADA sigue en 37.037 con `POLITICA_HISTORICA_PREVIA` y nota "política anterior"; la abierta pasa a `SIN_POLITICA_APLICADA` y al recalcular toma 100 bp → 8.000. La auditoría del retiro conserva los valores previos 450, 275 y 300.

**S13 — Persistencia y reapertura.** Cuatro ciclos de cierre/reapertura: importes idénticos, `recalculate` con `changed=0`, historial sin filas nuevas. Tras la última reapertura: PAGADA 4.000, convenio 4.750 con descuento 25.000, y `current_policy` exactamente `{code: COMISION_GENERAL_1PCT, scope: GENERAL, status: CANONICA_APROBADA, version: 1, effective_from: 2026-08-01, rate_bp: 100, rate_percent: "1.00", rounding: HALF_UP, currency: GS}`.

**S14 — Export.** `contract_version == 2`; claves exactas del sobre; bloque `policy` completo; cada entrada trae `policy_status/code/version/effective_from/scope` + `rate_bp` + `commission_amount` (la pendiente de saldo con `rate_bp=None` y `SIN_POLITICA_APLICADA`). Sin datos de cliente: el JSON serializado no contiene `client_key`, `idempotency`, `cliente`, el sobre `SOBRE-77`, `envelope`, `payload_json`, `identity_key`, `source_sale_id` ni `content_hash`. Disclaimer con `1.00%`, `5%` y `HALF_UP`. KPI = 4.000 + 4.750.

**S15 — Interfaz 1920x1080 (tkinter, root oculto).** Cabecera: `Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde 2026-08-01 · redondeo HALF_UP a Gs. enteros`. Encabezados de ambas tablas: `Comisión 1,00%`; caption KPI `COMISIÓN OFICIAL 1,00%` con valor `8.750 Gs.` y base `875.000 Gs.`. Desglose del convenio seleccionado: `Total de la venta 500.000 Gs.` / `− Descuento de convenio (5%) 25.000 Gs.` / `= Base comisionable 475.000 Gs.` / `= Comisión oficial (1,00% de la base) 4.750 Gs.`, con nota de política. Ancho de columnas: detalle 1.271 px y resumen 1.275 px, ambos dentro del panel izquierdo de 1.310 px (1.310 + 540 + sashes < 1.920): no hay recorte de la columna de comisión. Botón Recalcular → `changed=0`; Exportar escribe un JSON con `contract_version: 2`.

**S16 — Regresión completa.** `python -m pytest -q` en el worktree: **317 passed en 27,39 s**, 0 fallos.

**Extras y fuzz.**
- Convenio corregido a la baja 1.000.000→600.000: la traza de política cae a `SIN_POLITICA_APLICADA` y el recálculo rehace la base completa → 30.000 / 570.000 / **5.700** (no reusa el descuento viejo).
- Cambio COMUN→CONVENIO→COMUN con un COBRO real de 1.000.000 en el libro: vuelve a común sin descuento, base 1.000.000, comisión 10.000 y el libro conserva un único `COBRO`. Un convenio "puro" (sin cobro real) degradado a común sí reabre el saldo y deja la comisión en `None`.
- Corrección de origen posterior a la revisión: pasa a `OBSERVADA` conservando 10.000, y el recálculo no la toca (`changed=0`).
- Concurrencia: 12 hilos con conexiones propias cobrando y recalculando a la vez sobre la misma base → 0 excepciones, 12 liquidaciones (ninguna duplicada), todos los importes iguales a la referencia externa.
- Fuzz de estado (semilla 4242): 120 ventas, 1.500 pasos aleatorios (cobros, reversas, revisar/aprobar/pagar/observar, anular, corregir origen), 1.122 operaciones efectivas y **0 excepciones no-`ValueError`**. Invariantes verificadas al final: ningún `rate_bp` distinto de 100, ninguna comisión que no sea el HALF_UP exacto de su base × tasa, ninguna `PENDIENTE_SALDO` con comisión, ninguna venta con dos liquidaciones activas, ninguna `PAGADA` sin política, ninguna anulada en estado `PAGADA`. Recálculo final: `{evaluated: 11, changed: 0}` dos veces seguidas.

---

## Bloqueantes

Ninguno.

---

## Observaciones no bloqueantes

1. **Una política con vigencia futura borra la comisión ya calculada de períodos abiertos anteriores.** `CanonicalCommissionPolicy.decide()` (`comisiones.py:172-182`) lee siempre la única fila vigente y nunca la versión que gobernaba el período de la liquidación. Verificado: una liquidación de `2026-09` en `CALCULADA` con 1% / 10.000 Gs pasó a `FUERA_DE_VIGENCIA` con importe `None` al publicar 2% vigente desde `2026-12-01`. `commission_policy_versions` guarda la historia pero ningún camino la consulta. No contradice la decisión aprobada (una sola tasa desde 2026-08-01), pero cualquier publicación futura reescribe hacia atrás lo abierto.
2. **La vigencia es de granularidad mensual aunque el parámetro sea una fecha completa.** `is_in_effect` compara `period[:7] >= effective_from[:7]` (`comision_policy.py:101-105`), así que una política vigente desde `2026-09-20` ya comisiona una venta del `2026-09-01` (verificado: 10.000 Gs). Está documentado en el docstring, pero la API acepta un día que no se respeta.
3. **`set_general_rate` acepta 0 bp y 10.000 bp sin confirmación.** Ambos están dentro del rango declarado; una publicación de 0% dejaría en cero, en silencio y de golpe, toda liquidación abierta al siguiente recálculo. No hay segunda barrera ni aviso.
4. **La migración no retira un alcance parcial escrito como `scope='GENERAL'` con `scope_value` no vacío.** El filtro de retiro es `approval_status IN (retiradas) OR scope<>'GENERAL'` (`repository.py:219-222`), de modo que una fila `GENERAL/'Ana'/900bp/CANONICA_APROBADA` sobrevive a todas las reaperturas y aparece en `policies()`. No afecta el cálculo (`current()` filtra `scope_value=''`, verificado) y ningún código productivo puede crearla: sólo manipulación directa de la base.
5. **El KPI "Comisión oficial" incluye las liquidaciones OBSERVADAS.** En `report()`, `eligible` sólo excluye `REVERTIDA` y `PENDIENTE_SALDO`. Verificado: al observar una liquidación de 10.000 Gs, `commission_amount` sigue en 10.000 y `pending_approval` baja a 0, con lo que la bandeja muestra como comisión oficial del mes un importe que está justamente bajo objeción.
6. **`_default_period` cae a la constante del piloto `"2099-04"`** (`comisiones_ui.py:192`) cuando el libro está vacío. Es un resto del piloto sintético visible en pantalla en una base nueva.
7. **La guarda `_require_official_calculation` de `mark_paid` es inalcanzable por la máquina de estados pública**: `APROBADA` sólo se llega desde `REVISADA`, que ya la exige, y toda corrección posterior desvía a `OBSERVADA`. Tuve que anular las columnas por SQL para ejercitarla. Es defensa en profundidad correcta, pero no comprobable desde la interfaz.

VERDICT: PASS
