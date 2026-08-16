# Informe de QA funcional independiente — BC-GESTION-CENTRAL-COMISION-POLICY-1PCT

| | |
|---|---|
| **Runner** | QA-IND-COMISION-POLICY-1PCT-002 (revisor independiente de calidad funcional) |
| **Rol** | QA independiente. Sin contacto con Librarian ni Auditor de esta generación |
| **Snapshot** | `7abc30e6d33eb5dc522be7e43aa3ad3886a65b32` (generación 2) |
| **Worktree** | `c:\Users\Usuario\Desktop\Proyecto X\PX-Core\.worktrees\gc-comision-policy-1pct-001` |
| **Timestamp UTC** | 2026-08-16T04:03:37Z |
| **Escenarios propios** | 66 (56 pasan, 10 fallan) en 4 archivos de scratchpad |
| **Worktree modificado** | No. `git status` limpio, HEAD sin mover |

Escenarios propios en:
`…\scratchpad\{qa_leak.py, qa_regression.py, qa_ui.py, qa_confirm.py}`

---

## Ataque a la fuga corregida

Reconstruí una base del piloto con **10 liquidaciones legadas** (2 tasas retiradas × 5 estados: 3% y 7% en `CALCULADA`, `REVISADA`, `APROBADA`, `OBSERVADA`, `PAGADA`), más las políticas sintéticas por `GENERAL`/`VENDEDORA`/`LOCAL` que dejaba el piloto, y la reabrí para correr la migración.

**Lo que intenté y falló (la fuga A2 está realmente cerrada):**

1. **`review` → `approve` → `mark_paid` sobre cada una de las 10 legadas**, en cadena, y repitiendo la cadena entera 3 veces por si un paso habilitaba al siguiente (`test_no_public_route_pays_a_retired_rate`, 10/10 pasan). Ninguna ruta pública logró pagar un importe distinto del 1% oficial. La guarda `_require_official_calculation` exige `policy_status = CANONICA_APROBADA`, no sólo que haya importe: la corrección de gen-1 es la correcta y ataja en los tres puntos de entrada.
2. **Alcances por vendedora y por local inyectados por SQL** (`VENDEDORA:Ana` al 9%, `LOCAL:Local B` al 9%) con `approval_status = CANONICA_APROBADA` para simular una fila "legítima": la migración los borra al reabrir y todo vuelve al 100 bp. No hay ruta a otro porcentaje por ahí.
3. **`recalculate` sobre legadas con `paid_at` no nulo**: la rama de reparación (`REVISADA`/`APROBADA` + `POLITICA_HISTORICA_PREVIA`) sí exige `paid_at IS NULL` y no las toca. Las `PAGADA` legadas al 3% y al 7% conservan importe, `paid_at` y etiqueta (`test_a_legacy_paid_settlement_is_never_repaired`).
4. **Reparación**: lleva al 1%, retira `reviewed_by/at` y `approved_by/at`, asienta `COMMISSION_POLICY_REPAIRED` con el importe reemplazado, y es idempotente sobre 12 corridas sin reasentar historial. La comisión no se pierde: 33.250 → 4.750 y la cadena se rehace hasta `PAGADA`.
5. **`REVERTIDA` legada**: fuera de todo; el recálculo no la toca ni le agrega historial.

**Lo que sí encontré atacando por los flancos que el paquete no cubre:**

- **`OBSERVADA` legada** (documentada como «no alcanzada»): conserva 33.250 Gs. al 7% para siempre, sin haber movido dinero nunca. No es pagable (bien), pero **no hay ninguna ruta que la lleve al 1%**; la única salida pública, `revert`, la deja en `REVERTIDA` y **no crea liquidación de reemplazo**. La comisión se destruye.
- **La otra etiqueta retirada, `SIN_POLITICA_CONFIGURADA`, no está reparada** — y es la etiqueta *por defecto* del piloto. Ver Q1.
- **La reparación no es el único camino a un importe no oficial**: `set_general_rate` + `Recalcular` produce el daño desde el flujo soportado. Ver Q2.

---

## Escenarios ejecutados

