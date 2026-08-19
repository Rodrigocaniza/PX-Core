# Verdict — QA, generación 8
Runner: QA-IND-COMISION-POLICY-1PCT-008
Snapshot: cf4fb258703e266148d7bb7332b79ffdddce926c
Veredicto: PASS

## Escenarios propios ejecutados

Todos con bases sqlite temporales construidas a mano desde el scratchpad de sesión (`qa_g8_common.py`, `qa_s1..qa_s9.py`), sin reutilizar ninguna prueba del paquete ni de las generaciones 1–7. Nada se escribió dentro del repo.

**E1 — Base migrada del piloto con comisión ya pagada (contrato 1).** Venta común de 1.000.000 Gs con liquidación `PAGADA` de 30.000 Gs al 3,00% y etiqueta retirada `SINTETICA_PENDIENTE_APROBACION`. Tras reabrir: `policy_status = POLITICA_HISTORICA_PREVIA`, `rate_bp = 300`, `commission_amount = 30.000 Gs` sin tocar. Libro de tasas de 2099-04 **vacío**, `pinned_for = None`, `policy_for_period` → 1,00% con `pinned=False`. KPI: comisión oficial 0 Gs, no oficial 30.000 Gs (1 liquidación). Seis reaperturas seguidas: mismos importes, cero eventos, cero asientos de pin/unpin.

**E2 — `PAGADA` canónica migrada (contrato 2).** Liquidación pagada de 20.000 Gs al 1,00% sobre 2.000.000 Gs con política canónica → la migración siembra `PINNED 100` (`origin=BACKFILL`, motivo «hecho economico vivo PAGADA en la base migrada»). Observarla y anular la venta después **no** suelta: el libro sigue en `['PINNED']`.

**E3 — Secuencia completa fijar → soltar → refijar sobre base migrada (contratos 1, 3, 6).** Sobre la base legada de E1 publiqué por error el 100,00% desde 2099-01-01; venta A de 10.000.000 Gs → 10.000.000 Gs de comisión; revisar+aprobar → `PINNED 10000`. Revertir esa única aprobación → **`UNPINNED 10000`**, `origin=COMMISSION_REVERTED`, `entry_id = 1f2246cf-…` (la liquidación retirada, contrato 6). La legada pagada de 30.000 Gs **no** sostuvo el mes. Corregí al 1,00% desde 2099-04-01; venta B de 10.000.000 Gs → **100.000 Gs**, no 10.000.000: el sobrepago de **9.900.000 Gs por venta** no reaparece. Aprobar B → `PINNED 100`; pagarla y observarla después no suelta. La legada terminó igual: 300 bp / 30.000 Gs / `POLITICA_HISTORICA_PREVIA`.

**E4 — Migración reevalúa `UNPINNED` y no inventa retiradas (contrato 5).** Base con libro `PINNED, UNPINNED` y una `APROBADA` canónica viva de 20.000 Gs → al reabrir queda `PINNED, UNPINNED, PINNED(100)`, sin que la migración escriba un solo `UNPINNED`. Misma base pero con evidencia sólo legada (30.000 Gs al 3%): queda en `PINNED, UNPINNED` y `pinned_for = None`. Base que llega `PINNED` sin evidencia viva: la migración no escribe `UNPINNED` (ver observación 1).

**E5 — Migrar == operar (contrato 4).** Reconstruí operando la secuencia completa (legada pagada → 100% publicado → aprobar A → revertir A → 1% publicado → aprobar y pagar B): libro `PINNED, UNPINNED, PINNED`, período fijado al 1,00%. Copié la misma base con la API `backup` de sqlite, borré el libro y reabrí: la migración siembra `PINNED 100` y `policy_for_period` da idénticos `rate_bp=100, pinned=True`. Una venta nueva de 10.000.000 Gs comisiona **100.000 Gs en ambas**.

