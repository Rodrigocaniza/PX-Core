# Autoverificación de consistencia del paquete

> Autoverificación de la ejecución implementadora. Los verdicts independientes están en
> `generation-N/` y el estado de revisión en `WORKFLOW.json` e `INDEPENDENCE.md`.

Resultado: **consistente**, verificado también por
`python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001`.

- `MANIFEST.sha256` fija **41 archivos**: los siete de código y pruebas tocados por la misión
  —uno más que en la generación 5, el archivo dirigido `test_comision_rate_boundary.py`—, los dos
  de herramientas, el contrato anterior anotado, y los 31 del paquete. `sha256sum -c`:
  **41/41 OK** ejecutado en el worktree donde se genera el paquete.
- **Alcance exacto de esa verificación.** Los hashes se toman sobre los bytes del worktree. Este
  repositorio corre con `core.autocrlf=true` y sin `.gitattributes`, de modo que git reescribe los
  finales de línea al hacer checkout: en un clon nuevo **33 de los 41 ficheros** —24 `.md`, siete
  `.py` y los dos `.json`— llegan con CRLF y sus hashes no coinciden. Los ocho restantes no
  cambian: siete ya traen CRLF en el worktree —`ARTIFACT_CONSISTENCY.md`, `COMMISSION_RULES.md`,
  los tres `PROMPT_*.txt` y las dos herramientas de `tools/`— y el octavo es el PNG, que es
  binario. El recuento cambió respecto de la generación 5 porque esta generación reescribió con
  finales LF todos los documentos que tocó. El propio `MANIFEST.sha256` llega con CRLF, que
  `sha256sum -c` ni siquiera puede analizar. El manifest acredita integridad
  **del paquete tal como se produce**, no reproducibilidad byte a byte entre checkouts. Es una
  propiedad heredada de cómo se construyó el paquete desde la generación 1, no algo que introduzca
  la generación 4; queda registrada como hallazgo abierto 23 y su corrección —fijar `-text` por
  `.gitattributes`— excede el alcance de esta generación, que es sólo B1 y B2.
- Quedan fuera del manifest exactamente dos archivos, por imposibilidad lógica: `MANIFEST.sha256`
  y el ZIP. El ZIP se reconstruyó después de escribir todos los documentos y se verificó miembro a
  miembro contra el worktree: **42 miembros, 42 byte-idénticos, 0 mismatch** — los 41 del manifest
  más el propio `MANIFEST.sha256`. El ZIP guarda los bytes del worktree, así que es el entregable
  que sí reproduce el paquete exactamente, con independencia de lo que git haga en un checkout.
