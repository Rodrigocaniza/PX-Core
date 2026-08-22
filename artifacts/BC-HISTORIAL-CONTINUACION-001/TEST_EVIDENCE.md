# Evidencia de pruebas

- Dirigidas post-commit: `28 passed in 0.29s`.
- `compileall`: PASS.
- Suite completa: `1410 passed`, con 2 fallos en
  `tests/gestion_central/test_ui_interactions.py`.
- Los mismos 2 fallos se reprodujeron sobre el worktree limpio de
  `origin/main`; no son regresiones de Historial.
- `git diff --check`: PASS (avisos ambientales LF/CRLF solamente).
- Escritura rechazada por prueba explícita de `PRAGMA query_only`.
