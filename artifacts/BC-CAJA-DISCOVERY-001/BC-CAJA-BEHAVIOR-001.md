# BC-CAJA-BEHAVIOR-001 — Behavior Contract & Executable Examples

Estado: READY_TO_START (definición preparada; no implementada)

## Objetivo

Convertir el comportamiento observable del Excel y de `CajaDiaria.py` en un contrato verificable, fixtures sintéticos y tests de caracterización, resolviendo o aislando reglas ambiguas antes de tocar UI o persistencia productiva.

## Entradas obligatorias

- `CajaDiaria.py` en `feature/caja-diaria@92a15f046ac652fa83d1b81a5411b6bbe363fee8`.
- `CANONICAL_DISCOVERY.md` de esta misión.
- La estructura informada de `Agosto PC 2026.xlsx`.
- El libro real cuando resulte accesible dentro del entorno autorizado; no bloquear los fixtures sintéticos por su ausencia.

## Alcance

- definir nombres, tipos y nulabilidad de las 14 columnas;
- caracterizar múltiples filas, caja inicial, totales, efectivo final, gastos y saldo `cancelado`;
- crear fixtures XLSX sintéticos sin datos personales;
- escribir tests del parser/cálculos históricos antes de refactorizar;
- proponer decisiones explícitas para cada `BUSINESS_RULE_UNKNOWN`;
- definir el contrato de arrastre sin implementarlo hasta aprobación;
- producir matriz `observado / supuesto / decidido / test`.

## Fuera de alcance

- UI, SQLite, migraciones, integración con Movimientos, datos reales, commit/push y cambios en otros productos.

## Criterios de aceptación

1. Fixture de día normal con caja inicial, varias líneas, todos los medios y gasto.
2. Fixture con Saldo numérico y `cancelado`, preservados sin coerción silenciosa.
3. Fixture con encabezado/fecha inválidos, duplicados y más de una caja inicial.
4. Tests que documenten el cálculo histórico y revelen explícitamente cualquier divergencia propuesta.
5. Ningún error monetario se transforma a cero sin resultado de validación visible.
6. Tabla completa de `BUSINESS_RULE_UNKNOWN`, cada uno con owner de decisión y efecto en el MVP.
7. Evidencia comparativa contra `Agosto PC 2026.xlsx` si el archivo está accesible; si no, estado `PENDING_REAL_WORKBOOK_VALIDATION` sin bloquear la caracterización sintética.

## Archivos previstos

```text
tests/caja_diaria/fixtures/
tests/caja_diaria/test_legacy_excel_contract.py
tests/caja_diaria/test_legacy_calculations.py
artifacts/BC-CAJA-BEHAVIOR-001/BEHAVIOR_MATRIX.md
artifacts/BC-CAJA-BEHAVIOR-001/BUSINESS_RULE_DECISIONS.md
```

## Riesgo principal

No convertir en política aprobada lo que solo es comportamiento legacy. Cada test debe rotular su fuente como `OBSERVED_LEGACY`, `USER_STATED_CONTRACT` o `APPROVED_RULE`.
