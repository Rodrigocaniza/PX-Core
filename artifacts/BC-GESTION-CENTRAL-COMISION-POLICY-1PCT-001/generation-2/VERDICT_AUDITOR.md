# Auditoría independiente de invariantes económicos — generación 2

| | |
|---|---|
| **Runner** | AUDITOR-IND-COMISION-POLICY-1PCT-002 |
| **Rol** | Auditor independiente de invariantes económicos (trabajo aislado; no vi Librarian ni QA) |
| **Snapshot** | `7abc30e6d33eb5dc522be7e43aa3ad3886a65b32` (worktree `gc-comision-policy-1pct-001`) |
| **Snapshot anterior** | `578bf8b7205c857f9032581744f1e5818dab99fa` |
| **Timestamp UTC** | 2026-08-16T04:05:25Z |
| **Worktree** | sin modificar (`git status` limpio); pruebas propias en scratchpad |
| **Suite del paquete** | `tests/gestion_central` → 123/123 PASS |
| **Suite propia** | 52 pruebas adversariales, 51 PASS / 1 FAIL (el FAIL es hallazgo real) |

Método: no reutilicé ni una sola aserción del paquete. Escribí cinco arneses propios que
reconstruyen bases legadas con el **código anterior a la misión** (`114aee8`), instrumentan el SQL
real de la migración vía `set_trace_callback`, comparan la aritmética contra `Fraction` exacto, y
ejercitan concurrencia real con hilos y barreras.

---

## Cierre de A1 y A2

### A1 — invariante de traza reformulado: **CERRADO** (con una imprecisión de redacción)

Construí una base con las ocho combinaciones alcanzables y verifiqué fila por fila que la traza es
**completa o vacía, nunca parcial**:

- `CANONICA_APROBADA` ⇒ cuatro campos no nulos + `rate_bp` + `commission_amount`.
- `FUERA_DE_VIGENCIA` ⇒ traza completa, sin importe.
- `POLITICA_HISTORICA_PREVIA` y `SIN_POLITICA_APLICADA` ⇒ los cuatro en `NULL`.

La propiedad **se sostiene sobre base nueva y sobre base migrada**. La afirmación *literal* del
encabezado («la traza está completa **exactamente cuando** la política es la aprobada») sigue siendo
falsa: `FUERA_DE_VIGENCIA` también la tiene completa. Observación, no bloqueante.

### A2 — fuga económica: **NO CERRADO**

La mitad que sí se cerró: una liquidación migrada con `POLITICA_HISTORICA_PREVIA` es rechazada en
los tres puntos de entrada, la reparación la devuelve a `CALCULADA` al 1% retirando revisión y
aprobación, y la cadena se rehace sobre el importe correcto. Lo reconstruí con el **código
pre-misión real**, no con SQL a mano.

Pero encontré **dos rutas por las que el resultado que A2 describe sigue ocurriendo**:

1. **Se paga un importe que no es el 1% oficial vigente** (bloqueante A1 abajo). Ruta 100% pública,
   sin base legada. La guarda comprueba la *etiqueta* `CANONICA_APROBADA`, que es un sello del
   pasado, no la política vigente.
2. **La comisión se destruye** (bloqueante A2 abajo). Una base piloto real que nunca tuvo política
   configurada produce `REVISADA`/`APROBADA` sin porcentaje; tras migrar quedan
   `SIN_POLITICA_APLICADA`: ni pagables ni alcanzables por la reparación.

---

## Invariantes reproducidos

**1. Un solo porcentaje.** **SE SOSTIENE.** Base legada con tres alcances → una sola fila `GENERAL`
al 1%; las dos retiradas en `central_audit` con su `rate_bp` previo. Barrido de escrituras: dos
`INSERT` y un `DELETE`, ningún `UPDATE`, ambos `INSERT` con `scope='GENERAL'` literal.

