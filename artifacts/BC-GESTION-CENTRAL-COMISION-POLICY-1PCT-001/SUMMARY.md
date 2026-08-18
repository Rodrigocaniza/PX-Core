# Resumen

Convierte el porcentaje de comisión de configuración sintética a **regla productiva canónica**:
**1% general de la base comisionable, igual para toda vendedora y todo local**, versionado, con
fecha de vigencia y con trazabilidad grabada en cada liquidación.

Esta misión cierra el único punto que quedaba pendiente de aprobación en
BC-GESTION-CENTRAL-COMISIONES-001. De su contrato económico quedan superadas tres cláusulas —la regla 5, la
sección «Configuración pendiente de aprobación» y la fórmula de redondeo entera—; las reglas 1 a 4
y 6 a 9 se mantienen sin cambio alguno. El detalle está en «Cláusulas superadas» de
`COMMISSION_POLICY_1PCT.md`, y el documento anterior lleva la anotación correspondiente en su
encabezado.

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
- El export estructurado sube a `contract_version: 3`: bloque `policy` del período exportado —con
  la marca `pinned`— y la política vigente al exportar aparte, en `current_policy`.
- La pantalla de Sol nombra el porcentaje vigente en el encabezado, el KPI y el desglose, y avisa
  cuando hay importes fuera de la política oficial.

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

- **Sólo la política vigente llega al pago.** `review`, `approve` y `mark_paid` exigen que haya
  importe, que su `policy_status` sea `CANONICA_APROBADA`, y que el porcentaje y la versión
  grabados coincidan con la política que rige hoy el período de esa liquidación. El sello se graba
  al calcular y puede quedar atrás: comprobar sólo el sello dejaría pasar un importe superado.
- **Nada que no sea el importe oficial se queda varado.** `recalculate` repara toda liquidación no
  pagada cuyo importe ya no sea el vigente —política retirada, ausente o versión superada—: la
  lleva al porcentaje del período, la devuelve a `CALCULADA` y retira la revisión y la aprobación
  que respaldaban el importe anterior, que queda asentado en el historial.
- **Nada que haya movido dinero es alcanzable.** `paid_at IS NULL` cuelga del `WHERE` entero de
  `recalculate`, no de una rama. `OBSERVADA` y `REVERTIDA` también quedan fuera.
- Recalcular es idempotente: la comparación incluye la traza de política completa, y una
  `REVISADA`/`APROBADA` ya correcta conserva su aval.
- **Cada liquidación se resuelve contra la versión de su propio período.** Programar el porcentaje
  del mes que viene no reescribe el mes en curso.
- **Un período tarifado conserva su tasa, y eso no se sostiene bloqueando la publicación.** La
  primera vez que se aplica un porcentaje a un período queda grabado en `commission_rated_periods`
  —una fila por período, escrita una sola vez, nunca actualizada ni borrada— y la resolución de ese
  período pasa por ahí antes que por el catálogo de versiones. Publicar siempre es posible y no
  reescribe lo tarifado. La protección **no** depende del estado de la liquidación: observar,
  revertir, anular la venta o corregir el origen cambian el estado y la evidencia sigue ahí.
  Tampoco hay frontera global: una venta con fecha errónea protege su propio mes y no congela
  ninguno anterior. Corregir la tasa de un período ya tarifado exige un flujo de corrección
  explícita y auditada, que hoy no existe.
- Un período anterior a toda vigencia no aplica el porcentaje hacia atrás: informa la base,
  marca `FUERA_DE_VIGENCIA` y no es revisable ni pagable. Un importe heredado de ese período se
  retira sin sustituto y **no tiene reparación posible**; lo que sí queda garantizado es que el
  valor retirado se asienta en `replaced`, en toda rama de `recalculate` que anule o reemplace un
  importe anterior, no sólo al reparar una `REVISADA` o una `APROBADA`.
- **La comisión oficial no se mezcla.** Los agregados separan `commission_amount` —sólo lo
  calculado con la política aprobada— de `non_official_amount`, y la bandeja avisa cuando hay
  importes de la segunda clase. Ningún total rotulado «oficial 1,00%» incluye otra cosa.
- La migración no toca dinero: las liquidaciones ya calculadas con la política sintética
  conservan su `rate_bp` y su `commission_amount`, y sólo pierden la etiqueta retirada.

Base exacta: `e7732603d9eb098867a272598e6d30803a4f1ac3`.

El export estructurado sube a `contract_version: 3`: su bloque `policy` pasa a ser el del período
exportado —con la marca `pinned` de si quedó fijado al tarifarse— y la política vigente al exportar
viaja aparte en `current_policy`. Rotular un período con la tasa global declararía oficial ahí un
porcentaje que en ese mes no rige.

Regresión completa **371/371 PASS** (302 de línea base + 69 de esta misión: 67 de dominio y 2 de
interfaz, de los cuales 26 son de la generación 5). Sin nómina, sin bancos, sin datos de clientes,
sin proveedor externo, sin red, sin producción, sin merge a `main`.
