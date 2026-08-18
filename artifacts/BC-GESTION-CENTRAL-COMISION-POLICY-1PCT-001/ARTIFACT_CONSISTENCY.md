# Autoverificación de consistencia del paquete

> Autoverificación de la ejecución implementadora. Los verdicts independientes están en
> `generation-N/` y el estado de revisión en `WORKFLOW.json` e `INDEPENDENCE.md`.

Resultado: **consistente**, verificado también por
`python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001`.

- `MANIFEST.sha256` fija **39 archivos**: los seis de código y pruebas tocados por la misión, los
  dos de herramientas, el contrato anterior anotado, y los 30 del paquete. `sha256sum -c`:
  **39/39 OK** ejecutado en el worktree donde se genera el paquete.
- **Alcance exacto de esa verificación.** Los hashes se toman sobre los bytes del worktree. Este
  repositorio corre con `core.autocrlf=true` y sin `.gitattributes`, de modo que git reescribe los
  finales de línea al hacer checkout: en un clon nuevo **20 de los 39 ficheros** —17 de los 25
  `.md`, uno de los dos `.json` y dos de los ocho `.py`— llegan con CRLF y sus hashes no coinciden.
  Los 19 restantes no cambian: 18 ya traen CRLF en el worktree —entre ellos `COMMISSION_RULES.md`
  y los tres `PROMPT_*.txt`— y el decimonoveno es el PNG, que es binario. El propio `MANIFEST.sha256` llega con CRLF, que `sha256sum -c` ni siquiera
  puede analizar. El manifest acredita integridad
  **del paquete tal como se produce**, no reproducibilidad byte a byte entre checkouts. Es una
  propiedad heredada de cómo se construyó el paquete desde la generación 1, no algo que introduzca
  la generación 4; queda registrada como hallazgo abierto 23 y su corrección —fijar `-text` por
  `.gitattributes`— excede el alcance de esta generación, que es sólo B1 y B2.
- Quedan fuera del manifest exactamente dos archivos, por imposibilidad lógica: `MANIFEST.sha256`
  y el ZIP. El ZIP se reconstruyó después de escribir todos los documentos y se verificó miembro a
  miembro contra el worktree: **40 miembros, 40 byte-idénticos, 0 mismatch** — los 39 del manifest
  más el propio `MANIFEST.sha256`. El ZIP guarda los bytes del worktree, así que es el entregable
  que sí reproduce el paquete exactamente, con independencia de lo que git haga en un checkout.
- Base idéntica en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`:
  `e7732603d9eb098867a272598e6d30803a4f1ac3`, que es la raíz de la misión: el padre directo del
  snapshot de la generación 1 y ancestro de los siguientes, uno por generación revisada.
  `WORKFLOW.generations[].snapshot_commit` fija cada snapshot **ya sometido a revisión**; el de la
  generación en curso viaja en `null` hasta el commit de registro posterior, porque un commit no
  puede contener su propio SHA. Así quedaron fijadas las generaciones 1 a 5 —la 5 en
  `2ac9f5c93ec99ed506133310ee6cd19f6779b971`, por este commit de registro—, y por eso la generación
  6, que es la que queda abierta, figura en `null`.
- Cifras coherentes en todos los documentos: **371/371** de regresión, 302 de línea base, **+69**
  casos, **171** en la suite del módulo, **120** casos entre los dos archivos de comisiones. De esos
  69, **26 son de la generación 5** (345 → 371), repartidos en 13 funciones nuevas más 13 casos de
  la matriz de transiciones parametrizada.
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
- En consecuencia, **dos afirmaciones de este paquete están demostradas falsas y se conservan**, para
  que la generación 6 las corrija con la evidencia a la vista: la de `MIGRATION.md` y
  `ARCHITECTURE_DELTA.md` según la cual «un importe heredado no oficial no fija nada, porque fijarlo
  lo volvería incorregible» —la comprobación mira la etiqueta, no si la tasa sigue siendo la oficial
  del período—, y la lectura implícita de que una fecha errónea quedó resuelta: ya no congela la
  publicación, pero fija ese mes para siempre y lo hace pagar mal en silencio.
- Los **quince** verdicts existen en `generation-1/` … `generation-5/` y coinciden con
  `WORKFLOW.generations[]` y con `INDEPENDENCE.md`; los doce anteriores se conservan sin retocar.
  `generation-6/` está vacío.
- La misión **no** está en Safe Closure. `WORKFLOW.current_state` es `IMPLEMENTED`, el
  `MISSION_LEASE` sigue `HELD` y `safe_closure` sigue `PENDING`.
- Captura 1920×1080 RGB, con su SHA-256 y su tamaño declarados en `VISUAL_EVIDENCE.md`, que también
  advierte que el PNG no es reproducible byte a byte porque el historial muestra marcas de tiempo
  reales.
- El contrato económico anterior queda anotado como parcialmente superado en su encabezado, sin
  retocar su cuerpo, y el alcance exacto de lo superado está en este paquete.
- Sin ventas reales, sin datos de clientes, sin secretos, sin proveedor externo, sin red, sin
  producción, sin merge a `main` y sin force-push.
