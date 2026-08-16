# Informe de auditoría independiente — invariantes económicos

| | |
|---|---|
| **Runner** | AUDITOR-IND-COMISION-POLICY-1PCT-001 |
| **Rol** | Auditor independiente de invariantes económicos (trabajo aislado; sin conocimiento de Librarian ni QA) |
| **Snapshot** | `578bf8b7205c857f9032581744f1e5818dab99fa` — worktree `gc-comision-policy-1pct-001` |
| **Timestamp UTC** | 2026-08-16T03:33:08Z |
| **Worktree al cierre** | limpio (`git status --porcelain modulos tests` → 0 líneas); toda prueba se escribió en scratchpad |
| **Suite del snapshot** | 317/317 PASS (reproducido por mí, 27 s) |

Método: no reutilicé ni una sola aserción del paquete. Escribí cinco arneses propios (`a1`–`a6`) que reconstruyen bases legadas con el **código anterior al commit** (`git show HEAD~1`), instrumentan el SQL real de la migración vía `set_trace_callback`, comparan la aritmética contra `Fraction` exacto, y ejercitan concurrencia real con hilos y barreras.

---

## Invariantes reproducidos

### A. Una sola fila `GENERAL`, ninguna ruta escribe otro alcance — **VERDADERO**
- Base nueva: 1 fila (`GENERAL`/`''`/100 bp/`CANONICA_APROBADA`).
- Base legada con 3 alcances (`GENERAL` 3 %, `LOCAL:L1` 4,5 %, `VENDEDORA:V1` 7 %): tras migrar queda **exactamente 1 fila** `GENERAL` al 1 %.
- Barrido de escrituras a `commission_policies` en todo el código productivo: **2 `INSERT`** (`comisiones.py:668`, `repository.py:240`) y **1 `DELETE`** (migración). Ningún `UPDATE`. Ambos `INSERT` fijan `CANONICAL_SCOPE` y `scope_value=''` como literales. `set_policy` ya no existe; `set_general_rate` no acepta `scope` ni `scope_value`.
- Refutación intentada por estado forjado a mano (`scope='GENERAL', scope_value='L1'`): sobrevive y quedan 2 filas — pero **no es alcanzable**: el `set_policy` anterior forzaba `scope_value = ""` para `GENERAL`. Ver observación 3.

### B. Traza inseparable del importe — **FALSO sobre base migrada** (ver bloqueante A1)
- Sobre base nueva: verdadero y sólido. 0 filas con `rate_bp` no nulo y traza incompleta; 0 filas con importe sin porcentaje; una corrección de origen tira importe **y** las cinco columnas de traza en el mismo `UPDATE`; el período fuera de vigencia queda sin importe con motivo.
- Sobre base migrada: **4 de 4** liquidaciones legadas quedan con `rate_bp=700` y `policy_code = policy_version = policy_effective_from = policy_scope = NULL`. Tras recalcular, **3 quedan así para siempre** (`REVISADA`, `APROBADA`, `PAGADA`).

### C. `recalculate` idempotente incluyendo los cinco campos de política — **VERDADERO**
- `{evaluated:6, changed:6}` → `changed:0` → `changed:0`; filas byte-idénticas incluido `updated_at`; el historial no crece.
- Refutación por corrupción dirigida: corrompí **uno por uno** `policy_code`, `policy_version`, `policy_effective_from`, `policy_scope` y `policy_status`. En los cinco casos `changed == 1` y el valor se corrige. La comparación cubre realmente los cinco campos.

### D. Nada sin porcentaje llega al pago — **VERDADERO en su literal**
- `review` rechaza (`FUERA_DE_VIGENCIA`, `rate_bp` nulo) y el estado no se mueve.
- Forcé `status='APROBADA'` por SQL directo: `mark_paid` igual rechaza; no queda `paid_at` ni referencia.
- Con `rate_bp=100` y `commission_amount=NULL`: también rechaza.
- `paid_at` se escribe en **un único sitio** (`comisiones.py:606`, dentro de `mark_paid`, guardado); nadie lo limpia.
- Advertencia: la guarda prueba **no-nulidad**, no **vigencia** de la política. Ver bloqueante A2.