- Base idéntica en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`:
  `e7732603d9eb098867a272598e6d30803a4f1ac3`, que es la raíz de la misión: el padre directo del
  snapshot de la generación 1 y ancestro de los siguientes, uno por generación revisada.
  `WORKFLOW.generations[].snapshot_commit` fija cada snapshot **ya sometido a revisión**; el de la
  generación en curso viaja en `null` hasta el commit de registro posterior, porque un commit no
  puede contener su propio SHA. Así quedaron fijadas las generaciones 1 a 5 —la 5 en
  `2ac9f5c93ec99ed506133310ee6cd19f6779b971`—, y por eso la generación 6, que es la que queda en
  revisión, figura en `null` hasta su propio commit de registro.
- Cifras coherentes en todos los documentos: **395/395** de regresión, 302 de línea base, **+93**
  casos, **195** en la suite del módulo, **144** casos entre los tres archivos de comisiones
  (112 + 8 + 24). De esos 93, **26 son de la generación 5** (345 → 371) y **26 de la generación 6**
  (371 → 395): 24 dirigidas más 2 de interfaz. La generación 6 además reescribe 23 casos de la 5 y
  retira 2 parametrizaciones, porque `CALCULADA` y `REVISADA` dejaron de ser estados protegidos a
  propósito.
- Backlogs idénticos: `HANDOFF.md` y `WORKFLOW.json` comparten los mismos **29** hallazgos abiertos
  — los 14 de la generación 2, los **8** de las observaciones de la generación 3, el **1** que la
  generación 4 detecta sobre el alcance del manifest, los **4** de las observaciones de la
  generación 4 y los **2** que aporta la generación 5. Los **37** heredados de la misión anterior se
  citan por referencia, no se recuentan.
- Los verdicts registrados por generación: 1, LIBRARIAN FAIL (L1, L2, L3), QA PASS, AUDITOR FAIL
  (A1, A2); 2, los tres FAIL con cuatro, tres y tres bloqueantes; 3, LIBRARIAN FAIL (L1, L2), QA
  **PASS**, AUDITOR FAIL (B1, B2); 4, LIBRARIAN **PASS**, QA **PASS**, AUDITOR FAIL (B1-g4, B2-g4).
  Se conservan sin retocar, incluidas las afirmaciones que quedaron desactualizadas por la propia
  corrección que provocaron, y la nota que el Librarian de la generación 4 añadió sobre la
  superficie que su revisión no cubrió.
- Los **quince** bloqueantes de las generaciones 1 y 2 figuran cerrados en
  `WORKFLOW.blockers_closed`, cada uno con su corrección localizable en código o documento, y todos
  los de código con prueba propia enumerada en `TEST_EVIDENCE.md`. Los tres runners de la
  generación 3 reverificaron ese cierre por su cuenta y los tres lo confirmaron, y los tres de la
  generación 4 volvieron a confirmarlo.
- Los **cuatro** bloqueantes de la generación 3 están cerrados y **los tres runners de la
  generación 4 lo verificaron por separado**: L1 y L2, documentales, recontando el ZIP y las
  observaciones; B1 y B2, económicos, ejecutando los exploits originales contra el código. B1 se
  cerró por decisión del propietario —opción (a), endurecer la guarda— y B2 asentando `replaced` en
  toda rama de `recalculate` que anule un importe. Lo que la generación 4 demostró es que **ninguno
  de los dos cierres era suficiente**: sus sucesores `B1-g4` y `B2-g4` quedan abiertos.
- La generación 5 toca **cinco ficheros** fuera de `artifacts/`: `repository.py` —la tabla
  `commission_rated_periods` y su siembra—, `comisiones.py` —`pinned_for`, la resolución fijada,
  el registro de la evidencia, la retirada de la guarda por estado, `policy_for_period`, el asiento
  `replaced` en la corrección de origen y el contrato 3—, `comisiones_ui.py` —la cabecera por
  período—, y los dos de pruebas. **`comision_policy.py` no cambia**: la aritmética `Decimal` y el
  único `HALF_UP` canónico son exactamente los de la generación 3.
- **La generación 5 fue INVALIDADA: los tres runners fallaron**, cada uno en una capa distinta y sin
  solaparse. Los tres confirmaron que `B1-g4` y `B2-g4` están cerrados y que el diseño de la
  evidencia durable es correcto; ninguno halló una transición que devuelva un período tarifado al
  catálogo. Lo que falla es lo que el diseño no cubrió: **cuándo se graba la evidencia**. `AB1-g5` y
  `AB2-g5` son económicos y quedan **abiertos**, con dinero mal pagado reproducido en ambos.
  `QB1-g5` y `QB2-g5` son de rotulado y quedan abiertos. Los seis del Librarian son documentales y se
  cierran en este commit de registro.
- Las **dos afirmaciones que la generación 5 conservó demostradas falsas a propósito quedan
  corregidas en la 6**, cada una con la evidencia a la vista: la de `MIGRATION.md` y
  `ARCHITECTURE_DELTA.md` sobre lo que la siembra fija —ahora la siembra depende del mismo hecho
  económico que la fijación en caliente, y ante evidencia ausente o discrepante no fija nada— y la
  lectura implícita de que una fecha errónea quedaba resuelta —un cálculo ya no graba una fijación,
  de modo que un tipeo que nadie aprueba no fija ningún mes—. Este paquete **ya no conserva ninguna
  afirmación demostrada falsa**.
- La generación 6 toca **seis ficheros** fuera de `artifacts/`: `comisiones.py` —el boundary
  explícito, `_pin_rated_period` desde `approve`/`mark_paid`, la retirada de la fijación en
  `recalculate` y el `policy_disclaimer` propio—, `repository.py` —la siembra reescrita y
  `_audit_seed_once`—, `comisiones_ui.py` —el rótulo de ausencia de tasa—, y los tres de pruebas,
  uno de ellos nuevo. **`comision_policy.py` sigue sin cambiar**: la aritmética `Decimal` y el
  único `HALF_UP` canónico son exactamente los de la generación 3.
- Los **quince** verdicts existen en `generation-1/` … `generation-5/` y coinciden con
  `WORKFLOW.generations[]` y con `INDEPENDENCE.md`; se conservan sin retocar y **no se reutilizan**
  como aprobación de la generación 6. `generation-6/` recibe los tres verdicts propios de esta
  generación.
- La misión **no** está en Safe Closure y **no** está cerrada. `WORKFLOW.current_state` es
  `GENERATION_6_REMEDIATED_PENDING_VERDICTS`, `safe_closure` sigue `PENDING` y el `MISSION_LEASE`
  está `ACQUIRED` en PC Casa. Remediar no cierra nada: el cierre depende de tres verdicts
  independientes sobre este snapshot.
- Captura 1920×1080 RGB, con su SHA-256 y su tamaño declarados en `VISUAL_EVIDENCE.md`, que también
  advierte que el PNG no es reproducible byte a byte porque el historial muestra marcas de tiempo
  reales.
- El contrato económico anterior queda anotado como parcialmente superado en su encabezado, sin
  retocar su cuerpo, y el alcance exacto de lo superado está en este paquete.
- Sin ventas reales, sin datos de clientes, sin secretos, sin proveedor externo, sin red, sin
  producción, sin merge a `main` y sin force-push.
