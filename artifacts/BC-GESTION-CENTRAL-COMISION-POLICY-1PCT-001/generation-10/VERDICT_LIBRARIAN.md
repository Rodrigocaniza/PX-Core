# Verdict — Librarian, generación 10
Runner: LIBRARIAN-IND-COMISION-POLICY-1PCT-010
Snapshot: bdc4f53fb8b3095ead16fbeadcc3d23ca6f2f2d8
Veredicto: FAIL

## Qué verifiqué y cómo

Todo contra el código y contra los bytes del worktree, ejecutando. No reutilicé ningún verdict de las generaciones 1..9; los leí sólo para saber qué se afirmaba haber corregido.

**Pruebas.** `python -m pytest -q` → **453 passed**. `python -m pytest tests/gestion_central -q` → **253 passed**. Recuento real por archivo con `--collect-only`: `test_comisiones.py` **112**, `test_comisiones_ui_interactions.py` **8**, `test_comision_rate_boundary.py` **24**, `test_comision_period_unpin.py` **23**, `test_comision_legacy_facts.py` **13**, `test_comision_rate_coherence.py` **13**, `test_comision_reconcile_reach.py` **9** = **202**. Coincide con lo declarado. La tabla de la generación 10 suma 2+3+2+2 = 9, que son las nueve del archivo nuevo.

**Los cuatro escritores de estado.** `grep` sobre todo el árbol: los únicos `UPDATE commission_entries` de producción son `comisiones.py:503` (`_apply_source_update`), `:637` (`_promote_to_eligible`), `:736` (`_set_status`) y `:1075` (`recalculate`), más dos en `repository.py:298,302` que sólo tocan `policy_status`. Los cuatro reconcilian de verdad: `_reconcile_period_pin` se llama en `:511`, `:645`, `:742` y `:1109`. Lo comprobé además por mutación, sobre una copia del árbol en el scratchpad: retirar la llamada de `recalculate` rompe **6** pruebas de comportamiento. La cobertura de comportamiento es real.

**Lectura del libro y `MAX(id)`.** El estado vigente de un período se lee en un único sitio, `CentralRepository.last_period_rate_event`; `pinned_periods_from` delega en ella. `MAX(id)` ya no aparece en producción.

**`MIGRATION.md`, fila a fila.** Las seis reglas de la tabla del paso 5 son ciertas hoy. «Sí aplica la regla»: lo ejecuté —base con `PINNED 100` cuyo hecho vivo pasa a `REVERTIDA` por SQL crudo, reapertura → libro `[PINNED@100 COMMISSION_APPROVED, UNPINNED@100 MIGRACION]`—, que es lo contrario de lo que decía la tabla de la generación 9 y motivó `L1-g9`. Los tres bloqueantes documentales de `L1-g9` quedan cerrados.

**Invariantes.** `ARCHITECTURE_DELTA.md` declara **1..14** sin huecos ni duplicados. El 10 ya no afirma que `_set_status` sea el único punto de paso y enumera los cuatro sitios correctos. Ninguno de los catorce me resultó falso **en el documento**; el problema está en el código que ese invariante describe (`L1-g10`).

**Paquete.** `sha256sum -c MANIFEST.sha256`: **57/57 OK**. ZIP: **58 miembros**, **0 mismatch**. Finales de línea: **50 en LF** (37 `.md`, 11 `.py`, 2 `.json`), **6 ya en CRLF** y el PNG binario — exactamente lo declarado, y el recuento vive sólo en `ARTIFACT_CONSISTENCY.md`. `check_mission_package_consistency` → `PAQUETE CONSISTENTE`.

**Captura.** SHA-256 `f0919e28…d93dc6`, **93.665 bytes**: idénticos a lo declarado.

**Backlog.** 29 entradas numeradas en `HANDOFF.md` y 29 en `WORKFLOW.non_blocking_findings_recorded`, mismo orden y mismo asunto una a una.

**Verdicts anteriores.** Cada uno de los **doce** verdicts de `generation-6/` a `generation-9/` tiene exactamente un commit. Ninguno fue retocado.

**Correcciones de la generación 9 comprobadas.** `L2-g9` cerrado. La observación 6 del Librarian de la 9 ya no está en el árbol. La observación 4 quedó corregida en `TEST_EVIDENCE.md`.

## Bloqueantes

**L1-g10 — La afirmación falsa de `L3-g9` sobrevive literal en el código entregado, en las dos docstrings que la sostenían.**

`ARCHITECTURE_DELTA.md` invariante 10 dice: «`_set_status` **no** es el único punto de paso: afirmarlo era falso». El código del mismo snapshot sigue afirmándolo:

