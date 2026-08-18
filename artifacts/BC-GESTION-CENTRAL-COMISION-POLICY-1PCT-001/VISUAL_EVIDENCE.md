# Evidencia visual

`screenshots/comision-1pct-1920x1080.png` — 1920×1080, RGB, 93.725 bytes.
SHA-256 `1c9a1e5e5fafec09cd55d1c2d619761240d7abedaf33a14fe83a49f702b07906`.

**Regenerada en la generación 6** (`L6-g5`): el rótulo del encabezado cambió al cambiar la regla
de fijación, así que la captura de la generación 3 dejó de coincidir con la pantalla real.

Generada por `python tools/capture_gestion_central_comisiones.py <destino>` sobre una base
temporal con el piloto sintético. El capturador ya no configura porcentaje: la política oficial
del 1% queda instalada por la migración y el recálculo la aplica sola.

El PNG **no es reproducible byte a byte**: el panel «Historial auditable» muestra el
`recorded_at` real de cada asiento, así que cada corrida produce un archivo distinto. El hash
identifica esta captura, no una propiedad estable del código. Todo lo demás de la imagen —cifras,
rótulos y disposición— sí es determinista y está verificado por las pruebas de interfaz.

## Lo que la captura demuestra

**Encabezado.** «Comisión oficial 1,00% de la base · COMISION_GENERAL_1PCT v1 · vigente desde
2026-08-01 · **fijada al aprobarse o pagarse** · redondeo HALF_UP a Gs. enteros». El porcentaje
vigente se nombra en pantalla, no se da por sabido, y el rótulo dice además **de dónde viene**: en
esta base el mes `2099-04` tiene una liquidación aprobada y otra pagada, así que su tasa ya quedó
fijada por un hecho económico oficial.

El mismo rótulo tiene otras dos formas, que la captura no muestra porque esta base no las
produce y que verifican las pruebas de interfaz:

- **Período todavía provisional** —ninguna liquidación del mes fue aprobada ni pagada—:
  «… · provisional: aún sin aprobación ni pago en el período». El mes sigue siendo corregible.
- **Período sin tasa en vigor** —anterior a toda vigencia publicada—: «Sin tasa oficial en vigor
  para AAAA-MM · se fija cuando una liquidación se aprueba o se paga · se informa sólo la base
  comisionable · redondeo HALF_UP a Gs. enteros», y el KPI pasa a «COMISIÓN OFICIAL — SIN TASA EN
  VIGOR». Antes de la generación 6 la pantalla caía aquí a la política global y la declaraba
  oficial de ese mes (`QB1-g5`): rotulaba «Comisión oficial 10,00%» donde no regía nada.

**KPIs.** `BASE COMISIONABLE 4.345.000 Gs.` y `COMISIÓN OFICIAL 1,00% 43.450 Gs.` — el 1% exacto
del agregado. El rótulo del KPI lleva el porcentaje vigente.

**Resumen por vendedora.** Tres locales y tres vendedoras distintas con
el mismo porcentaje: 620.000 → 6.200; 1.425.000 → 14.250; 2.300.000 → 23.000.

**Ventas del período.** Columnas `Desc. 5%`, `Base comisionable` y `Comisión` visibles en la misma
fila. La columna se titula «Comisión» a secas y no «Comisión 1,00%»: una fila puede arrastrar un
importe heredado de una política retirada, y el encabezado no puede declararlo oficial. El
porcentaje vigente lo nombran el encabezado de la pantalla, el KPI y el desglose.

Se leen los tres casos de la decisión aprobada:

- Común cancelada (S-301, `PAGADA`): 620.000 → base 620.000 → **6.200**.
- Común con saldo (S-302, `PENDIENTE SALDO`): 340.000 con saldo 240.000 → base 0 → comisión **—**.
- Convenio (S-103, `CALCULADA`): 500.000 → desc. 25.000 → base 475.000 → **4.750**.

**Desglose del cálculo oficial**, con la venta de convenio seleccionada:

```
  Total de la venta                        500.000 Gs.
− Descuento de convenio (5%)                25.000 Gs.
= Base comisionable                        475.000 Gs.
= Comisión oficial (1,00% de la base)        4.750 Gs.
```

Debajo, la nota de política: «Política oficial COMISION_GENERAL_1PCT v1: 1,00% de la base
comisionable, igual para toda vendedora y local, vigente desde 2026-08-01. Redondeo HALF_UP a
guaraní entero».

**Historial auditable** con `SALE_REGISTERED → ELEGIBLE` y `COMMISSION_RECALCULATED → CALCULADA`.

**Sin banda de aviso**, porque en esta base todos los importes llevan la política vigente. Cuando
hay alguno que no, la bandeja inserta sobre las tablas una franja con su total y su recuento; lo
verifica `test_the_screen_never_calls_official_an_amount_from_a_retired_policy`.

**Estados visibles**: `PAGADA`, `PENDIENTE SALDO`, `REVISADA`, `CALCULADA`, `APROBADA`,
`OBSERVADA`. Los cinco botones de acción, `Recalcular` y `Exportar resumen`, todos dentro de la
pantalla.

Ninguna columna monetaria queda recortada; `test_full_hd_layout_keeps_every_control_visible` lo
verifica sumando anchos contra el ancho visible de cada tabla.

## Lo que no muestra

Datos reales: la captura es del piloto sintético. No hay nombres de clientes, ni nómina, ni
bancos, ni referencias productivas.
