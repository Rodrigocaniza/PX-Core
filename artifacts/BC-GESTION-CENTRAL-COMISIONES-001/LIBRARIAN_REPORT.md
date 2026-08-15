# Librarian

**Verdict: PASS (SELF_REVIEW)** — emitido por la misma ejecución que implementó la misión.
**No cuenta como revisión independiente.** Ver `INDEPENDENCE.md`.

## Contratos y trazabilidad

- `COMMISSION_STATES` fija los ocho estados exigidos y está verificado por contrato en `test_state_contract_and_append_only_history`.
- `AGREEMENT_DISCOUNT_BP = 500` es la única fuente del 5%; no hay literales de descuento dispersos.
- `ENTRY_EXPORT_FIELDS` fija el orden y el conjunto del resumen exportable (`contract_version: 1`), verificado por igualdad exacta de claves.
- Cada regla económica aprobada tiene fila propia en `COMMISSION_RULES.md` con su prueba asociada.

## Límites

- `comisiones.py` no importa Tk, red ni proveedor externo; `comisiones_ui.py` no calcula.
- No se tocó BC Caja, BC-Core, BC-Finanzas, `main` ni worktrees ajenos.
- La ingesta reutiliza `ReviewService.list_sales` sin modificar `real_sync.py`.

## Identidad y orden de datos

- Identidad de venta: `sha256(branch, source_sale_id)` → `uuid5`. Estable entre reaperturas.
- Identidad de liquidación: `uuid5(sale_id, sequence)`, con secuencia creciente por venta.
- Identidad de cobro: `sha256` del cobro completo, columna `idempotency_key UNIQUE`.
- Orden de listado determinista: `branch, saleswoman, sale_date, sequence`.

## Evidencia

- `MANIFEST.sha256` fija código, pruebas, capturador, captura y verdicts.
- Captura 1920×1080 regenerada tras corregir tres defectos visuales reales (ver `TEST_EVIDENCE.md`).
