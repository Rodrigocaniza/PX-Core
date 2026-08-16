# VERDICT_LIBRARIAN — BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001

- **Runner**: LIBRARIAN-IND-COMISION-POLICY-1PCT-001 (independiente, sin contacto con QA ni Auditor)
- **Rol**: revisor de veracidad documental
- **Snapshot**: `578bf8b7205c857f9032581744f1e5818dab99fa` (worktree `.worktrees/gc-comision-policy-1pct-001`, rama `mission/bc-gestion-central-comision-policy-1pct-001`, árbol limpio)
- **Base declarada**: `e7732603d9eb098867a272598e6d30803a4f1ac3`
- **Timestamp UTC**: 2026-08-16T03:28:37Z

## Verificaciones

**1. Base exacta.** `git rev-parse 578bf8b^` → `e7732603d9eb098867a272598e6d30803a4f1ac3`. `git merge-base e7732603 578bf8b` → `e7732603…`. La base es el padre directo, no sólo un ancestro. `git rev-parse main` → `d88f595`; `git merge-base --is-ancestor 578bf8b main` → falso: **sin merge a `main`**, como declara SUMMARY.md.

**2. Conteos de pruebas.** Ejecutados en este snapshot:

| Declarado | Comando | Resultado |
|---|---|---|
| 317 regresión completa | `python -m pytest -q` | **317 passed in 33.65s** ✓ |
| 117 suite del módulo | `pytest tests/gestion_central/ -q` | **117 passed** ✓ |
| 66 comisiones | `test_comisiones.py` (61) + `test_comisiones_ui_interactions.py` (5) | **66** ✓ |
| 51 → 66 | base: 47 + 4 | **51** ✓ |
| 302 línea base | 317 − 15; delta de `def test_` en `tests/` entre base y snapshot = **+15** (303→318) | consistente ✓ |
| 15 añadidas (14 dominio + 1 interfaz) | dominio: 15 añadidas − 1 eliminada = **+14**; interfaz: **+1** | ✓ |

El "+14 de dominio" es neto: se añaden 15 funciones y se elimina `test_policy_is_synthetic_pending_approval_and_optional`. TEST_EVIDENCE lo declara correctamente (14 numeradas + la que reemplaza a la eliminada).

**3. Nombres de prueba citados.** Los 24 nombres entre backticks de TEST_EVIDENCE.md existen en `tests/`, salvo `test_policy_is_synthetic_pending_approval_and_optional`, citado precisamente como **eliminado**. Leí el cuerpo de las 15 pruebas nuevas: cada afirmación de la tabla de validaciones dirigidas se corresponde con aserciones reales (4.000; base 0 y `commission_amount is None` + cobro parcial posterior; 25.000/475.000/4.750; tres locales/tres vendedoras con `{100}` y `{4_000}`; cuatro `recalculate` con dos asientos `COMMISSION_RECALCULATED`; versión 2 al 2% con `updated_at` intacto; `FUERA_DE_VIGENCIA` + `pytest.raises("política oficial")`; 0,50→1 / 1,50→2 / 0,49→0 / 12.345,67→12.346; reapertura con `changed == 0`; `contract_version: 2`). La lista de "pruebas preexistentes actualizadas" (7) coincide **exactamente** con el conjunto de funciones modificadas (5 en dominio + 2 en interfaz); "todas las demás siguen intactas" es cierto (comparación función a función contra `e7732603`).

**4. Tabla de estados de política.** `comision_policy.POLICY_STATUSES == ('CANONICA_APROBADA','FUERA_DE_VIGENCIA','POLITICA_HISTORICA_PREVIA','SIN_POLITICA_APLICADA')`. La tabla de COMMISSION_POLICY_1PCT.md tiene esos cuatro, sin sobrantes ni faltantes. Los cuatro se emiten realmente: `POLICY_CANONICAL`/`POLICY_OUT_OF_EFFECT` en `decide()`, `POLICY_ABSENT` en `_create_entry`/`_apply_source_update`, `POLICY_LEGACY` en la migración.

