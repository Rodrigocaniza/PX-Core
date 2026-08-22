# Auditor — PASS

- Durabilidad: WAL + `synchronous=FULL`; outbox permanece hasta ACK.
- Idempotencia: unicidad por `event_id` y `(installation_id, idempotency_key)` en emisor/receptor.
- Anti-replay: nonce durable; firma, timestamp y revocación quedan en el puerto de BC Seguridad.
- Autoridad: Sync replica hechos y no ejecuta mutaciones cross-branch.
- Conflictos: se conservan hechos distintos; apertura y resolución explícita quedan auditadas.
- Historial: adaptador implementa `HistoryReader`, sólo proyecta el journal y conserva origen.
- FactuFácil: adaptador asistido/desactivado sustituible; no hay scraping ni fuente canónica externa.
- Auditoría de enqueue, intento, error, ACK, recepción, duplicado y conflicto está persistida.
- No hay cambios de producción, migraciones operativas, contraseñas globales ni force-push.
