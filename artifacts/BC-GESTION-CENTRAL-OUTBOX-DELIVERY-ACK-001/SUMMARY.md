# Resumen

Se implementó un transporte local-first sustituible y durable para mensajes de BC Gestión Central. La creación transaccional alimenta un dispatcher con envelope v1, receptor simulado persistente, entrega/ACK idempotentes, backoff limitado, recuperación de envíos abandonados, errores sanitizados e historial append-only.

Sol dispone de una bandeja separada con KPIs, filtros por fecha/sucursal/PC/estado, intentos y fechas, detalle auditable, procesamiento local, reintento seguro y cancelación con motivo. No existe red, envío real, credenciales ni cambio productivo.

Base exacta: `c87d8571535c70b4177364146fb2795219e50edf` de `mission/bc-gestion-central-supervision-operativa-001`.
