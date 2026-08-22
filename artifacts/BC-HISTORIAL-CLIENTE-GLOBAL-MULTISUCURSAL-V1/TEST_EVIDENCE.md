# Tests A–L

- A/B: visibilidad cruzada Asunción ↔ Pilar — PASS.
- C: ficha única con CI/RUC fuerte — PASS.
- D: branch/fecha/tipo/sobre explícitos — PASS.
- E/F: operador no modifica sucursal ajena — PASS.
- G: Admin puede operar ambas por política — PASS.
- H: proyección sin costo, margen, comisiones ni datos administrativos — PASS.
- I: Historial read-only; DELETE rechazado — PASS.
- J/K: sin DB paralela ni migración — PASS.
- L: 1421 tests PASS; 3 fallos reproducidos idénticos en `origin/main` limpio.
- Dirigidos post-commit: 41 PASS en 0.41 s.
- PR #14: PR CI / pytest PASS, run `32539018964`, 3m03s.
- PR #13: CI FAILURE (1409 PASS, 3 fallos: dos preexistentes y un test de
  creationflags no portable). La continuación corrige el test portable.
