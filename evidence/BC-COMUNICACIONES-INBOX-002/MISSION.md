# BC-COMUNICACIONES-INBOX-002

Repositorio objetivo: `PX-Core`. Base: `5ed42aef6994bcbe491e8178c27bf5ded48c8414`.

Objetivo: convertir la biblioteca existente en el primer incremento operable de bandeja
unificada local, sin conexión real a WhatsApp ni credenciales.

## Alcance cerrado

- cuentas, conversaciones y mensajes;
- estados `NUEVO`, `EN_CURSO`, `RESUELTO` y transiciones validadas;
- asignación a operador;
- filtros combinables por negocio, sucursal, cuenta, estado, operador y texto;
- vista cronológica y respuesta mediante proveedor simulado;
- contadores de estados;
- auditoría append-only;
- migración SQLite `002`, datos demo explícitos e idempotentes;
- UI 1366×768 accesible desde el botón `Bandeja`.

Fuera de alcance: API real, credenciales, WhatsApp Web y conversaciones reales.
