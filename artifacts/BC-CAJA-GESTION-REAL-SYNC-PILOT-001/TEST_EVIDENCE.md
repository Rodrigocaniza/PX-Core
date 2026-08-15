# Evidencia de verificación

- Focalizadas de sincronización/revisión/callbacks: **13 PASS**.
- Regresión completa PX-Core: **225 PASS**.
- Smoke del EXE empaquetado: **PASS**, 3 filas sintéticas.
- Callbacks EXE: abrir revisión, seleccionar, campo, fila completa, lote,
  filtro, volver y persistencia tras reapertura: **PASS**.
- Full HD 1920×1080: tabla y controles principales visibles; scroll horizontal
  disponible para columnas; no hay controles superpuestos: **PASS**.
- SQLite fuente sintética: hash antes/después idéntico: **PASS**.
- EXE final SHA-256: `49B8E270854142401AC96BA0089417663093E2185C936ED8CCD0E00A0C528E84`.
- Instalación transaccional y copia de rollback: **PASS**.
- Self-check del ejecutable anterior conservado en rollback: **PASS**.
- Importación local: período 2026-08-12, 5 ventas activas, integridad central `ok`.
- Hash de BC Caja antes/después: idéntico: **PASS**.

Los datos usados por pruebas y smoke están marcados como sintéticos y usan
fechas 2099/documentos `DOC-*`. La captura real no está versionada.
