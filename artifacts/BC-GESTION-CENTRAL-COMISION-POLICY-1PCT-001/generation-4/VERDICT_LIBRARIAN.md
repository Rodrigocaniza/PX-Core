# VERDICT_LIBRARIAN — BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001 (generación 4)

| | |
|---|---|
| **Runner** | LIBRARIAN-IND-COMISION-POLICY-1PCT-004 (independiente; sin contacto con QA ni Auditor) |
| **Rol** | Revisor independiente de veracidad documental |
| **Snapshot** | `5652e46ce7127060ed50d96e464e732809351550` — verificado con `git rev-parse HEAD`; árbol limpio antes y después (`git status --porcelain` vacío en ambos extremos) |
| **Base declarada** | `e7732603d9eb098867a272598e6d30803a4f1ac3` |
| **Timestamp UTC** | 2026-08-18T01:41:45Z |
| **Ficheros modificados por mí** | ninguno. Sin `git add`, `commit`, `checkout` ni `push`. Temporales fuera del repositorio. |

---

## Cierre de los bloqueantes de la generación 3

Los cuatro reverificados contra **este** snapshot, sin reutilizar las conclusiones de `generation-3/`. Leí los verdicts conservados sólo para conocer el enunciado exacto de cada bloqueante; la comprobación es propia.

| ID | Origen | Veredicto de cierre |
|---|---|---|
| **L1** | LIB gen3 — «27 miembros» del ZIP; eran 31 | **CERRADO** |
| **L2** | LIB gen3 — «veinte observaciones» de la generación 2; eran diecisiete | **CERRADO** |
| **B1** | AUD gen3 — re-tarifado retroactivo de un período ya liquidado | **CERRADO** |
| **B2** | AUD gen3 — importe retirado sin asentar, y sin salida antes de la vigencia | **CERRADO** |

**L1.** `ARTIFACT_CONSISTENCY.md` declara ahora «**34 miembros, 34 byte-idénticos, 0 mismatch** — los 33 del manifest más el propio `MANIFEST.sha256`». Verificado abriendo el ZIP con `zipfile` y comparando byte a byte cada miembro contra el worktree: `members 34 / dirs 0 / mismatch 0 / missing 0`. La composición declarada también es exacta. No queda ni un residuo de las cifras anteriores: `grep` de `27 miembros`, `31 miembros`, `30 archivos` y `30/30` sobre los `.md` del paquete no devuelve nada fuera de `generation-N/`.

**L2.** `INDEPENDENCE.md:63` dice ahora «Sus **diecisiete** observaciones no bloqueantes —seis del Librarian, cinco de QA y seis del Auditor—». Recontado por mí sobre los verdicts conservados: gen2 Librarian **6**, QA **5**, Auditor **6** = **17**. Correcto. Reconté además las otras dos generaciones, porque el defecto histórico de este documento es acertar en una y estimar la otra: gen1 → 8 + 7 + 8 = **23**, que es lo que declara; gen3 → Librarian 6, QA 4, Auditor 7 = **17**, que es exactamente lo que declara el párrafo nuevo. Las tres cifras son ciertas. *(Nota metodológica: el verdict de QA de la generación 3 numera sus observaciones como `O1`–`O4`, no como lista Markdown; contarlas con un patrón de lista da 0. Son cuatro.)*

**B1 — verificado ejecutando el exploit del Auditor contra el código de este snapshot, no leyendo el diff.** Sobre una base nueva, con una liquidación de 10.000.000 Gs del período `2026-08` calculada al 1% (100.000 Gs) y **aprobada**:

```
set_general_rate(4000, '2026-08-01') -> RECHAZADO: "la vigencia 2026-08-01 gobernaría el período
                                        2026-08, que ya fue liquidado…"
set_general_rate(0,    '2026-08-01') -> RECHAZADO (idem)
set_general_rate(9999, '2026-01-01') -> RECHAZADO: "la vigencia no puede retroceder…"
recalculate -> {'evaluated': 1, 'changed': 0}
después: APROBADA, rate_bp=100, commission_amount=100000, policy_version=1
versiones publicadas: [(1, 100, '2026-08-01')]   <- ninguna versión espuria
republicar idéntico -> (1, False)                <- idempotencia intacta
set_general_rate(200, '2026-10-01') -> (2, True) <- el futuro sigue programable
tras publicar el futuro: rate_bp=100, commission_amount=100000  <- el período liquidado no se mueve
```

