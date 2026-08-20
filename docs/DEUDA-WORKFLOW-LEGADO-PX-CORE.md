# Deuda — migración del WORKFLOW legado de PX-Core al esquema moderno

Las misiones de BC Caja alojadas en PX-Core registran su ciclo de vida en
`artifacts/<MISION>/WORKFLOW.json` con una forma legada: cada entrada de `history` es un
evento plano `{"event_index", "event", "gate", "generation", "handoff_id", "bundle_sha256"}`
y el empaquetado emite `MANIFEST.sha256`.

El motor de BC Command Center (`BC-Core/tools`) espera otra forma. Por eso, sobre este
formato:

- `tools/mission_closure_assist.py` aborta en `WorkflowRecord.from_dict` con
  `KeyError: 'from_state'`, porque `TransitionEntry` exige `from_state`/`to_state`
  en vez de un evento plano;
- `tools/record_mission_verdict.py` rechaza el veredicto porque exige un `MANIFEST.json`
  de AUTO-003 en disco, y estas misiones producen `MANIFEST.sha256`.

Consecuencia operativa: estas misiones no pueden cerrarse por Safe Closure y se cierran
por la vía legada, anexando el evento de veredicto al `WORKFLOW.json` y sellando el
bundle del gate. `BC-CAJA-OPERATOR-UX-001` se cerró así (evento 20, `AUDITOR_PASS`,
`revision: 20`, `current_state: READY_FOR_COMMIT`).

La migración pendiente, que no bloquea ninguna misión en curso, requiere:

- traducir el historial plano a transiciones `from_state`/`to_state` sin perder
  `event_index`, `handoff_id` ni `bundle_sha256` de los gates ya sellados;
- emitir `MANIFEST.json` junto a `MANIFEST.sha256` en el empaquetado, para que
  `record_mission_verdict.py` pueda validar el hash que registró AUTO-003;
- reejecutar los dos tools sobre una misión ya cerrada como prueba de equivalencia,
  verificando que el veredicto derivado coincide con el registrado a mano.

Hasta entonces, no debe forzarse `mission_closure_assist.py` ni
`record_mission_verdict.py` sobre misiones con este formato: fallan por contrato, no
por un defecto de la evidencia.
