# Verdict — Librarian, generación 8
Runner: LIBRARIAN-IND-COMISION-POLICY-1PCT-008
Snapshot: cf4fb258703e266148d7bb7332b79ffdddce926c
Veredicto: FAIL

## Qué verifiqué y cómo

- **Regresión.** `python -m pytest -q` → **431 passed**. `python -m pytest tests/gestion_central -q` → **231 passed**. Ambas coinciden con lo declarado en SUMMARY.md y TEST_EVIDENCE.md.
- **Recuento real por archivo de comisiones** (`pytest --collect-only -q`, agrupado por fichero): `test_comisiones.py` **112**, `test_comisiones_ui_interactions.py` **8**, `test_comision_rate_boundary.py` **24**, `test_comision_period_unpin.py` **23**, `test_comision_legacy_facts.py` **13** = **180**. Coincide con «51 → 180». La derivada 302 + 129 (125 dominio + 4 interfaz) cuadra: 172 − 47 = 125 y 8 − 4 = 4.
- **Predicado de vitalidad.** `grep -rn "LIVE_OFFICIAL_FACT_SQL\|PERIOD_MATCH_SQL"` sobre todo el árbol: definidos en `modulos/gestion_central/comision_policy.py:75` y `:83`. `LIVE_OFFICIAL_FACT_SQL` se usa en dos sitios y sólo dos — `modulos/gestion_central/comisiones.py:770` (caliente) y `modulos/gestion_central/repository.py:343` (siembra) — sin reescrituras. `PERIOD_MATCH_SQL` se usa en **un** solo sitio: `comisiones.py:770`. Ver bloqueante L2-g8.
- **Escritor único del libro.** `grep -rn "commission_period_rate_events"` en todo el árbol: un solo `INSERT INTO commission_period_rate_events`, en `modulos/gestion_central/repository.py:406`, dentro de `CentralRepository.record_period_rate_event`. Ningún `UPDATE` ni `DELETE` en código de producción (los únicos `DELETE` viven en fixtures de prueba; ver observación 2). Los tres llamadores declarados existen: `comisiones.py:801` (`_pin_rated_period`), `comisiones.py:836` (`_reconcile_period_pin`), `repository.py:427` (`_record_seed_event`).
- **Invariantes de ARCHITECTURE_DELTA.md.** Numerados 1..14, sin huecos ni duplicados. Contrastados uno a uno contra el código. El **12** es cierto en sus tres partes: la siembra no escribe ningún `UNPINNED` (`_record_seed_event` sólo emite `"PINNED"`), no escribe sobre `commission_entries` (`repository.py:340-386` sólo lee), y la atribución a `_migrate_commission_policy` (`repository.py:245-300`) es correcta: sólo `UPDATE commission_entries SET policy_status=...` sin tocar `rate_bp` ni `commission_amount`. El **11** es falso en su segunda mitad (L2-g8) y el **10** es falso (L1-g8).
- **Demostración empírica del L1-g8.** Sobre la base del piloto (`pilot_base`, entrada `entry-P`: `status=PAGADA`, `paid_at='2099-05-10'`, `policy_status='POLITICA_HISTORICA_PREVIA'`, `rate_bp=300`), `CommissionService._live_official_facts(con, "2099-04")` devuelve `[]`. Una liquidación con `paid_at` **no** sostiene su mes.
- **MANIFEST y ZIP.** `sha256sum -c MANIFEST.sha256` desde la raíz del worktree: **49/49 OK**, 0 fallos. El manifest incluye los seis verdicts de `generation-6/` y `generation-7/`. Verificación miembro a miembro del ZIP con `zipfile`: **50 miembros, 50 byte-idénticos al worktree, 0 mismatch** (los 49 del manifest más `MANIFEST.sha256`).
- **Finales de línea.** Recuento real sobre los 49 ficheros del manifest: **7** ya traen CRLF (`COMMISSION_RULES.md`, los tres `PROMPT_*.txt`, las dos herramientas de `tools/` y el PNG) y **42** llevan LF, repartidos en **31 `.md`, 9 `.py` y 2 `.json`**. Coincide exactamente con ARTIFACT_CONSISTENCY.md:18-21. El recuento vive en un solo sitio: HANDOFF.md:107 remite a `ARTIFACT_CONSISTENCY.md` sin repetir cifras.
- **Captura.** `screenshots/comision-1pct-1920x1080.png`: **93.665 bytes**, SHA-256 `f0919e28ac9a60911357ab6db29c1af9e374cc77a2b1038e522de2f078d93dc6`, cabecera IHDR **1920×1080**, color type 2 (RGB). Los tres coinciden con VISUAL_EVIDENCE.md:3-4. Los tres rótulos citados son literalmente los que produce `modulos/gestion_central/comisiones_ui.py:252-266`.
- **Backlog.** HANDOFF.md numera **29** hallazgos (1..29, sin huecos) y `WORKFLOW.non_blocking_findings_recorded` tiene **29** entradas, correspondientes una a una en el mismo orden y con el mismo contenido.
- **Checker.** `python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001` → `PAQUETE CONSISTENTE`.
- **Verdicts previos.** `generation-6/` y `generation-7/` contienen sus tres verdicts cada uno. `git log --name-status` sobre ambas rutas muestra sólo dos commits, ambos con estado `A`: `8e049e2` (gen-6) y `f657c2d` (gen-7). Ninguno fue modificado después.
- **Base.** `git log -1 --format=%P 578bf8b7…` = `e7732603d9eb098867a272598e6d30803a4f1ac3`: la base es en efecto el padre directo del snapshot de la generación 1, como afirma ARTIFACT_CONSISTENCY.md:37-38, y es ancestro de HEAD.
- **Otros contrastes.** `SINTETICA_PENDIENTE_APROBACION` sólo sobrevive en `RETIRED_POLICY_STATUSES` (`comision_policy.py:54`) y en pruebas/documentación que la citan como retirada. Tabla de estados de política completa y sin sobrantes frente a `POLICY_STATUSES`. `WORKFLOW.generations` fija los snapshots 1..7 y deja la 8 en `null`, como declara ARTIFACT_CONSISTENCY.

