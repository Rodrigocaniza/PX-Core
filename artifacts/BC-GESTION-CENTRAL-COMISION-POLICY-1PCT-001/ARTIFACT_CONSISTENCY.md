# Autoverificación de consistencia del paquete

> Autoverificación de la ejecución implementadora. Los verdicts independientes están en
> `generation-N/` y el estado de revisión en `WORKFLOW.json` e `INDEPENDENCE.md`.

Resultado: **consistente**, verificado también por
`python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001`.

- `MANIFEST.sha256` fija **60 archivos**: los once de código y pruebas tocados por la misión, los
  dos de herramientas, el contrato anterior anotado, y los 46 del paquete, que incluyen los quince
  verdicts de `generation-6/` a `generation-10/`. `sha256sum -c`: **60/60 OK**. Los briefs de
  los runners se escriben **antes** de empaquetar desde la generación 9: hacerlo después desajustaba
  el manifest en el propio worktree, y los Librarian de la 7 y la 8 tuvieron que explicarlo.
- **Alcance exacto de esa verificación.** Los hashes se toman sobre los bytes del worktree. Este
  repositorio corre con `core.autocrlf=true` y sin `.gitattributes`, de modo que git reescribe los
  finales de línea al hacer checkout: en un clon nuevo **53 de los 60 ficheros** —40 de los 41
  `.md`, once `.py` y los dos `.json`— llegan con CRLF y sus hashes no coinciden. Los siete
  restantes no cambian: seis ya traen CRLF en el worktree —`COMMISSION_RULES.md`, los tres
  `PROMPT_*.txt` y las dos herramientas de `tools/`— y el séptimo es el PNG, que es binario.
  **`ARTIFACT_CONSISTENCY.md` es uno de los 53, no uno de los siete**: se reescribe con finales LF,
  y en la generación 6 su redacción se clasificó a sí misma al revés, que fue el bloqueante
  `L1-g6`. **Este recuento vive sólo aquí**: repetirlo en el backlog lo dejó desfasado tres veces
  seguidas y abrió `L4-g6` y `L4-g7`. El propio `MANIFEST.sha256` llega con
  CRLF, que `sha256sum -c` ni siquiera puede analizar. El manifest acredita integridad
  **del paquete tal como se produce**, no reproducibilidad byte a byte entre checkouts. Es una
  propiedad heredada de cómo se construyó el paquete desde la generación 1, no algo que introduzca
  la generación 4; queda registrada como hallazgo abierto 23 y su corrección —fijar `-text` por
  `.gitattributes`— sigue fuera del alcance de esta misión, cuyo objeto es la política económica de
  comisión y no el empaquetado.
- Quedan fuera del manifest exactamente dos archivos, por imposibilidad lógica: `MANIFEST.sha256`
  y el ZIP. El ZIP se reconstruyó después de escribir todos los documentos y se verificó miembro a
  miembro contra el worktree: **61 miembros, 61 byte-idénticos, 0 mismatch** — los 60 del manifest
  más el propio `MANIFEST.sha256`. El ZIP guarda los bytes del worktree, así que es el entregable
  que sí reproduce el paquete exactamente, con independencia de lo que git haga en un checkout.