**5. Ejemplos numéricos.** Ejecutados contra `comision_policy`: 400.000→4.000; 500.000→25.000/475.000/4.750; 333.333→16.667/316.666/**3.167**; 1.234.567→**12.346**; bordes 50→1, 150→2, 49→0. Los 5 `verified_examples` de WORKFLOW.json y las dos tablas de SUMMARY/COMMISSION_POLICY_1PCT coinciden. `is_in_effect('2026-07','2026-08-01')` → False; `('2026-08',…)` → True. Agregado de la captura: 620.000+1.425.000+2.300.000 = 4.345.000 → 43.450 ✓.

**6. Captura.** `comision-1pct-1920x1080.png`: **93.628 bytes**, SHA-256 `a85af0eb7da012fcd7721cafc505f7d8a6fb9ecc39826e57b112d646d14dfa47`, IHDR **1920×1080**, colour-type 2 (RGB). Los tres valores declarados son exactos. Leí el PNG como imagen y verifiqué **todo** lo que VISUAL_EVIDENCE dice que se ve: encabezado literal con `1,00% / COMISION_GENERAL_1PCT v1 / vigente desde 2026-08-01 / HALF_UP`; KPIs `BASE COMISIONABLE 4.345.000 Gs.` y `COMISIÓN OFICIAL 1,00% 43.450 Gs.`; columna `Comisión 1,00%` en ambas tablas; las tres filas 620.000→6.200 / 1.425.000→14.250 / 2.300.000→23.000; S-301 PAGADA 620.000→6.200; S-302 PENDIENTE SALDO 340.000 saldo 240.000 → base 0 → «—»; S-103 CALCULADA 500.000→25.000→475.000→4.750; el desglose de cuatro líneas con los signos `−`/`=`/`=`; la nota de política textual; historial `SALE_REGISTERED→ELEGIBLE` y `COMMISSION_RECALCULATED→CALCULADA`; los seis estados listados; los cinco botones de acción más `Recalcular` y `Exportar resumen`. Ninguna columna monetaria recortada. La captura es del piloto sintético (período 2099-04), sin datos de clientes.

**7. Etiqueta retirada.** `git grep SINTETICA_PENDIENTE_APROBACION` en `modulos/`: **una sola aparición**, `comision_policy.py:42`, dentro de `RETIRED_POLICY_STATUSES`. No aparece en `comisiones.py`, `comisiones_ui.py` ni `repository.py`. `test_the_retired_label_survives_only_as_the_thing_the_migration_removes` verifica exactamente eso sobre el fuente.

**8. Reglas canónicas anteriores.** Ver L3.

**9. Code spans.** Backticks pares en los 7 `.md` del paquete (124/80/72/110/66/124/52). Sin spans rotos.

**10. Backlog.** HANDOFF.md: 9 ítems numerados. `WORKFLOW.non_blocking_findings_recorded`: 9. Coinciden en cantidad y en contenido ítem a ítem. Verifiqué los nueve contra el código: (1) `comisiones.py:805` usa `sign="="` y la captura muestra los dos badges de piloto duplicados ✓; (2) `git grep` confirma que ni `register_payment` ni `sync_review_sales` tienen llamador fuera de `tests/` ✓; (3) `assert "float(" not in source` existe en `test_no_external_provider_or_secrets_in_module` ✓; (4) heredado 16 existe ✓; (5) `is_in_effect('2026-08','2026-08-15') == True` — la vigencia intramensual efectivamente no se respeta al día ✓; (6) el `WHERE status IN ('ELEGIBLE','CALCULADA')` deja fuera `REVISADA`/`APROBADA` ✓; (7) `POLICY_STATUSES` sólo se importa en `comisiones.py:22` y nunca se usa ✓; (8) la migración hace `DELETE` de las políticas por alcance tras auditarlas, sin fila en `commission_policy_versions` ✓; (9) `set_general_rate` devuelve `(version, bool)`, sin vista previa ✓. Las referencias cruzadas «heredado 8/11/7/16» apuntan a los ítems correctos del handoff anterior.

**11. Checker.** `python tools/check_mission_package_consistency.py` → `BC-GESTION-CENTRAL-COMISIONES-001: PAQUETE CONSISTENTE` (rc=0). Con argumento → `BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001: PAQUETE CONSISTENTE` (rc=0). Sigue sirviendo a ambos.

**12. "Lo que NO cambia" y alcance.** `git diff --name-only e7732603 578bf8b` toca 21 rutas: los 13 del paquete nuevo, 4 de `modulos/gestion_central/`, 2 de `tests/gestion_central/` y 2 de `tools/`. Nada de BC Caja, BC-Core, BC-Finanzas, otros worktrees ni `main`. Verificado que **no** cambian: `COMMISSION_STATES` (8 estados), los índices parciales únicos `idx_commission_entry_active`/`idx_commission_entry_period`, el libro append-only, `_settled_amount`, ni las reglas de convenio 5%→1%, cobros parciales informativos, ventas anuladas y exclusión de gastos/entregas. Los reemplazos de ARCHITECTURE_DELTA se confirman contra la base: `StoredCommissionPolicy.rate_for()` devolvía `(rate, status)`, existía la cascada `VENDEDORA→LOCAL→GENERAL`, existía `set_policy(actor, scope, rate_bp, scope_value)` y `POLICY_ABSENT = "SIN_POLITICA_CONFIGURADA"`; hoy ninguno existe. Los cinco reexports declarados (`AGREEMENT_DISCOUNT_BP`, `BASIS_POINTS`, `apply_basis_points`, `agreement_discount`, `commissionable_base`) están presentes. La migración corre desde `CentralRepository.__init__ → migrate()`, en la misma transacción, y los 4 pasos de MIGRATION.md coinciden línea a línea con `_migrate_commission_policy`.

## Bloqueantes

1. **L1 — Conteo falso de hallazgos heredados.** `HANDOFF.md:20` afirma: «Los **veinte** del handoff de BC-GESTION-CENTRAL-COMISIONES-001 siguen abiertos y sin corregir». El handoff anterior registra **37**, no veinte: `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/HANDOFF.md`, sección «Hallazgos no bloqueantes registrados y NO corregidos», ítems numerados 1..37, y `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/WORKFLOW.json → non_blocking_findings_recorded` tiene `len == 37`. La misión declara además que «no los tocó», así que los 37 siguen abiertos. El checker no lo detecta porque sólo compara HANDOFF contra WORKFLOW **dentro** del mismo paquete, nunca contra el paquete continuado. Es un conteo verificable y erróneo sobre la deuda técnica que se hereda.

2. **L2 — Contradicción interna del canon documental sobre el porcentaje.** `HANDOFF.md:15` dirige al revisor a `artifacts/BC-GESTION-CENTRAL-COMISIONES-001/COMMISSION_RULES.md` como «Reglas económicas ya canónicas», y ese documento —no modificado por esta misión y no marcado como superado— afirma hoy lo contrario del código entregado: la regla 5 dice que `policy_status` es `SIN_POLITICA_CONFIGURADA` o `SINTETICA_PENDIENTE_APROBACION` (ninguno de los dos se produce ya; ambos están en `RETIRED_POLICY_STATUSES`), cita como evidencia `test_policy_is_synthetic_pending_approval_and_optional` (**eliminada** por este mismo commit), y su sección «Configuración pendiente de aprobación» declara que «El porcentaje de comisión **no** existe canónicamente… **no es una regla productiva**», exactamente lo opuesto a SUMMARY.md y COMMISSION_POLICY_1PCT.md. Además su fórmula de redondeo documentada, `(importe * puntos_basicos + 5000) // 10000`, ya no es la implementación (equivalente numéricamente para enteros no negativos, pero distinta). `SUMMARY.md:7-8` sostiene que esas reglas «se mantienen tal cual», lo cual es falso para la regla 5. `COMMISSION_POLICY_1PCT.md:3-5` sí acota bien el alcance («elegibilidad, estados y convenio»), pero HANDOFF y SUMMARY no, y nada en el paquete anota COMMISSION_RULES.md como superado en sus cláusulas de porcentaje. El paquete entregado deja el canon diciendo dos cosas opuestas sobre el mismo asunto.

3. **L3 — Afirmación falsa sobre las columnas de la migración.** `MIGRATION.md:9-11`: «Siete columnas nuevas sobre dos tablas existentes, **todas con `DEFAULT`**». En `repository.py::_add_missing_columns` sólo 3 de las 7 llevan `DEFAULT` (`commission_policies.code`, `.version`, `.effective_from`); las 4 de `commission_entries` se añaden como `policy_code TEXT`, `policy_version INTEGER`, `policy_effective_from TEXT`, `policy_scope TEXT`, sin cláusula `DEFAULT`. Sin consecuencia funcional (son anulables y el `ALTER` es seguro, y ARCHITECTURE_DELTA:41-42 sí las describe correctamente como «todas anulables»), pero la afirmación es literalmente falsa contra el código.

## Observaciones no bloqueantes

1. **Evidencia de ausencia de floats sobrevalorada.** `COMMISSION_POLICY_1PCT.md:93-94`: «No se usan floats en ningún punto: la prueba `test_no_external_provider_or_secrets_in_module` sigue verificándolo sobre el fuente». Esa prueba lee **sólo** `modulos/gestion_central/comisiones.py`; no lee `comision_policy.py`, que es precisamente donde vive ahora toda la aritmética `Decimal`/`HALF_UP`. Es decir, el módulo del que habla la frase no está cubierto por la prueba que se cita como evidencia. Además, `comisiones.py:800` sí produce un float (`AGREEMENT_DISCOUNT_BP / 100` → `5.0`) para rotular «Descuento de convenio (5%)»; no es aritmética monetaria y la aserción `"float(" not in source` no lo detecta, pero «en ningún punto» no es exacto. El backlog (ítem 3) registra la debilidad de la aserción, no esta brecha de cobertura.

2. **Referencias colgantes en el paquete.** `HANDOFF.md:3-4` remite a `INDEPENDENCE.md` y a `generation-N/`, y `WORKFLOW.json → generations[0].evidence` apunta a `artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001/generation-1/`. Ninguno de los dos existe en este snapshot (el paquete son 12 archivos más `screenshots/`). Coherente con un estado pre-revisión, pero hoy son punteros a la nada.

3. **El snapshot no queda registrado en el paquete.** `WORKFLOW.json → generations[0].snapshot_commit` es `null` aunque el paquete se publica en `578bf8b`. No hay ningún archivo del paquete que fije de forma verificable el commit inmutable que se somete a revisión; los tres revisores dependen de que se lo pasen por prompt.

4. **`PROMPT_LIBRARIAN.txt` pide verificar artefactos inexistentes.** Exige «MANIFEST.sha256 completo y verificable; ZIP byte-idéntico al worktree». El paquete no contiene ni `MANIFEST.sha256` ni ZIP alguno, de modo que ese tramo del prompt es inverificable por construcción.

5. **Ambigüedad menor de conteo.** TEST_EVIDENCE.md:7 «Comisiones en particular: 51 → 66 pruebas» sólo cuadra sumando los dos archivos (`test_comisiones.py` + `test_comisiones_ui_interactions.py`). Es cierto, pero el nombre de la suite no lo dice y `test_comisiones.py` por sí solo da 61.

6. **`policy_status` de una venta con saldo.** SUMMARY.md:38 presenta la comisión como «**0** (no pagable)» mientras `WORKFLOW.json` la registra como `null`. En el código es `NULL` en `rate_bp` y `commission_amount`, y `0` sólo en el KPI agregado (`commission_amount or 0`). Ambas lecturas son defendibles, pero los dos documentos no dicen lo mismo.

7. **Invariante 1 de ARCHITECTURE_DELTA es más fuerte que la migración.** «Después de migrar, `commission_policies` contiene exactamente una fila, de alcance `GENERAL`». La consulta de retiro selecciona `approval_status IN (retiradas) OR scope<>'GENERAL'`, así que una hipotética fila `('GENERAL', scope_value≠'')` con estado no retirado sobreviviría. Ninguna ruta de código la puede crear (el propio documento lo dice), pero el invariante depende de esa premisa, no de la migración.

8. **`POLICY_STATUSES` es un import muerto.** `comisiones.py:22` lo importa y nunca lo usa. El backlog lo registra como «se define y no se usa» (ítem 7); no menciona que además queda como import sin consumidor.

`VERDICT: FAIL`
