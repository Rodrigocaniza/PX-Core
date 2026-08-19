# Verdict — QA, generación 9
Runner: QA-IND-COMISION-POLICY-1PCT-009
Snapshot: f284b6c5fc2d0f31ffce7567146cce9371e9502a
Veredicto: PASS

## Escenarios propios ejecutados

**S1 — 7% histórico vivo contra 1% prospectivo (camino caliente).** Publiqué v2 = 7% (vigencia 2026-08-01), liquidé una venta común de 400.000 Gs en 2026-09 (base 400.000, comisión 28.000 Gs), la revisé, aprobé y pagué: libro `[PINNED 700]`. Publiqué después v3 = 1% con vigencia 2026-09-01, que abarca ese mes. `policy_for_period("2026-09")` = 700 bp, `pinned=True`; `2026-10` = 100 bp sin fijar. La PAGADA siguió en 28.000 Gs al 7%. Un convenio nuevo de 500.000 Gs en ese mismo mes: descuento 25.000, base 475.000, comisión 33.250 Gs al 7%; una venta común de 400.000 Gs en 2026-10: 4.000 Gs al 1%. Tres recálculos seguidos: `changed=0` y ningún evento nuevo. Export: `policy.rate_percent="7.00"`, `current_policy.rate_percent="1.00"`, KPI comisión oficial 61.250 Gs.

**S2 — base migrada del piloto con políticas por vendedora (7%) y por local (5%).** Base construida a mano con `commission_policies` de alcance `VENDEDORA:Vendedora Uno` a 700 bp y `LOCAL:Óptica Asunción` a 500 bp, más una PAGADA viva de 28.000 Gs al 7% en 2026-09. Al abrir: la migración borra los dos alcances retirados y los asienta en `COMMISSION_POLICY_RETIRED` con su `rate_bp` previo, deja el 1% general, y escribe `[PINNED 700]` con `origin='MIGRACION'`. El importe pagado quedó en 28.000 Gs. Venta nueva en 2026-09: 28.000 Gs al 7%; venta nueva en 2026-10: 4.000 Gs al 1%.

**S2b — etiqueta retirada.** Misma base pero con la liquidación pagada rotulada `SINTETICA_PENDIENTE_APROBACION`: pasa a `POLITICA_HISTORICA_PREVIA`, conserva sus 28.000 Gs, **no** fija el mes (libro vacío), el mes se resuelve al 1% sin fijar y el reporte la deja en `non_official_amount=28.000 Gs` con `commission_amount=0`.

**S3 — evidencia discrepante 7%/5% en el mismo mes.** Dos pagos vivos, 28.000 Gs al 7% y 20.000 Gs al 5%: la apertura no fija nada y asienta `COMMISSION_PERIOD_RATE_SEED_SKIPPED / EVIDENCIA_DISCREPANTE` con `rates_bp=[500,700]` y los dos ids. Una venta nueva de 400.000 Gs se calcula al 1% (4.000 Gs) y **aprobarla no forma pin**: libro sigue vacío. Pantalla y export dicen «el período todavía no tiene una tasa fijada», sin afirmar que nadie aprobó. Los 28.000 y 20.000 Gs intactos. Al retirar (observar) el hecho de 5% en una variante con una APROBADA a 5%, el mes se fija al 7% respaldado.

**S4 — pin sostenido por un hecho de su misma tasa.** PAGADA de 28.000 Gs y APROBADA de 42.000 Gs, ambas al 7%: `[PINNED 700]`. Al observar la APROBADA el libro sigue `[PINNED 700]` (sin `UNPINNED`), el mes sigue al 7% y los dos importes no cambian. Igual en S6: revertir la primera de dos aprobaciones no suelta.

**S5 — pin a una tasa que ningún hecho vivo lleva (apertura).** Base migrada con evento legado `PINNED 500` (política por local) y una PAGADA viva de 28.000 Gs al 7%. Al abrir, el libro queda `PINNED 500 → UNPINNED 500 → PINNED 700`, con un `COMMISSION_PERIOD_RATE_UNPINNED` y un `COMMISSION_PERIOD_RATE_PINNED` en `central_audit`. Reabrir tres veces no agrega eventos.

**S7 — la misma corrección en caliente.** Base con `PINNED 700` legado, una APROBADA al 7% (28.000 Gs) y una PAGADA al 1% (4.000 Gs): al abrir se suelta (`UNPINNED 700`) sin elegir tasa; al observar la APROBADA del 7%, una sola transición escribe `PINNED 100`. Secuencia completa `PINNED 700 → UNPINNED 700 → PINNED 100`; ningún importe cambia.

