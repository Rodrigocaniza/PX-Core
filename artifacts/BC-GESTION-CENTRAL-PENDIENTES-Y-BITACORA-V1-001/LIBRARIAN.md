# Librarian — PASS

- Misión independiente: base `feature/bc-gestion-central-sync-receiver-v1-001`,
  sin depender de la vista de proyecciones Sync ni apilarse sobre ella.
- Reutiliza `ReviewService` (`list_sales`, `pending_corrections`, `notes`,
  `events`) y `COLORS`; no duplica esquema, permisos ni tema visual.
- `pending_alerts` es la lectura simétrica que faltaba junto a
  `pending_corrections`; no crea tabla ni estado nuevo.
- Cambios sobre código existente: un método de lectura en `real_sync.py` y el
  enganche del botón en `ui.py`.
- Telegram, Inventario, Seguridad, Historial y Caja quedan sin tocar.
- No hay producción, servicio, credenciales ni migración operativa.
