# BC-CAJA-UI-001 — Legacy UI → Core Services + SQLite

Fecha: 2026-08-10

Estado técnico: IMPLEMENTATION_COMPLETED / VERIFIED

Checkpoint previo: `1795dc6` publicado en `origin/feature/caja-diaria`.

## Resultado

La ventana existente `CajaDiaria.py` fue adaptada progresivamente; no se creó una segunda aplicación ni se cambió CustomTkinter.

El flujo normal ahora permite:

1. abrir la ventana desde la navegación existente de PX-Core;
2. seleccionar fecha y unidad;
3. crear la Caja indicando caja inicial o recuperar una existente;
4. cargar una línea manual conservando el orden mental de campos;
5. persistir inmediatamente en SQLite;
6. ver TOTAL, Efectivo, Tarj./Cheq., Gastos y efectivo final;
7. importar el análisis legacy a SQLite sin escribir TXT;
8. registrar arqueo en SQLite;
9. cerrar la Caja y bloquear nuevas altas;
10. reiniciar el controller/aplicación y recuperar Caja, líneas, totales y cierre.

## Cambios principales

- `CajaDiaria.abrir_caja_diaria(parent, controller=None)` mantiene compatibilidad con la llamada actual de `interfaz.py` y permite inyección para tests.
- `CashDayUIController` traduce los nombres legacy hacia `CashEntry` y servicios.
- `build_cash_day_controller()` compone repositorio, service y controller.
- La UI nunca importa ni usa `sqlite3`.
- Los errores esperables se traducen a mensajes operativos sin traceback ni SQL.
- Los campos no se limpian cuando una operación falla; tras alta exitosa se preservan fecha, unidad y caja inicial para velocidad.
- La importación queda bloqueada si el analizador legacy reporta errores.

## Estado pendiente

`PENDING_REAL_WORKBOOK_VALIDATION` continúa vigente. No se implementó arrastre, reapertura ni reglas contables no confirmadas.
