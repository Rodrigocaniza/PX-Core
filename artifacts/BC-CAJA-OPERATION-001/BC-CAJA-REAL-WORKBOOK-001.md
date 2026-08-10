# BC-CAJA-REAL-WORKBOOK-001 — Validación con Agosto PC 2026

Estado: READY_FOR_AUTHORIZATION / REQUIERE WORKBOOK ACCESIBLE

## Objetivo

Validar BC Caja contra `Agosto PC 2026.xlsx` y ajustar únicamente diferencias reales necesarias antes del piloto.

## Alcance

1. Trabajar sobre una copia autorizada del workbook, sin datos expuestos en artifacts.
2. Inventariar hojas, fechas, encabezados, fórmulas, filas informativas y totales.
3. Ejecutar preview sin persistencia.
4. Comparar resultado legacy/Core contra el workbook.
5. Validar caja inicial, múltiples filas, medios, Saldo, Gastos, cierre y efectivo final.
6. Resolver si existe evidencia suficiente para arrastre.
7. Ajustar importer y fixtures solo donde la evidencia lo demuestre.
8. E2E de importación hacia DB temporal, reload y cierre.
9. Emitir verdict de piloto.

## Exclusiones

Rediseño UI, BC Gestión, cloud, multiusuario, estadísticas o reglas no observadas.

## Gate

El archivo aún no está accesible dentro del workspace. Mantener `PENDING_REAL_WORKBOOK_VALIDATION` hasta entonces.
