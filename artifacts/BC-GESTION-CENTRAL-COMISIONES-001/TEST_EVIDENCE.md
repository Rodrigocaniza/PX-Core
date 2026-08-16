# Evidencia de pruebas

## Generación 7 (vigente)

- Dominio de comisiones: **45/45 PASS**.
- Interacción Tk y Full HD: **4/4 PASS**.
- Regresión completa: **300/300 PASS** en 26.90 s.
- Línea base heredada: 251 pruebas; esta misión suma 49 sin romper ninguna existente.

## FAIL de revisores independientes (generación 6) y su corrección

18. **El total de un convenio no podía corregirse a la baja — bloqueante de QA.** La liquidación
    por convenio sólo se revertía cuando la venta *dejaba* de ser convenio, así que en una
    corrección CONVENIO→CONVENIO `settled` seguía valiendo el total viejo y la guarda disparaba con
    un mensaje que invocaba un cobro inexistente. La venta quedaba clavada en el total anterior,
    con 95.000 Gs. de base sobrevaluada por venta afectada en el escenario del revisor.

19. **La excepción no capturada truncaba el lote de sincronización — mismo bloqueante.**
    `sync_review_sales` no capturaba el rechazo por fila, de modo que un total corregido en el
    origen propagaba el error y salteaba en silencio todas las filas posteriores del lote.

    Corregidos: toda corrección sobre un convenio re-expresa su liquidación —se revierte la
    anterior y se asienta la nueva por el total corregido, conservando siempre los cobros reales—,
    y la sincronización cuenta la fila rechazada en `rejected` y continúa. Cubierto por
    `test_an_agreement_total_can_be_corrected_downwards`,
    `test_correcting_an_agreement_keeps_the_real_payments` y
    `test_a_rejected_row_never_truncates_the_sync_batch`.

## FAIL de revisores independientes (generación 5) y su corrección

15. **La fila `CONVENIO` sobrevivía a la conversión de la venta a común — bloqueante de QA y del
    Auditor, encontrado por ambos de forma independiente.** Es un defecto **introducido por la
    propia corrección estructural de la generación 5**. Una venta convertida de convenio a común
    quedaba con `paid_amount` completo y saldo 0 pese a que el cliente nunca pagó nada: llegaba a
    `PAGADA` con comisión sobre cero cobros reales, el asiento era irreversible
    (`revert_payment` filtra `kind='COBRO'`) y el cobro real posterior se rechazaba por «supera el
    saldo pendiente», dejando la venta permanentemente incobrable. Tras una reversa rutinaria el
    residuo producía además 400.000 Gs. de subfacturación.

16. **El KPI «Cobros parciales» informaba dinero ya revertido — bloqueante de QA.** La consulta
    excluía las filas `CONVENIO` pero no los cobros con `REVERSA`: una seña revertida seguía
    contando como cobrada en la cifra de portada.

17. **`HANDOFF.md` declaraba abierto un hallazgo ya cerrado — bloqueante del Librarian.** El ítem 5
    afirmaba que `revert_payment()` no rechazaba ventas anuladas cuando el código sí lo hacía,
    contradiciendo a `ARCHITECTURE.md` y a `TEST_EVIDENCE.md`.

    Corregidos sin inventar ninguna regla: `_reverse_agreement_settlement` revierte en el libro la
    liquidación por convenio cuando la venta deja de serlo —que es exactamente lo que
    `COMMISSION_RULES.md` ya documentaba—, el KPI excluye los cobros revertidos, y el hallazgo
    obsoleto se quitó del backlog. Cubierto por
    `test_downgrading_an_agreement_to_a_common_sale_reopens_the_balance`,
    `test_a_downgraded_agreement_keeps_only_real_payments` y
    `test_reverted_payments_are_never_reported_as_collected`.

## FAIL de revisores independientes (generación 4) y su corrección

11. **Cobro posterior del origen descartado en silencio — bloqueante del QA independiente.**
    `_apply_source_update` ignoraba `sale.initial_paid`: una venta ingerida con saldo y cobrada
    después quedaba atrapada para siempre en `PENDIENTE_SALDO`, con `sync_review_sales` informando
    éxito y sin error, observación ni asiento. Subpago del 100% por la vía de ingesta documentada.

12. **`paid_amount` negativo y sin respaldo — bloqueante del Auditor independiente.** La rama
    CONVENIO fijaba `paid = total_amount` sin consultar el libro; combinado con una reversión
    posterior producía `paid_amount = -300.000` y un KPI informando como cobrado dinero ya
    revertido.

13. **`revert_payment` sin guarda de tipo — bloqueante del QA independiente.** Dejaba `paid_amount`
    sin correspondencia con el libro y cerraba la única puerta hacia `ELEGIBLE`.

