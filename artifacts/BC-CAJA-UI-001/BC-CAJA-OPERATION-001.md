# BC-CAJA-OPERATION-001 — Cierre, Arrastre, Historial y Recovery Operativo

Estado: READY_FOR_AUTHORIZATION / NO INICIADA

## Objetivo

Completar exclusivamente los gaps operativos necesarios para un piloto real, sobre la UI/Core/SQLite ya integrados.

## Alcance candidato

1. Historial visual simple por fecha/unidad y detalle de movimientos.
2. Edición/eliminación controlada por ID solo en OPEN.
3. Flujo de backup/restore SQLite y recovery verificable.
4. Checklist de cierre y consulta de arqueo.
5. Decisión e implementación de arrastre solo después de validación de negocio.
6. Política de reapertura/corrección solo si se aprueba.
7. Migración explícita de TXT real si existe, con backup y dry-run.
8. Validación contra `Agosto PC 2026.xlsx` cuando esté accesible.
9. Smoke/pilot checklist en copia temporal antes de datos productivos.

## Gates que siguen abiertos

- `PENDING_REAL_WORKBOOK_VALIDATION`;
- arrastre automático vs confirmado y días sin actividad;
- reapertura;
- semántica de Saldo/Ordenes/Cuotas;
- balance TOTAL vs medios;
- política de duplicados/reimportación.

## Exclusiones

Dashboard, cloud, API, multiusuario, permisos complejos, Telegram, sincronización y BC Gestión.

## Criterio de salida

Aplicación lista para piloto controlado con historial, recovery y cierre operativo; ninguna regla desconocida codificada implícitamente.
