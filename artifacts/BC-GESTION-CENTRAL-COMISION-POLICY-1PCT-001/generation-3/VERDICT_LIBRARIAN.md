# VERDICT_LIBRARIAN — BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 (generación 3)

| | |
|---|---|
| **Runner** | LIBRARIAN-IND-COMISION-POLICY-1PCT-003 (independiente; sin contacto con QA ni Auditor) |
| **Rol** | Revisor independiente de veracidad documental |
| **Snapshot** | `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a` — árbol limpio antes y después (`git status --porcelain` vacío en ambos extremos) |
| **Base declarada** | `e7732603d9eb098867a272598e6d30803a4f1ac3` |
| **Timestamp UTC** | 2026-08-18T00:55:51Z |
| **Ficheros modificados por mí** | ninguno |

---

## Cierre de bloqueantes de las generaciones 1 y 2

Reverificados uno por uno contra el código y los documentos de **este** snapshot, sin reutilizar las conclusiones de `generation-1/` ni `generation-2/`.

| ID | Origen | Veredicto de cierre |
|---|---|---|
| **L1** | LIB gen1 | **CERRADO** |
| **L2** | LIB gen1 | **CERRADO** |
| **L3** | LIB gen1 | **CERRADO** |
| **A1** | AUD gen1 | **CERRADO** |
| **A2** | AUD gen1 | **CERRADO** |
| **G2-L1** | LIB gen2 | **CERRADO para la generación 1; el mismo defecto reaparece para la generación 2** (ver bloqueante L2) |
| **G2-L2** | LIB gen2 | **CERRADO** |
| **G2-L3** | LIB gen2 | **CERRADO** |
| **G2-L4** | LIB gen2 | **CERRADO** |
| **G2-Q1** | QA gen2 | **CERRADO** |
| **G2-Q2** | QA gen2 | **CERRADO** |
| **G2-Q3** | QA gen2 | **CERRADO** |
| **G2-A1** | AUD gen2 | **CERRADO** |
| **G2-A2** | AUD gen2 | **CERRADO** |
| **G2-A3** | AUD gen2 | **CERRADO** |

**L1.** `HANDOFF.md` declara «los **treinta y siete**» heredados. Verificado: `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/HANDOFF.md` tiene 37 ítems numerados y su `WORKFLOW.json` trae `len(non_blocking_findings_recorded) == 37`. Cerrado.

**L2 / G2-L2.** El encabezado de `COMMISSION_RULES.md` declara **exactamente tres** cláusulas superadas —regla 5, sección «Configuración pendiente de aprobación» y la **fórmula de redondeo** `(importe * puntos_basicos + 5000) // 10000`—, que es lo mismo que dicen `SUMMARY.md` (línea 8) y «Cláusulas superadas» de `COMMISSION_POLICY_1PCT.md`. Los tres documentos coinciden en el número y en el contenido. La enumeración «reglas 1 a 4 y 6 a 9» ya no omite la regla 9. El cuerpo del contrato anterior no fue retocado. Cerrado.

**L3.** `MIGRATION.md` paso 1 distingue tres columnas `NOT NULL … DEFAULT` en `commission_policies` de cuatro anulables sin `DEFAULT` en `commission_entries`. Exacto contra `repository.py::_add_missing_columns` (líneas 190-199): `code TEXT NOT NULL DEFAULT ''`, `version INTEGER NOT NULL DEFAULT 1`, `effective_from TEXT NOT NULL DEFAULT ''` frente a `policy_code TEXT`, `policy_version INTEGER`, `policy_effective_from TEXT`, `policy_scope TEXT`. Cerrado.

**A1 / G2-L3.** El invariante 2 de `ARCHITECTURE_DELTA.md` («completa o vacía, nunca a medias») es verdadero contra el código, y la prueba que se cita, `test_a_complete_trace_means_a_policy_evaluated_it_and_an_empty_one_means_none_did`, sí ejercita los cuatro estados: leído el cuerpo, afirma `seen == {POLICY_CANONICAL, POLICY_OUT_OF_EFFECT, POLICY_LEGACY, POLICY_ABSENT}` y conserva `POLITICA_HISTORICA_PREVIA` marcando la legada como `PAGADA` antes de recalcular, que es justo lo que la reparación de la generación 2 volvía inalcanzable. Cerrado.

