# VERDICT_QA — Generación 4

| Campo | Valor |
|---|---|
| Misión | BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 |
| Generación | 4 |
| Rol | QA-IND-COMISION-POLICY-1PCT-004 (revisión funcional independiente) |
| Snapshot revisado | `5652e46ce7127060ed50d96e464e732809351550` (verificado con `git rev-parse HEAD`) |
| Worktree | `.worktrees\gc-comision-policy-1pct-001` |
| Módulo | `modulos/gestion_central/` (`comisiones.py`, `comision_policy.py`, `comisiones_ui.py`, `repository.py`) |
| Escenarios propios | `…\scratchpad\qa-gen4\` (`harness.py`, `s1_b1.py`, `s2_settled.py`, `s3_gaps.py`, `s4_revert_exploit.py`, `s5_b2.py`, `s6_money.py`, `s7_rest.py`, `s8_export.py`, `s9_o1.py`) |
| Árbol al empezar | limpio (`git status --porcelain` vacío) |
| Árbol al terminar | limpio (`git status --porcelain` vacío) — cero escrituras en el repositorio |
| Timestamp UTC | 2026-08-18T01:40:39Z |
| **VEREDICTO** | **PASS** |

---

## 1. Método

No reutilicé las pruebas del paquete para formar juicio. Construí un arnés propio (`harness.py`) que levanta `CommissionService` sobre una base SQLite temporal por escenario, y escribí diez escenarios independientes que atacan B1, B2, la exactitud monetaria y —explícitamente— los huecos que el paquete no cubre. La regresión del paquete se ejecutó **al final**, sólo como confirmación (88 pruebas del módulo, 345 de la suite completa, todas verdes).

Donde necesité reconstruir estados que el producto ya no permite alcanzar por su API (una liquidación heredada de un período anterior a la vigencia, con sello de política antigua), lo hice por SQL directo sobre la base temporal, nunca tocando el repositorio.

---

## 2. Cierre de B1 — vigencia que re-tarifa un período ya liquidado

**Bloqueante original:** `set_general_rate` aceptaba una vigencia *igual* a la última publicada; como `is_in_effect` resuelve por mes, esa vigencia gobernaba exactamente los mismos períodos que la anterior, incluidos los ya liquidados, que se re-tarifaban al alza o a cero y se pagaban.

**Decisión de propietario aplicada:** opción (a), endurecer la guarda. El código añade una segunda guarda: además de prohibir el retroceso estricto (`effective_from < MAX(effective_from)`), rechaza toda vigencia cuyo mes no sea **posterior** al último período con liquidaciones en `CALCULADA/REVISADA/APROBADA/PAGADA` (`SETTLED_STATES`).

### Lo que verifiqué por mi cuenta

**2.1 Vigencia anterior — rechazada.** (`s1_b1.py`)
```
1.1 anterior: ('ValueError', 'la vigencia no puede retroceder: la última publicada rige desde 2026-08-01')
```

**2.2 Vigencia igual y vigencia dentro del mes ya liquidado — rechazadas, en los cuatro estados liquidados.** (`s2_settled.py`) Para cada uno de `CALCULADA`, `REVISADA`, `APROBADA`, `PAGADA` llevé una venta común de 400.000 hasta ese estado en el período 2026-08 e intenté publicar 5% con vigencia `2026-08-01` (igual a la publicada) y `2026-08-20` (mitad del mes ya liquidado):

```
PASS  [CALCULADA] vigencia igual rechazada | la vigencia 2026-08-01 gobernaría el período 2026-08, que ya…
PASS  [CALCULADA] vigencia mismo mes rechazada | la vigencia 2026-08-20 gobernaría el período 2026-08, que ya…
PASS  [REVISADA]  … | PASS [APROBADA] … | PASS [PAGADA] …   (12/12)
```

**2.3 Vigencia futura válida — aceptada, y el período cerrado no se mueve.** En los cuatro estados, `set_general_rate(500, "2026-09-01")` devolvió `(2, True)` y el importe de agosto siguió siendo 4.000 con `rate_bp=100`.

**2.4 La vía indirecta —publicar y recalcular— tampoco toca el período cerrado.** Tras publicar la versión futura ejecuté `recalculate` sin filtros:
```
[CALCULADA] recalculate no re-tarifa | ({'evaluated': 1, 'changed': 0}, 'CALCULADA', 100, 4000)
[REVISADA]  … ('REVISADA', 100, 4000)     [APROBADA] … ('APROBADA', 100, 4000)
[PAGADA]    … ({'evaluated': 0, …}, 'PAGADA', 100, 4000)
```
`REVISADA` y `APROBADA` conservan además su aval, porque `in_force_for(period)` resuelve por período y la versión de septiembre no gobierna agosto. `PAGADA` ni siquiera es evaluada (`paid_at IS NULL` cuelga del `WHERE` entero).

**2.5 La idempotencia de republicar lo idéntico sobrevive a la guarda nueva.** (`s3_gaps.py`) Con el período 2026-08 ya liquidado, republicar 100 bp desde 2026-08-01 —que la guarda de período liquidado rechazaría— devuelve `(1, False)` sin excepción y sin crear versión. Esto funciona porque el retorno idempotente está **antes** de la guarda de período liquidado; el orden es correcto y es lo que evita que la operación segura se vuelva un error.

**2.6 `ELEGIBLE` no cuenta como liquidado.** Una entrada `ELEGIBLE` (y una `PENDIENTE_SALDO`) en 2026-08 no bloquea publicar con vigencia 2026-08-01; tras recalcular toma la tasa nueva (300 bp → 12.000). Correcto: elegible es «pendiente de cálculo», todavía no se le aplicó porcentaje alguno.

**Conclusión B1: cerrado desde mi ángulo funcional.** La guarda cubre los cuatro estados liquidados, no rompe la idempotencia, no confunde `ELEGIBLE` con liquidado, y bloquea tanto la vía directa como la indirecta.

---

## 3. Cierre de B2 — asiento `replaced` y reparación del período anterior a la vigencia

**Bloqueante original:** `recalculate` sólo asentaba `replaced` en las ramas `REVISADA`/`APROBADA`, y no reparaba el período anterior a la vigencia; un importe retirado desaparecía sin dejar rastro en ninguna ruta pública.

### Lo que verifiqué por mi cuenta (`s5_b2.py`)

**3.1 Período anterior a la vigencia, en las cuatro ramas.** Instalé por SQL una liquidación heredada del período `2025-06` con `rate_bp=500` y `commission_amount=20.000`, en cada uno de `ELEGIBLE`, `CALCULADA`, `REVISADA` y `APROBADA`, y recalculé:

```
PASS  [ELEGIBLE]  periodo previo a vigencia queda sin porcentaje | ('CALCULADA', None, None, 'FUERA_DE_VIGENCIA')
PASS  [ELEGIBLE]  asiento replaced presente y correcto | [{'rate_bp': 500, 'commission_amount': 20000, 'policy_status': 'CANONICA_APROBADA'}]
PASS  [CALCULADA] … idénticos      PASS [REVISADA] … idénticos      PASS [APROBADA] … idénticos
```
El importe retirado (500 bp / 20.000) queda íntegro en `commission_entry_history.details_json.replaced` en las cuatro ramas, incluidas `ELEGIBLE` y `CALCULADA`, que era exactamente el hueco de B2.

**3.2 El asiento no se repite.** Un segundo `recalculate` sobre el mismo estado devuelve `{'evaluated': 1, 'changed': 0}` y el número de filas de historial no cambia (2 → 2) en las cuatro ramas.

**3.3 El asiento no se inventa cuando no había importe previo.** Una `ELEGIBLE` recién creada, sin `rate_bp` ni `commission_amount`, produce un `COMMISSION_RECALCULATED` **sin** clave `replaced`.

**3.4 Cambio de tasa antes de la revisión.** Con la entrada en `ELEGIBLE` y período 2026-09, publicar 200 bp desde 2026-09-01 y recalcular da 8.000 y asienta `replaced = {rate_bp: 100, commission_amount: 4000, policy_status: CANONICA_APROBADA}`. La variante `CALCULADA` de ese mismo escenario **no es alcanzable**: la guarda de B1 rechaza la publicación porque la entrada ya está liquidada. Mi escenario la marcó FAIL y al inspeccionarlo resultó ser la guarda funcionando; lo dejo consignado porque la interacción es informativa, no un defecto: en el producto real la única vía por la que una `CALCULADA` cambia de importe es la corrección de origen o la reparación por política fuera de vigencia, y ambas asientan `replaced`.

**Conclusión B2: cerrado desde mi ángulo funcional.** Todo importe anulado o reemplazado queda asentado, en todas las ramas alcanzables, sin repetición y sin invención (con la matización de O3).

---

## 4. Exactitud monetaria — sin cambios (`s6_money.py`)

- Barrido exhaustivo de `apply_basis_points` sobre 0..20.000 guaraníes × cinco tasas (1, 100, 333, 500, 10000 bp) contra `Decimal(...).quantize(Decimal(1), ROUND_HALF_UP)` calculado independientemente: **100.005 casos, cero divergencias.**
- Medio guaraní exacto redondea hacia arriba en sus bordes: 50→1, 150→2, 250→3, 350→4, 450→5; 49→0.
- Venta común 400.000 → base 400.000 → comisión 4.000.
- Convenio 500.000 → descuento 25.000 → base 475.000 → comisión 4.750. El orden 5% antes de 1% se conserva.
- Venta común con saldo: `PENDIENTE_SALDO`, sin comisión pagable (`commission_amount is None`); `review` la rechaza por transición inválida.
- Venta anulada: la entrada queda `REVERTIDA` sin liquidación activa, conservando su importe histórico como auditoría.
- Barrido de las tres fuentes del módulo: cero aritmética en coma flotante.
- Export: `contract_version: 2`, bloque `policy` completo (código, alcance, versión, vigencia, `rate_bp`, `rate_percent`, `rounding: HALF_UP`, `currency: GS`) y traza de política por entrada (`policy_status/code/version/effective_from/scope`), sin dato alguno de cliente.
- Persistencia y reapertura: importe, tasa y versión de política sobreviven; la reapertura no duplica versiones de política ni entradas.
- UI: `comisiones_ui.py` mantiene las columnas «Base comisionable» y «Comisión oficial» en ambos anchos (1920 y compacto) y encabeza el panel con `Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1`, derivado de `rate_percent_text`, no escrito a mano.

---

## 5. Bloqueantes

**Ninguno.**

Busqué activamente los tres huecos que pedía el encargo —un estado o secuencia donde la guarda no aplique y debería, una ruptura de la programación legítima hacia adelante, y una rama donde el asiento `replaced` se pierda— y ninguno produjo un comportamiento económicamente incorrecto que justifique un bloqueante. Lo que sí encontré está abajo, con su reproducción, porque el propietario debe verlo.

---

## 6. Observaciones no bloqueantes

### O1 (heredada de la generación 3) — **sigue abierta, pero acotada**

Una vigencia a mitad de mes se sigue aplicando desde el día 1 de ese mes, porque `is_in_effect` compara `período[:7] >= effective_from[:7]`. La guarda nueva **no la cierra: la acota.**

Reproducción (`s9_o1.py`), con dos ventas de septiembre aún `ELEGIBLE`:
```
publicar 5% desde 2026-09-15: ('OK', (2, True))
  venta 2026-09-02: rate=500 com=20000 eff=2026-09-15
  venta 2026-09-25: rate=500 com=20000 eff=2026-09-15
