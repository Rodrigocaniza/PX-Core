# BC Caja Operator UX — evidencia visual

- Base exacta: `ec4e2e00f056df693dbb97dbf72ff308660832b4`.
- EntryPoint validado: `bc_caja.main([])` mediante `tools/capture_bc_caja_entrypoint.py`.
- Datos: SQLite temporal aislada; ningún dato operativo fue modificado.
- Full HD: proceso DPI-aware y contenido anclado al origen físico; tres bloques horizontales, tres KPI globales, draft separado y tabla de nueve columnas.
- Compacto 1366×768: los mismos tres bloques permanecen visibles, con controles compactos y scroll real.
- Privacy: enmascara únicamente Venta total del día, Efectivo y Saldo pendiente.
- Venta en curso: importes visibles, no persistida y excluida del contador de movimientos.
- SQLite: se conserva el UPSERT de `cash_entries`; no reaparece DELETE/reinsert incompatible con FK.

## Capturas

- `final-1920x1080.png`: bbox real `x=0 y=0 width=1920 height=1061`; cero columnas negras laterales y controles completos.
- `final-1366x768.png`: 1366×768.

## Verificación interactiva

- Formato/total/saldo: `1.500.000 + 250.000 = 1.750.000`; saldo `250.000`.
- Gasto integrado: PASS.
- Scroll con 30/20 movimientos: PASS.
- Sin solapamiento formulario/acciones: PASS en ambos perfiles.
- Arqueo conforme, faltante y sobrante: PASS.
