# BC Caja RC27 — Pulido posterior a la prueba manual

Solo los hallazgos reales del usuario tras validar el circuito de punta a
punta. **No se rediseñó Seguimiento**: la vista, los tres botones, la
agrupación, el reuso de filas y el circuito quedan como estaban.

---

## 1 y 2 · Sucursal automática y alerta

Seguimiento ya abría acotado a la sucursal de la caja (`todas` arranca en
`False`). Lo que sobraba era el botón **Ver todas las sucursales** compitiendo
por espacio con las acciones del día, y una tabla vacía que no decía de qué
sucursal hablaba.

- El botón sale de la barra y pasa a `Más`, como consulta administrativa.
- La tabla vacía ahora dice: **`No hay trabajos pendientes en <Sucursal>`**,
  con el recordatorio de dónde mirar el otro local. Antes se leía como "no hay
  nada" cuando podía haber trabajo en Pilar.
- La alerta sigue abriendo exactamente sus trabajos: cada alerta viaja con su
  `grupo` y el clic aplica el filtro solo (verificado en RC25 y de nuevo aquí).

Bindings canónicos intactos: `PC → ASUNCIÓN`, `P2 → PILAR`, `PILAR → PILAR`.

## 3 · Seleccionar todo

`Seleccionar visibles` → **`Seleccionar todo`**, y la función se renombró con
él (`seleccionar_todo`) para que el código diga lo mismo que la pantalla.
Semántica sin cambios: todos los trabajos que la vista está mostrando. Sigue
sin reconstruir la tabla (RC26).

## 4 · Cierre normal

`RECIBIDO EN PILAR` ya era el cierre automático y se verificó que lo sea de
verdad: sale de Activos, entra en Completados, conserva sus 5 transiciones,
`next_action` devuelve `NINGUNA` y **deja de generar alertas en las dos
sucursales**. No se pide ninguna acción extra. No hizo falta tocar nada.

## 5 · Cerrar por excepción

`Cerrar trabajo` → **`Cerrar por excepción`**, dentro de `Más`. Ahora exige:

| Requisito | Cómo se cumple |
|---|---|
| Motivo obligatorio | rechaza vacío y solo espacios |
| Usuario | rechaza responsable vacío |
| Fecha/hora | `recorded_at` de la transición |
| Historial auditado | transición `<etapa> → CERRADO` con `Cierre por excepción: <motivo>` |

Es la salida para lo que **no** llegó a completarse —cancelación, devolución a
exhibición, trabajo sin efecto, corrección administrativa—, nunca el final
normal del circuito.

## 6 y 7 · Queda a confirmar

**Decisión de modelado.** Se implementó como **condición, no como etapa
nueva**. El trabajo está físicamente `RECIBIDO EN ASUNCIÓN`; lo único que
cambia es que todavía no corresponde despacharlo. Es exactamente el patrón ya
establecido para `reception_issue` y coherente con la regla de RC26 —el
trabajo conserva siempre su etapa física—. La operadora igual lo lee como
estado, porque la fila muestra:

```
QUEDA A CONFIRMAR · RECIBIDO EN ASUNCIÓN     Cliente confirma mañana
```

Modelarlo así evitó además reconstruir `tracked_works` para ampliar su `CHECK`
en una base con trabajos reales y dos tablas referenciándola: un riesgo que
este cambio no necesitaba correr. Migración `021` = dos `ALTER TABLE`.

La observación breve se lee en la columna Observación: *Cliente confirma
mañana · Esperando llamada · Falta confirmar cristal · Esperando autorización*.

**Resolver confirmación** es la acción principal, con dos caminos y nada más:

- **Confirmó** → pide laboratorio y plazo, y el trabajo sale al laboratorio.
- **Canceló** → cierre por excepción con motivo obligatorio y traza.

No se despliega la lista de estados para que la operadora elija uno.

## 8 · Corregir estado

Dentro de `Más`. Solo retrocesos **declarados explícitamente**:

| Desde | Puede volver a |
|---|---|
| `RECIBIDO EN ASUNCIÓN` | `ENVIADO DESDE PILAR` |
| `EN LABORATORIO` | `RECIBIDO EN ASUNCIÓN` |
| `RECIBIDO DEL LABORATORIO` | `EN LABORATORIO` |
| `ENVIADO A PILAR` | `RECIBIDO DEL LABORATORIO` |
| `RECIBIDO EN PILAR` | `ENVIADO A PILAR` |
| `ENVIADO DESDE PILAR` · `CERRADO` | — |

Hay una prueba que verifica que **ningún retroceso salta más de un paso**.
Exige estado anterior, estado nuevo, motivo obligatorio, usuario y fecha/hora,
y deja la traza en el historial. Un salto arbitrario se rechaza explicando qué
sí admite; para eso está el cierre por excepción, no una edición silenciosa.

## 9 · UX

Máximo tres acciones principales: **Acción siguiente · Novedad · Más**.
Verificado en la ventana real. Las excepciones son entradas de menú, nunca
botones. No reaparecieron botones de transición individuales.

---

## Defecto encontrado fuera de alcance, y corregido

Al correr la regresión aparecieron **19 fallos que no venía causando este
cambio**: fallan igual en el commit limpio. Es un bug real y dependiente de la
hora.

`list_shipment_candidates` filtraba `date(o.created_at) BETWEEN ? AND ?`.
`created_at` se guarda en **UTC** y las fechas que elige la operadora son del
**día del negocio**: a partir de las 21:00 locales el UTC ya es del día
siguiente, así que **los pedidos cargados de noche desaparecían de los
candidatos del envío**. La prueba manual se hizo de tarde y por eso no se vio.

Se corrigió comparando instantes en vez de fechas sueltas: los límites del día
local se convierten a UTC (`_limites_utc_del_dia`, límite superior exclusivo).
Se corrigió porque dejaba la suite roja y porque rompe el primer paso del
circuito —armar el envío desde Pilar—, no para ampliar el alcance.

---

## Gates

| Gate | Resultado |
|---|---|
| Regresión completa | **579 PASS / 0 FAIL** |
| Focused RC27 | 39 PASS |
| RC19–RC26 sin regresión | incluido en la regresión |
| Smoke GUI RC27 1920×1080 | PASS · `Sucursal: ASUNCION` · `Resolver confirmación` |
| Smoke GUI RC27 1366×768 | PASS · ídem |
| Smoke GUI RC25 1920×1080 y 1366×768 | PASS |
| Smoke GUI RC19 | PASS |
| Reuso de filas | `BC_CAJA_REUSO_FILAS_OK destruidos=0 creados=0` |
| Estabilidad en reposo | `ESTABLE en reposo` |
| Correos / cierres nuevos | 0 / 0 |

### Tests actualizados a propósito

| Test | Motivo |
|---|---|
| `test_rc11` · `test_rc13` · `test_recovery_drill` · `test_sqlite_*` | La migración 021 extiende el esquema |
| `test_rc24` menú `Más` | Rótulos nuevos y excepciones auditadas |
| `test_rc24` · `test_rc25` · `test_rc26` | Renombre `seleccionar_visibles` → `seleccionar_todo` |

### Evidencia

| Archivo | Qué muestra |
|---|---|
| `rc27-confirmar-1920x1080.png` | Sucursal automática, `QUEDA A CONFIRMAR · RECIBIDO EN ASUNCIÓN`, observaciones breves, tres botones |
| `rc27-confirmar-1366x768.png` | Lo mismo sin desborde |
| `rc27-1920x1080.png` · `rc27-1366x768.png` | Circuito RC25 sin regresión |
| `rc27-rc19-1920x1080.png` | RC19 sin regresión |

### Límite de la sonda

El contenido del menú `Más` no se verifica sobre la ventana: `tk_popup` abre
un bucle de eventos modal que no devuelve el control en modo automatizado.
Queda cubierto a nivel de fuente en `test_rc27_pulido_post_prueba.py`, que
verifica las cinco entradas y que no quedaron rótulos viejos.

---

## Estado

Producción sigue en **`1.0.0-rc.25`**. **No se construyó ni instaló ninguna
build nueva**: queda preparada para la instalación consolidada cuando se
autorice. DatePicker y FactuFácil no iniciados.