**A2 / G2-A1.** `_require_current_policy` (`comisiones.py:227-245`) exige, en ese orden: importe presente, `policy_status == CANONICA_APROBADA`, y **coincidencia de `(rate_bp, version)` contra `self.policy.decide(period=entry["period"])`**, es decir contra la política que rige hoy el período, no contra el sello grabado. Está cableada como `guard` en `review`, `approve` y `mark_paid`. La deriva de versión queda cortada. Cerrado.

**G2-A3.** `recalculate` construye la consulta como `WHERE status IN (...) AND paid_at IS NULL` (`comisiones.py:777-779`): la guarda cuelga del `WHERE` entero, no de la rama de reparación. La afirmación de `SUMMARY.md`, `COMMISSION_POLICY_1PCT.md` y el invariante 5 de `ARCHITECTURE_DELTA.md` es ahora literalmente cierta. Cerrado.

**G2-Q1 / G2-A2.** La reparación ya no depende de la etiqueta: `recalculate` compara la tupla completa `(gross, discount, base, rate_bp, commission, policy_status, policy_code, policy_version, policy_effective_from, policy_scope)` contra el objetivo y repara cualquier `REVISADA`/`APROBADA` no pagada que difiera, sea `POLITICA_HISTORICA_PREVIA` o `SIN_POLITICA_APLICADA`. Cubierto por `test_a_legacy_settlement_without_any_rate_is_repaired_too[REVISADA|APROBADA]`, que existe y pasa. Cerrado.

**G2-Q2.** `CanonicalCommissionPolicy.in_force_for(period)` (`comisiones.py:174-180`) filtra `catalogue()` por `is_in_effect(period, …)` y toma la vigencia más reciente que no supera el período; `decide()` la usa. Además `set_general_rate` rechaza una vigencia anterior a `MAX(effective_from)` publicado. El historial se lee, no es decorativo. Cubierto por `test_scheduling_the_next_rate_never_touches_the_current_period` y `test_a_policy_version_can_never_re_rate_a_closed_period`. Cerrado.

**G2-Q3.** `report`/`export_summary` separan `commission_amount` de `non_official_amount` (`comisiones.py:995`, `1008`, `1020`); la interfaz rotula el KPI `COMISIÓN OFICIAL {percent}` (`comisiones_ui.py:246`) y las columnas de tabla «Comisión» a secas (`comisiones_ui.py:40`, `48`), con la franja de aviso condicionada a `kpi["non_official_amount"]` (`:248-250`). Cerrado.

**G2-L4 — reverificado por mí con git, sin fiarme del documento.**
- `git rev-parse 578bf8b^` → `e7732603d9eb098867a272598e6d30803a4f1ac3`
- `git rev-parse 7abc30e^` → `578bf8b7205c857f9032581744f1e5818dab99fa`
- `git rev-list --parents -n1 75f5c57` → padre `7abc30e6d33eb5dc522be7e43aa3ad3886a65b32`
- `git merge-base --is-ancestor e7732603 75f5c57` → verdadero; `git rev-list --count e773260..75f5c57` → **3**

`ARTIFACT_CONSISTENCY.md` dice ahora «la raíz de la misión: el padre directo del snapshot de la generación 1 y ancestro de los siguientes, uno por generación revisada». Es **exacto**. Cerrado.

---

## Verificaciones ejecutadas

**1. Base declarada.** Idéntica y exacta en `SUMMARY.md` (última línea), `MISSION_LEASE.json` y `WORKFLOW.json`: `e7732603d9eb098867a272598e6d30803a4f1ac3`. Coincide con el commit real.

**2. Conteos de pruebas — todos reales, ejecutados por mí.**