Los dos vectores del Auditor —al alza (4.000.000 Gs) y a cero— están cerrados, la guarda de retroceso sigue en pie, y las dos propiedades que el paquete promete no romper (idempotencia y programación hacia adelante) se sostienen. La guarda existe en `comisiones.py:735-745`, va **después** del corto-circuito de idempotencia —como declara `WORKFLOW.blockers_open[B1].closure`—, y rechaza toda vigencia cuyo mes no sea posterior a `MAX(substr(period,1,7))` sobre `SETTLED_STATES`. Es exactamente lo que dicen `SUMMARY.md`, `COMMISSION_POLICY_1PCT.md` y el invariante 5 de `ARCHITECTURE_DELTA.md`.

**B2 — verificado reconstruyendo el sub-caso (b) del Auditor por mi cuenta**, con una legada de período `2026-07` (anterior a la vigencia) al 7% / 560.000 Gs, en los dos estados que tomaban la rama sin asiento:

```
[ELEGIBLE]  COMMISSION_RECALCULATED  replaced -> {'commission_amount': 560000, 'rate_bp': 700,
                                                  'policy_status': 'POLITICA_HISTORICA_PREVIA'}
[ELEGIBLE]  idempotente: 3 filas de historial -> 3
[CALCULADA] COMMISSION_RECALCULATED  replaced -> {mismo bloque}
[CALCULADA] idempotente: 3 -> 3
```

El importe retirado ya sobrevive en ruta pública, y el asiento no se repite al recalcular otra vez. La condición del código (`repairing or replaces_amount`, `comisiones.py:857-869`) cubre tanto el cambio de `commission_amount` como el de `rate_bp`, y no inventa asiento cuando no había importe previo. Coincide con el invariante 7 de `ARCHITECTURE_DELTA.md` y con `TEST_EVIDENCE.md`.

**Las dos frases que el Auditor demostró falsas están corregidas, y no quedan reliquias.** `grep` de `re-tarifar` y `pasado` sobre `COMMISSION_POLICY_1PCT.md` no devuelve ninguna ocurrencia de la afirmación absoluta anterior; el docstring de `comisiones.py:696` fue reescrito como las dos guardas. La promesa de reparación universal quedó acotada a «cuyo período **esté en vigencia**», con el sub-caso sin salida documentado explícitamente. **Y el paquete dice lo que el propietario decidió que dijera**: `SUMMARY.md`, `COMMISSION_POLICY_1PCT.md`, el docstring de `set_general_rate` y `WORKFLOW.policy_decision_b1.out_of_scope` afirman los cuatro, sin ambigüedad, que el flujo de corrección explícita y auditada **hoy no existe** y no se implementa en esta generación. No hay sobreventa de alcance en este punto.

---

## Verificaciones ejecutadas

