# Handoff

Cadena: Librarian → QA → Auditor, con independencia real en tres subagentes separados por
generación. Estado de revisión de este snapshot: ver `INDEPENDENCE.md`. Evidencia de las
generaciones ya revisadas en `generation-1/` a `generation-5/`.

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
4. **`OBSERVADA` no tiene salida de corrección** (QA-003 obs.). El propio código manda liquidaciones
   a `OBSERVADA` con el texto «requiere corrección manual», pero no existe hoy ninguna vía de
   corrección manual ni en la API ni en la UI. Es el complemento natural del hallazgo 3.
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
12. **Defecto preexistente ajeno a la misión** (LIB-001 obs. 4):
   `tests/gestion_central/test_ui_interactions.py` (commit `bb27034`) define dos veces
   `test_detail_uses_horizontal_full_hd_layout_without_primary_vertical_scroll`; pytest sólo
   recolecta la segunda y un cuerpo de aserciones queda muerto. **Fuera del alcance de esta
   misión**; conviene abrirlo como corrección propia.

## Siguiente bloque recomendado

Definir canónicamente el porcentaje de comisión (general, por local o por vendedora) y convertir
`commission_policies` en regla productiva aprobada. Junto con eso, resolver los hallazgos 1 a 4 y el 11,
que son los que afectan lo que Sol ve o lo que puede corregir.
