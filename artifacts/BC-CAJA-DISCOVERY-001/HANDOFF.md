# Handoff — BC-CAJA-DISCOVERY-001

Resultado: PASS técnico de discovery; no equivale a un gate humano registrado por Command Center.

Writer canónico recomendado para la siguiente misión: PX-Core `feature/caja-diaria`.

Siguiente misión: `BC-CAJA-BEHAVIOR-001`.

Punto de partida: adaptar `CajaDiaria.py`; no reescribir UI ni crear Caja dentro de BC-Core.

Condiciones antes de implementación funcional:

- preservar el working tree limpio de PX-Core;
- no tocar los cambios preexistentes de BC-Core;
- crear/usar un worktree limpio de la versión avanzada del Command Center solo cuando exista una integración válida para gobernar PX-Core;
- mantener un solo writer;
- no registrar verdicts, leases o `WORKFLOW.json` a mano;
- no ejecutar commit/push fuera de Safe Closure;
- tratar `Agosto PC 2026.xlsx` como validación pendiente mientras no esté accesible desde el workspace.

Evidencia canónica: `CANONICAL_DISCOVERY.md` y `BC-CAJA-BEHAVIOR-001.md` en este directorio.