- `comisiones.py:779`, docstring de `_reconcile_period_pin` — la función que el arreglo trata: «Se invoca desde `_set_status`, que es por donde pasa **toda** transición de estado… y cualquier ruta futura también.»
- `repository.py:400`, docstring de `reconcile_period_rate`: «Se invoca desde `_set_status` —por donde pasa toda transición— y desde la apertura de la base, **de modo que ninguna ruta puede saltársela**.»

Las dos son falsas por partida doble: la enumeración es incompleta —`_reconcile_period_pin` tiene cuatro llamadores— y la premisa es falsa. La prueba de que se trata de una edición a medias está a quince líneas en el mismo fichero: `comisiones.py:642` dice «`_set_status` no es el único punto de paso». El mismo fichero afirma las dos cosas.

No es una reliquia en una sección histórica: es la garantía «por construcción» que `L3-g9` demostró falsa, en tiempo presente, en la docstring de la función que la generación 10 dice haber amarrado. `HANDOFF.md` afirma haber cerrado «`L3-g9`, por los dos lados»; el lado del código quedó sin tocar.

**L2-g10 — La prueba estructural no comprueba lo que el paquete dice que comprueba; la «guarda que falla si alguien la rompe mañana» no falla.**

Repliqué la lógica exacta de `test_toda_funcion_que_escribe_un_estado_reconcilia_su_periodo` —es puramente textual— y la corrí sobre variantes de `comisiones.py`:

- **Un escritor de estado nuevo que parta el SQL en dos literales pasa invisible.** Añadí `cierre_masivo` con `con.execute("UPDATE commission_entries" " SET status='APROBADA' WHERE id=?", …)` y **sin reconciliar**: la guarda **PASA**. El detector busca la cadena exacta `"UPDATE commission_entries SET"`, y el propio módulo ya parte literales de SQL largo en varias líneas.
- **La comprobación de reconciliación es una búsqueda de subcadena en el cuerpo, no una llamada.** Borré la llamada real de `recalculate` dejando un comentario que nombra `_reconcile_period_pin(`: la guarda **PASA**.
- **El alcance es un solo fichero.** Un `UPDATE … SET status` escrito mañana en `repository.py` o `service.py` queda fuera.

La propiedad que la prueba sí verifica es más estrecha: que las cuatro funciones **de `comisiones.py`** cuyo cuerpo contiene ese literal exacto mencionan `_reconcile_period_pin(`. Es un tripwire útil, y lo digo sin ironía. Pero el paquete lo declara como cuantificador universal y como garantía «por construcción» sobre las rutas futuras, y no lo es. Es la misma forma de defecto que `L3-g9`, esta vez sobre la prueba escrita para cerrarla.

## Observaciones no bloqueantes

1. **`zip(escriben, nombres)` empareja mal.** `escriben` va en orden de fichero y `nombres` está `sorted`. El `assert` es correcto, pero el mensaje de fallo atribuye el defecto a otra función.
2. **`test_el_libro_se_lee_en_un_solo_sitio` cuenta una cadena, no una propiedad.** Una segunda lectura escrita con otro espaciado o con `ORDER BY recorded_at DESC` no la haría fallar. Y `MAX(id) AS` == 0 no impide un `MAX(id)` sin alias.
3. **«La lectura del libro… ahora es una sola» es literalmente inexacto.** `commission_period_rate_events` se lee con cuatro `SELECT` distintos. Lo que se unificó es la lectura del **estado vigente**.
4. **`live_official_facts_sql(by_period=False)` sigue sin ningún llamador.** Era la observación 2 del Librarian de la generación 9.
5. **`HANDOFF.md:337` y `:462` repiten la frase falsa**, en secciones históricas que la sección de la generación 10 retracta unas líneas más abajo. Fuera de bloqueantes por coherencia con el criterio aplicado en la generación 9.
6. **La regla «un pago manda sobre una aprobación»** sigue sin poder decidir una tasa. Observación 3 del Librarian de la 9, aún abierta.
7. **Dos ejecuciones concurrentes de `pytest` sobre este árbol se pisan.** No es un defecto del paquete, pero conviene saberlo antes de leerlo como una regresión.

## Superficie que mi revisión NO cubrió

- **Ataque económico activo, fuzzing y exploración de estados.**
- **La semántica económica de la generación 9 en sí** —7% preservado, 1% prospectivo—: la di por comprobada por las pruebas y por el verdict del Auditor de la 9.
- **Concurrencia, rendimiento y comportamiento bajo WAL con varios procesos.**
- **Renderizado real de la interfaz.**
- **Los documentos de `generation-1/` a `generation-5/`.**
- **El resto del árbol** fuera de `modulos/gestion_central/`, `tests/gestion_central/` y las dos herramientas del manifest.
- **El comportamiento del paquete en un clon limpio.**
- **La prueba de que las 9 pruebas de la generación 10 fallan con el código anterior.** Verifiqué la dirección contraria por mutación en una sola de ellas.
