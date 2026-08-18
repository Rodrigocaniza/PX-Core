# Autoverificación de consistencia del paquete

> Autoverificación de la ejecución implementadora. Los verdicts independientes están en
> `generation-N/` y el estado de revisión en `WORKFLOW.json` e `INDEPENDENCE.md`.

Resultado: **consistente**, verificado también por
`python tools/check_mission_package_consistency.py artifacts/BC-GESTION-CENTRAL-COMISION-POLICY-1PCT-001`.

- `MANIFEST.sha256` fija **33 archivos**: los seis de código y pruebas tocados por la misión, los
  dos de herramientas, el contrato anterior anotado, y los 24 del paquete. `sha256sum -c`:
  **33/33 OK**.
- Quedan fuera del manifest exactamente dos archivos, por imposibilidad lógica: `MANIFEST.sha256`
  y el ZIP. El ZIP se reconstruyó después de escribir todos los documentos y se verificó miembro a
  miembro contra el worktree: **34 miembros, 34 byte-idénticos, 0 mismatch** — los 33 del manifest
  más el propio `MANIFEST.sha256`.
- Base idéntica en `SUMMARY.md`, `MISSION_LEASE.json` y `WORKFLOW.json`:
  `e7732603d9eb098867a272598e6d30803a4f1ac3`, que es la raíz de la misión: el padre directo del
  snapshot de la generación 1 y ancestro de los siguientes, uno por generación revisada.
  `WORKFLOW.generations[].snapshot_commit` fija cada snapshot **ya sometido a revisión**; el de la
  generación en curso viaja en `null` hasta el commit de registro posterior, porque un commit no
  puede contener su propio SHA. Por eso la generación 3 se publicó con `null` y este commit la fija
  en `75f5c5728cf9194b3e4c91a3b1e83c10ea1ec48a`, y por eso la generación 4 vuelve a figurar en
  `null`.
- Cifras coherentes en todos los documentos: **345/345** de regresión, 302 de línea base, **+43**
  casos, **145** en la suite del módulo, **94** casos entre los dos archivos de comisiones. De esos
  43, **14 son de la generación 4** (331 → 345), repartidos en 10 funciones nuevas más 4 casos de
  parametrización.
- Backlogs idénticos: `HANDOFF.md` y `WORKFLOW.json` comparten los mismos **22** hallazgos abiertos
  — los 14 de la generación 2 más los **8** que aportan las observaciones no bloqueantes de la
  generación 3. Los **37** heredados de la misión anterior se citan por referencia, no se recuentan.
- Los **nueve** verdicts existen en `generation-1/`, `generation-2/` y `generation-3/` y coinciden
  con lo registrado en `WORKFLOW.json` e `INDEPENDENCE.md`: generación 1, LIBRARIAN FAIL (L1, L2,
  L3), QA PASS, AUDITOR FAIL (A1, A2); generación 2, los tres FAIL con cuatro, tres y tres
  bloqueantes; generación 3, LIBRARIAN FAIL (L1, L2), QA **PASS**, AUDITOR FAIL (B1, B2). Se
  conservan sin retocar, incluidas las afirmaciones que quedaron desactualizadas por la propia
  corrección que provocaron.
- Los **quince** bloqueantes de las generaciones 1 y 2 figuran cerrados en
  `WORKFLOW.blockers_closed`, cada uno con su corrección localizable en código o documento, y todos
  los de código con prueba propia enumerada en `TEST_EVIDENCE.md`. Los tres runners de la
  generación 3 reverificaron ese cierre por su cuenta y los tres lo confirmaron.
- Los **cuatro** bloqueantes de la generación 3 figuran en `WORKFLOW.blockers_open`, los cuatro
  como `CERRADO_PENDIENTE_VERIFICACION` o cerrados en el commit de registro. L1 y L2 eran
  documentales —los recuentos del ZIP y de las observaciones de la generación 2—. **B1 y B2 son
  económicos y se cierran en la generación 4**: B1 por decisión del propietario (opción (a),
  endurecer la guarda), B2 asentando `replaced` en toda rama que anule un importe. Las dos frases
  que el Auditor demostró falsas están corregidas en `COMMISSION_POLICY_1PCT.md`, y ninguna
  afirmación del paquete debe leerse como verificada hasta que los tres runners se pronuncien sobre
  el snapshot de la generación 4.
- La generación 4 toca **dos** ficheros de código y **uno** de pruebas: `comisiones.py` —la guarda
  de período liquidado, el asiento `replaced` y los dos docstrings— y `test_comisiones.py` —diez
  funciones nuevas y una modificada—. `comision_policy.py`, `comisiones_ui.py` y `repository.py`
  quedan **sin un solo cambio**: la exactitud monetaria `Decimal` y el único `HALF_UP` canónico son
  exactamente los de la generación 3.
- La misión **no** está en Safe Closure. `WORKFLOW.current_state` es `IMPLEMENTED`, el
  `MISSION_LEASE` sigue `HELD` y `safe_closure` sigue `PENDING`.
- Captura 1920×1080 RGB, con su SHA-256 y su tamaño declarados en `VISUAL_EVIDENCE.md`, que también
  advierte que el PNG no es reproducible byte a byte porque el historial muestra marcas de tiempo
  reales.
- El contrato económico anterior queda anotado como parcialmente superado en su encabezado, sin
  retocar su cuerpo, y el alcance exacto de lo superado está en este paquete.
- Sin ventas reales, sin datos de clientes, sin secretos, sin proveedor externo, sin red, sin
  producción, sin merge a `main` y sin force-push.