**E6 — Convergencia de `recalculate` (contrato 7).** Base migrada con legada `PAGADA` 30.000 Gs, legada `APROBADA` 60.000 Gs y legada `CALCULADA` 90.000 Gs: pasada 1 `{evaluated:2, changed:2}`, pasada 2 `{changed:0}`. La pagada queda intacta (300 bp / 30.000 Gs), las otras dos pasan a 1,00% (20.000 Gs y 30.000 Gs) perdiendo el aval (`approved_by=NULL`), sin escribir ningún evento de tasa. Después aprobar y pagar la reparada entra sin rechazo y fija `PINNED 100`. Caso con desfijado en medio del mismo bucle: la liquidación evaluada después del `UNPINNED` sí lo ve y cobra 100.000 Gs en vez de 10.000.000 Gs. Ver observación 2 sobre el número de pasadas.

**E7 — Vitalidad múltiple e idempotencia (contrato 3).** Dos aprobaciones canónicas de 100.000 Gs cada una en 2099-04 sobre base migrada: una sola `PINNED`; revertir la primera **no** suelta; anular la venta de la segunda sí, con `UNPINNED` que nombra `b4d955d8-…`. Repetir la anulación y recalcular no duplica: un único evento `UNPINNED` y un único asiento en auditoría. Cobro que se cae (`revert_payment` de 4.000.000 Gs sobre venta de 10.000.000 Gs ya aprobada por 100.000 Gs) → `PINNED, UNPINNED` nombrando la liquidación. Una legada `CALCULADA` nunca entra a la cadena: `review` la rechaza con «la liquidación no lleva la política oficial vigente (POLITICA_HISTORICA_PREVIA): recalcule antes de continuar» y no fija nada.

**E8 — Rotulado en pantalla y export en los tres puntos, sobre base migrada.** Panel Tk real (`CommissionsPanel`, 1920x1080 lógico):
- P1 fijado: cabecera «Comisión oficial 100,00% de la base · COMISION_GENERAL_1PCT v2 · vigente desde 2099-01-01 · **fijada al aprobarse o pagarse**»; KPI «COMISIÓN OFICIAL 100,00% = 10.000.000 Gs.»; export `pinned=True`, disclaimer «…tasa ya fijada por un hecho económico oficial (aprobación o pago)…».
- P2 soltado: misma tasa de catálogo pero «**todavía sin tasa fijada: el período sigue siendo corregible**», KPI oficial 0 Gs, export `pinned=False`.
- P3 refijado: «Comisión oficial 1,00% … v3 … fijada al aprobarse o pagarse», KPI oficial 100.000 Gs, no oficial 30.000 Gs, export `pinned=True`, `rate_percent="1.00"`.

En los tres puntos la fila legada muestra «Importe calculado con una política anterior a la regla aprobada (3,00%). No es pagable con este importe. Ya fue pagado: se conserva tal cual por auditoría.» y ni la cabecera ni el disclaimer declaran nunca oficial el 3,00%. El export mantiene la legada con `status=PAGADA, rate_bp=300, commission_amount=30000, policy_status=POLITICA_HISTORICA_PREVIA`.

**E9 — Evidencia mixta y períodos con fecha completa.** Legada 3% + canónica 1% pagadas en el mismo mes: la migración fija 1,00% desde la canónica y **no** declara evidencia discrepante (ningún `SEED_SKIPPED`). Dos canónicas pagadas al 1% y 2%: evidencia discrepante, no se siembra nada y el export dice «el período todavía no tiene una tasa fijada». Liquidación migrada con `period='2099-04-10'`: se siembra bajo `2099-04` y el código en caliente la ve.

**Regresión completa:** `python -m pytest -q` → **431 passed in 51.29s**, sin fallos ni warnings de error.

## Bloqueantes

Ninguno.

## Observaciones no bloqueantes