| # | Escenario | Resultado / números reales |
|---|---|---|
| 6 | Común 400.000 cancelada; con saldo; parciales | base 400.000 → **4.000**. Con saldo: `PENDIENTE_SALDO`, base 0, comisión `None`, `review` rechazada. Último guaraní cobrado → período 2099-09, 4.000. 3 parciales de 250.000 → `PARTIAL_PAYMENT_INFORMATIVE` ×3, KPI parciales 750.000 / comisión 0; al cancelar, 10.000 | PASA |
| 7 | Convenio 500.000; orden 5%→1% | 500.000 / **25.000** / **475.000** / **4.750**. Fuzz 1..400.000: **20.000 totales** donde el orden inverso difiere. El servicio graba siempre el orden 5%→1%. Convenios 1.000.050→9.500, 333.333→3.167, 10.050→96, 99.999→950 | PASA |
| 8 | Mismo 1% para toda vendedora y local | 6 combinaciones local×vendedora → `{(100, CANONICA_APROBADA, 7.770)}`. No existe `set_policy`; alcances inyectados por SQL se retiran al reabrir | PASA |
| 9 | Anulada sin comisión; reversión con auditoría | Anulada → `REVERTIDA`, KPI comisión 0, `void_sale` idempotente, `SALE_VOIDED` en historial. Reversión de cobro → `REVERTIDA` + `PENDIENTE_SALDO` nueva | PASA |
| 10 | HALF_UP en bordes vs HALF_EVEN y truncamiento | 12 bordes exactos (49→0, 50→**1**, 150→**2**, 250→**3**, 350→**4**, 1.050→**11**). Barrido 0..200.000: **1.000 mitades exactas**, en todas HALF_UP = truncamiento+1. Fuzz 400 montos hasta 50.000.000 contra referencia independiente: coincidencia total | PASA |
| 11 | Recálculo idempotente, estados mezclados | 8 liquidaciones en seis estados; **30 corridas** con `changed = 0`, snapshot y conteo de historial idénticos | PASA |
| 12 | Cambio de política no mueve lo pagado | Pagada 8.000 al 1% v1; publicada v2 al 2,5%; 3 recálculos → sigue 8.000, `rate_bp = 100`, `policy_version = 1` | PASA |
| 13 | Período anterior a la vigencia | 2026-07 → `FUERA_DE_VIGENCIA`, base 500.000 informada, comisión `None`, los tres puntos de pago rechazan. 2026-08 → 5.000 | PASA |
| 14 | `set_general_rate` versionado/idempotente/validado/auditado | v1 idempotente `(1, False)`; v2 y v3 creadas; repetir v2 → `(2, False)`. Rechaza `-1`, `10001`, `True`, `1.5`, `"100"`, `None`, y fechas inválidas. 2 auditorías. `AUDITOR` denegado | PASA |
| 15 | Migración idempotente y persistencia | 6 reaperturas: entry, `policies`, `policy_versions` y conteo de auditoría byte a byte idénticos; `changed = 0` | PASA |
| 16 | Export `contract_version` 2 | v2 con `policy` completa, traza por fila, sin `envelope` ni `source_sale_id`, sin términos de cliente | PARCIAL — ver O1 |
| 17 | Interfaz 1920x1080 | Cabecera correcta. Anchos: detalle **1.271 px**, resumen **1.275 px** sobre `minsize=1310` → entra sin recorte. Filas y desglose correctos | PARCIAL — ver Q3 |
| 18 | Regresión completa del paquete | `python -m pytest -q` → **323 passed in 36.79s** | PASA |
| — | Permisos | `OPERADOR_LOCAL` sin lectura, `AUDITOR` sin escritura, lectura de política permitida al auditor | PASA |
| — | Fuzz de bordes de entrada | 12 entradas inválidas rechazadas en el borde; convenio con `initial_paid` parcial rechazado; 9.999.999.999.999 sin pérdida de precisión; 50 Gs → **1** | PASA |

---

## Bloqueantes

### Q1 — La reparación cubre sólo una de las dos etiquetas retiradas, y la que falta es la del piloto por defecto

`recalculate` repara `REVISADA`/`APROBADA` sólo cuando `policy_status = POLITICA_HISTORICA_PREVIA`. Una liquidación legada con la **otra** etiqueta retirada, `SIN_POLITICA_CONFIGURADA` → `SIN_POLITICA_APLICADA` (`rate_bp` nulo), queda permanentemente varada.

Contraste directo, misma base, mismo estado `APROBADA`:

```
recalculate = {'evaluated': 1, 'changed': 1}
  con 7% legado   -> CALCULADA  8000  CANONICA_APROBADA   ← reparada
  sin porcentaje  -> APROBADA   None  SIN_POLITICA_APLICADA ← intacta, para siempre
```

10 recálculos seguidos devuelven `{'evaluated': 0, 'changed': 0}`. `review`, `approve` y `mark_paid` la rechazan (correcto, no hay fuga económica). Las únicas salidas públicas son `observe` (callejón sin salida) y `revert`, que la deja en `REVERTIDA` **sin liquidación de reemplazo** sobre una venta cancelada y no anulada: **se pierden los 8.000 Gs. de comisión oficial que le corresponden**. Es exactamente el patrón que el Auditor rechazó en gen-1, sobreviviendo en la otra rama.

