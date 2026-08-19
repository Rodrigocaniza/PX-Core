# Verdict — Librarian, generación 9
Runner: LIBRARIAN-IND-COMISION-POLICY-1PCT-009
Snapshot: f284b6c5fc2d0f31ffce7567146cce9371e9502a
Veredicto: FAIL

## Qué verifiqué y cómo

Todo contra el código y contra los bytes del worktree, ejecutando; ningún documento se aceptó como prueba de otro. No reutilicé ningún verdict de las generaciones 1..8.

**Pruebas.** `python -m pytest -q` → **444 passed**. `python -m pytest tests/gestion_central -q` → **244 passed**. Recuento real por archivo con `--collect-only`: `test_comisiones.py` **112**, `test_comisiones_ui_interactions.py` **8**, `test_comision_rate_boundary.py` **24**, `test_comision_period_unpin.py` **23**, `test_comision_legacy_facts.py` **13**, `test_comision_rate_coherence.py` **13** = **193**. Coincide. Funciones: 94 / 8 / 24 / 23 / 13 / 11, con 6 parametrizaciones en `test_comisiones.py` (94+18=112) y 1 en el archivo de la generación 9 (11+2=13).

**Unicidad de decisión y de escritura.** `grep` sobre todo el árbol: hay exactamente **un `INSERT`** sobre `commission_period_rate_events` en producción (`repository.py:436`, dentro de `record_period_rate_event`) y **ningún `UPDATE` ni `DELETE`**; los únicos borrados están en fixtures de prueba. `record_period_rate_event` se invoca sólo desde `reconcile_period_rate` (`repository.py:396` y `:407`), y `reconcile_period_rate` decide exclusivamente con `comision_policy.resolve_period_rate`. Las dos rutas —`_set_status` en caliente y `_backfill_period_rate_events` al abrir la base— entran por la misma función. `LIVE_OFFICIAL_FACT_SQL`, `BOUNDARY_SQL_IN`, `PERIOD_KEY_SQL` y `PERIOD_MATCH_SQL` se definen una sola vez y la consulta entera sale de `live_official_facts_sql`; no hay un segundo texto equivalente.

**Semántica económica de la generación 9, ejecutada.** Escenario propio en directorio temporal: publiqué 7% vigente desde `2099-01`, registré una venta de 10.000.000, calculé, revisé, aprobé y pagué; luego publiqué el 1%. Resultado: el libro conserva `PINNED 700`, `decide('2099-04')` devuelve **700** y `decide('2099-05')` devuelve **100**; `recalculate` no toca el importe pagado (700.000); reabrir la base (migrar) no escribe nada y sigue devolviendo 700. La preservación de la tasa histórica viva y el carácter prospectivo del 1% son reales.

**Paquete.** `sha256sum -c MANIFEST.sha256` desde la raíz del repo: **53/53 OK**. ZIP: **54 miembros**, los 53 del manifest más el propio `MANIFEST.sha256`, **0 mismatch** byte a byte contra el worktree. Finales de línea recontados fichero a fichero: **46 en LF** (34 `.md` de 35, 10 `.py`, 2 `.json`), **6 ya en CRLF** y el PNG binario; `ARTIFACT_CONSISTENCY.md` está entre los 46, como declara. El recuento vive sólo en `ARTIFACT_CONSISTENCY.md`. `python tools/check_mission_package_consistency.py …` → `PAQUETE CONSISTENTE`.

**Captura.** SHA-256 `f0919e28…d93dc6`, **93.665 bytes**, **1920×1080**, color type 2 (RGB): idénticos a lo declarado. Los tres rótulos citados son literalmente los que produce `comisiones_ui.py:251-267`. `git log` del PNG confirma que su última regeneración fue el commit de la generación 7, como dice `VISUAL_EVIDENCE.md`.

**Backlog.** 29 entradas numeradas en `HANDOFF.md` y 29 en `WORKFLOW.non_blocking_findings_recorded`, mismo orden y mismo asunto una a una.

**Verdicts anteriores.** `git log` por fichero: cada uno de los nueve verdicts de `generation-6/`, `generation-7/` y `generation-8/` tiene **exactamente un commit**; ninguno fue retocado.

**Invariantes.** `ARCHITECTURE_DELTA.md` declara 1..14 sin huecos ni duplicados. Verifiqué el 11, el 12 y el 13. El 10 falla en su parte estructural: ver `L3-g9`.

## Bloqueantes

**L1-g9 — `MIGRATION.md` describe una migración que ya no es la que corre; tres filas de su tabla de reglas son falsas.**

- «**No inventa retiradas** | **no escribe un solo `UNPINNED`**». Falso. Lo demostré: base con un `PINNED 100` cuyo hecho vivo desaparece, se reabre, y el libro queda `[('2099-04','PINNED',100,'COMMISSION_APPROVED'), ('2099-04','UNPINNED',100,'MIGRACION')]`. Es justamente lo que la propia página declara dos párrafos antes y lo que dice el invariante 12.
- «**Es idempotente** | sólo mira períodos cuyo último evento no sea ya `PINNED`». Falso. `_backfill_period_rate_events` recoge **todos** los períodos con entradas o con libro y llama a `reconcile_period_rate` sobre cada uno; la idempotencia sale de que la reconciliación no escribe cuando ya coincide.
- «**Es auditable** | todo período sembrado deja `COMMISSION_PERIOD_RATE_SEEDED`». Falso. `COMMISSION_PERIOD_RATE_SEEDED` **no existe en ninguna línea del árbol**; las acciones reales son `COMMISSION_PERIOD_RATE_PINNED` y `COMMISSION_PERIOD_RATE_UNPINNED`.

