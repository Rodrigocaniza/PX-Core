# Handoff

Cadena: Librarian → QA → Auditor, con independencia real en tres subagentes separados por
generación. Estado de revisión de este snapshot: ver `INDEPENDENCE.md`. Evidencia de las
generaciones ya revisadas en `generation-1/` a `generation-7/`.

## Matriz de revisión

- Reglas económicas, estados, período, identidad e idempotencia → `modulos/gestion_central/comisiones.py`
- Persistencia, índices parciales únicos y migración → `modulos/gestion_central/repository.py`
- Bandeja, filtros, KPIs, desglose, acciones e historial → `modulos/gestion_central/comisiones_ui.py`
- Entrada desde el panel → `modulos/gestion_central/ui.py`
- Validación de dominio → `tests/gestion_central/test_comisiones.py`
- Validación de interfaz y Full HD → `tests/gestion_central/test_comisiones_ui_interactions.py`
- Evidencia visual → `tools/capture_gestion_central_comisiones.py` y `VISUAL_EVIDENCE.md`
- Contrato económico → `COMMISSION_RULES.md`
- Arquitectura, invariantes y límites → `ARCHITECTURE.md`

## Hallazgos no bloqueantes registrados y NO corregidos

Se corrigieron únicamente los bloqueantes, según el protocolo. Abiertos, ordenados por riesgo:

1. **Fechas ISO en formato básico o de semana** (QA-002 obs. 1, QA-003 obs.). `date.fromisoformat` acepta
   `"20990410"` y `"2099-W15-3"`; el período derivado queda bien formado, pero los consumidores
   que cortan la cadena (`substr(sale_date,1,7)`, el KPI `sales_in_period`, el desplegable de
   meses) no las reconocen. No se pierde ni se duplica dinero. Normalizar al almacenar
   (`date.fromisoformat(...).isoformat()`) lo cerraría de raíz.
2. **`paid_amount` se calcula por estado y no por `paid_at`** (QA-002 obs. 3, AUD-002 O2). Al
   observar una liquidación ya pagada, el KPI «Pagado» cae a 0 aunque el dinero salió.
3. **Las liquidaciones `OBSERVADA` suman a los KPIs monetarios** (QA-001 obs. 2, QA-002 obs. 4).
   No hay fuga de dinero, pero «Comisión calculada» sobreestima lo liquidable y el contador
   `observed` que el KPI ya calcula no se muestra en pantalla.
4. **`OBSERVADA` pagada no tiene salida de corrección** (QA-003 obs., acotado por AUD-006 O2 y
   AUD-007 O1). Una `OBSERVADA` **no pagada** sí tiene salida: `revert()` la acepta y la UI expone
   el botón «Revertir», y una corrección de origen recalcula su base en el lugar. Lo que no tiene
   salida es la `OBSERVADA` que ya movió dinero: `revert()` está correctamente bloqueado por
   `_reject_paid` y no existe otra vía de corrección. Es el complemento natural del hallazgo 3.
5. **Ventas mixtas (convenio parcial) mal clasificadas** en `sync_review_sales` (QA-001 obs. 3).
   El error es conservador —nunca paga de más— y las reglas aprobadas no definen la venta mixta.
   Requiere decisión de negocio antes de tocar código.
6. **`test_state_contract_and_append_only_history` no prueba append-only** (AUD-002 O3). Ejecuta
   `DELETE` + `rollback()`, que demuestra que el rollback de SQLite funciona. La propiedad real se
   cumple, pero la suite no la protege ante regresiones.
7. **`assert "float(" not in source` es más débil que la propiedad declarada** (AUD-001 obs.,
   AUD-003 O4).
8. **Cosméticos de UI** (QA-003): badge de piloto duplicado entre shell y panel, y el signo «×»
   delante de un importe que ya es el producto.
9. **`register_payment` con la misma clave y monto distinto descarta sin traza** (QA-004 obs.).
    Es error del llamador, pero convendría un asiento de historial en el descarte.
10. **Los cobros legados quedan con `client_key` NULL tras la migración** (AUD-004 O5) y pierden la
    idempotencia derivada del contenido que tenían bajo el esquema anterior.
11. **Ni `register_payment` ni `sync_review_sales` tienen llamador productivo** (QA-004 obs.): la
    bandeja sólo se puebla hoy con el capturador sintético. Es el cableado que debe resolver el
    próximo bloque para que el ciclo de cobros sea alcanzable desde el producto.
12. **Cosméticos de `TEST_EVIDENCE.md`** (LIB-005 obs.): numeración descendente por bloques y
    cuatro bullets de gates ubicados bajo la sección equivocada.
13. **Una corrección de origen que declara *menos* cobrado se ignora en silencio** (AUD-005 obs.):
    el libro nunca se reduce. Coherente con append-only y con exigir `revert_payment`, pero no está
    documentado en `COMMISSION_RULES.md`.
14. **Atribución obsoleta de convenio en el KPI** tras el descenso de una liquidación ya pagada
    (QA-006 obs.): la entrada conserva la foto del convenio mientras la venta ya es común.