### E. Un cambio de política no mueve dinero ya liquidado — **VERDADERO**
- Con `PAGADA`/`APROBADA`/`REVISADA`/`OBSERVADA`/`REVERTIDA`/`CALCULADA` en base, publicar v2 al 9 % **no toca ni una columna** de ninguna liquidación (diff fila a fila, todas las columnas).
- El `recalculate` posterior sólo alcanza `CALCULADA`. La `PAGADA` conserva 4.000 Gs al 1 % v1; la `CALCULADA` adopta 36.000 Gs al 9 % v2.
- `set_general_rate` idempotente al repetir porcentaje+vigencia; `commission_policy_versions` append-only (v1 intacta).

### 1. Ausencia real de floats — **verdadero en el camino monetario**
No me conformé con `"float(" not in source`. Verifiqué la propiedad:
- `FloatOperation` **trapeado** en el contexto decimal: las siete funciones de `comision_policy` corren sin excepción → no mezclan `float` con `Decimal`.
- Bytecode: **cero constantes `float`** en los tres módulos.
- Barrido de operadores `BINARY_OP /` en bytecode: 2 sitios en `comision_policy` (ambos `Decimal/Decimal`), 2 en `comisiones_ui` (`pathlib`), y **1 float real** en `comisiones.py:800`. Ver observación 1.
- `pyg()` formatea con `int(value or 0)`.
- SQLite: `typeof()` sobre las 9 columnas monetarias → sólo `integer`/`null`, nunca `real`.
- Export contrato v2 recorrido recursivamente: **ni un `float`**; `rate_percent` es `"1.00"` (texto); KPI de comisión = suma exacta que yo recalculé.

### 2. Exactitud Decimal y redondeo único — **verdadero**
- 200.000 casos aleatorios + bordes contra HALF_UP exacto sobre `Fraction`: **0 divergencias**. Confirma HALF_UP genuino, no bancario (12.350 → 124, 12.450 → 125).
- Cociente por 10.000 **exacto**: con `Inexact` y `Rounded` trapeados en prec 60, la división no dispara ninguno.
- **Magnitudes donde prec 60 no alcanza** (lo que se me pidió buscar): el producto se vuelve inexacto a partir de ~10⁵⁷ Gs, pero busqué explícitamente resultados *silenciosamente mal* en el rango 10⁵⁰–10⁶⁵ y **no existe ninguno**: a partir de ~10⁶¹ Gs `quantize` lanza `InvalidOperation`. El modo de falla es ruidoso, no corrupción callada. Exacto hasta 10⁵⁰ Gs, treinta órdenes de magnitud por encima de la masa monetaria mundial.

### 3. La migración no escribe ningún importe — **verdadero**
Instrumenté todo el SQL de `migrate()` sobre base legada. Once sentencias mutantes; los cuatro `UPDATE commission_entries` tocan **sólo** `policy_status`. Ningún `SET` menciona `rate_bp`, `commission_amount`, `gross_amount`, `commissionable_base` ni `agreement_discount`. Comparación fila a fila antes/después: **0 importes cambiados, 0 estados cambiados**.

### 4. Retiro por alcance auditado con valor previo — **verdadero para lo alcanzable**
Las tres políticas previas quedaron en `central_audit` como `COMMISSION_POLICY_RETIRED` con su `rate_bp` exacto (300/450/700), su `approval_status` previo y `replaced_by`. Verifiqué el **orden**: todo `DELETE` va precedido de su asiento. Hueco residual no alcanzable: observación 2.

### 5. Idempotencia de la migración al reabrir — **verdadero**
40 reaperturas consecutivas: políticas, versiones y liquidaciones **idénticas**; la auditoría **no crece** (6 → 6); una sola versión canónica. Además verifiqué lo inverso, que nadie probó: reabrir **no pisa** un porcentaje legítimamente publicado por el operador (250 bp v2 sobrevive 10 reaperturas).

### 6. Concurrencia — **verdadero**
- **`mark_paid`**, 16 hilos con barrera, 3 repeticiones: siempre **1 OK / 15 `ValueError`**, un solo asiento `COMMISSION_PAID`, la referencia grabada es la del único éxito. Cero `OperationalError`.
- **`set_general_rate`**, 16 hilos mismo porcentaje: **1 sola versión creada**. 24 hilos con porcentajes distintos: versiones **1..25 consecutivas, sin huecos ni duplicados**, `UNIQUE(policy_id,version)` nunca violado, la fila vigente coincide con la última versión del historial. Cero errores de bloqueo.
- **`register_payment`**, 12 hilos por el saldo total: 1 aceptado, `paid_amount == libro`, sin sobrecobro. Con `idempotency_key` concurrente: **1 solo cobro**.

