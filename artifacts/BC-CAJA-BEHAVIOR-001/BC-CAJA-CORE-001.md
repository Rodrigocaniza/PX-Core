# BC-CAJA-CORE-001 — Domain + Services + SQLite Foundation

Estado: READY_FOR_CANONICAL_AUTHORIZATION / NO INICIADA

## Objetivo

Crear la base productiva mínima de BC Caja reutilizando el contrato congelado, sin rediseñar UI ni integrar BC Gestión.

## Baseline obligatorio

- PX-Core `feature/caja-diaria` y HEAD que resulte vigente al iniciar.
- `CajaDiaria.py` permanece como adaptador legacy y evidencia.
- `BEHAVIOR_CONTRACT.md`, `GAP_MATRIX.md` y fixtures/tests de BC-CAJA-BEHAVIOR-001.
- Estado del workbook: `PENDING_REAL_WORKBOOK_VALIDATION` hasta evidencia contraria.

## Alcance implementable

1. `CashDay`, `CashEntry`, `CashDayStatus`, value objects monetarios y errores del dominio.
2. Cálculos puros compatibles con el baseline confirmado.
3. Servicios: open/get, add/edit/remove while OPEN, totals, close, cash count y history query.
4. `CashDayRepository` como puerto; ninguna dependencia SQLite en dominio/application.
5. Adaptador SQLite local, transacciones, foreign keys y migración `001`.
6. Composition root mínimo sin conectar todavía widgets productivos.
7. Migrar los cinco `expectedFailure` a PASS gradualmente, sin borrar su intención.
8. Tests unitarios y de repositorio con SQLite temporal.

## Esquema mínimo propuesto

- `cash_days`: id, business_date, unit, opening_cash, status, opened_at, closed_at, closing totals/version.
- `cash_entries`: id, cash_day_id, los 14 campos del contrato, origin, source_reference, created_at, updated_at.
- `cash_counts`: id, cash_day_id, counted_total, expected_total, difference, status, denomination detail, recorded_at.
- `schema_migrations`: version, applied_at.

La forma final del esquema debe derivarse del dominio y tests; no codificar Ordenes/Cuotas/Saldo como monto hasta decisión.

## Gates de negocio

- arrastre automático/confirmado y días sin actividad;
- reapertura y corrección de cierre;
- balance TOTAL vs medios;
- semántica de saldo `cancelado`;
- tipos de Ordenes/Cuotas;
- política de duplicados/importación;
- tratamiento de gastos no efectivos.

Los gates no bloquean modelos, repositorio y cálculos confirmados; sí bloquean cualquier código que presuponga esas reglas.

## Exclusiones

UI nueva, PostgreSQL/API, red/multiusuario, BC Gestión, importación productiva del workbook real, estadísticas, permisos, Telegram y sincronización.

## Criterios de aceptación

- dominio no importa CustomTkinter, openpyxl ni sqlite3;
- application depende de puertos, no del adaptador SQLite;
- SQLite usa transacciones y constraints explícitos;
- día CLOSED rechaza mutaciones;
- consulta por fecha/unidad y rango probada;
- cálculos confirmados coinciden con fixtures legacy;
- todos los tests legacy siguen verdes;
- cada test MVP implementado deja de ser expected failure;
- ningún unknown se resuelve implícitamente;
- no se modifica UI.
