# Auditor — PASS

- Licencia y revocación se reverifican; contexto/branch/capacidad/vigencia fallan cerrados.
- Credencial, firma, payload, nonce y timestamp se validan antes del inbox.
- Inbox y efecto se confirman en una transacción durable con dos barreras de unicidad.
- Replay se rechaza; retry/ACK perdido reciben ACK idempotente sin segundo efecto.
- Reinicio conserva inbox, proyección y auditoría; orden estable por timestamp/event_id.
- Rechazos registran identidad declarada y motivo sanitizado sin secretos.
- No hay escritura cross-branch ni dependencia canónica de FactuFácil.
