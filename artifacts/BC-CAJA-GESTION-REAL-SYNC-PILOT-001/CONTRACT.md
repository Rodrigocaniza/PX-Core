# Contrato de implementación propietaria de PX-Core

- Autoridad de implementación: PX-Core.
- Base canónica: `origin/main@bb270343bf90e4f7b4cc3dede903b600ab66765f`.
- Rama: `feature/bc-caja-gestion-real-sync-pilot-001`.
- BC-Core: reservado/pausado; no requerido, consultado ni modificado.
- Entrada autorizada: copia SQLite local creada con Backup API; apertura `mode=ro` y `query_only`.
- La base productiva de BC Caja nunca es abierta por el importador.
- Datos reales: exclusivamente fuera de Git y de `artifacts/`.
- Salida: estado de revisión central, historial y outbox pendiente local; sin correo, Telegram ni escritura a BC Caja.
- Usuario operativo: `sol.piloto`, rol `ADMIN_CENTRAL`; auditores tienen lectura y operadores de sucursal no acceden a revisión central.
- BC-Finanzas y producción general: desconectados/deshabilitados.

## Alcance funcional

Tabla horizontal fila por venta con fecha, sobre, cliente, CI/RUC, teléfono,
vendedora, artículos, códigos, laboratorio, receta/observaciones, importes,
entrega, estado FactuFácil y registrador. Incluye revisión por campo/fila/lote,
selección extendida, teclado, filtros, navegación, progreso, observaciones
append-only, correcciones, revalidación selectiva, alertas pendientes y
persistencia tras reinicio.

FactuFácil se presenta como `NO DISPONIBLE PILOTO`: no existe conexión real.