**2. Traza completa ⟺ política aprobada.** **SE SOSTIENE en su forma verificable.**

**3. Idempotencia con traza.** **SE SOSTIENE.** Primer pase `changed=N`, siguientes `changed=0`;
una sola entrada `COMMISSION_POLICY_REPAIRED`; el 5% no se reaplica.

**4. Sólo la política vigente llega al pago.** **FALSO.** Ver bloqueante A1.

**5. Un cambio de política no mueve dinero pasado.** **SE SOSTIENE** para lo pagado. La segunda
mitad («nada que haya movido dinero es alcanzable por `recalculate`») es **falsa como enunciado**:
ver bloqueante A3.

**Decimal / HALF_UP / ausencia de floats.** **SE SOSTIENE.** Cero literales float. Medio guaraní
sube y no redondea al par: 50→1, 150→2, 250→3, 475.050×1%→4.751, (10¹⁸+50)×1%→10¹⁶+1.

**Migración sin importes e idempotente.** **SE SOSTIENE.** Ni un importe se mueve; políticas,
versiones y auditoría idénticas tras cuatro re-migraciones.

**Invariantes heredados.** **TODOS SE SOSTIENEN.** Común comisiona sólo al cancelarse; 5% exactamente
una vez; nada que movió dinero llega a `REVERTIDA` (probé cuatro vías); libro append-only única
fuente de `paid_amount`; ninguna comisión sobre venta anulada o con saldo.

**Concurrencia** (8–16 hilos, `BEGIN IMMEDIATE`, repeticiones). **SE SOSTIENE.** `mark_paid`:
exactamente un `ok`. `approve`: exactamente un `ok`. `set_general_rate`: versiones consecutivas y
únicas. `recalculate` ×6 concurrentes: `changed` total = 5, exactamente 5 eventos. **Reparación vs
pago sobre la misma liquidación legada**: `paid_at` queda `NULL` siempre, a lo sumo un
`COMMISSION_POLICY_REPAIRED`, una sola fila.

---

## Riesgo introducido por la reparación

| Criterio | Resultado |
|---|---|
| Nunca alcanza nada con `paid_at` | **NO.** La cláusula sólo cuelga de la rama `REVISADA`/`APROBADA`. Ver A3. |
| Retira revisión y aprobación de forma consistente | **SÍ.** |
| Idempotente | **SÍ.** |
| Auditada con el importe reemplazado | **SÍ.** `details.replaced` con el importe anterior. |
| No revive ni duplica liquidaciones | **SÍ.** Sólo `UPDATE`, nunca `INSERT`. |
| No rompe la idempotencia general | **SÍ.** |
| Índice único de liquidación activa intacto | **SÍ.** `PRAGMA integrity_check = ok`. |
| Concurrencia reparación ↔ pago | **SÍ.** |

**Riesgo propio no cubierto por el paquete:** para una liquidación legada cuyo período es anterior a
la vigencia, la reparación la deja `CALCULADA`/`FUERA_DE_VIGENCIA` con `commission_amount = NULL`.
El importe anterior queda auditado, pero la tabla de `MIGRATION.md` promete «vuelve a `CALCULADA`
al 1%», que no es lo que ocurre.

---

## Bloqueantes

### A1 — Se paga un importe que no es el porcentaje oficial vigente (deriva de versión)

`_require_official_calculation` comprueba `policy_status = CANONICA_APROBADA`, que es un sello
grabado en el momento del cálculo, no la política en vigor. Tras `set_general_rate`, toda
liquidación ya calculada conserva el sello con su tasa anterior y **pasa las tres guardas**.

```
register_sale(convenio 500.000) → recalculate()      # 4.750, CANONICA_APROBADA v1
set_general_rate(SOL, 50, "2026-08-01")              # nueva política oficial 0,5%, v2
review → approve → mark_paid                          # PAGADA 4.750
```

