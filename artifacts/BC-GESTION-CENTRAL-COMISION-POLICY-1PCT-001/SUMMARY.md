# Resumen

Convierte el porcentaje de comisión de configuración sintética a **regla productiva canónica**:
**1% general de la base comisionable, igual para toda vendedora y todo local**, versionado, con
fecha de vigencia y con trazabilidad grabada en cada liquidación.

Las reglas económicas de BC-GESTION-CENTRAL-COMISIONES-001 no se reescriben ni se rediscuten: se
mantienen tal cual y esta misión sólo cierra el único punto que quedaba pendiente de aprobación.

## Qué cambia

- El porcentaje deja de ser opcional y deja de configurarse por vendedora o por local. Existe una
  única política general, `COMISION_GENERAL_1PCT`, con `rate_bp = 100`, estado `CANONICA_APROBADA`,
  versión y vigencia `2026-08-01`.
- La etiqueta `SINTETICA_PENDIENTE_APROBACION` desaparece: ningún código la produce y la migración
  la retira de las bases existentes.
- Todo el cálculo monetario pasa a `Decimal` con `ROUND_HALF_UP` a guaraní entero, con la política
  de redondeo explícita en `comision_policy.py` y probada en sus bordes.
- Cada liquidación graba con qué política se calculó: `policy_code`, `policy_version`,
  `policy_effective_from`, `policy_scope` y `policy_status`.
- El export estructurado sube a `contract_version: 2` y lleva el bloque `policy` completo.
- La pantalla de Sol nombra el porcentaje vigente: encabezado, KPI, columnas y desglose.

## Lo que NO cambia

- Venta común: comisiona sólo al quedar totalmente cancelada, en el período de esa cancelación.
- Convenio: primero 5% de descuento sobre el total, después el 1% sobre la base resultante.
- Cobros parciales: informativos, nunca generan comisión pagable.
- Ventas anuladas: no comisionan.
- Gastos y entregas a administración: nunca ingresan al libro.
- Los ocho estados, el libro append-only de cobros y los índices parciales únicos.

## Ejemplos verificados

| Caso | Total | Descuento | Base | Comisión |
|---|---:|---:|---:|---:|
| Venta común cancelada | 400.000 | 0 | 400.000 | **4.000** |
| Venta común con saldo | 400.000 | — | 0 | **0** (no pagable) |
| Convenio | 500.000 | 25.000 | 475.000 | **4.750** |
| Convenio (borde de redondeo) | 333.333 | 16.667 | 316.666 | **3.167** |
| Común (borde de redondeo) | 1.234.567 | 0 | 1.234.567 | **12.346** |

Los dos últimos son medio guaraní hacia arriba: `3.166,66 → 3.167` y `12.345,67 → 12.346`.

## Protecciones

- `recalculate` sólo alcanza `ELEGIBLE` y `CALCULADA`. `PAGADA`, `APROBADA`, `REVISADA`,
  `OBSERVADA` y `REVERTIDA` quedan fuera del `WHERE` y no cambian nunca por un recálculo,
  ni siquiera después de publicar una versión nueva de la política.
- Recalcular es idempotente: la comparación incluye la traza de política completa, así que
  repetirlo no duplica liquidaciones ni asienta historial de más.
- `review` y `mark_paid` exigen que la política oficial ya esté aplicada: nada sin porcentaje
  entra a la cadena de pago.
- Un período anterior a la vigencia no aplica el porcentaje hacia atrás: informa la base,
  marca `FUERA_DE_VIGENCIA` y no es revisable ni pagable.
- La migración no toca dinero: las liquidaciones ya calculadas con la política sintética
  conservan su `rate_bp` y su `commission_amount`, y sólo pierden la etiqueta retirada.

Base exacta: `e7732603d9eb098867a272598e6d30803a4f1ac3`.

Regresión completa **317/317 PASS** (302 de línea base + 15 de esta misión: 14 de dominio y 1 de
interfaz). Sin nómina, sin bancos, sin datos de clientes, sin proveedor externo, sin red, sin
producción, sin merge a `main`.
