# Verdict — Librarian, generación 11
Runner: LIBRARIAN-IND-COMISION-POLICY-1PCT-011
Snapshot: 75d7f1b6d0ff090abe9f1c063388c38b3f2f4ab0
Veredicto: FAIL

## Qué verifiqué y cómo

**Pruebas y recuentos.** `python -m pytest -q` → **456 passed**. `python -m pytest tests/gestion_central -q` → **256 passed**. Recuento real por archivo, recolectado uno a uno con `--collect-only -q`: `test_comisiones.py` 112, `test_comisiones_ui_interactions.py` 8, `test_comision_rate_boundary.py` 24, `test_comision_period_unpin.py` 23, `test_comision_legacy_facts.py` 14, `test_comision_rate_coherence.py` 13, `test_comision_reconcile_reach.py` 11 = **205**. Coincide exactamente con lo declarado. Las tres pruebas nuevas de la generación son reales: `test_un_importe_inventado_no_llega_al_pago`, `test_la_guarda_atrapa_una_violacion_sintetica` y `test_los_escritores_exentos_son_los_declarados` (453 → 456).

**`L1-g10`.** Cerrado. Las docstrings de `_reconcile_period_pin` (`comisiones.py:788`) y de `reconcile_period_rate` (`repository.py:402`) enumeran ahora los cuatro escritores y dicen explícitamente que `_set_status` **no** es el único punto de paso. Barrí «único punto de paso», «por donde pasa» y «toda transición de estado» sobre todo el árbol: no queda ninguna afirmación viva de la forma antigua. Las apariciones restantes son citas históricas etiquetadas como tales.

**La guarda estructural, ejercitada de verdad.** No la leí: la corrí contra árboles mutados. Copié `modulos/gestion_central/` al scratchpad, le inyecté el escritor que desarmó la versión anterior —`cierre_masivo` con el literal SQL partido en dos y sin reconciliar— y apunté `MODULO` a la copia. La guarda **falla** y lo reporta por nombre: `comisiones.py::cierre_masivo escribe commission_entries y no reconcilia su período`; `test_los_escritores_exentos_son_los_declarados` también falla y exhibe el conjunto real. La afirmación «verificada contra el módulo real» de `TEST_EVIDENCE.md` es cierta, y el caso concreto que motivó `L2-g10` está cerrado.

**La autocomprobación.** Comprueba algo, y algo pertinente: los tres casos que evadían la versión textual —literal partido, mención en comentario, `INSERT` en vez de `UPDATE`— se construyen como fuente y se exige que sean detectados como escritores sin reconciliación, con un contrapunto positivo para que la aserción no sea vacua. `_sql_de` recoge también las `JoinedStr`, de modo que el `f"UPDATE commission_entries SET {…}"` de `_set_status` sí se ve; `_llama_a` exige un nodo `Call` real, así que un comentario ya no cuenta; y el recorrido cubre los quince módulos del paquete, no uno.

**Dónde el análisis sintáctico sigue ciego.** Probé doce formas de escritor contra el detector y, las que evadían, las inyecté además en una copia del módulo real. `executemany` con literal se detecta; un helper genérico que reciba la sentencia como parámetro se detecta, porque el literal sigue estando en el cuerpo del llamador; los métodos anidados se detectan. **No se detectan**: el SQL izado a una constante de módulo, el armado por concatenación en tiempo de ejecución, el `f-string` que interpola el nombre de la tabla, el `DELETE`/`REPLACE INTO` y el `lambda`. Con cuatro de esos escritores inyectados en la copia del módulo real —constante de módulo, concatenación, interpolación y `DELETE`, ninguno reconciliando— **las cuatro pruebas estructurales pasan en silencio**. De ahí el bloqueante.

**Las dos exenciones.** Son las correctas y siguen siéndolo, verificado contra el código. `_create_entry` se invoca desde tres sitios y en todos el `status` es `ELEGIBLE` o `PENDIENTE_SALDO`, con `rate_bp` y `commission_amount` en `NULL`: no puede fabricar un hecho vivo. `_migrate_commission_policy` sólo escribe `policy_status` en sus dos `UPDATE`, sin tocar tasa ni importe, y `migrate()` llama a `_backfill_period_rate_events` en la línea inmediatamente siguiente, dentro de la misma transacción.

**Invariante 4 y la guarda aritmética.** Describe la guarda nueva y es cierto. La comprobación vive en `_require_current_policy`, que cuelga de `_require_official_and_live`, que es el `guard=` de las tres puertas. Lo verifiqué por comportamiento: manipulando `commission_amount` a 9.000.000 sobre una base de 10.000.000, tanto `approve` como `mark_paid` rechazan con «el importe no es el que produce la tasa aplicada».

**Invariantes.** `ARCHITECTURE_DELTA.md` declara **1..14** sin huecos ni duplicados. Contrasté los catorce contra el código. El único `INSERT` sobre `commission_period_rate_events` en producción está en `repository.py:478`, y no hay `UPDATE` ni `DELETE`. El 10 es el que falla, y por eso está en Bloqueantes.

**Empaquetado.** `MANIFEST.sha256` con **60** entradas: `sha256sum -c` da 60/60 OK. ZIP con **61** miembros; comparé miembro a miembro contra el worktree por SHA-256 y ninguno difiere. Recuento de finales de línea recalculado por mí: **53 llegarían con CRLF**, siete no cambian. Coincide con lo declarado, y el recuento vive sólo en `ARTIFACT_CONSISTENCY.md`. Captura: 93.665 bytes, 1920×1080, RGB, SHA-256 `f0919e28…d93dc6`.

