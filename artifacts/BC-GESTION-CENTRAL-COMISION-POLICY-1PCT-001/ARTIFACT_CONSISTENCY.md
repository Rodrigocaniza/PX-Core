# Autoverificación de consistencia del paquete

> Autoverificación de la ejecución implementadora. Los verdicts independientes están en
> `generation-N/` y el estado de revisión en `WORKFLOW.json` e `INDEPENDENCE.md`.

Resultado: **consistente**, verificado también por
`python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001`.

- `MANIFEST.sha256` fija **36 archivos**: los seis de código y pruebas tocados por la misión, los
  dos de herramientas, el contrato anterior anotado, y los 27 del paquete. `sha256sum -c`:
  **36/36 OK** ejecutado en el worktree donde se genera el paquete.
- **Alcance exacto de esa verificación.** Los hashes se toman sobre los bytes del worktree. Este
  repositorio corre con `core.autocrlf=true` y sin `.gitattributes`, de modo que git reescribe los
  finales de línea al hacer checkout: en un clon nuevo **21 de los 36 ficheros** —19 de los 22
  `.md`, uno de los dos `.json` y uno de los ocho `.py`— llegan con CRLF y sus hashes no coinciden.
  Los 15 restantes no cambian: 14 ya traen CRLF en el worktree —entre ellos `COMMISSION_RULES.md`—
  y el decimoquinto es el PNG, que es binario. El propio `MANIFEST.sha256` llega con CRLF, que `sha256sum -c` ni siquiera
  puede analizar. El manifest acredita integridad
  **del paquete tal como se produce**, no reproducibilidad byte a byte entre checkouts. Es una
  propiedad heredada de cómo se construyó el paquete desde la generación 1, no algo que introduzca
  la generación 4; queda registrada como hallazgo abierto 23 y su corrección —fijar `-text` por
  `.gitattributes`— excede el alcance de esta generación, que es sólo B1 y B2.
- Quedan fuera del manifest exactamente dos archivos, por imposibilidad lógica: `MANIFEST.sha256`
  y el ZIP. El ZIP se reconstruyó después de escribir todos los documentos y se verificó miembro a
  miembro contra el worktree: **37 miembros, 37 byte-idénticos, 0 mismatch** — los 36 del manifest
  más el propio `MANIFEST.sha256`. El ZIP guarda los bytes del worktree, así que es el entregable
  que sí reproduce el paquete exactamente, con independencia de lo que git haga en un checkout.
- Base idéntica en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`:
  `e7732603d9eb098867a272598e6d30803a4f1ac3`, que es la raíz de la misión: el padre directo del
  snapshot de la generación 1 y ancestro de los siguientes, uno por generación revisada.
  `WORKFLOW.generations[].snapshot_commit` fija cada snapshot **ya sometido a revisión**; el de la
  generación en curso viaja en `null` hasta el commit de registro posterior, porque un commit no
  puede contener su propio SHA. Así quedaron fijadas las generaciones 1 a 4 —la 3 en
  `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a` por el commit de registro `b90a5db`, y la 4 en
  `5652e46ce7127060ed50d96e464e732809351550` por este commit de registro—, y por eso la generación
  5, que es la que queda abierta, figura en `null`.
- Cifras coherentes en todos los documentos: **345/345** de regresión, 302 de línea base, **+43**
  casos, **145** en la suite del módulo, **94** casos entre los dos archivos de comisiones. De esos
  43, **14 son de la generación 4** (331 → 345), repartidos en 10 funciones nuevas más 4 casos de
  parametrización.
- Backlogs idénticos: `HANDOFF.md` y `WORKFLOW.json` comparten los mismos **27** hallazgos abiertos
  — los 14 de la generación 2, los **8** de las observaciones de la generación 3, el **1** que la
  generación 4 detecta sobre el alcance del manifest, y los **4** de las observaciones de la
  generación 4. Los **37** heredados de la misión anterior se citan por referencia, no se recuentan.
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
- La generación 4 toca **dos ficheros** fuera de `artifacts/`: `comisiones.py` —la guarda de período
  liquidado, el asiento `replaced` y los dos docstrings— y `test_comisiones.py` —diez funciones
  nuevas y una modificada—. `comision_policy.py`, `comisiones_ui.py` y `repository.py` quedan **sin
  un solo cambio**: la exactitud monetaria `Decimal` y el único `HALF_UP` canónico son exactamente
  los de la generación 3.
- **La generación 4 fue INVALIDADA.** Librarian PASS, QA PASS, Auditor **FAIL** con dos bloqueantes
  económicos nuevos, `B1-g4` y `B2-g4`, registrados en `WORKFLOW.blockers_open`. En consecuencia,
  **dos afirmaciones de este paquete están demostradas falsas y se conservan sin corregir**, para
  que la generación 5 las arregle con la evidencia a la vista: el invariante 5 de
  `ARCHITECTURE_DELTA.md` («el re-tarifado retroactivo no tiene ruta pública, ni directa ni
  indirecta») y el invariante 7 («todo importe retirado queda asentado»), con sus ecos en
  `COMMISSION_POLICY_1PCT.md` y `SUMMARY.md`. Nada de lo que este documento afirma sobre B1 y B2
  debe leerse como verificado.
- Los **doce** verdicts existen en `generation-1/` … `generation-4/` y coinciden con
  `WORKFLOW.generations[]` y con `INDEPENDENCE.md`. Los nueve anteriores se conservan sin retocar.
- La misión **no** está en Safe Closure. `WORKFLOW.current_state` es `REMEDIATION`, el
  `MISSION_LEASE` sigue `HELD` y `safe_closure` sigue `PENDING`.
- Captura 1920×1080 RGB, con su SHA-256 y su tamaño declarados en `VISUAL_EVIDENCE.md`, que también
  advierte que el PNG no es reproducible byte a byte porque el historial muestra marcas de tiempo
  reales.
- El contrato económico anterior queda anotado como parcialmente superado en su encabezado, sin
  retocar su cuerpo, y el alcance exacto de lo superado está en este paquete.
- Sin ventas reales, sin datos de clientes, sin secretos, sin proveedor externo, sin red, sin
  producción, sin merge a `main` y sin force-push.
