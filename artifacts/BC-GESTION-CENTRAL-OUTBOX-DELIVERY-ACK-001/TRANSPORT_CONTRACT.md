# Contrato preparatorio de transporte v1

## Delivery envelope

Campos: `contract_version=1`, `message_id`, `idempotency_key`, `target.unit`, `target.pc`, `author`, `body`, `created_at`, `attempt` y `sent_at`. El receptor deduplica por `idempotency_key`; repetir el envelope debe devolver el mismo receipt lógico.

## Receipt / ACK

Campos: `contract_version=1`, `receipt_id`, `message_id`, `idempotency_key`, `receiver`, `received_at` y `status=ACCEPTED`. Gestión Central deduplica por `receipt_id` e `idempotency_key`; un ACK repetido no cambia historial ni fechas.

## Errores y reintentos

- `TRANSIENT_OFFLINE`, `TRANSIENT_TIMEOUT`: reintento con backoff 5s, 15s, 60s; máximo 4 intentos totales.
- `PERMANENT_UNKNOWN_TARGET`, `PERMANENT_REJECTED`: `FALLIDO`, sin reintento automático.
- Errores persistidos: código y texto sanitizado; nunca excepciones, rutas, tokens o credenciales.
- Equipos desconectados: permanecen en `REINTENTO` hasta próxima ejecución o agotamiento.

## Compatibilidad BC-Remote

El puerto recibe y devuelve estructuras inmutables sin dependencia de protocolo. Un adaptador futuro podrá serializar JSON sobre BC-Remote/servicio central conservando versión, idempotencia y receipts. Telegram no se implementa aquí.
