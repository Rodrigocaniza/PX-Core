# BC-CAJA-OPERATOR-UX-001

Base exacta `ec4e2e00f056df693dbb97dbf72ff308660832b4`.

La pantalla principal ahora funciona como terminal de venta: header azul, tres KPI globales, tres bloques de carga, Venta en curso separada, operaciones secundarias compactas y Movimientos del día con nueve columnas. Privacy afecta sólo KPI. El flujo simple directo, Multi-Item, Pedidos, Arqueo, Historial, gastos, retiros y continuidad permanecen conectados a los controladores existentes.

SQLite: el repositorio no fue modificado; se preserva el UPSERT que mantiene `orders.cash_entry_id` y atomicidad.

Evidencia:

- EntryPoint real `bc_caja.main([])` en DB temporal: PASS 1920 y 1366.
- Capturas hash-bound: Full HD y compacto.
- Focales: 57 passed.
- Suite completa: 125 passed.
- `git diff --check`: PASS.

Artifact scope: 14 miembros listados en `MANIFEST.sha256`, sin datos operativos.