| Afirmación | Comando | Resultado |
|---|---|---|
| Regresión 331/331 | `python -m pytest -q` | **331 passed** ✔ |
| Suite del módulo 131 | `pytest tests/gestion_central/` | **131 passed** ✔ |
| Dos archivos de comisiones 80 | `pytest test_comisiones.py test_comisiones_ui_interactions.py` | **80 passed** ✔ |
| 74 y 6 respectivamente | por archivo | **74** y **6** ✔ |
| Funciones 47 → 71 y 4 → 6 | `git show` de la base vs. actual, contando `^def test_` | 47→71 y 4→6 ✔ |
| Línea base 302, +29 (27 dominio + 2 interfaz) | 302 + 29 = 331; 25 funciones nuevas − 1 eliminada + 3 parametrizaciones ×2 = 27 casos netos de dominio | ✔ |
| 3 nuevas parametrizadas sobre `REVISADA`/`APROBADA` | `grep parametrize` | exactamente 3 ✔ |

**Pruebas citadas.** Los 25 nombres de `TEST_EVIDENCE.md`, los 5 de `MIGRATION.md` y los 2 de interfaz existen todos en `tests/`. El único nombre citado que no existe es `test_policy_is_synthetic_pending_approval_and_optional`, citado precisamente como **eliminada** — comprobado: es la única función removida respecto de `e7732603`.

**«Todas las demás pruebas … siguen intactas, sin retoques».** Verificado por comparación AST función a función contra `e7732603`, normalizando finales de línea: en `test_comisiones.py` se modificaron **exactamente** `test_amounts_stay_integers_end_to_end`, `test_an_agreement_total_can_be_corrected_downwards`, `test_source_correction_after_review_never_pays_a_stale_base`, `test_source_correction_before_review_recomputes_the_whole_base` y `test_structured_export_has_stable_contract_and_no_customer_data`; en el archivo de interfaz, `test_navigation_filters_and_state_reasons` y `test_observe_revert_recalculate_and_export`. Son **las mismas siete** que enumera «Pruebas preexistentes actualizadas». Ninguna otra fue tocada. La afirmación es cierta.

**3. `MANIFEST.sha256`.** 30 líneas; `sha256sum -c` → **30/30 OK, 0 fallos**. La composición declarada («seis de código y pruebas, dos de herramientas, el contrato anterior anotado, y los 21 del paquete» = 30) es exacta. Los seis de código coinciden con los seis archivos no documentales que toca el diff contra la base. Del paquete quedan fuera exactamente dos archivos: `MANIFEST.sha256` y el ZIP (23 ficheros en el directorio − 2 = 21). ✔

**4. ZIP contra el worktree.** Verificado miembro a miembro descomprimiendo en memoria y comparando bytes: **31 miembros, 31 byte-idénticos, 0 mismatch, 0 ausentes**. Byte-identidad: perfecta. **Recuento declarado: falso** — ver bloqueante L1.

**5. Captura.** `artifacts/…/screenshots/comision-1pct-1920x1080.png`: PIL → `(1920, 1080) RGB`; tamaño → **93307** bytes; `sha256sum` → `4c616c0c90b8d3bb6f3806a1d5ac85ea3d0cecb4846cb4e250b4dffd2105019e`. Coincide exactamente con `VISUAL_EVIDENCE.md` y con la línea correspondiente del manifest. Inspeccionada la imagen: encabezado, KPIs `4.345.000` / `43.450`, resumen por vendedora `620.000→6.200`, `1.425.000→14.250`, `2.300.000→23.000`, filas S-301 / S-302 / S-103 con sus cifras, desglose de cuatro líneas con «= Comisión oficial (1,00% de la base) 4.750», nota de política, historial `SALE_REGISTERED→ELEGIBLE` y `COMMISSION_RECALCULATED→CALCULADA`, ausencia de banda de aviso, los seis estados y los cinco botones más `Recalcular` y `Exportar resumen`: **todo lo que el documento afirma se lee en la imagen**. La advertencia de no reproducibilidad byte a byte es correcta (el historial muestra `recorded_at` reales). El capturador `tools/capture_gestion_central_comisiones.py` ya no contiene `set_policy` ni `set_general_rate` ni `rate_bp`: «el capturador ya no configura porcentaje» es cierto.