14. **El contrato de idempotencia no cumplía lo afirmado — bloqueante del Auditor independiente.**
    El chequeo de saldo precedía al de reintento, de modo que reintentar el cobro que cancela la
    venta fallaba por saldo en vez de descartarse. La prueba citada no podía alcanzar el caso.

    Los cuatro tenían una sola raíz y se corrigieron de raíz: **el libro append-only es ahora la
    única fuente de verdad de `paid_amount`**. El convenio liquida mediante una fila `CONVENIO`,
    toda diferencia declarada por el origen se asienta como una fila más, `revert_payment` recalcula
    desde el libro y rechaza ventas anuladas o convertidas en convenio, y el reintento se reconoce
    antes de validar importes. Cubierto por `test_resync_with_a_later_payment_settles_the_sale`,
    `test_paid_amount_is_always_backed_by_the_ledger`,
    `test_convenio_settlement_is_recorded_in_the_ledger`,
    `test_retrying_the_cancelling_payment_is_discarded_not_rejected` y
    `test_reverting_a_payment_on_a_voided_sale_is_rejected`.

## FAIL de revisores independientes (generación 3) y su corrección

9. **La comisión de una venta cobrada se perdía tras una reversión — bloqueante del QA
   independiente de generación 3.** La clave de idempotencia de `register_payment` se derivaba del
   contenido del cobro y el chequeo de duplicados no excluía los cobros ya reversados. Tras una
   `revert_payment` motivada, volver a cargar el mismo recibo real devolvía `(None, False)` sin
   excepción y sin asiento en el historial, indistinguible de un duplicado legítimo: la venta
   quedaba con saldo fantasma y la vendedora nunca cobraba su comisión. El único workaround era
   falsear la fecha, que además movía la comisión de período.

10. **Dos cobros parciales legítimos idénticos se colapsaban en uno** (mismo monto, misma fecha,
    misma referencia opcional), dejando un saldo fantasma que mantenía la liquidación en
    `PENDIENTE_SALDO` indefinidamente.

    Ambos corregidos con un contrato de idempotencia explícito: `register_payment` acepta un
    `idempotency_key` del llamador para proteger reintentos de integración; sin clave, cada llamada
    es un cobro real distinto; y un cobro revertido deja de bloquear su clave. La identidad interna
    del cobro se separó de la clave del llamador (`client_key`), con migración aditiva idempotente.
    Cubierto por `test_a_reverted_payment_can_be_registered_again`,
    `test_two_identical_genuine_payments_are_both_registered` y
    `test_explicit_idempotency_key_protects_integration_retries`.

## FAIL de revisores independientes (generación 2) y su corrección

6. **Comisión pagable sobre una base congelada — bloqueante del QA independiente de generación 2.**
   La guarda de `_apply_source_update` sólo cubría `PAGADA` y `APROBADA`. Una corrección de origen
   sobre una liquidación `REVISADA` reescribía `gross_amount` y `sale_kind` sin recalcular
   `agreement_discount`, `commissionable_base` ni `commission_amount`; como `REVISADA` no es
   recalculable, el camino `REVISADA → APROBADA → PAGADA` liquidaba sobre la base anterior.
   Verificado por el revisor: 11.400 Gs. de subpago y 54.150 Gs. de sobrepago en sus escenarios, y
   omisión completa del 5% al cambiar el tipo de venta. Alcanzable sin intervención humana desde
   `sync_review_sales`. Defecto **preexistente** de la generación 1 que su QA no había encontrado.
   Corregido con `REVIEWED_STATES` y recálculo completo de la base antes de la revisión. Cubierto
   por `test_source_correction_after_review_never_pays_a_stale_base` y
   `test_source_correction_before_review_recomputes_the_whole_base`.

7. **Reatribución de comisión ya pagada — observación O1 del Auditor de generación 2.** La misma
   guarda permitía reescribir `saleswoman` y `gross_amount` de una entrada `OBSERVADA` que antes
   estuvo `PAGADA`, reagrupando bajo otra vendedora dinero ya desembolsado. Cerrada por la misma
   corrección, al pasar la guarda a `_was_paid`. Cubierta por
   `test_source_correction_cannot_reattribute_already_paid_commission`.

8. **Defectos documentales — bloqueantes B1/B2/B3 del Librarian y B1/B2 del Auditor.** El paquete
   describía en pasado una revisión de generación 2 que aún no había ocurrido, remitía a un
   directorio inexistente, y el ZIP transportaba un `ARTIFACT_CONSISTENCY.md` obsoleto que se
   auto-certificaba con cifras de la generación invalidada, en un archivo excluido del manifest.
   Errores de la ejecución implementadora, no del producto. Corregidos: todo documento se escribe
   antes de empaquetar, el manifest cubre ahora `ARTIFACT_CONSISTENCY.md`, y ningún documento
   describe una revisión no ocurrida.

## FAIL de revisores independientes (generación 1) y su corrección