Es la cuarta aparición del patrón, con la misma forma que `L1-g8`: la generación cambió la regla y el documento de contrato que describe esa operación no se tocó. Quien lea `MIGRATION.md` para saber qué hace la migración con una base de producción obtiene tres respuestas equivocadas, incluida la garantía de que jamás retira una fijación.

**L2-g9 — `HANDOFF.md` cita un rótulo de pantalla que el código no produce.** Línea 172: « · provisional: aún sin aprobación ni pago en el período». Esa cadena no existe en el árbol. `comisiones_ui.py:262` emite « · todavía sin tasa fijada: el período sigue siendo corregible». El propio `VISUAL_EVIDENCE.md` explica que esa redacción cambió en la generación 7 —y por qué la anterior era falsa sobre una base con evidencia discrepante—, pero `HANDOFF.md` quedó con la cita de la generación 6.

**L3-g9 — El invariante 10 apoya su garantía «por construcción» en un choke point que no lo es, y omite un tercer llamador.** Dice que `reconcile_period_rate` «se invoca desde `_set_status` —**por donde pasa toda transición de estado**—… así que las cuatro rutas de `AB1-g6` y **cualquiera futura** quedan cubiertas por construcción». Instrumenté `_set_status` y `_history`: un `recalculate` sobre una liquidación `ELEGIBLE` produce la transición `ELEGIBLE → CALCULADA` con **cero llamadas a `_set_status`** (`comisiones.py:1069` escribe `status='CALCULADA'` con un `UPDATE` directo, y lo mismo hacen `_apply_source_update` en `:508` y la promoción a elegible en `:639`). La prueba de que `_set_status` no cubre todo está en el propio código: `recalculate` tiene que llamar a `_reconcile_period_pin` por su cuenta —un tercer sitio de invocación que la enumeración del invariante no menciona.

Verifiqué que hoy **no hay fuga económica** por esta vía: las rutas que esquivan `_set_status` sólo tocan estados no vivos, salvo la rama de reparación, que sí reconcilia explícitamente. Lo que es falso es la afirmación estructural, y con ella la garantía de que «cualquiera futura» queda cubierta: una transición de boundary escrita mañana en cualquiera de esos tres `UPDATE` directos no reconciliaría nada.

## Observaciones no bloqueantes

1. **«El último evento del período» está escrito tres veces.** `comisiones._last_period_rate_event`, la consulta en línea de `repository.reconcile_period_rate` —literalmente el mismo SQL, copiado— y `comisiones._pinned_periods_from`, que lo resuelve con un `JOIN … MAX(id)` distinto. Ningún documento reclama unicidad aquí, así que no es bloqueante, pero es exactamente la forma de duplicación que abrió `AB1-g6`, `AB1-g7` y `AB1-g8`.
2. **`live_official_facts_sql(by_period=False)` no tiene ningún llamador**, ni en producción ni en pruebas.
3. **La regla «un pago manda sobre una aprobación» de `resolve_period_rate` es inalcanzable como criterio de tasa**: el chequeo de ambigüedad devuelve `AMBIGUOUS` antes, de modo que cuando se llega al `sorted` todos los hechos llevan ya la misma tasa. Sólo decide qué liquidación se cita como causa del `PINNED`.
4. **`TEST_EVIDENCE.md` llama «13 pruebas dirigidas» a lo que son 11 funciones y 13 casos.**
5. **`MIGRATION.md`: «Tenerlo escrito dos veces falló dos generaciones seguidas»**, cuando el resto del paquete cuenta tres.
6. **Docstring de `set_general_rate`:** conserva «lo tarifado nunca se re-tarifa», que la generación 9 supera explícitamente.
7. **`HANDOFF.md` §«Generación 6 — qué se hizo»** describe funciones que ya no existen. Como sección histórica es admisible; anotado sólo porque es la fuente probable de la que `MIGRATION.md` arrastró `L1-g9`.

## Superficie que mi revisión NO cubrió

- **Ataque económico activo y fuzzing.** Mis ejecuciones fueron sólo las necesarias para contrastar afirmaciones concretas.
- **Concurrencia, rendimiento y comportamiento bajo WAL con varios procesos.**
- **Renderizado real de la interfaz.** Verifiqué el PNG por sus metadatos y las cadenas de rótulo contra el código, no la disposición pixel a pixel.
- **Los documentos de `generation-1/` a `generation-5/`** y las afirmaciones históricas del paquete sobre generaciones anteriores a la 6.
- **El resto del árbol** fuera de `modulos/gestion_central/`, `tests/gestion_central/` y las dos herramientas del manifest.
- **El comportamiento del paquete en un clon limpio.**
- **Prueba de que las 13 pruebas de la generación 9 fallan con la regla anterior.** `TEST_EVIDENCE.md` afirma que la decisiva se verificó en los dos sentidos y da los valores `10000` / `700`; no revertí el código para reproducirlo.