15. **Una corrección sobre una liquidación `OBSERVADA` no pagada recalcula su base en silencio**
    (QA-006 obs.), a diferencia de `REVISADA`/`APROBADA`/`PAGADA`. Asimetría menor, sin efecto
    sobre dinero.
16. **`COMMISSION_RULES.md` y `ARCHITECTURE.md` generalizan de más** (AUD-006 O1, AUD-008 O3):
    afirman que al convertir un convenio en venta común «no existían cobros que arrastrar» y que la
    venta «recupera su saldo completo». Cierto para la venta nacida convenio, pero no para el camino
    COMÚN→CONVENIO→COMÚN, donde el código correctamente conserva los cobros previos.
17. **La guarda de `sync_review_sales` enumera tipos en vez de garantizar el invariante**
    (QA-008 obs. 1, AUD-008 O1): un `payload` que no sea diccionario escapa por `AttributeError` y
    trunca el lote. **No alcanzable**: los dos productores del repositorio construyen `payload`
    siempre como diccionario y `sync_review_sales` no tiene llamador productivo. Conviene ampliar la
    guarda o validar el tipo en el borde.
18. **Aserción casi tautológica** en `test_downgrading_an_agreement_to_a_common_sale_reopens_the_balance`
    (AUD-006 O4): pasaría ante una regresión; la propiedad real la cubren las líneas anteriores.
19. **Divergencia preexistente ajena a la misión** (AUD-004 O5, AUD-006 O8): `main` local está
    detrás de `origin/main`. No la produjo esta rama.
20. **`ARCHITECTURE.md` afirma que `paid_amount` «nunca se asigna por fuera del libro»**
    (AUD-006 O6, AUD-007 O2). En el alta el valor se escribe directo en el `INSERT`, aunque la misma
    transacción asienta la fila del libro por el mismo importe y el invariante **de resultado** se
    cumple en todos los casos verificados. Imprecisión de mecanismo, no falsedad del invariante.
21. **La máquina de estados de `ARCHITECTURE.md` reparte las rutas a `REVERTIDA` de forma laxa**
    (AUD-007 O7): el conjunto de estados de origen es completo, pero la atribución por función es
    imprecisa.
22. **Aserción repetida en `test_review_sync_reports_invalid_dates_instead_of_losing_them`**
    (AUD-007 O5): compara el dict completo y luego una de sus claves.
23. **Una venta hoy CONVENIO no admite `revert_payment` sobre sus cobros reales previos**
    (QA-007 obs.). Coherente con la guarda de la generación 4, pero deja sin salida un cobro real
    mal cargado en una venta convertida a convenio.
24. **Una corrección de origen puramente no financiera sobre un convenio dispara igualmente la
    reversión-y-reasiento** (QA-007 obs.): el neto siempre queda exacto y el append-only lo
    justifica, pero es ruido evitable si se compara el total antes de re-expresar.
25. **Una corrección de origen que cambia `sale_date` conserva el `cancelled_date` anterior**
    (QA-007 obs.), de modo que la comisión queda atribuida al mes viejo. **No alcanzable por la
    ingesta real**, porque la identidad de `review_sales` incorpora `business_date`; es un defecto
    de contrato de la API de dominio, latente.
26. **`sync_review_sales` no permite conciliar el lote** (QA-008 obs. 1 y 2): una fila ya registrada
    y sin cambios no incrementa ningún contador, y `rejected` es sólo un número sin traza de qué
    filas no se ingirieron. Las filas siguen en `review_sales`, pero el operador no puede saber
    cuáles faltan.
27. **`CommissionSaleInput` valida obligatoriedad sobre `str(valor)`** (QA-008 obs. 3), así que
    `None`, `0` o `[]` pasan la validación y el rechazo llega después como error de base. Sin
    impacto monetario.
28. **Los KPI de cobros parciales se calculan sobre el saldo actual** (QA-008 obs. 5): cuando una
    venta con parciales queda cancelada más adelante, esos parciales dejan de figurar en el KPI del
    mes en que ocurrieron.
29. **`test_expenses_and_administration_deliveries_never_enter_the_ledger` promete más que lo que
    prueba** (LIB-008 obs.): son dos `pytest.raises` sobre el constructor, sin construir un gasto ni
    tocar el libro. Igual observación para la prueba citada por la regla 8, que cubre sólo la mitad
    `REVERTIDA`.
30. **Defecto preexistente ajeno a la misión** (LIB-001 obs. 4):
   `tests/gestion_central/test_ui_interactions.py` (commit `bb27034`) define dos veces
   `test_detail_uses_horizontal_full_hd_layout_without_primary_vertical_scroll`; pytest sólo
   recolecta la segunda y un cuerpo de aserciones queda muerto. **Fuera del alcance de esta
   misión**; conviene abrirlo como corrección propia.

## Siguiente bloque recomendado

Definir canónicamente el porcentaje de comisión (general, por local o por vendedora) y convertir
`commission_policies` en regla productiva aprobada. Junto con eso, resolver los hallazgos 1 a 4 y el 11,
que son los que afectan lo que Sol ve o lo que puede corregir.