### 7. Invariantes económicos heredados — **verdaderos**
- Venta común: con saldo → base 0 sin comisión; cobro parcial insuficiente → sigue sin comisionar; al cancelarse totalmente → 4.000 Gs.
- Convenio: 500.000 → descuento 25.000, base 475.000, comisión 4.750, **estable tras tres recálculos**; corregido a 600.000 → 30.000/570.000/5.700. El 5 % se aplica exactamente una vez.
- Liquidación que movió dinero **nunca** llega a `REVERTIDA`: probé cuatro vías (`revert` directo, `observe`→`revert`, `revert_payment`, `void_sale`). Todas terminan en `PAGADA`/`OBSERVADA`. Cero filas `REVERTIDA` con `paid_at`.
- Libro append-only: **cero** `UPDATE`/`DELETE` sobre `commission_payments` en código productivo; las tres asignaciones de `paid_amount` provienen de `_settled_amount`; `paid_amount` cuadra con la suma neta del libro en todas las ventas.

### 8. Ninguna comisión sobre venta anulada o con saldo — **verdadero**
Anulada → `REVERTIDA`, fuera del `WHERE` del recálculo, KPI 0. Con saldo → nunca recibe `rate_bp` tras tres recálculos. Reversión de cobro reabre saldo y deja la comisión en 0. Barrido global: **0 liquidaciones vivas con importe sobre venta anulada o con saldo**.

---

## Bloqueantes

**A1 — El invariante B declarado es FALSO sobre toda base migrada.**
`ARCHITECTURE_DELTA.md` §2 afirma sin salvedad: «Si `rate_bp` no es nulo en una liquidación calculada, su `policy_code`, `policy_version` y `policy_effective_from` describen la política que lo produjo (traza inseparable del importe)». Reconstruí una base del piloto anterior con el código de `HEAD~1` y la migré: **4 de 4** liquidaciones quedan con `rate_bp=700` y las cuatro columnas de traza en `NULL`. `NULL` no describe ninguna política. `recalculate` repara sólo la `CALCULADA`; `REVISADA`, `APROBADA` y `PAGADA` **quedan permanentemente con importe y sin traza**, por diseño del `WHERE`. La migración añade las columnas como anulables y nunca las puebla. El importe y su traza sí son separables, y quedan separados exactamente en las liquidaciones que ya movieron o están por mover dinero. Reproducción: `a5_legado.py`.

**A2 — Fuga económica real: el porcentaje retirado llega al pago por el flujo normal, y el remedio documentado no existe.**
La guarda `_require_official_calculation` (`comisiones.py:97-102`) sólo comprueba **no-nulidad**, no que el porcentaje sea el vigente. Consecuencias reproducidas end-to-end sobre base migrada, sin tocar SQL, usando sólo la API pública que la pantalla invoca:

1. Una `APROBADA` legada se paga con `mark_paid` **sin ninguna objeción**: 33.250 Gs contra los 4.750 Gs oficiales — **×7, +28.500 Gs por liquidación**. Con el 3 % sintético que `MIGRATION.md` cita como caso real, es ×3. La `PAGADA` resultante es irreversible por diseño (invariante 7, que sí se cumple).
2. Una `CALCULADA` legada admite `review`→`approve`→`mark_paid` **antes de que nadie pulse Recalcular**, con el mismo resultado. `MIGRATION.md` promete en su tabla que el primer `recalculate` la corrige, pero **nada lo fuerza** y este caso no figura entre los hallazgos abiertos.
3. En el mismo instante, `breakdown` rotula la línea **«Comisión oficial (7,00 % de la base)»** — llama «oficial» al porcentaje que la migración acaba de retirar — mientras el encabezado, el KPI y la cabecera de columna de la pantalla dicen «Comisión oficial 1,00 %» y el KPI suma importes al 7 %. El export v2 abre con `rate_percent: "1.00"` y `policy_disclaimer` «igual para toda vendedora y local» sobre entradas al 7 % con `policy_code: null`. La pantalla afirma el 1 % y liquida el 7 %.
4. **La salida manual que el paquete declara no funciona.** `HANDOFF.md` §6 y `MIGRATION.md` afirman que la corrección es «observar o revertir y volver a calcular». La ejecuté: `observe` → `revert` → `recalculate` deja la venta **sin ninguna liquidación viva**; el recálculo evalúa 0 filas y la comisión legítima de 4.750 Gs **desaparece del reporte** (KPI base 0, comisión 0). No existe ruta al importe correcto: o se paga ×7, o se pierde entera. Reproducción: `a6_salida_manual.py`.

