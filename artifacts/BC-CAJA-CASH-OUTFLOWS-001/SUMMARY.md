# BC-CAJA-CASH-OUTFLOWS-001

Estado: CLOSED
Versión: BC Caja 1.0.0-rc.3

- Salidas de Caja extensibles con tipos `GASTO` y `ENTREGA_ADMINISTRACION`.
- Crear, cargar por doble clic/Editar, modificar y anular con motivo.
- Auditoría append-only `CREATE/UPDATE/VOID` y bloqueo total en cajas cerradas.
- Venta total no descuenta salidas; gastos económicos excluyen entregas.
- Efectivo esperado = caja inicial + efectivo cobrado - gastos - entregas.
- Resumen superior compacto con seis indicadores; saldo y convenios en resumen secundario.
- Grilla ampliada, scroll nativo, orden cronológico y lotes de 250 preservados.
- Regresión completa: 157 passed. Targeted: 34 passed. Smoke EXE y visual 1366×768: PASS.
- Verification → Packaging → Artifact Consistency → Librarian → QA → Auditor → Safe Closure: PASS.
