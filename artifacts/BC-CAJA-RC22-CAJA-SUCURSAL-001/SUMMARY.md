# BC Caja RC22 — Caja fija a sucursal y seguimiento por local

## Lo que había

`UNIDADES = [PC, MVPC, P2, MVP2, ADMINISTRACIÓN]` son **cajas**, no sucursales,
y el formulario dejaba elegir cualquiera libremente. `app_settings.branch`
—`{"branch": "…Casa Central", "cashbox": "PC"}`— ya ligaba esta instalación a
su caja, pero **nada lo usaba**. `board()` tenía un filtro `origin_branch` que
la UI nunca pasaba: la pestaña mostraba todo el sistema, por eso los dos
locales veían las mismas alertas.

## Modelo canónico implementado

`Sucursal → Caja → sesión/cajera`, nunca al revés.

- **Migración 018** crea `cash_register_branches(cash_register → branch)`:
  persistente, único por caja, con responsable y motivo, y auditado en
  `admin_audit_log` en cada asignación. Reasignar es una acción
  administrativa explícita, no algo que ocurra operando.
- `tracked_works` gana `processing_branch`, de modo que un trabajo conserva
  **origen** y **sucursal de proceso**.
- La cajera vive en la sesión/cash day y no toca el vínculo: hay prueba de que
  abrir la caja con otra persona no cambia la sucursal ni la responsabilidad.

## Responsabilidad por etapa

`RESPONSABLE_POR_ETAPA` es la única fuente de verdad y cubre las siete etapas:

| Etapa | Próxima acción |
|---|---|
| ENVIADO DESDE PILAR | proceso (Asunción): recibir |
| RECIBIDO EN ASUNCIÓN | proceso: enviar al laboratorio |
| EN LABORATORIO | proceso: seguimiento |
| RECIBIDO DEL LABORATORIO | proceso: enviar encomienda |
| ENVIADO A PILAR | origen (Pilar): recibir |
| RECIBIDO EN PILAR | nadie: circuito completo |

Se resuelve con los valores reales del trabajo, no con nombres cableados:
un origen "ENCARNACIÓN" enruta a Encarnación. Hay prueba de que el bloque de
alertas **no menciona** `saleswoman`, `vendedora`, `cajera` ni `opened_by`.

## Vista y alertas

- Seguimiento abre mostrando lo que **esta sucursal** tiene que resolver.
- `Ver todas las sucursales` queda como alcance administrativo explícito.
- Las alertas se calculan con `pending_actions_for_branch`: por próxima acción
  pendiente del local, no por existencia global del trabajo.
- Un clic en la alerta aplica **el filtro que la originó**, no siempre
  `Atrasados`.
- Si la caja no tiene sucursal asignada, la barra lo dice y el alcance queda
  deshabilitado: no se adivina.

## Demostración con los 15 TEST reales

```
etapa                              ASUNCIÓN                         PILAR
Pilar envía 15                     ve 15 · 15 por recibir           ve 0 · —
Asunción recibe los 15             ve 15 · 15 por enviar a lab      ve 0 · —
3 al laboratorio, vencidos         ve 15 · 3 atrasados              ve 0 · —
3 recibidos del laboratorio        ve 15 · 12 por enviar a lab      ve 0 · —
encomienda en camino a Pilar       ve 12 · 12 por enviar a lab      ve 3 · 3 por recibir
recibidos en Pilar                 ve 12                            ve 0 · —
```

La responsabilidad se transfiere exactamente al salir la encomienda, y el
circuito cierra en `RECIBIDO EN PILAR`.

## Dato histórico ambiguo: FAIL-CLOSED sobre `P2`

| Caja | Días | Movimientos | Vínculo |
|---|---|---|---|
| `PC` | 6 | 8 | ASUNCIÓN, derivado de `app_settings.branch` |
| `PILAR` | 1 | 0 | PILAR, caja del escenario TEST |
| `P2` | 1 | 0 | **sin asignar** |

`P2` tiene un único día, cero movimientos y fecha futura (18/08/2026). Nada en
la base dice a qué sucursal pertenece, así que la migración **no le inventa
una**. Queda sin vincular y el sistema lo trata explícitamente. Asignarla es
una decisión de negocio, no técnica.

## Verificación

- Regresión canónica: **410 PASS, 0 FAIL**.
- Smoke GUI real con contexto de sucursal.
- Smoke de dos locales sobre los 15 TEST reales, sin sembrar nada nuevo.
- Escenario devuelto a su punto de partida.