Y no es un caso de laboratorio: verifiqué contra `git show e773260:modulos/gestion_central/service.py` que **`bootstrap_synthetic_pilot` nunca sembraba ninguna fila en `commission_policies`**, de modo que el `StoredCommissionPolicy.rate_for` del piloto devolvía `(None, 'SIN_POLITICA_CONFIGURADA')` para *toda* liquidación, y `review`/`approve`/`mark_paid` del piloto **no tenían guarda**. La base legada por defecto es precisamente esta.

`MIGRATION.md` enumera los casos en una tabla y **omite la fila `REVISADA`/`APROBADA` sin porcentaje**.

### Q2 — Publicar la próxima vigencia destruye la comisión del mes en curso; las versiones se graban pero nunca se leen

`CanonicalCommissionPolicy.decide` resuelve el porcentaje leyendo **sólo la fila vigente** de `commission_policies` y la contrasta contra el período de la liquidación. `commission_policy_versions` se escribe y se lista, pero **nunca se consulta para calcular**. No existe resolución de política por período.

```
5 liquidaciones de 1.000.000 en 2099-12, calculadas al 1% → KPI comisión = 50.000
set_general_rate(150, "2100-01-01")  → v2 creada; por sí sola no toca nada (correcto)
Recalcular (el botón de la pantalla) → {'evaluated': 4, 'changed': 4}
KPI comisión = 10.000
```

Las 4 liquidaciones no revisadas pasan a `rate_bp = NULL`, `FUERA_DE_VIGENCIA`, y **dejan de ser pagables**. Se destruyen 40.000 Gs. de comisión ya calculada con un clic, sin advertencia.

El reverso es igual de grave: publicar con vigencia **pasada** re-tarifa períodos anteriores ya cerrados —una liquidación de 2026-08 calculada al 1% pasa de 20.000 a 80.000 al republicar 400 bp con `effective_from = 2026-08-01`—, precisamente lo que el versionado dice evitar.

### Q3 — La grilla, el resumen, los KPI y el export rotulan «oficial 1,00%» un importe calculado con la política retirada

El desglose de la fila seleccionada acierta, pero **todas las vistas agregadas no**. `_apply_policy_labels` reescribe incondicionalmente los encabezados con el porcentaje vigente y `report` suma `commission_amount` de toda liquidación elegible sin mirar `policy_status`.

```
columna 'Comisión 1,00%'          = 33.250 Gs.   (es 700 bp de la base)
KPI 'COMISIÓN OFICIAL 1,00%'      = 37.250 Gs.   (oficial real: 4.000 Gs.)
resumen por vendedora, Bea        = base 475.000 → comisión 33.250  (= 700 bp)
export kpi.commission_amount      = 80.000 Gs.   junto a
export policy_disclaimer          = "Comisión oficial 1.00% de la base comisionable…"
```

No es transitorio: las legadas `PAGADA` (por diseño) y las legadas `OBSERVADA` (por Q1) conservan su importe retirado indefinidamente.

---

## Observaciones no bloqueantes

1. **`cancelled_date` viaja siempre nulo en el contrato v2.** `ENTRY_EXPORT_FIELDS` lo declara, pero `list_entries` expone la de la venta como `sale_cancelled_date`; `row.get("cancelled_date")` devuelve `None` en el 100% de las filas exportadas.

2. **La guarda de `paid_at` de la reparación no cubre las dos ramas.** El docstring afirma «la reparación exige `paid_at IS NULL`», pero eso sólo rige para la rama `REVISADA`/`APROBADA`. Hoy es **inalcanzable** por API pública; es un invariante afirmado y no impuesto.

3. **`COMMISSION_POLICY_1PCT.md` afirma de más.** «Ese es el único caso en que un importe no oficial permanece, y ya está pagado» es falso: una `OBSERVADA` legada conserva su importe al 7% para siempre sin haber movido dinero jamás.

4. **`is_in_effect` compara sólo `AAAA-MM`.** Una vigencia a mitad de mes rige el mes completo hacia atrás. Inocuo con la fecha canónica, pero no documentado.

5. **Una corrección de origen sobre una `OBSERVADA` legada borra el importe histórico sin registrarlo.** El asiento `SOURCE_UPDATED` guarda la base nueva pero **no** el importe reemplazado, a diferencia de `COMMISSION_POLICY_REPAIRED`.

---

**Nota de método:** no modifiqué ningún archivo del worktree. La corrección concreta de A2 —la guarda de política oficial en los tres puntos de la cadena de pago— la considero correcta y bien probada; los bloqueantes que reporto son brechas de cobertura de esa misma corrección (Q1), un camino distinto al mismo daño económico por el flujo soportado (Q2) y el incumplimiento del requisito de rotulado en las vistas agregadas (Q3).

VERDICT: FAIL
