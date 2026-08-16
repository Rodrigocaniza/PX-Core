# BC Caja RC24 — Simplificación operativa de Seguimiento

## Alcance real de la misión

El pedido abarca 15 áreas, incluyendo estados de dominio nuevos, rediseño
completo de la barra de acciones, selección múltiple, diálogos masivos,
conciliación de recepción y alertas en la página principal. Es alcance de
varias misiones, así que se ejecuta por capas.

**Esta capa entrega dominio y servicio completos y verdes.** La capa de
interfaz queda pendiente y está descrita al final.

## 1. Autoridad única `next_action`

`domain/tracking.next_action(status, overdue, reception_issue)` es la única
función que decide qué corresponde hacer. La barra de acciones, las alertas y
las operaciones masivas preguntan ahí, de modo que no puedan discrepar.

| Situación | Acción |
|---|---|
| ENVIADO DESDE PILAR | Recibir en Asunción |
| RECIBIDO EN ASUNCIÓN | Enviar a laboratorio |
| EN LABORATORIO, en plazo | Recibir del laboratorio |
| EN LABORATORIO, vencido | **Contactar laboratorio** |
| RECIBIDO DEL LABORATORIO | Enviar a Pilar |
| ENVIADO A PILAR | Recibir en Pilar |
| RECIBIDO EN PILAR | ninguna |
| NO LLEGÓ | Resolver recepción |

`ETIQUETA_ACCION` da el texto del botón y `TRANSICION_DE_ACCION` la etapa
destino; `CONTACTAR` y `RESOLVER` no transicionan, y el servicio lo respeta.

## 2. Selección y acción masiva

- `next_action_for(ids)` devuelve la acción común, el rótulo ya pluralizado
  —`Recibir 5 en Asunción`— o el motivo por el que no hay acción única:
  *"Los trabajos seleccionados están en etapas diferentes."*
- `apply_next_action(ids, ...)` ejecuta esa acción sobre toda la selección.
- El envío masivo a laboratorio toma un solo laboratorio y un solo plazo, y
  **cada trabajo conserva su transición individual auditada**.

## 3. Discrepancias de recepción

Migración 019 agrega `reception_issue`, que **no es una etapa**: convive con
la etapa y por eso no entra en el `CHECK` de `status`.

- **NO LLEGÓ** — figuraba en el envío y no apareció. Sigue ligado al lote y
  `next_action` devuelve `RESOLVER_RECEPCION`, así que no puede avanzar al
  laboratorio. Si aparece después, recibirlo limpia la discrepancia.
- **NO ESTABA EN LISTA** — `add_unlisted_reception(order_id)` **reutiliza el
  pedido existente**: no se recarga cliente ni receta. Queda registrado quién
  lo agregó. El marcador persiste, porque documenta que entró fuera del envío
  declarado.

## 4. Conciliación

`reception_reconciliation(shipment_id)` → `Declarados · Recibidos · No llegó ·
Extra`. `recibidos` cuenta solo entre los declarados: sumar los extra haría
que los números no cierren contra lo que Pilar envió.

## 5. Observación en una línea

`BoardRow.observation` resuelve qué mostrar sin abrir el detalle: la
discrepancia si la hay, si no la última novedad —con su nuevo plazo cuando
existe—, si no el plazo comprometido.

## Defectos que encontraron las pruebas

- Recibir limpiaba **cualquier** discrepancia, incluida `NO ESTABA EN LISTA`,
  que debe persistir. Acotado a `NO LLEGÓ`.
- `recibidos` contaba los extra y la conciliación no cerraba.

## Verificación

- Regresión canónica: **432 PASS, 0 FAIL** (RC23 dejó 410; RC24 suma 22).
- Sin tocar economía, cierres, correo, arqueos, convenios, FactuFácil ni
  Comunicaciones.

## Pendiente: capa de interfaz

Queda por implementar sobre esta base: los tres botones
(`Acción siguiente` / `Novedad` / `Más`), la columna selector con
`Seleccionar visibles` y contador, el diálogo único de envío masivo, la
columna Observación, la línea de conciliación, los atajos de novedad
(*Más tarde hoy* / *Mañana*), la alerta en la página principal de Caja y la
agrupación compacta de estados. El dominio y el servicio ya exponen todo lo
necesario para hacerlo sin volver a tocar reglas.
