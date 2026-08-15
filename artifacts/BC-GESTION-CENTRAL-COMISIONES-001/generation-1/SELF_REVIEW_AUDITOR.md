# Auditor

**Verdict: PASS (SELF_REVIEW)** — emitido por la misma ejecución que implementó la misión.
**No cuenta como revisión independiente y no habilita Safe Closure.** Ver `INDEPENDENCE.md`.

## Arquitectura local-first

- Sin red, sin proveedor externo, sin nómina, sin banco, sin liquidación contable externa.
- SQLite local con WAL; escrituras bajo `BEGIN IMMEDIATE`; migración idempotente.
- Cálculo separado de la interfaz; puerto de política preparado para el futuro.

## Permisos

- Lectura: `dashboard.read`, con `OPERADOR_LOCAL` explícitamente denegado.
- Escritura: `reviews.manage`. `AUDITOR` puede leer y no puede transicionar.
- Verificado en `test_permissions`.

## Identidad, duplicados e idempotencia

- Índice parcial único: una sola liquidación viva por venta.
- Índice parcial único: una sola liquidación por venta y período.
- `idempotency_key UNIQUE` en cobros; el reintento devuelve `(None, False)` sin efecto.
- `recalculate` compara el tuple completo antes de escribir: sin cambio, no hay escritura ni evento.

## Historial y correcciones

- `commission_entry_history` es append-only: sólo hay `INSERT` en todo el módulo.
- Ninguna ruta lleva `PAGADA` a `REVERTIDA`. Reversión de cobro, anulación de venta o corrección de origen sobre una liquidación pagada producen `OBSERVADA` con motivo.

## Datos sensibles

- El libro no guarda nombre, documento ni teléfono del cliente: sólo local, vendedora, sobre e importes.
- El resumen exportado (`comisiones-<período>.local.json`) hereda esa restricción; el contrato de exportación se verifica por igualdad exacta de claves.
- Los artifacts y la captura usan exclusivamente datos sintéticos de años 2099.

## Observación honesta

`tools/capture_gestion_central_comisiones.py` autentica con la credencial sintética
`sol.piloto` del bootstrap del piloto, ya existente en el repositorio y usada igual por el
capturador de FactuFácil. No es un secreto nuevo ni una credencial productiva.

## Riesgo aceptado y documentado

El porcentaje de comisión no es canónico. La bandeja opera y liquida la **base comisionable**
aunque no exista porcentaje; cuando existe, queda marcado `SINTETICA_PENDIENTE_APROBACION`
en la base, en la cabecera de la pantalla y en el resumen exportado.