**1. Snapshot y base.** `git rev-parse HEAD` → el declarado. La base `e7732603` aparece idéntica y exacta en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`, y es un commit real. `git log e7732603..HEAD` → seis commits, uno por generación más los dos de registro/corrección.

**2. Recuentos de pruebas — los ocho, ejecutados por mí, ninguno estimado.**

| Cifra declarada | Comando | Resultado |
|---|---|---|
| Regresión **345**/345 | `python -m pytest -q` | **345 passed** ✔ |
| Suite del módulo **145** | `pytest tests/gestion_central/` | **145 passed** ✔ |
| Dos archivos de comisiones **94** | `pytest test_comisiones.py test_comisiones_ui_interactions.py` | **94 passed** ✔ |
| **88** y **6** por archivo | por archivo | **88** y **6** ✔ |
| `test_comisiones.py` 47 → **81** funciones | diff contra la base | 47 → **81** ✔ |
| Interfaz 4 → 6 funciones y 6 casos | idem | 4 → **6** ✔ |
| **5** parametrizadas aportando 7 casos extra | `grep -c parametrize` + lectura de cada decorador | **5**; 2+2+2+4+2 → **+7**; 81+7 = **88** ✔ |
| «51 → 94» entre los dos archivos | funciones en la base (47+4) con **0** `parametrize` | **51** casos ✔ |
| +43 (41 dominio + 2 interfaz), 302 + 43 = 345 | 88−47 = **41**; 6−4 = **2** | ✔ |

**3. Las 10 funciones nuevas y los 14 casos de la generación 4 — recontados contra el snapshot anterior, no contra el documento.** Diff de nombres `75f5c57` → `HEAD` sobre `test_comisiones.py`: **10 funciones añadidas, 0 eliminadas**, y son exactamente las diez que enumeran las dos tablas de `TEST_EVIDENCE.md` (7 para B1, 3 para B2). De ellas, `test_a_settled_period_is_never_re_rated` está parametrizada sobre los cuatro estados liquidados (+3) y `test_an_annulled_amount_before_effective_date_is_recorded_as_replaced` sobre `ELEGIBLE`/`CALCULADA` (+1): **10 + 4 = 14** casos nuevos, y 331 + 14 = **345**. Un diff AST además confirma que la generación 4 añade cuatro ayudantes que el documento no cuenta como pruebas —correctamente, porque no lo son—.

**4. «La generación 4 modifica una sola prueba».** Cierto, verificado por comparación AST función a función contra `75f5c57`: la única con cuerpo distinto es `test_a_settlement_calculated_under_an_older_version_is_never_paid`. Es propia de la misión, y efectivamente **gana** la aserción `pytest.raises(..., "ya fue liquidado")`. Ninguna prueba fue eliminada en esta generación.

**5. `TEST_EVIDENCE.md` enumera exactamente las pruebas que existen.** Todos los nombres citados existen en `tests/`. El único citado que no existe es `test_policy_is_synthetic_pending_approval_and_optional`, citado precisamente como eliminada — y sigue siendo la **única** función removida en toda la misión. Las siete «preexistentes actualizadas» son exactamente las siete listadas. La afirmación «todas las demás siguen intactas» es cierta.

**6. `ARCHITECTURE_DELTA.md` declara ocho invariantes y ninguno es falso.** Contados: **8**, numerados 1-8 sin saltos. El 5 y el 7 son los nuevos y los verifiqué por ejecución. Los otros seis los reverifiqué contra el código de este snapshot. El invariante 5 sostiene «el re-tarifado retroactivo no tiene ruta pública, ni directa ni indirecta»: lo intenté por las dos vías —publicación directa y publicación seguida de `recalculate`— y las dos quedan cerradas.

**7. `MANIFEST.sha256`: 33 archivos y su composición.** 33 líneas; `sha256sum -c` → **33/33 OK**. La composición declarada es exacta: 6 + 2 + 1 + 24 = **33**.

**8. La afirmación nueva sobre el alcance de la verificación del manifest — verificada, y es cierta en su cifra principal.** `git config core.autocrlf` → **true**; no existe `.gitattributes`. Simulé el checkout limpio para las 33 rutas comparando los bytes del worktree contra el blob de `HEAD` con la conversión LF→CRLF:

```
would DIFFER on clean checkout: 21
identical: 12
```

**21 de 33.** Exacto. Verifiqué también las dos sub-afirmaciones: `MANIFEST.sha256` está en LF y **también** llegaría con CRLF; y un manifest con CRLF es inanalizable por `sha256sum -c` —lo reproduje y falla en cada línea—. La conclusión del documento es correcta y, cosa notable, es una **rebaja** de lo que el paquete afirmaba antes, no una exageración. *(Sobre la glosa entre guiones, ver observación 1.)*

**9. ZIP: 34 miembros, byte-idéntico.** 0 directorios, 0 ausentes, 0 mismatch. Incluye `generation-3/` completa.

**10. Backlog: 23 hallazgos, idénticos en los dos extremos.** `HANDOFF.md` tiene **23** ítems numerados; `WORKFLOW.non_blocking_findings_recorded` tiene **23** entradas. Los comparé **uno por uno, en orden**: los 23 pares coinciden en sujeto y numeración. La descomposición que declara `ARTIFACT_CONSISTENCY.md` —14 + 8 + 1— es exacta.

**11. Nueve verdicts.** Los nueve ficheros existen (3 × 3), están en el manifest y en el ZIP, y coinciden con `WORKFLOW.generations[]` y con `INDEPENDENCE.md`. «Se conservan sin retocar» es literalmente cierto: `git diff b90a5db HEAD` sobre los tres directorios `generation-N/` no devuelve nada.

**12. Ficheros tocados por la generación 4.** `git diff --name-only 75f5c57 HEAD` fuera de `artifacts/` da exactamente `modulos/gestion_central/comisiones.py` y `tests/gestion_central/test_comisiones.py`. La afirmación de que `comision_policy.py`, `comisiones_ui.py` y `repository.py` quedan **sin un solo cambio** es cierta, y con ella la de que la exactitud monetaria es la misma de la generación 3. *(Sobre la redacción del recuento, ver observación 2.)*

**13. Tabla de estados de política.** Los cuatro son exactamente `POLICY_STATUSES`. Completa y sin sobrantes.

**14. `SINTETICA_PENDIENTE_APROBACION`.** Una sola vez en código productivo: `comision_policy.py:42`, dentro de `RETIRED_POLICY_STATUSES`.

**15. Reglas canónicas anteriores.** La generación 4 no redocumenta ninguna regla canónica contradiciéndola: su único cambio de contenido económico es endurecer una guarda, y lo declara como tal.

**16. Code spans.** Comprobados los quince `.md` del paquete: cero bloques cercados sin cerrar. La única línea con backticks impares está dentro de un verdict conservado que el paquete declara que no retoca.

**17. Captura.** SHA-256, tamaño (93.307 bytes) y dimensiones (1920×1080 RGB) coinciden con `VISUAL_EVIDENCE.md` y con su línea del manifest. Sigue siendo veraz porque la generación 4 no toca `comisiones_ui.py`.

**18. Estado de la misión.** `current_state` = `IMPLEMENTED`, `safe_closure` = `PENDING`, `MISSION_LEASE.state` = `HELD`. Sin merge a `main`.

**19. Checker.** `PAQUETE CONSISTENTE`.

---

## Bloqueantes

**Ninguno.**

Verifiqué con comandos las once cifras que el paquete pone en juego más la afirmación nueva del CRLF, y **las trece son exactas**. Busqué específicamente el patrón que produjo L1, L2, G2-L1 y G2-L2 —una cifra que la corrección desactualiza y nadie recuenta— rastreando por `grep` los valores viejos: no sobrevive ninguno. Los recuentos de esta generación se hicieron, no se estimaron.

---

## Observaciones no bloqueantes

1. **La glosa del recuento CRLF es más gruesa que el recuento.** `ARTIFACT_CONSISTENCY.md` describe los 21 ficheros como «los `.md`, el `.json` y dos `.py`». El **21 es exacto**; el desglose no lo es del todo. En la práctica son **18 de los 19 `.md`** —`COMMISSION_RULES.md` ya está en CRLF en el worktree y por tanto **no** difiere—, **1 de los 2 `.json`** —`MISSION_LEASE.json` difiere, `WORKFLOW.json` no— y 2 de los 8 `.py`. 18 + 1 + 2 = 21. Un «18 de los 19 `.md`, uno de los dos `.json` y dos `.py`» sería literal. Es el mismo tipo de imprecisión que el hallazgo que el documento acaba de registrar, en la frase que lo registra.

2. **«Dos ficheros de código y uno de pruebas» admite una lectura falsa.** Los ficheros realmente tocados fuera de `artifacts/` son **dos en total**: uno de código y uno de pruebas. La enumeración que sigue a los dos puntos es correcta y completa, y la frase se sostiene si se lee «dos ficheros de código, uno de ellos de pruebas» — pero la lectura aditiva, que es la natural en castellano, da tres. No lo trato como bloqueante porque la lista es exacta y el propio texto la desambigua a renglón seguido; sí lo señalo porque es exactamente el género de frase del que salieron L1 y L2.

3. **El checker sigue sin mirar el ZIP ni contar observaciones.** Las dos afirmaciones que fallaron en la generación 3 seguirían cayendo fuera de su alcance hoy. Registrado como hallazgo abierto 20.

4. **`generations[3].snapshot_commit: null`.** Es la mecánica declarada y el paquete la explica ahora con nombres y commit concretos, que era justamente la observación 2 de la generación 3. Queda cerrada como observación.

5. **«No se usan floats en ningún punto» sigue siendo literalmente inexacto.** `COMMISSION_POLICY_1PCT.md:173` mantiene la frase absoluta, y `comisiones.py:919` sigue produciendo un float en una etiqueta. Sin riesgo económico. Heredada de la generación 1, registrada parcialmente como hallazgo 3.

6. **`SUMMARY.md` y `WORKFLOW.json` siguen discrepando sobre la venta con saldo.** La tabla dice «**0** (no pagable)»; `verified_examples` dice `"commission": null`. Ninguna es falsa, pero el mismo caso se declara de dos formas. Abierta desde la generación 1 y aún no incorporada al backlog de 23.

7. **`MIGRATION.md` paso 1 sigue atribuyendo `commission_policy_versions` a `_add_missing_columns`**, cuando la crea el `CREATE TABLE IF NOT EXISTS` de `migrate()`. Ya está registrada como hallazgo abierto 22, correctamente y sin corregir, según el protocolo.

---

## VEREDICTO

# **PASS**

No encontré ninguna afirmación del paquete demostrablemente falsa contra el código o contra el artefacto.

Los cuatro bloqueantes de la generación 3 están cerrados y lo verifiqué por mi cuenta: **L1** y **L2** recontando el ZIP (34 miembros byte-idénticos) y las observaciones de las tres generaciones (23 / 17 / 17), **B1** ejecutando el exploit del Auditor —vigencia igual, al alza y a cero— contra el código de este snapshot y viéndolo rechazado sin romper idempotencia ni programación hacia adelante, y **B2** reconstruyendo el sub-caso `ELEGIBLE`/`CALCULADA` y comprobando que el importe retirado queda asentado en `replaced` de forma idempotente.

Las trece cifras que el paquete pone en juego son exactas, ejecutadas y no estimadas. No sobrevive ningún residuo de los recuentos que la corrección desactualizó.

El paquete tampoco exagera lo que esta generación hace. Toca un fichero de código y uno de pruebas, declara intactos los otros tres módulos —lo son—, dice que modifica una sola prueba —es una—, acota la promesa de reparación al caso en que realmente se cumple, y afirma en cuatro sitios distintos que el flujo de corrección explícita **no existe** y no se implementa aquí, que es la decisión del propietario. La afirmación nueva sobre el manifest es notable por ir en la dirección contraria a la sobreventa: rebaja el alcance de una garantía que el propio paquete venía dando por mayor, y registra la brecha como hallazgo abierto en vez de corregirla fuera de alcance.

Las siete observaciones son eso: dos imprecisiones de redacción en `ARTIFACT_CONSISTENCY.md` que no alteran ninguna cifra, y cinco carryovers ya registrados en el backlog o explícitamente fuera de alcance. Ninguna justifica un FAIL.

*Árbol limpio al terminar, igual que al empezar. No modifiqué ningún archivo del repositorio; los temporales quedaron en el scratchpad. Trabajé solo, sin conocer los verdicts de QA ni del Auditor de esta generación.*

---

## Nota de registro posterior

Este verdict fue emitido sin conocer los de QA ni del Auditor. El Auditor emitió **FAIL** sobre este mismo snapshot con dos bloqueantes económicos (B1-g4 y B2-g4) que demuestran falsas dos afirmaciones que yo di por ciertas en mis puntos 6 y 12: el invariante 5 de `ARCHITECTURE_DELTA.md` («no tiene ruta pública, ni directa ni indirecta») y el invariante 7 («todo importe retirado queda asentado»). Verifiqué el invariante 5 por las dos vías que el paquete nombra —publicación directa y publicación seguida de `recalculate`— y no exploré las transiciones a `OBSERVADA`/`REVERTIDA`, que es por donde el Auditor lo derribó. Mi PASS se mantiene tal como se emitió, sin retocar, y esta nota queda para que la generación 5 sepa exactamente qué superficie no cubrió este rol.
