# E2E Evidence — DB temporal

Test: `CashOperationE2ETests.test_two_days_edit_void_close_backup_and_restart`.

## Día 1

1. Abre Caja PC con 500.000 PYG.
2. Agrega venta efectivo 300.000.
3. Agrega venta tarjeta 400.000.
4. Agrega gasto 50.000.
5. Corrige venta efectivo a 350.000.
6. Anula venta tarjeta con motivo.
7. Confirma totales válidos: TOTAL 350.000; efectivo 350.000; tarjeta 0; gastos 50.000.
8. Confirma efectivo esperado 800.000.
9. Cierra Caja y verifica snapshot.
10. Genera backup SQLite.
11. Reinicia controller y consulta exactamente tres movimientos, incluido el anulado.

## Día 2

1. Verifica que sin caja inicial no se crea el día: no hay arrastre implícito.
2. Abre explícitamente con 800.000.
3. Agrega venta efectivo 100.000.
4. Verifica esperado 900.000.
5. Reinicia otra vez.
6. Recupera Día 2 OPEN con esperado 900.000.

Resultado: PASS.