## Bloqueantes

**L1-g8 — El paquete sigue afirmando que `paid_at` basta para sostener el mes; la generación 8 cambió exactamente esa regla y no actualizó el contrato.**

Afirmaciones falsas:
- `ARCHITECTURE_DELTA.md:117` (invariante **10**): «**Una `PAGADA` viva nunca desfija**: `paid_at` cuenta como hecho vivo aunque la liquidación se observe después o la venta se anule.»
- `COMMISSION_POLICY_1PCT.md:96-98`: «**Una `PAGADA` viva nunca suelta el período.** El dinero efectivamente consolidado está protegido: **una liquidación con `paid_at` sostiene su mes** aunque después se observe o se anule la venta.»
- `HANDOFF.md:341`: «`_live_official_facts` cuenta `paid_at`, así que el dinero consolidado sostiene el período…»
- `SUMMARY.md:75`: «**Una `PAGADA` viva nunca suelta**: el dinero consolidado sostiene su mes…»

Evidencia: `modulos/gestion_central/comision_policy.py:75-79` antepone `e.rate_bp IS NOT NULL AND e.policy_status = 'CANONICA_APROBADA'` a la disyunción, de modo que la rama `e.paid_at IS NOT NULL` **nunca** se evalúa sola. Comprobado en ejecución: con la entrada `entry-P` (`PAGADA`, `paid_at='2099-05-10'`, `POLITICA_HISTORICA_PREVIA`), `_live_official_facts(con,"2099-04")` devuelve `[]`. Es precisamente lo que prueba `tests/gestion_central/test_comision_legacy_facts.py:121` y lo que HANDOFF.md:385-392 describe como el cierre de `AB1-g7`.

Gravedad: `COMMISSION_POLICY_1PCT.md` es el documento de contrato económico de la misión y **no fue tocado en toda la generación 8** (`git diff 41131a6 HEAD --stat` no lo lista), pese a que la generación cambió la definición de «hecho económico oficial vivo». El invariante 10 tampoco se tocó: es una reliquia literal de la redacción de la generación 7, la misma clase de defecto que el encargo pide cazar. Un lector del contrato concluye que toda comisión pagada del piloto congela su mes — justo lo contrario de lo que hace el código, y lo contrario de lo que el propio paquete presenta como su corrección principal.

**L2-g8 — «Los dos lados emparejan el período con `PERIOD_MATCH_SQL`» es falso: hay un solo usuario de esa constante, y la migración empareja con un segundo texto equivalente.**

Afirmaciones falsas:
- `ARCHITECTURE_DELTA.md:119-121` (invariante **11**): «Los dos lados evalúan la vitalidad con **el mismo SQL**, `comision_policy.LIVE_OFFICIAL_FACT_SQL`, y **emparejan el período con `PERIOD_MATCH_SQL`**: no hay dos textos «equivalentes» que puedan separarse.»
- `MIGRATION.md:94-96`, `HANDOFF.md:397-398` y `HANDOFF.md:406` («`substr(period,1,7)` **en los dos lados**») repiten la misma afirmación.

