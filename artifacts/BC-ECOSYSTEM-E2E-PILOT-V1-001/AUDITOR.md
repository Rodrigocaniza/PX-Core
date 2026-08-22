# Auditor — PASS

- Licencias y firmas temporales se generan en memoria con primitivas reales Ed25519.
- Cada instalación tiene identidad, secreto sellado y licencia independientes.
- Claims se validan antes de inbox; nonce/replay, revocación y manipulación fallan cerrados.
- Outbox/inbox sobreviven reinicios y dos barreras idempotentes evitan efectos duplicados.
- Historial lee Central con SQLite `mode=ro` y `query_only`; conserva sucursal e identidad fuerte.
- Homónimos sin documento no se fusionan; operador no obtiene escritura cross-branch.
- FactuFácil sigue siendo adapter asistido/desactivable, sin scraping.