Los dos bloqueantes se reprodujeron con los escenarios exactos de cada revisor y se verificaron
muertos tras la corrección.

4. **`_month()` no validaba la fecha — bloqueante Q1 del QA independiente.**
   `"2099-4-10"` producía el período `"2099-4-"`: la venta quedaba CALCULADA con base y comisión
   correctas pero no aparecía en ningún reporte mensual, sin error ni marca de estado. Alcanzable
   desde `sync_review_sales`, que pasaba sin validar la fecha del snapshot SQLite externo.
   Corregido con `date.fromisoformat` y validación en la ingesta, que ahora devuelve
   `invalid_date` en vez de perder la fila. Cubierto por
   `test_invalid_dates_are_rejected_and_never_produce_a_period` y
   `test_review_sync_reports_invalid_dates_instead_of_losing_them`.

5. **`PAGADA → OBSERVADA → REVERTIDA` — bloqueantes A1, A2 y A3 del Auditor independiente.**
   Una liquidación pagada alcanzaba `REVERTIDA` en dos llamadas autorizadas, liberando el índice
   parcial de unicidad y habilitando un segundo pago de la misma venta mientras `report()` ocultaba
   el primero por excluir las revertidas. Además, `ARCHITECTURE.md` afirmaba explícitamente que esa
   ruta no existía. Corregido con el invariante `_was_paid`, aplicado en las tres rutas que pueden
   producir `REVERTIDA` (`revert`, `_revert_commission_effect`, `void_sale`). Cubierto por
   `test_paid_settlement_can_never_reach_reverted_even_through_observed` y
   `test_voiding_a_paid_sale_observes_instead_of_reverting`.

## Generaciones históricas invalidadas

- Generación 6: 297/297 PASS. Cifra correcta, pero ninguna prueba cubría la corrección a la baja
  de un convenio ni la resiliencia del lote de sincronización.
- Generación 5: 294/294 PASS. Cifra correcta, pero ninguna prueba cubría el descenso
  CONVENIO→COMÚN, que era justamente lo que la propia corrección había roto.
- Generación 4: 289/289 PASS. Cifra correcta, pero ninguna prueba cubría el re-sync con un cobro
  modificado ni el reintento del cobro que cancela la venta.
- Generación 3: 287/287 PASS. Cifra correcta, pero la suite afirmaba como idempotencia deseada
  justamente el comportamiento defectuoso del libro de cobros.
- Generación 2: 284/284 PASS. Cifra correcta, pero la suite no cubría la corrección de origen en
  estado `REVISADA`, que era la ventana desprotegida.
- Generación 1: 280/280 PASS. Cifra correcta, pero la suite no cubría ninguno de los dos
  bloqueantes de esa generación.

Todas las cifras eran ciertas y todas las suites revisadas estaban verdes al ser revisadas.
Ninguna regresión verde sustituye a una revisión independiente.

## Cambio de contrato en una prueba existente

`test_duplicate_payment_key_is_idempotent` afirmaba que dos cobros idénticos consecutivos debían
colapsar en uno. Esa afirmación **era el defecto**, no la garantía. Se reemplazó por
`test_explicit_idempotency_key_protects_integration_retries`, que verifica la idempotencia real —la
del reintento con clave explícita— y por las dos pruebas que cubren los cobros genuinos.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Escaneo heurístico de secretos: PASS; las únicas coincidencias están dentro del propio test de prohibición.
- Captura 1920×1080: PASS.

## FAIL preservados y corregidos durante la implementación

1. **Explicación del convenio desaparecía tras el cálculo.**
   `test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance` falló porque, al pasar
   a `CALCULADA`, el motivo mostrado dejaba de mencionar el convenio. La misión exige mostrar
   siempre por qué una venta recibió el descuento. Corregido: `breakdown()` antepone el motivo del
   convenio en todos sus estados. Prueba repetida: PASS.

2. **KPI «Cobros parciales» sin formato monetario.**
   La primera captura mostró `700000` en crudo. `partial_payments_amount` faltaba en `AMOUNT_KEYS`.
   Corregido y fijado por aserción en `test_full_hd_layout_keeps_every_control_visible`.

3. **Tabla principal recortada a 1920×1080.**
   La primera captura cortaba «Base comisionable» y ocultaba por completo la columna «Comisión»;
   el resumen por vendedora también se cortaba. Causa: el panel izquierdo tenía `minsize=980`
   frente a 1470 px de columnas. Corregido recalibrando anchos y paneles, y fijado con una guarda
   de regresión que compara la suma de anchos de columna contra el ancho visible de cada tabla.
   Evidencia visual regenerada tras la corrección.

## Reproducción

```
python -m pytest -q
python -m compileall -q modulos tools tests bc_gestion_central.py
git diff --check
python tools/capture_gestion_central_comisiones.py artifacts/BC-GESTION-CENTRAL-COMISIONES-001/screenshots/comisiones-1920x1080.png
```