1. **Un `PINNED` heredado sin hecho vivo sobrevive a la migración y el rótulo lo declara fijado.** Reproducción (`qa_s9.py`): base con libro `PINNED 10000` cuya aprobación quedó `REVERTIDA` y donde lo único pagado es una legada de 30.000 Gs — exactamente lo que producía la generación 7, cuya vitalidad sí contaba a la legada. Al reabrir con este código la migración no escribe `UNPINNED` (por diseño declarado, contrato 5) y el período sigue fijado al 100,00%: una venta nueva de 10.000.000 Gs se calcula y hasta se revisa por **10.000.000 Gs**, y la cabecera afirma «Comisión oficial 100,00% … fijada al aprobarse o pagarse» sin que exista hecho vivo alguno. El dinero está protegido: `approve` rechaza con «la política del período cambió desde el cálculo (v2 → v1): recalcule antes de continuar», la propia transición de `review` escribe el `UNPINNED` que faltaba, y tras recalcular la liquidación queda en **100.000 Gs**. No lo marco bloqueante porque no es alcanzable operando con este código —sólo importando un libro producido por la generación 7— y porque los contratos 3 y 5 se contradicen justo en esta celda; pero es la única celda donde el rótulo afirma una fijación que hoy nadie sostiene.

2. **`recalculate` no siempre converge en una sola pasada cuando la reparación suelta el propio período.** Reproducción (`qa_s5.py`): base migrada con `APROBADA` canónica al 1% cuya base quedó desfasada (1.000.000 Gs registrados sobre venta de 10.000.000 Gs), fijada por la siembra, más una publicación posterior del 2%. Pasada 1: repara la base a 10.000.000 Gs conservando la tasa fijada (100.000 Gs) y escribe `UNPINNED`; pasada 2: ya sin fijación, resuelve por catálogo y pasa a **200.000 Gs**; pasada 3: `changed=0`. No hay rechazo sin explicación —el intento intermedio devuelve «la política del período cambió desde el cálculo (v1 → v2): recalcule antes de continuar»— ni importe pagable erróneo, pero el estado intermedio queda visible en pantalla hasta el segundo recálculo.

3. **El KPI «Pagado» mezcla lo oficial con lo legado.** En P3 la pantalla muestra «COMISIÓN OFICIAL 1,00% = 100.000 Gs.» y «Pagado = 130.000 Gs.», porque `paid_amount` suma también los 30.000 Gs de la liquidación con `POLITICA_HISTORICA_PREVIA` que `commission_amount` excluye. Es defendible (el dinero salió), pero deja un «pagado» mayor que la comisión oficial sin nota que lo explique; sólo el aviso naranja menciona los 30.000 Gs aparte.

4. **El aviso «Recalcule las no pagadas» es permanente en toda base migrada del piloto.** La única liquidación no oficial de mis bases es una `PAGADA`, que por diseño `recalculate` nunca alcanza; el aviso queda encendido para siempre pidiendo una acción que ya no aplica a esa fila.

## Superficie que mi revisión NO cubrió

- **Ventas de convenio en las bases legadas**: todas mis liquidaciones migradas fueron `COMUN`; no crucé el descuento del 5% con `POLITICA_HISTORICA_PREVIA` ni con la secuencia de fijado.
- **Multi-período y multi-local sobre bases migradas**: casi todo se concentró en `2099-04` y un solo local/vendedora; no probé interferencia entre meses adyacentes ni filtros por sucursal en el rotulado.
- **Concurrencia**: nada de dos procesos migrando o aprobando la misma base a la vez, ni de `BEGIN IMMEDIATE` bajo contención; el libro append-only se validó sólo en serie.
- **Bases anteriores al esquema `commission_*` actual** (columnas realmente ausentes, tablas del piloto muy viejas): construí las mías sobre el esquema ya creado y les inyecté las etiquetas retiradas.
- **Export a archivo en disco y captura visual real 1920x1080**: verifiqué el diccionario de `export_summary` y los textos de los widgets, no el fichero exportado ni una captura de pantalla.
- **Datos reales del piloto**: seguí trabajando con datos sintéticos propios; no abrí ninguna base de producción ni el zip del paquete.
- **Aritmética de bordes del redondeo, roles/permisos, y el resto de módulos** (Caja, entregas, FactuFácil): fuera de mi eje; sólo los cubre la regresión, que pasó entera.
