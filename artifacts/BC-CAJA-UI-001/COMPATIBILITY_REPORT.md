# Compatibility Report

## Preservado

- acceso desde `interfaz.py` sin cambiar la firma utilizada;
- ventana CustomTkinter, tamaño y navegación modal;
- pestañas `Importar Excel`, `Cargar manual` y `Arqueo`;
- terminología y campos del Excel/operación;
- orden de carga, unidad `PC` por defecto y fecha DD-MM-AAAA;
- parser/preview Excel legacy mientras el workbook real no esté disponible;
- helpers y funciones TXT para rollback técnico y tests de caracterización.

## Cambio operativo deliberado

- la primera alta del día exige caja inicial;
- la fecha se conserva después de guardar para carga rápida;
- los totales se muestran inmediatamente;
- montos inválidos ya no se convierten a cero;
- avisos de importación bloquean el guardado;
- el cierre es real y bloquea modificaciones;
- la persistencia normal es SQLite.

## No conectado todavía

- edición/eliminación visual por movimiento;
- listado histórico visual;
- recovery/backup guiado;
- arrastre;
- reapertura;
- importer definitivo contra `Agosto PC 2026.xlsx`;
- BC Gestión.

El TXT no se elimina, pero la UI nueva no realiza doble escritura TXT + SQLite.