Evidencia: `grep -rn "PERIOD_MATCH_SQL"` sobre todo el árbol devuelve tres apariciones — la definición en `comision_policy.py:83`, el import en `comisiones.py:22` y **un único uso**, en `comisiones.py:770`. La siembra de la migración (`modulos/gestion_central/repository.py:341-345`) filtra con `WHERE e.period IS NOT NULL AND {comision_policy.LIVE_OFFICIAL_FACT_SQL}` y empareja el período **fuera del SQL**, en Python: `official.setdefault(str(row["period"])[:7], []).append(row)` (`repository.py:348-349`). No hay `substr` en el lado de la migración. Son, literalmente, los «dos textos equivalentes que pueden separarse» que el invariante declara inexistentes.

No he encontrado divergencia de comportamiento hoy: `substr(x,1,7)` y `str(x)[:7]` coinciden para los datos posibles, y `test_un_periodo_con_fecha_completa_se_empareja_igual` lo cubre. Pero el paquete no afirma «coinciden»: afirma que **no existen dos textos**, y esa afirmación de unicidad es falsa contra el código. Es la tercera aparición del patrón que costó `AB1-g6` y `AB1-g7`, con la agravante de que la parte unificada volvió a ser la que ya coincidía y la que se dejó duplicada es la que decide el agrupamiento.

## Observaciones no bloqueantes

1. **Alcance real de la prueba de escritor único.** `test_el_libro_tiene_un_solo_escritor` sólo recorre `modulos/gestion_central/*.py`, no «todo el código» como dice ARCHITECTURE_DELTA.md:57. Verifiqué el árbol entero a mano y el resultado es el mismo para código de producción, pero la guarda automática no cubre `tools/`, `interfaz.py` ni `main.py`.
2. **`DELETE FROM commission_period_rate_events` sí existe en el árbol**, en cinco fixtures de prueba. Son simulaciones de bases legadas y no rutas de producción, pero «ningún `UPDATE` ni `DELETE` en todo el código» es más ancho que lo cierto.
3. **El titular del invariante 11, «Migrar y operar dan el mismo resultado», es más fuerte que la realidad.** Ante evidencia discrepante la migración deja el período sin fijar mientras que en caliente la primera aprobación lo habría fijado. El paquete lo documenta correctamente en otra parte, pero el titular no admite la excepción.
4. **`_migrate_commission_policy` lee `commission_rated_periods` sin normalizar el período** (`repository.py:360`), mientras que `known` y `official` usan claves ya recortadas a `AAAA-MM`. Una fila heredada con fecha completa no se restaría y produciría un `COMMISSION_PERIOD_RATE_SEED_SKIPPED` espurio. Es ruido de auditoría, no dinero, y es la misma raíz que L2-g8.
5. **El docstring de `record_period_rate_event`** afirma que evento y asiento se escriben juntos «de modo que no existe un estado en el que uno esté sin el otro», sin mencionar el parámetro `audit=False` que la propia siembra usa para asentar en su lugar `COMMISSION_PERIOD_RATE_SEEDED`. La propiedad global se mantiene; la descripción omite la excepción.
6. **`SUMMARY.md` describe la vitalidad sin nombrar nunca la condición de política canónica**, aunque la migración y el código la exigen desde esta generación. Es el mismo hueco de L1-g8 en un documento de resumen.

## Superficie que mi revisión NO cubrió

- **No fuzzé ni construí escenarios propios más allá de los que ya existen en la suite.** Mi comprobación empírica del predicado de vitalidad se apoyó en el helper `pilot_base` del propio paquete; no monté bases legadas independientes con combinaciones distintas de estado, política y anulación.
- **No verifiqué la corrección económica de los importes** (redondeo, convenio, bordes) más allá de que la suite pasa. Esa superficie es del Auditor.
- **No inspeccioné la interfaz en ejecución.** Contrasté los rótulos de VISUAL_EVIDENCE.md contra el fuente de `comisiones_ui.py` y contra el hash/tamaño/dimensiones del PNG, pero **no leí la imagen**.
- **No revisé el contenido de los seis verdicts de `generation-6/` y `generation-7/`.** Comprobé que existen, que están en el manifest y que no fueron retocados desde su commit de alta.
- **No revisé las generaciones 1 a 5 ni los documentos de la misión anterior** salvo `COMMISSION_RULES.md` en lo que toca a su presencia en el manifest.
- **No evalué concurrencia, rendimiento, seguridad ni el comportamiento sobre una base productiva real.**
- **No verifiqué reproducibilidad del ZIP ni del manifest en un checkout limpio**; comprobé ambos contra los bytes del worktree, que es lo que el paquete declara y acota como su alcance (hallazgo abierto 23).