```
La venta del **2** de septiembre cobra la tasa que declara regir desde el **15**.

Lo que la guarda sí cambió: si ese mismo mes ya tiene alguna liquidación calculada, la publicación se rechaza por completo.
```
publicar 5% desde 2026-09-15: la vigencia 2026-09-15 gobernaría el período 2026-09, que ya fue liquidado…
```

En términos precisos: **la guarda de B1 elimina la mitad económicamente grave de O1 —la retroactividad sobre importes ya calculados, revisados, aprobados o pagados— y deja en pie la mitad benigna: la retroactividad dentro del mes en curso sobre liquidaciones que aún no tienen porcentaje aplicado.** El residuo sigue siendo una discrepancia entre lo que la vigencia declara (día 15) y lo que gobierna (todo el mes), y sigue siendo un dato que el sello de la liquidación registra fielmente (`policy_effective_from: 2026-09-15` sobre una venta del día 2). Recomiendo cerrarla en una generación futura por una de dos vías: rechazar en `normalize_effective_from` toda vigencia que no sea día 1 de mes, o hacer que `is_in_effect` resuelva por fecha de cancelación y no por mes. No bloquea porque no hay dinero mal pagado: ninguna liquidación afectada tenía importe previo.

### O2 — revertir una liquidación reabre su mes para re-tarifación retroactiva

La guarda de período liquidado consulta sólo `SETTLED_STATES`. Una entrada llevada a `REVERTIDA` (o una `PAGADA` llevada a `OBSERVADA`) deja de contar, y su mes vuelve a ser publicable.

Reproducción (`s4_revert_exploit.py`):
```
original: CALCULADA 100 4000
publicar 100% agosto: ('OK', (2, True))
nueva entrada: CALCULADA 2026-08 10000 400000
```
Una venta común de agosto ya calculada al 1% termina, tras `revert` + publicar 100% con vigencia de agosto + re-declaración de origen, comisionando 400.000 — y esa entrada es pagable, porque `_require_current_policy` la compara contra la versión que ahora gobierna agosto y coincide.

No lo elevo a bloqueante por cuatro razones concretas que verifiqué: (a) exige un `REVERTIDA` explícito, que es una acción destructiva y auditada, no un efecto silencioso —que era la naturaleza de B1—; (b) `revert` rechaza toda liquidación que movió dinero (`_reject_paid`), así que ningún importe pagado es alcanzable por esta ruta; (c) la entrada original conserva íntegros su importe, su sello de política y su historial; (d) el contrato que la guarda declara en su propio docstring —«no se re-tarifa **por esta vía**»— se cumple: la vía es otra. Aun así, es el camino por el que un operador con `reviews.manage` obtiene de hecho el «flujo de corrección explícito y auditado» que el docstring declara inexistente, y el propietario debería decidir si quiere que la guarda considere también los períodos de las entradas `REVERTIDA` y `OBSERVADA`.

Verifiqué además la variante `PAGADA → OBSERVADA` (`s3_gaps.py` 3.5): publicar para ese mes queda permitido, pero el importe pagado sigue intacto en 100 bp / 4.000 tras recalcular, porque `OBSERVADA` es un estado sin salida hacia el cálculo. Ahí no hay daño económico alcanzable.

### O3 — `replaced` se asienta con valores nulos cuando no había nada que reemplazar

En la rama de reparación (`repairing = status in {REVISADA, APROBADA}`) el asiento se escribe incondicionalmente. Una liquidación legada en `REVISADA` sin tasa alguna produce:
```
replaced asentado: [{'rate_bp': None, 'commission_amount': None, 'policy_status': 'SIN_POLITICA_APLICADA'}]
```
Es un asiento que no reemplaza importe alguno. Registra un dato cierto (el estado de política anterior), así que no falsea nada, pero contra la letra de «el asiento no se invente» es ruido: un lector del historial ve un `replaced` donde no hubo retiro de valor. Coste de arreglo trivial (`if replaces_amount or (repairing and entry["commission_amount"] is not None)`), impacto económico nulo.

### O4 — una venta con fecha futura errónea congela toda publicación de tasas

La guarda usa `MAX(substr(period,1,7))` global sobre las entradas liquidadas. Una venta registrada con fecha 2099 —un error de tipeo plausible en carga manual— que llegue a `CALCULADA` fija el suelo de la guarda en 2099-04 y bloquea **cualquier** publicación futura:
```
venta 2099 liquidada; publicar 2026-09 -> ValueError: la vigencia 2026-09-01 gobernaría el período 2099-04, que ya fue liquidado…
```
Es un problema de disponibilidad operativa, no de corrección económica: la guarda falla del lado seguro. Se destraba revirtiendo la entrada errónea. Vale la pena considerar validar en `CommissionSaleInput` que `sale_date` no sea desmesuradamente futura, o acotar la guarda a períodos no posteriores al mes en curso.

---

## 7. Regresión del paquete (confirmatoria)

```
tests/gestion_central/test_comisiones.py ....  88 passed in 5.02s
tests/                                   ....  345 passed in 29.23s
```

Revisé las diez funciones que el paquete añade en la generación 4 (`test_a_rate_effective_before_the_last_published_one_is_rejected` … `test_recalculate_records_nothing_replaced_when_there_was_no_previous_amount`). Lo que afirman es cierto: lo comprobé de forma independiente en §2 y §3 con escenarios construidos por mí, sin reusar sus fixtures. Los huecos que dejan son los cuatro de §6: ninguna de ellas cubre la reapertura de un mes por reversión (O2), el asiento nulo en la rama de reparación (O3), ni el bloqueo global por fecha futura (O4); y O1 no está cubierta por diseño, porque sigue abierta.

El uso de `_inject_policy_version` por SQL en el paquete está correctamente justificado: ahora que la guarda prohíbe alcanzar un período liquidado, ésa es la única forma de reconstruir un sello desfasado, que es un estado que sí puede llegar migrado desde otra instalación. Verifiqué que la guarda de pago `_require_current_policy` sigue defendiendo contra él.

---

## 8. Veredicto

# **PASS**

B1 y B2 quedan cerrados desde el ángulo funcional. La guarda endurecida rechaza la vigencia anterior, la igual y cualquiera dentro de un mes ya liquidado, en los cuatro estados liquidados, tanto por la vía directa como por la indirecta de publicar y recalcular; preserva la idempotencia de republicar lo idéntico y no confunde `ELEGIBLE` con liquidado. El asiento `replaced` sobrevive en todas las ramas alcanzables, incluidas `ELEGIBLE` y `CALCULADA` y el período anterior a la vigencia, sin repetirse. La exactitud monetaria `Decimal` y el `HALF_UP` canónico no cambiaron: 100.005 casos verificados contra una implementación de referencia independiente, cero divergencias.

Las cuatro observaciones son residuos acotados, no defectos económicos reproducibles: ninguna permite que dinero ya pagado cambie de importe, y las dos que permiten re-tarifar un mes cerrado (O1 en su residuo, O2) exigen o bien que no haya nada calculado todavía, o bien una reversión explícita y auditada. Recomiendo tratar O1 y O2 como trabajo de una generación siguiente, con decisión de propietario sobre cada una.