**6. Tabla de estados de política.** Los cuatro de `COMMISSION_POLICY_1PCT.md` son exactamente `POLICY_STATUSES` de `comision_policy.py:38`: `CANONICA_APROBADA`, `FUERA_DE_VIGENCIA`, `POLITICA_HISTORICA_PREVIA`, `SIN_POLITICA_APLICADA`. Completa y sin sobrantes. ✔

**7. Reglas canónicas anteriores.** «Lo que NO cambia» de `SUMMARY.md` y la sección «Cuándo se paga» de `COMMISSION_POLICY_1PCT.md` reproducen sin contradicción las reglas 1-4 y 6-9: venta común elegible sólo al quedar cancelada, convenio 5% antes del 1%, cobros parciales informativos, anuladas sin comisión, gastos y entregas fuera del libro, ocho estados (`COMMISSION_STATES` tiene exactamente 8), libro append-only e índices parciales únicos. Ninguna regla canónica se redocumenta contradiciéndola; las tres cláusulas superadas están declaradas como tales en ambos extremos. ✔

**8. `SINTETICA_PENDIENTE_APROBACION`.** En código productivo aparece **una sola vez**, en `comision_policy.py:42` dentro de `RETIRED_POLICY_STATUSES`. No aparece en `comisiones.py`, `comisiones_ui.py` ni `repository.py`. Las demás apariciones son prosa que la declara retirada, el contrato anterior anotado, las pruebas que verifican su ausencia, y evidencia histórica de misiones previas. `test_the_retired_label_survives_only_as_the_thing_the_migration_removes` afirma exactamente eso y pasa. ✔

**9. Code spans.** Comprobados los nueve `.md` del paquete: cero líneas con número impar de backticks fuera de bloques cercados, cero bloques cercados sin cerrar. La tabla partida de `TEST_EVIDENCE.md` que señalaba la generación 2 ya no existe: «Validaciones dirigidas» renderiza como una sola tabla. ✔

**10. Backlog.** `HANDOFF.md` tiene 14 hallazgos numerados; `WORKFLOW.non_blocking_findings_recorded` tiene 14 entradas, en el mismo orden y sobre los mismos sujetos, ítem por ítem (1 signo/badge, 2 `register_payment`, 3 `assert float(`, 4 documentos que generalizan, 5 granularidad mensual, 6 pagada no oficial, 7 `OBSERVADA` legada, 8 `POLICY_STATUSES`, 9 retiro por alcance, 10 `set_general_rate`, 11 `cancelled_date`, 12 checker, 13 corrección de origen sobre `OBSERVADA`, 14 nota de `SIN_POLITICA_APLICADA` pagada). Idénticos. ✔

**11. Migración contra el código.** Los cuatro pasos de `MIGRATION.md` coinciden con `repository.py::_migrate_commission_policy` (líneas 207-266): retiro auditado como `COMMISSION_POLICY_RETIRED` con `rate_bp` y estado previos, borrado sólo de alcances distintos de `GENERAL`, siembra condicionada a que no exista una `GENERAL` `CANONICA_APROBADA` con `ON CONFLICT(scope, scope_value)`, versión con `INSERT OR IGNORE` sobre `UNIQUE(policy_id,version)` —constraint verificada en el `CREATE TABLE` de la línea 180—, y reetiquetado que **no toca** `rate_bp` ni `commission_amount`. ✔

**12. Contrato de export.** `contract_version: 2`, bloque `policy` completo y `policy_disclaimer` presentes en `export_summary` (`comisiones.py:1032-1055`). ✔

**13. Checker del paquete.** `python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001` → `PAQUETE CONSISTENTE`. La afirmación de `ARTIFACT_CONSISTENCY.md` de que existe y pasa es cierta (con la salvedad de la observación 1).

---

## Bloqueantes

### L1 — `ARTIFACT_CONSISTENCY.md` declara un recuento de miembros del ZIP que es falso

`ARTIFACT_CONSISTENCY.md:12-14`:

> El ZIP se construyó después de escribir todos los documentos y se verificó miembro a miembro contra el worktree: **27 miembros, 27 byte-idénticos, 0 mismatch**.

