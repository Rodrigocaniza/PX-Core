# Librarian — PASS

- Slice aislado: lectura y pantalla nuevas; el receptor, Historial, Caja,
  Telegram, Inventario y Seguridad quedan sin tocar.
- Reutiliza `Unit`, `Principal`/`PERMISSIONS`, `CanonicalBranchCatalog`, `COLORS`
  y el estilo de `ReviewPanel`; no duplica catálogo, permisos ni tema visual.
- El único cambio sobre código existente es el enganche en `ui.py`: parámetro
  `sync_database` y botón «Recepción Sync».
- No define esquema propio ni mantiene copia paralela de las proyecciones.
- No hay producción, servicio, credenciales, IP ni migración operativa.