**Backlog y coherencia.** `HANDOFF.md` y `WORKFLOW.json` declaran los mismos **29** hallazgos. `check_mission_package_consistency` → `PAQUETE CONSISTENTE`. `generation-6/` a `generation-10/` contienen los **quince** verdicts; el diff de `HEAD~1..HEAD` sobre `generation-6/` a `generation-9/` está **vacío**.

## Bloqueantes

**L1-g11 — La cobertura que el invariante 10 declara es universal y la guarda no la tiene: cuatro escritores de `commission_entries` inyectados en el módulo real no reconcilian y la suite pasa entera.**

`ARCHITECTURE_DELTA.md` (invariante 10) afirma, sin ninguna reserva, que lo que sostiene la garantía sobre las rutas futuras es «una prueba estructural que recorre el árbol sintáctico de todos los módulos y **falla si una función que escribe `commission_entries` —con `UPDATE` o con `INSERT`— no reconcilia**». Las docstrings corregidas remiten a esa misma garantía, y el docstring de `test_los_escritores_exentos_son_los_declarados` afirma que «si aparece un escritor nuevo, hay que nombrarlo».

Copié `modulos/gestion_central/` y añadí a `comisiones.py` cuatro métodos que escriben `commission_entries` y no reconcilian nada:

- `cierre_por_constante`, con el SQL izado a una constante de módulo (`con.execute(SQL_CIERRE, …)`);
- `cierre_por_concatenacion`, con `"UPDATE " + _TABLA + " SET status='PAGADA' …"`;
- `cierre_por_interpolacion`, con `f"UPDATE {_TABLA} SET status='PAGADA' …"`;
- `cierre_por_delete`, con `DELETE FROM commission_entries`.

Con `MODULO` apuntando a esa copia, las cuatro pruebas estructurales **pasan las cuatro**. Los tres primeros son escritores por `UPDATE`, exactamente el caso que el invariante dice que hace fallar la prueba. La afirmación es demostrablemente falsa tal como está escrita.

No es una posibilidad teórica: izar SQL a constantes de módulo es el estilo que este mismo paquete ya practica y celebra —`LIVE_OFFICIAL_FACT_SQL`, `PERIOD_MATCH_SQL`, `BOUNDARY_SQL_IN`, `PERIOD_KEY_SQL`—, y la generación 11 acaba de añadir `period_key` con ese mismo criterio. Un mantenedor futuro que escriba `con.execute(SQL_CIERRE, …)` siguiendo la convención del propio módulo no recibirá ningún aviso, y el documento le habrá prometido que sí.

Es la misma forma que `L2-g10` un nivel más adentro, y el remedio es igual de barato por cualquiera de los dos lados: **acotar la afirmación** —decir que la guarda ve el SQL que aparece como literal dentro del cuerpo de la función, y que ése es el alcance de la garantía— o **extender la guarda** para resolver las constantes de módulo y las concatenaciones, y para cubrir `DELETE` y `REPLACE INTO` junto a `UPDATE` e `INSERT`. Lo que no puede quedar es la frase universal sin la prueba que la sostenga.

## Observaciones no bloqueantes

1. **`_llama_a` no mira el receptor.** Compara sólo el nombre del atributo, de modo que `cualquier_objeto.reconcile_period_rate()` cuenta como reconciliación aunque no lo sea. Hoy no hay ninguna llamada así en el árbol.
2. **Las exenciones se declaran por nombre desnudo, no por nombre calificado.** Un método `_create_entry` en cualquier clase de cualquier módulo hereda la exención.
3. **Las otras guardas de unicidad siguen siendo textuales.** `test_el_libro_tiene_un_solo_escritor` y `test_los_dos_lados_deciden_con_la_misma_funcion` cuentan subcadenas y son evadibles por el mismo literal partido que motivó `L2-g10`. Las afirmaciones que protegen **son ciertas hoy**; lo débil es el candado, no la puerta.
4. **La prueba de la guarda aritmética sólo ejercita `review`.** El invariante 4 habla de las tres puertas. Comprobé que `approve` y `mark_paid` rechazan de verdad, pero eso lo demostré yo, no la suite.
5. **`period_key` convive con cuatro normalizaciones crudas** en `repository.py` y `comision_policy.py`.
6. **Importes muertos en `comisiones.py`.** `BOUNDARY_SQL_IN` y `LIVE_OFFICIAL_FACT_SQL` se importan y no se usan; `RATING_BOUNDARY_STATES` sólo aparece en un comentario.
7. **`HANDOFF.md:337` enuncia en presente la frase que `L3-g9` demostró falsa.** Está dentro del relato de la generación 7 y el documento la desmiente en la línea 552, así que se lee como registro histórico.

## Superficie que mi revisión NO cubrió

- **No demostré que no exista un escritor de `commission_entries` fuera de `modulos/gestion_central/`.** Mi búsqueda es tan textual como la guarda que critico y compartiría sus puntos ciegos.
- **No audité el comportamiento económico.** No hice diferencial contra la generación 10 ni reconstruí escenarios de tarifación.
- **No revisé la interfaz** más allá del rótulo, el hash y las dimensiones de la captura.
- **No verifiqué `MIGRATION.md` línea a línea contra el código.** El fichero no cambió en esta generación.
- **No comprobé que los verdicts de `generation-6/` a `generation-9/` sean los originales**, sólo que este commit no los toca.
- **No evalué el rendimiento ni la concurrencia** de la guarda aritmética dentro del `BEGIN IMMEDIATE`.
