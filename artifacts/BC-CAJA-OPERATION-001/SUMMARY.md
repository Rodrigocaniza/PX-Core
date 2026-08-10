# BC-CAJA-OPERATION-001 — Operación completa para piloto

Fecha: 2026-08-10

Estado técnico: IMPLEMENTATION_COMPLETED / VERIFIED

Checkpoint UI-001: `8ce8253`, publicado en `origin/feature/caja-diaria`.

## Resultado

BC Caja cubre ahora el flujo operativo previo a validación con el workbook real:

- Caja por fecha/unidad con caja inicial explícita;
- alta inmediata de ventas, medios y gastos;
- totales actualizados;
- edición por movimiento;
- anulación lógica con motivo, sin borrado físico;
- revisiones append-only `CREATE/UPDATE/VOID`;
- historial por fecha con movimientos activos/anulados y estado OPEN/CLOSED;
- Caja cerrada en modo consulta;
- cierre con snapshot y timestamp persistidos;
- ruta estable de datos fuera del código/cwd;
- `quick_check`, transacciones, WAL, synchronous FULL y backup en cada cierre;
- migración 001→002 preservando datos existentes;
- recuperación completa después de restart.

## No implementado deliberadamente

- arrastre automático;
- reapertura administrativa;
- migración automática de TXT;
- semántica nueva para Saldo/Ordenes/Cuotas;
- integración BC Gestión;
- funciones fuera del piloto.

Estado obligatorio: `PENDING_REAL_WORKBOOK_VALIDATION`.
