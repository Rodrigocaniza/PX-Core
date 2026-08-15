# Arquitectura de transporte central y ACK

## Flujo operativo

1. Sol crea una indicación para sucursal/PC; Gestión Central persiste mensaje y outbox en una transacción.
2. Un dispatcher reclama el evento durable, crea un envelope versionado y llama a un `TransportAdapter` desacoplado.
3. El adaptador simulado determinista devuelve entrega, fallo transitorio o fallo permanente sin red ni equipos reales.
4. Una recepción aceptada registra `ENTREGADO`; el receptor sintético emite un receipt/ACK idempotente y pasa a `CONFIRMADO`.
5. Fallos transitorios pasan a `REINTENTO` con backoff limitado; fallos permanentes o agotamiento pasan a `FALLIDO`.
6. Al reiniciar, mensajes `ENVIANDO` abandonados se recuperan a `REINTENTO`, sin duplicar entrega ni ACK.

## Componentes y límites

- Dominio: máquina de estados, envelope, receipt, errores sanitizados y políticas de backoff.
- Persistencia: SQLite local durable, historial append-only e identificadores únicos.
- Puerto: interfaz `TransportAdapter`; no conoce Telegram, credenciales ni secretos.
- Adaptador: simulador determinista sustituible luego por BC-Remote/servicio central.
- UI: bandeja separada del dashboard, con filtros, detalle auditable, reintento y cancelación segura.
- BC Caja sigue siendo origen de movimientos; esta misión no escribe allí.

## Role-State Binding

- `ADMIN_CENTRAL` y `SUPERVISOR`: lectura, creación, reintento y cancelación dentro del alcance autorizado.
- `AUDITOR`: lectura e historial; sin mutaciones.
- `OPERADOR_LOCAL`: sin acceso a la bandeja central.

## Criterios de aceptación

- Estados mínimos persistentes y transiciones validadas.
- Idempotencia de creación, entrega y ACK.
- Reintentos sin duplicación, recuperación de `ENVIANDO`, fallo permanente y cancelación auditada.
- Filtros por fecha, sucursal, PC y estado; visibilidad de intentos, tiempos y error sanitizado.
- Reapertura durable, pruebas completas, captura 1920×1080 y cero transporte externo.