El ZIP tiene **31** miembros, no 27. Verificado abriéndolo con `zipfile` y contando `infolist()`: 31 entradas, 0 de ellas directorios. Y la comparación byte a byte que ejecuté cubre esos 31: `members: 31 / mismatch 0 / missing 0`. El contenido es impecable; **el número no lo es**.

Es un residuo literal de la generación 2. El diff de `ARTIFACT_CONSISTENCY.md` entre `7abc30e` y `75f5c57` muestra que la línea inmediatamente anterior se actualizó de «26 archivos … 26/26 OK» a «30 archivos … 30/30 OK», y que la línea de los miembros del ZIP **quedó sin tocar**. Cuando el manifest fijaba 26 archivos, 26 + `MANIFEST.sha256` = 27 era correcto; con 30 archivos el ZIP contiene 30 + `MANIFEST.sha256` = **31**.

Es el mismo tipo de defecto que G2-L1 y G2-L2: un conteo que la propia corrección desactualizó y que nadie recontó. Y afecta a la única afirmación del paquete sobre la integridad del entregable que se distribuye.

**Corrección**: `27 miembros, 27 byte-idénticos` → `31 miembros, 31 byte-idénticos`.

---

### L2 — `INDEPENDENCE.md` declara veinte observaciones no bloqueantes en la generación 2; son diecisiete

`INDEPENDENCE.md:63`:

> Los diez bloqueantes se corrigieron y sólo ellos. Sus **veinte** observaciones no bloqueantes quedaron registradas, no corregidas.

Contadas sobre los verdicts que el propio paquete conserva, bajo el encabezado `## Observaciones no bloqueantes` de cada uno:

- `generation-2/VERDICT_LIBRARIAN.md` → 6
- `generation-2/VERDICT_QA.md` → 5
- `generation-2/VERDICT_AUDITOR.md` → 6

Total **17**, no veinte. Verificado además leyendo las tres secciones íntegras: el Librarian numera 1-6, QA 1-5 y el Auditor 1-6; ninguno tiene observaciones numeradas fuera de esa sección (la tabla «Riesgo introducido por la reparación» del Auditor no está numerada ni rotulada como observación, y aun sumándola entera no se llega a veinte).

Que el mismo documento acierte con la generación 1 —«**veintitrés** … ocho del Librarian, siete de QA y ocho del Auditor»; verificado: 8 + 7 + 8 = 23— demuestra que el recuento se hizo para una generación y se estimó para la otra.

Esto es **literalmente G2-L1 repetido un párrafo más abajo**: aquel bloqueante decía «INDEPENDENCE declaraba quince observaciones de la generación 1; son veintitrés», se corrigió la cifra de la generación 1, y al añadir el párrafo de la generación 2 se introdujo el mismo error de recuento en el mismo fichero. El propio `INDEPENDENCE.md` afirma que la independencia «se pagó sola» porque los revisores encuentran lo que la autorrevisión no ve; un paquete que documenta su propio proceso de revisión no puede equivocarse al contar lo que ese proceso produjo.

**Corrección**: `veinte` → `diecisiete` (Librarian 6, QA 5, Auditor 6).

---

## Observaciones no bloqueantes

1. **El checker no mira el ZIP, que es justo donde sobrevivió L1.** `tools/check_mission_package_consistency.py` no contiene una sola referencia a `zip`, ni cuenta observaciones de los verdicts. `ARTIFACT_CONSISTENCY.md` presenta su `PAQUETE CONSISTENTE` como respaldo del bloque entero de afirmaciones, y dos de ellas —los miembros del ZIP y los recuentos de `INDEPENDENCE.md`— caen fuera de su alcance. La herramienta no miente; el documento sugiere una cobertura mayor que la real.