El paquete divulga que estas liquidaciones «no se corrigen solas» y quedan visibles; no divulga que son **pagables tal cual al porcentaje retirado**, ni que el remedio que propone destruye la comisión. La misión existe precisamente para las bases del piloto sintético, que son exactamente las que exhiben esto.

---

## Observaciones no bloqueantes

1. **Único float real del módulo: `comisiones.py:800`.** `AGREEMENT_DISCOUNT_BP / 100:.0f` es división verdadera y produce `5.0`. Es una etiqueta de texto sobre una constante exactamente representable, nunca toca un importe, y la línea gemela `:821` usa `// 100` sobre la misma constante. No hay riesgo económico, pero contradice literalmente el docstring («no se usan floats en ningún punto») y confirma con un caso concreto el hallazgo abierto 3 del handoff: `assert "float(" not in source` no detecta esto.

2. **Reemplazo no auditado de una `GENERAL` con estado desconocido.** Si `commission_policies` tiene una fila `GENERAL` cuyo `approval_status` no está en `RETIRED_POLICY_STATUSES` ni es `CANONICA_APROBADA`, la migración la pisa con el 1 % **sin asentar el valor previo** (verificado: 777 bp → 100 bp, 0 asientos de retiro). No alcanzable: el `set_policy` anterior sólo escribía `SINTETICA_PENDIENTE_APROBACION`. Es robustez frente a base editada a mano, no un defecto vivo.

3. **Fila `GENERAL` con `scope_value` no vacío sobrevive la migración**, dejando 2 filas y rompiendo «exactamente una». Tampoco alcanzable: el código anterior forzaba `scope_value = ""` para `GENERAL`. El predicado de retiro (`approval_status IN (...) OR scope<>'GENERAL'`) podría cerrarse a `OR scope_value<>''`.

4. **Doble redondeo en el convenio.** La cadena es `HALF_UP(descuento)` → `HALF_UP(comisión)`, no un único redondeo final. Es correcto: el descuento del 5 % es en sí un importe entero en guaraníes. Medí la divergencia contra el cálculo en una sola pasada sobre los totales 1..399.999: **1.800 casos, siempre exactamente 1 Gs**. Irrelevante económicamente, pero la frase «el único redondeo del cálculo es el HALF_UP final» describe `apply_basis_points`, no la cadena del convenio.

5. **`localcontext()` hereda la política de redondeo ambiente.** `apply_basis_points` fija `prec=60` pero no `rounding` ni las trampas; el redondeo explícito sólo se pasa en `quantize`. Hoy es inocuo porque la división es exacta en todo rango realista, pero un llamador que altere el contexto global no sería detectado (`Inexact` no está trapeado).

6. **`prec=60` falla ruidosamente, no en silencio.** Por encima de ~10⁶¹ Gs, `quantize` lanza `InvalidOperation` en lugar de devolver un importe corrupto. Es el modo de falla correcto y vale la pena dejarlo dicho en el contrato.

7. **`POLICY_LEGACY` sin defensa de nulidad.** `_policy_note` hace `int(rate)` en la rama `POLITICA_HISTORICA_PREVIA`. Hoy la migración garantiza `rate_bp IS NOT NULL` para esa etiqueta, así que no es alcanzable; ninguna guarda lo valida (relacionado con el hallazgo abierto 7 del handoff, `POLICY_STATUSES` definido y no usado).

8. **La bandeja no muestra `rate_bp` ni `policy_status` como columna.** `ENTRY_COLUMNS` no los incluye; el operador sólo ve la discrepancia si selecciona la fila y lee la nota del desglose. Es lo que hace invisible el bloqueante A2 en la práctica.

---

VERDICT: FAIL
