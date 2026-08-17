# BC-GESTION-CENTRAL-CAJAS-PILOT-001

Piloto funcional local de una consola central para Óptica Asunción, Óptica
Pilar, Consultorio Asunción y Consultorio Pilar.

## Entregado

- Panel de cuatro unidades con ingresos, medios de cobro, gastos, retiros,
  movimientos, estado y frescura de sincronización.
- Roles `ADMIN_CENTRAL`, `SUPERVISOR`, `AUDITOR` y `OPERADOR_LOCAL`, con acceso
  de unidad y mínimo privilegio.
- Usuarios con PBKDF2 y auditoría de altas e inicios de sesión.
- Recepción de snapshots idempotente, rechazo de colisiones y trazabilidad.
- Alertas por sincronización demorada, diferencia de caja y caja abierta tarde;
  reconocimiento auditable por usuarios autorizados.
- Consola Tk adaptable: cuatro columnas en 1500 px o más, dos en resoluciones
  menores, priorizada para 24 pulgadas/Full HD.
- Entry point `bc_gestion_central.py` y lanzador Windows.

## Aislamiento

La base del piloto vive en un directorio propio. El bootstrap usa fechas 2099,
nombres genéricos y montos ficticios. No hay transporte de red, secretos reales,
conector de producción ni activación general.

Credencial sintética inicial: `admin.piloto` / `Piloto-Temporal-2026`. Debe
usarse únicamente en el piloto aislado.