2. **`generations[2].snapshot_commit: null` y `evidence: generation-3/` apuntan a algo que aún no existe.** Es la mecánica declarada —un commit no puede contener su propio SHA— y no lo trato como bloqueante. Pero `ARTIFACT_CONSISTENCY.md:15-17` afirma en presente que «`WORKFLOW.generations[].snapshot_commit` fija cada snapshot sometido a revisión», y para la generación que se está sometiendo a revisión ahora mismo eso todavía no es cierto. Una frase que dijera «fija cada snapshot ya revisado; el de la generación en curso se fija en el commit de registro posterior» describiría la mecánica sin dejar la excepción implícita. Se enlaza con el hallazgo abierto 12 del backlog.

3. **El párrafo de cabecera de `INDEPENDENCE.md` sigue hablando sólo del snapshot de la generación 1.** «Los tres corrieron en paralelo sobre `578bf8b…`» encabeza un documento que ahora cubre tres generaciones sobre tres snapshots distintos. Las secciones por generación lo desambiguan, pero el párrafo general quedó fijado en la primera.

4. **«No se usan floats en ningún punto» sigue siendo literalmente inexacto.** `comisiones.py` produce un float en `AGREEMENT_DISCOUNT_BP / 100:.0f` para rotular «Descuento de convenio (5%)». No es aritmética monetaria y no hay riesgo económico —toda la ruta del dinero es `Decimal`, comprobado en `comision_policy.py`—, pero la frase de `COMMISSION_POLICY_1PCT.md` es absoluta y la prueba que cita como evidencia, `test_no_external_provider_or_secrets_in_module`, ni siquiera lee `comision_policy.py`. El backlog lo registra parcialmente (hallazgo 3); la brecha de cobertura del módulo sigue sin registrarse como tal. Heredada de la generación 1, sin cambios.

5. **`MIGRATION.md` paso 1 atribuye la tabla nueva a `_add_missing_columns`.** «Columnas aditivas (`_add_missing_columns`). Siete columnas nuevas sobre dos tablas existentes, más la tabla `commission_policy_versions`». Las siete columnas son exactas, pero la tabla la crea el bloque `CREATE TABLE IF NOT EXISTS` de `migrate()` (`repository.py:175-181`), no esa función. Ambas corren en la misma transacción, así que el efecto descrito es correcto; la atribución no.

6. **`SUMMARY.md` y `WORKFLOW.json` siguen discrepando sobre la venta con saldo.** La tabla de ejemplos dice comisión «**0** (no pagable)»; `verified_examples` dice `"commission": null`. El código escribe `commission_amount = None` y el KPI agrega 0, de modo que ninguna de las dos es falsa, pero el mismo caso verificado se declara de dos formas distintas. Es la observación 6 del Librarian de la generación 2 y la 6 de la generación 1, aún abierta y no incorporada al backlog de 14.

---

## VEREDICTO

# **FAIL**

Dos afirmaciones del paquete son demostrablemente falsas contra el artefacto y contra la evidencia que el propio paquete conserva:

1. **L1** — `ARTIFACT_CONSISTENCY.md`: «27 miembros» del ZIP; son **31**.
2. **L2** — `INDEPENDENCE.md`: «veinte observaciones no bloqueantes» en la generación 2; son **diecisiete**.

Ambas son recuentos que la corrección de esta misma generación desactualizó sin recontar, el mismo mecanismo que produjo G2-L1 y G2-L2. Todo lo demás que verifiqué es cierto: los quince bloqueantes están cerrados en código y documento, la base declarada es exacta y la relación de ancestría es la que ahora se describe, la regresión da 331/331 real, el manifest verifica 30/30, el ZIP es byte-idéntico al worktree, la captura coincide en hash, tamaño, dimensiones y contenido, la tabla de estados es completa y sin sobrantes, la etiqueta retirada sólo sobrevive en `RETIRED_POLICY_STATUSES`, los code spans están balanceados y los dos backlogs son idénticos.

Corregidas L1 y L2 —dos cifras, sin tocar código ni pruebas— el paquete queda veraz en todo lo que este rol puede comprobar.

*Árbol limpio al terminar: `git status --porcelain` sin salida. No modifiqué ningún archivo, no ejecuté `git add`, `commit`, `checkout` ni `push`. Trabajé solo, sin conocer los verdicts de QA ni del Auditor.*
