# BC-CAJA-MOVIMIENTOS-SCROLL-001

Estado: CLOSED
Versión: BC Caja 1.0.0-rc.2

- Se eliminó el contador `Mostrando X de X movimientos`.
- Se eliminaron todos los botones de paginación visibles.
- La grilla usa únicamente scroll vertical y horizontal nativo.
- Todos los movimientos del día se ordenan por fecha/hora e identificador estable.
- El render se divide en lotes internos de 250 para mantener respuesta con volúmenes altos.
- El espacio inferior liberado amplía la grilla.
- Regresión: 153 passed.
- Smoke visual real 1366×768: PASS.
- Verification → Packaging → Artifact Consistency → Librarian → QA → Auditor → Safe Closure: PASS.
