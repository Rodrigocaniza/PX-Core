# BC Caja — Gap Matrix

| RULE | LEGACY | EXCEL/OPERACIÓN | MVP DECISION | TEST | STATUS |
|---|---|---|---|---|---|
| Orden A:N | Consumido por posición | Orden informado coincide | Preservar vocabulario; importer futuro resolverá encabezados explícitos | `test_reported_column_order_matches_legacy_positions` | PENDING_REAL_WORKBOOK_VALIDATION |
| Día vacío | Hoja con CAJA INICIAL=0 produce cero entries | Día vacío solicitado | CashDay OPEN válido con cero entries | `test_empty_day_with_opening_is_a_valid_legacy_day` | CONFIRMED |
| Caja inicial | Efectivo de fila especial; falta→0; duplicada→última | Requerida | Campo explícito; duplicada/inválida debe bloquear importación | legacy duplicate test + futuro CORE | MVP_NEW |
| Venta efectivo | Acumula TOTAL y Efectivo | Requerida | Conservar | representative fixture | CONFIRMED |
| Tarjeta/cheque | Un solo monto combinado | Requerida combinada | Conservar combinado en MVP | representative fixture | CONFIRMED |
| Operación mixta | Permitida sin balance | Requerida | Conservar; validación del balance pendiente | representative fixture | PENDING_REAL_WORKBOOK_VALIDATION |
| Gastos | Reduce efectivo esperado | Requerido | Conservar fórmula hasta decisión contraria | `test_closing_formula_uses_opening_cash_cash_sales_and_expenses` | CONFIRMED |
| Varias filas | Permanecen independientes | Cliente puede ocupar varias filas | Conservar; no fusionar silenciosamente | representative fixture | CONFIRMED |
| Saldo numérico | Texto | Requerido | Preservar literal inicialmente | representative fixture | PENDING_REAL_WORKBOOK_VALIDATION |
| Saldo cancelado | Texto literal | Reportado | Preservar; semántica contable pendiente | representative fixture | BUSINESS_RULE_UNKNOWN |
| Ordenes/Cuotas | Texto, fuera de totales | Requeridas | Preservar; tipos/efecto pendiente | representative fixture | BUSINESS_RULE_UNKNOWN |
| Cierre | Cálculo efímero, sin estado | Requerido | CashDay CLOSED persistido e inmutable | desired OPEN/CLOSED tests | MVP_NEW |
| Efectivo final | inicial + efectivo - gastos | Requerido | Conservar como baseline | calculation test | CONFIRMED |
| Arrastre | No existe | Requerido | Política explícita antes de implementación | expected-failure carry policy | BUSINESS_RULE_UNKNOWN |
| Consulta histórica | Función por fecha/unidad | Requerida | Puerto `get_by_date_and_unit` y rango | expected-failure repository test | MVP_NEW |
| Reapertura | No existe | No comprobada | No implementar hasta decisión | documentado | BUSINESS_RULE_UNKNOWN |
| Edición | No existe; solo elimina día completo | Flujo real no comprobado | Edición por ID solo en OPEN | legacy delete test + futuro CORE | MVP_NEW |
| Monto inválido | Aviso y cero | No comprobado | Rechazar explícitamente | legacy invalid test + desired invalid-money test | MVP_NEW |
| Fila sin descripción | Se descarta aun con monto | No comprobado | No descartar silenciosamente; exigir clasificación | legacy discard test | LEGACY_ONLY |
| Duplicado | Omite día entero por fecha/unidad | No comprobado | Importación atómica e idempotente con identidad de origen | documentado | BUSINESS_RULE_UNKNOWN |
| Persistencia | TXT reescrito completo | Uso local | Repository contract + SQLite transaccional | preparado para CORE-001 | MVP_NEW |
| Workbook real | No accesible | Evidencia primaria reportada | Comparación obligatoria antes del importer productivo | pendiente | PENDING_REAL_WORKBOOK_VALIDATION |
