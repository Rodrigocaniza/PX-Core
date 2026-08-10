# BC-CAJA-CORE-001 — Domain + Services + SQLite Foundation

Fecha: 2026-08-10

Estado técnico: IMPLEMENTATION_COMPLETED / VERIFIED

Repo: PX-Core

Branch: `feature/caja-diaria`

HEAD base: `92a15f046ac652fa83d1b81a5411b6bbe363fee8`

## Resultado

Se creó la foundation de BC Caja exclusivamente dentro de PX-Core. `CajaDiaria.py`, la UI y los demás repos BC no fueron modificados.

### Dominio

- `CashDay` con identidad estable, fecha, unidad, caja inicial y estados `OPEN/CLOSED`.
- `CashEntry` conserva los 14 campos del contrato y añade origen/referencia/timestamps.
- Importes PYG como enteros o ausencia explícita; floats, booleanos, negativos y texto inválido se rechazan.
- Totales compatibles con el baseline: TOTAL, Efectivo, Tarj./Cheq., Gastos y efectivo esperado.
- Alta, edición y eliminación por ID solo mientras la Caja está OPEN.
- Cierre con snapshot inmutable de totales y bloqueo de mutaciones posteriores.
- Arqueo con denominaciones, diferencia y estados `OK/SOBRA/FALTA`.
- Ordenes, Cuotas y Saldo siguen siendo texto; no se inventó semántica contable.

### Aplicación

- `CashDayRepository` como puerto independiente de infraestructura.
- `CashDayService`: abrir, obtener, consultar rango, agregar/editar/eliminar, importar lote, calcular, cerrar y registrar arqueo.
- `CarryForwardPolicy` existe únicamente como boundary; no hay implementación concreta porque la regla sigue desconocida.
- No existe integración con BC Gestión.

### SQLite

- Migración versionada `001_caja_diaria.sql`.
- Tablas `cash_days`, `cash_entries`, `cash_counts`, `schema_migrations`.
- Foreign keys, constraints, índices y unicidad `(business_date, unit)`.
- Escritura del agregado dentro de `BEGIN IMMEDIATE`, con rollback ante fallo.
- WAL y busy timeout para base en archivo.
- Consultas por ID, fecha/unidad y rango.
- Arqueos persistidos con detalle de denominaciones.
- Composition root disponible, todavía desconectado de CustomTkinter.

## Verificación

Comando:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

Resultado fresco: `Ran 31 tests ... OK`.

- 12 caracterizaciones legacy continúan verdes.
- Los 5 contratos MVP antes marcados `expectedFailure` ahora pasan normalmente.
- Se añadieron 14 pruebas de dominio, servicios y SQLite.
- Se comprobó rollback transaccional, round-trip completo, cierre, consulta histórica y migración idempotente.

## Boundary preservado

- Sin UI nueva ni modificación de widgets.
- Sin importer productivo nuevo.
- Sin migrar TXT ni crear una base real en `Datos/`.
- Sin arrastre, reapertura, sincronización, usuarios, estadísticas o API.
- `PENDING_REAL_WORKBOOK_VALIDATION` sigue vigente.

## BUSINESS_RULE_UNKNOWN

- política concreta de arrastre y días sin actividad;
- reapertura/corrección de cierre;
- balance entre TOTAL y medios;
- semántica de Saldo `cancelado`;
- tipo/efecto de Ordenes y Cuotas;
- deduplicación/importación incremental;
- medio de pago real de Gastos.