**S6 — cuatro puntos de la secuencia, con rotulado de pantalla y export.**
1. Calculado sin fijar (28.000 + 42.000 Gs al 7%): pantalla «Comisión oficial 7,00% … · todavía sin tasa fijada: el período sigue siendo corregible», KPI «COMISIÓN OFICIAL 7,00% / 70.000 Gs.», export `pinned=false`.
2. Aprobadas → `PINNED 700` y publicado el 1%: pantalla «Comisión oficial 7,00% … · fijada al aprobarse o pagarse», KPI 70.000 Gs., export `policy=7.00 pinned=true` frente a `current_policy=1.00`.
3. Revertidas las dos → `UNPINNED 700`: pantalla «Comisión oficial 1,00% … v3 … · todavía sin tasa fijada», KPI 0 Gs., export `1.00 pinned=false`.
4. Venta nueva calculada al 1% (4.000 Gs) y aprobada → `PINNED 100`: pantalla «Comisión oficial 1,00% … · fijada al aprobarse o pagarse», KPI «COMISIÓN OFICIAL 1,00% / 4.000 Gs.», export `1.00 pinned=true` v3. Libro íntegro `PINNED 700 → UNPINNED 700 → PINNED 100`; reabrir no lo altera.

**S8 — qué fija y qué no, a la tasa histórica.** ELEGIBLE, CALCULADA y REVISADA al 7% no escriben evento; APROBADA fija `PINNED 700`; pagar mantiene el pin sin evento nuevo. Publicar el 1% asienta `protected_periods=["2026-09"]`. Observar la PAGADA no suelta; revertirla se rechaza; anular la venta de origen tampoco suelta; `recalculate` no reinterpreta los 28.000 Gs.

**S9 — migrar y operar coinciden, y reabrir es idempotente.** Cinco configuraciones de hechos (PAGADA 700; APROBADA 700; 700+700; 700+500; sólo CALCULADA 700) dan `[PINNED 700]`, `[PINNED 700]`, `[PINNED 700]`, `[]` y `[]`. Abrir 26 veces cada base deja exactamente el mismo libro.

**S10 — prospectividad.** Con el 7% pagado en 2026-08 y el 1% publicado desde 2026-09: 2026-08 → 700 fijado, 2026-09 → 100, 2026-10 → 100, 2026-07 → sin tasa; el disclaimer de 2026-07 no emite `None` ni porcentaje inventado.

**S11 — cadena de pago completa en mes migrado fijado al 7%.** Pago legado con `policy_code='COMISION_PILOTO_VENDEDORA'`, `version=9`, `scope='VENDEDORA'`: convenio nuevo de 500.000 Gs → base 475.000, 33.250 Gs al 7%, revisado, aprobado y pagado sin rechazos; KPI oficial 61.250 Gs, `non_official=0`, export `7.00 pinned=true`.

**S12 — auditoría de la secuencia en caliente.** `PINNED`(origin `COMMISSION_APPROVED`) → `UNPINNED`(origin `COMMISSION_REVERTED`) → `PINNED`, los tres con su asiento en `central_audit`.

**Regresión:** `python -m pytest -q` → 444 passed.

## Bloqueantes
Ninguno.

## Observaciones no bloqueantes

1. **`recalculate` necesita dos pasadas cuando su propia reparación forma el pin.** Base migrada con PAGADA al 7% y APROBADA al 5% (discrepancia, mes sin fijar): la pasada 1 repara la APROBADA al 1% (4.000 Gs) y, al reconciliar, fija el mes a `PINNED 700`; la entrada queda CALCULADA a 4.000 Gs dentro de un mes fijado al 7%. La pasada 2 la lleva a 28.000 Gs y la 3 ya no cambia nada. El dinero está protegido —`review` rechaza el importe caduco— pero el rótulo de esa fila y el del mes se contradicen durante una pasada.

2. **El mensaje de rechazo nombra la versión y no la tasa:** «la política del período cambió desde el cálculo (v1 → v1): recalcule antes de continuar». Cuando lo que cambió es el porcentaje y no la versión, el texto no dice nada útil.

3. **El código de política se llama `COMISION_GENERAL_1PCT` también cuando la tasa fijada es 7%**: pantalla y export publican «Comisión oficial 7,00% … (COMISION_GENERAL_1PCT v2)».

4. **En bases migradas el pin hereda `code`/`version`/`scope` del hecho legado**, de modo que el export puede declarar `policy.scope="VENDEDORA"` —un alcance que la migración retiró— mientras el disclaimer del mismo documento cierra con «igual para toda vendedora y local».

## Superficie que mi revisión NO cubrió

Concurrencia y transacciones simultáneas sobre la misma base; captura visual real a 1920x1080 (verifiqué los textos de `policy_label` y de los KPI con Tk, no imágenes); el resto de la pantalla de comisiones (detalle por entrada, `policy_note`, exportación a archivo en disco); roles distintos de ADMIN_CENTRAL y el control de permisos; los demás módulos del repositorio; el paquete `.zip` y el `MANIFEST.sha256` del artefacto; migración desde datos productivos reales o desde esquemas anteriores distintos de los que construí; volumen y rendimiento con miles de períodos; y el comportamiento con más de dos tasas históricas distintas conviviendo en meses encadenados.
