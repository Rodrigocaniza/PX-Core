# Arquitectura, estados y permisos

## Límites

- BC Command Center gobierna misión, lease, gates y cierre; no contiene lógica operativa.
- BC Gestión Central conserva snapshots recibidos y ejecuta consulta, revisión, alertas, auditoría y outbox.
- BC Caja es owner y origen local de movimientos. El importador consume únicamente una copia SQLite `query_only`.

## Local-first y contrato futuro

`central_messages` conserva la intención; `central_outbox` contiene evento, payload canónico, estado `PENDING` e `idempotency_key` SHA-256 único. Un transporte futuro podrá reclamar eventos y registrar intentos sin cambiar el contrato de dominio. No hay transporte en esta iteración.

## Modelo de estados

- Datos: `SIN_DATOS | SINCRONIZADO | ATRASADO`; calidad: `COMPLETO | INCOMPLETO | CONFLICTO`.
- Alertas: `PENDIENTE → VISTO → CORREGIDO → VERIFICADO`; `PENDIENTE|VISTO → DESCARTADO`; `CORREGIDO → VISTO` permite invalidar una corrección no satisfactoria.
- Mensajes/outbox: `PENDIENTE/PENDING`; no se declara entrega sin adaptador aprobado.
- Revisión de ventas conserva sus estados e invalida únicamente campos modificados por una nueva versión fuente.

## Role-State Binding

- `ADMIN_CENTRAL` (Sol): lectura global, revisión, transiciones, mensajes y auditoría.
- `SUPERVISOR`: lectura, revisión, transiciones y mensajes dentro de su alcance.
- `AUDITOR`: lectura global sin mutaciones.
- `OPERADOR_LOCAL`: sincroniza solo su unidad; no accede a revisión central ni mensajes.

## Base verificada

El remoto verificado el 2026-08-15 expone `origin/main@098a9fbd95549cd4308a4754b69f90aa93eb6fca` y `origin/feature/bc-caja-gestion-real-sync-pilot-001` en el mismo commit. El hash solicitado `774e561…` y la rama con prefijo `mission/` no existen en el remoto consultado; se usa la base remota verificable, que sí contiene los contratos y artifacts de la misión anterior.