- Base idéntica en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`:
  `e7732603d9eb098867a272598e6d30803a4f1ac3`, que es la raíz de la misión: el padre directo del
  snapshot de la generación 1 y ancestro de los siguientes, uno por generación revisada.
  `WORKFLOW.generations[].snapshot_commit` fija cada snapshot **ya sometido a revisión**; el de la
  generación en curso viaja en `null` hasta el commit de registro posterior, porque un commit no
  puede contener su propio SHA. Así quedaron fijadas las generaciones 1 a 5 —la 5 en
  `2ac9f5c93ec99ed506133310ee6cd19f6779b971`, la 6 en `a5d6955828850b322c7ea00f5b46e3b5e7f3d7e4` y
  la 7 en `41131a6a111be6e33ad1d47497bf22b128faf6e3`, la 8 en
  `cf4fb258703e266148d7bb7332b79ffdddce926c`, la 9 en
  `f284b6c5fc2d0f31ffce7567146cce9371e9502a` y la 10 en
  `bdc4f53fb8b3095ead16fbeadcc3d23ca6f2f2d8`—, y por eso la generación 11, que es la que queda en
  revisión, figura en `null` hasta su propio commit de registro.
- Cifras coherentes en todos los documentos: **456/456** de regresión, 302 de línea base, **+154**
  casos, **256** en la suite del módulo, **205** casos entre los siete archivos de comisiones
  (112 + 8 + 24 + 23 + 14 + 13 + 11). De esos 154, **26 son de la generación 5** (345 → 371), **26
  de la 6** (371 → 395), **23 de la 7** (395 → 418), **13 de la 8** (418 → 431), **13 de la 9**
  (431 → 444), **9 de la 10** (444 → 453) y **3 de la 11** (453 → 456). La 6 reescribió 23 casos de la 5 y retiró 2 parametrizaciones; la 7 reescribió 5 de
  la 6; la 9 reescribió los que nombraban el `origin` de un evento, que pasó a ser la causa de la
  reconciliación en vez del boundary.
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
  `ARCHITECTURE_DELTA.md` sobre lo que la siembra fija, y la lectura implícita de que una fecha
  errónea quedaba resuelta. Las **cinco** que el Librarian de la generación 6 halló —`L1-g6` a
  `L5-g6`, todas documentales— se cierran en este commit de registro.
- La afirmación que la generación 6 conservó demostrada falsa —«un tipeo que será anulado nunca
  alcanza `APROBADA` ni `PAGADA`, así que no puede fijar un mes»— **deja de importar en la 7**: el
  período ya no queda fijado para siempre por un hecho que después se anula, así que el caso que la
  refutaba no produce daño. `SAFE_PAUSE.md` conserva la frase porque es un acta fechada en la
  pausa. Este paquete **no conserva ninguna afirmación vigente demostrada falsa**.
- La generación 6 tocó **seis ficheros** fuera de `artifacts/`, la 7 ocho, la 8 nueve, la 9 diez y
  la 10 cinco. La generación 11 toca **cinco**: los tres de `modulos/gestion_central/` y dos de
  pruebas. Los de la 7 fueron:
  `comision_policy.py` —que recibe `RATING_BOUNDARY_STATES` y `BOUNDARY_SQL_IN`, porque el
  repositorio y el cálculo necesitan el mismo predicado—, `comisiones.py` —el libro de eventos,
  `CentralRepository.record_period_rate_event` como único escritor real —un solo `INSERT` en todo
  el código—, `_reconcile_period_pin` desde `_set_status`, y
  la guarda de venta anulada—, `repository.py` —la tabla nueva y la siembra sobre el libro—,
  `comisiones_ui.py` —la redacción de la rama sin fijar—, y los cuatro de pruebas, uno de ellos
  nuevo. **La aritmética de `comision_policy.py` no cambia**: el `Decimal` y el único `HALF_UP`
  canónico son exactamente los de la generación 3; lo único que se le añade es el boundary
  compartido, que no calcula dinero.
- Las generaciones **6 a 10 fueron INVALIDADAS**. Las tres primeras por el mismo defecto
  estructural en una columna distinta: la misma regla escrita en dos sitios, y cada corrección unificando la mitad
  que ya coincidía. La 6 dejó el boundary de salida sin cerrar (`AB1-g6`); la 7 unificó la lista de
  estados y dejó divergente el filtro de política (`AB1-g7`); la 8 unificó el predicado de vitalidad
  y dejó divergente la regla de decisión (`AB1-g8`). La **generación 9** extrae la decisión entera a
  `resolve_period_rate` y su aplicación a `reconcile_period_rate`, de modo que fijar, soltar y
  refijar son la misma operación en un solo sitio. La **9** obtuvo el **primer `PASS` del Auditor
  de toda la misión** y quedó invalidada sólo por el Librarian, con tres afirmaciones falsas y
  ninguna económica; la más seria, `L3-g9`, era una garantía «por construcción» que no lo era. La
  **generación 10** la amarra con una prueba estructural. Queda pendiente de sus tres verdicts. Los tres confirmaron por separado que
  `AB1-g5` y `AB2-g5` están cerrados, y el Auditor midió los 400.000 Gs de diferencia
  desapareciendo en los dos escenarios exactos de la generación 5. Lo que invalida la generación es
  el boundary de **salida**, que esta generación no tocó: la evidencia se crea con un hecho
  económico y no se retira cuando el hecho se retira.
- Los **treinta** verdicts existen en `generation-1/` … `generation-10/` y coinciden con
  `WORKFLOW.generations[]` y con `INDEPENDENCE.md`; los quince anteriores se conservan sin retocar y
  **no se reutilizan** como aprobación de ninguna generación posterior.
- La misión **no** está en Safe Closure y **no** está cerrada. `WORKFLOW.current_state` es
  `SAFE_PAUSED`, `safe_closure` sigue `PENDING` y el `MISSION_LEASE` quedó
  `RELEASED_FOR_SAFE_PAUSE`. La generación 11 fue **INVALIDADA** por un único bloqueante del
  Librarian, `L1-g11`, no económico; el Auditor y QA dieron `PASS`. Los tres hallazgos económicos
  que el Auditor abrió sobre este snapshot están registrados **aparte y priorizados** en
  `ECONOMIC_FINDINGS_OPEN.md`, por decisión del propietario: no se absorben dentro de ninguna
  generación. Las generaciones 10 y 11 no requirieron decisión nueva; la 9 **sí llevó decisión
  de propietario**, registrada en
  `WORKFLOW.policy_decision_gen9`: una `PAGADA` viva conserva la tasa económica real con la que fue
  pagada, y el 1% es prospectivo. La 8 no la había requerido, porque el módulo ya trataba una
  liquidación con `POLITICA_HISTORICA_PREVIA` como no oficial en todas partes menos en la línea
  defectuosa.
- Captura 1920×1080 RGB, con su SHA-256 y su tamaño declarados en `VISUAL_EVIDENCE.md`, que también
  advierte que el PNG no es reproducible byte a byte porque el historial muestra marcas de tiempo
  reales.
- El contrato económico anterior queda anotado como parcialmente superado en su encabezado, sin
  retocar su cuerpo, y el alcance exacto de lo superado está en este paquete.
- Sin ventas reales, sin datos de clientes, sin secretos, sin proveedor externo, sin red, sin
  producción, sin merge a `main` y sin force-push.