Pagado 4.750; oficial vigente sobre la misma base, según el propio `decide()`, 2.375. **El doble.**
Simétrico hacia arriba: con la política al 3% se paga 4.750 en vez de 14.250.

Prueba decisiva: dos ventas idénticas, mismo local, misma vendedora, mismo período, ambas
`CANONICA_APROBADA` al pagarse, **importes distintos** según si alguien corrió `recalculate` entre
medio. El importe oficial depende del orden en que un humano apretó los botones.

Falsifica textualmente el invariante 4 de `ARCHITECTURE_DELTA.md`, el apartado homónimo de
`COMMISSION_POLICY_1PCT.md` y la protección tercera de `SUMMARY.md`. La justificación de diseño
—«no recalcular para no mover dinero pasado»— no cubre este caso: la liquidación **no estaba
pagada**, y el pago ocurre después del cambio de política.

### A2 — Liquidación legada sin porcentaje: impagable, irreparable, y el único remedio la destruye

El código pre-misión no exigía porcentaje ni para revisar, ni para aprobar, ni para pagar, y sin
política configurada `rate_for` devolvía `(None, "SIN_POLITICA_CONFIGURADA")`. Una base piloto sin
política —el estado por defecto— produce por tanto `REVISADA`/`APROBADA` con `rate_bp IS NULL`.

Lo construí **ejecutando ese código real**. Tras la migración: `SIN_POLITICA_APLICADA`, no pagable
(correcto), **no reparable** (`evaluated=0`), y el único camino disponible (`observe` → `revert`) la
deja `REVERTIDA` sin reemplazo. La comisión se destruye. Es literalmente la segunda mitad del
bloqueante A2 de la generación 1, vigente para esta variante.

### A3 — Afirmación de invariante falsa: `recalculate` sí alcanza filas con `paid_at`

`SUMMARY.md`, el docstring de `recalculate` y el invariante 5 de `ARCHITECTURE_DELTA.md` afirman que
nada con `paid_at` es alcanzable. **Las tres son falsas**: la cláusula `paid_at IS NULL` sólo protege
la rama de reparación. Con `status IN ('ELEGIBLE','CALCULADA')` y `paid_at` no nulo, `recalculate`
reescribe tasa e importe y la deja pagable: verifiqué la cadena completa, que produce un **segundo
pago** pisando `paid_at`.

Ningún camino del código actual produce ese estado, de modo que hoy no es explotable. Lo listo como
bloqueante porque es una afirmación de invariante falsa en un paquete cuyo objeto son los
invariantes económicos, porque el propio módulo se niega a confiar en `status` para esto (`_was_paid`
existe precisamente por eso), y porque el bloqueante A1 de la generación 1 fue exactamente esto. La
corrección es una cláusula: subir `AND paid_at IS NULL` al `WHERE` completo.

---

## Observaciones no bloqueantes

1. **«Exactamente cuando» es literalmente falso.** La formulación exacta es: traza completa ⟺
   `policy_status ∈ {CANONICA_APROBADA, FUERA_DE_VIGENCIA}`.

2. **`MIGRATION.md` describe mal la reparación de períodos anteriores a la vigencia.**

3. **Sin separación de funciones sobre el porcentaje.** `set_general_rate` y `mark_paid` exigen el
   mismo permiso. Un mismo principal publica una política del 100%, recalcula y cobra 475.000 sobre
   una base de 475.000.

4. **Único float del módulo, en una etiqueta.** `AGREEMENT_DISCOUNT_BP / 100:.0f`, mientras la línea
   gemela usa `//`.

5. **Nota engañosa en una `PAGADA` sin política.** Dice «recalcule para obtener la comisión oficial»
   y `recalculate` jamás la tocará.

6. **Cifras de evidencia verificadas.** `tests/gestion_central` → 123/123 PASS. No audité el conteo
   global ni el `MANIFEST.sha256` (fuera de mi mandato).

VERDICT: FAIL
