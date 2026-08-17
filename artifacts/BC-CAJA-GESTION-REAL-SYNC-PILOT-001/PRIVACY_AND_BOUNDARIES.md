# Privacidad y límites

- Ninguna SQLite, WAL, SHM, payload de venta, documento, teléfono o nombre real se incluye en Git/artifacts.
- La copia real reside fuera del repositorio, bajo almacenamiento local del piloto.
- El importador verifica integridad SQLite y estabilidad SHA-256 durante la lectura.
- No hay clientes HTTP, SMTP, Telegram ni conexión a BC-Finanzas.
- El outbox de alertas queda `PENDING` y auditado; no entrega mensajes.
- La base productiva de BC Caja permanece intacta y en solo lectura operacional.
- No se leen ni modifican credenciales DPAPI.
- Producción general permanece deshabilitada.

