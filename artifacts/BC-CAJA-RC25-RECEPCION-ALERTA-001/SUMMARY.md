# BC Caja RC25 — Recepción con discrepancias en pantalla y alerta principal

Cierra las Misiones 2 y 3. La Misión 1 (tres botones, selección múltiple,
chips anclados) queda intacta y sigue verde.

**Principio aplicado:** la operadora no aprende el workflow. La pantalla le
dice qué requiere atención ahora y cuál es la próxima acción válida.

---

## Misión 2 — Recepción con discrepancias en pantalla

RC24 ya tenía el dominio. Lo que faltaba era que se viera.

### La discrepancia se lee en la propia fila

`BoardRow.alert` ahora antepone la discrepancia sin borrar la etapa física:

| Situación | Lo que lee la operadora |
|---|---|
| No apareció en el envío | `NO LLEGÓ · ENVIADO DESDE PILAR` |
| Llegó sin figurar | `NO ESTABA EN LISTA · RECIBIDO EN ASUNCIÓN` |

El orden de prioridad es atraso → discrepancia → confirmado. El atraso va
primero porque exige una llamada ahora; un `NO LLEGÓ` nunca puede estar
atrasado, así que no compiten.

`NO LLEGÓ` sigue ligado a su lote y `next_action` devuelve
`RESOLVER_RECEPCION`, de modo que **bloquea el avance** hasta resolverse.

### La barra de recepción

Aparece sobre la tabla mientras el lote no terminó de recibirse, y desaparece
cuando cerró. Trae exactamente tres cosas:

```
Declarados 15 · Recibidos 12 · No llegó 2 · Extra 1   [ No llegó ]  [ + No estaba en lista ]
```

- **Recibir no tiene botón propio**: ya es la `Acción siguiente` de un trabajo
  `ENVIADO DESDE PILAR`, y duplicarlo daría dos caminos para lo mismo.
- **No llegó** aplica a toda la selección (`mark_batch_not_arrived`). Recibir
  era masivo desde RC24; marcar lo que falta tenía que serlo también, o la
  discrepancia sale más cara de registrar que el caso normal y termina sin
  registrarse.
- **+ No estaba en lista** abre una búsqueda por Sobre o cliente sobre los
  pedidos ya cargados (`search_receivable_orders`). Se elige el pedido y se
  cuelga al lote: **no se vuelve a escribir cliente ni receta**. Queda
  registrado quién lo agregó (`created_by`) y cuándo (`created_at` y la
  transición auditada).

### Conciliación

`reception_reconciliation(works)` es ahora la única cuenta, en el dominio. El
servicio la aplica al lote y el tablero al conjunto visible, así que la línea
que lee la operadora y la que audita el lote no pueden discrepar.

`recibidos` cuenta solo entre los declarados: sumar los extra no cerraría
contra el total que Pilar envió.

**Defecto encontrado y corregido en el smoke:** la cabecera mostraba a la vez
`Enviados: 16 / Recibidos: 13` (lo que hay en pantalla) y `Declarados 15`
(el lote declarado) — dos totales distintos para la misma palabra. Ahora se
muestra una sola cuenta de recepción a la vez.

---

## Misión 3 — Alerta principal y agrupación operativa

### La alerta llega a donde está la operadora

`pending_actions_for_branch` se muestra en la **franja superior**, visible
desde la pantalla principal de Caja y desde cualquier pestaña:

```
⚠ 15 por recibir desde Pilar — clic para ver
```

Es específica de la sucursal, muestra cantidad, y el clic abre Seguimiento
**con el filtro ya aplicado**: cada alerta viaja con su `grupo`, así que no
hay que volver a tocar `Atrasados` ni buscar a mano. Se muestra una sola
alerta —la más urgente—; dos o tres compitiendo obligan a decidir cuál mirar,
que es justo lo que la alerta viene a evitar.

**Decisión de ubicación.** Primero se puso en la cabecera de Caja. El smoke
GUI mostró que ahí competía por el ancho con los seis importes de RC18 y
**recortaba Gastos y Entregado**. Se movió a la franja superior, que tenía
lugar libre. `baseline-caja-1366x768.png` documenta que el recorte del
resumen a 1366 es anterior a esta misión y no lo introduce.

### Bindings

Migración `020` siembra los tres vínculos que la operación declaró
inequívocos:

| Caja | Sucursal |
|---|---|
| `PC` | `ASUNCIÓN` |
| `P2` | `PILAR` |
| `PILAR` | `PILAR` |

`INSERT OR IGNORE` respeta cualquier asignación administrativa previa. El
principio de la 018 sigue vigente: **una caja desconocida no inventa
sucursal**, y el test lo verifica con `CAJA-NUEVA`.

### Agrupación simple

Los seis grupos son **secciones de una misma lista**, no seis pantallas ni
seis barras de botones:

```
Por recibir · 3
    …filas…
En laboratorio · 13
    …filas…
```

Los nueve filtros bajaron a tres (`Activos`, `Completados`, `Todos`), que son
otro eje: alcance, no etapa. La operadora no elige etapa — ve todas las suyas
de una vez. Un clic en el encabezado enfoca ese grupo y otro lo deshace.

**El orden de las filas no cambió.** Agrupar es presentación; hacerlo en el
tablero habría enterrado un atrasado debajo de dos etapas anteriores. El
tablero sigue devolviendo las excepciones primero y la UI las reparte.

### Observaciones operativas

Legibles en la lista, sin abrir el detalle:

| Antes | Ahora |
|---|---|
| `16-08 17:30` | `☎ Hoy 17:30 · Lab confirmó salida 14:30` |
| `17-08 15:00` | `✆ Mañana 15:00` |
| `Debía 17-08 15:00` | `Vence Mañana 15:00` |

- Días relativos (`etiqueta_dia`): la operadora razona en "hoy/mañana", no en
  fechas contra el calendario.
- Medio de contacto en un carácter (`☎` línea, `✆` WhatsApp): el rótulo
  completo no entra en la columna.
- **`Debía` solo cuando el plazo ya venció.** Un trabajo que vence mañana no
  "debía" nada; leerlo en pasado hacía pensar que había un problema donde no
  lo había. Defecto detectado al revisar la captura.

El detalle conserva la fecha absoluta: ahí se verifica un dato, no se barre
una lista.

---

## Prueba final con los mismos 15 TEST

`tests/caja_diaria/test_rc25_e2e_15_test.py` recorre el circuito completo sin
sembrar otro escenario, verificando en cada paso lo que se vería en pantalla.

| # | Paso | Verificado |
|---|---|---|
| 1 | Pilar envía 15 | `count == 15` |
| 2 | Asunción alerta | `"15 por recibir desde Pilar"`; Pilar no alerta |
| 3 | Clic abre esos 15 | mismo conjunto de ids, sin extras |
| 4 | 12 recibidos | rótulo `Recibir 12 en Asunción` |
| 5 | 2 `NO LLEGÓ` | ligados al lote, avance bloqueado |
| 6 | 1 `NO ESTABA EN LISTA` | pedido reutilizado, autoría registrada |
| 7-8 | Selección múltiple → Alfa/Beta/Gamma | laboratorio por fila |
| 9 | Atrasados | agrupados por laboratorio, acción pasa a *Contactar* |
| 10-11 | Novedades hoy/mañana | `Hoy 17:30`, `Mañana 15:00` en la fila |
| 12 | Retorno del laboratorio | selección mixta rechazada; contactar y recibir |
| 13 | Envío a Pilar | `SEND_TO_PILAR` |
| 14 | Alerta en Pilar | 13, grupo `por_recibir_pilar` |
| 15 | Recepción final | `RECIBIDO EN PILAR` |
| 16 | Completados | salen de activos, quedan consultables |

**Hallazgo real del recorrido.** 12 recibidos + 2 `NO LLEGÓ` = 14: **el
decimoquinto queda sin revisar**, y la recepción sigue abierta justamente por
eso. La línea no lo disimula y la alerta de Asunción lo sigue reclamando
(3 pendientes) aunque el lote grande ya cerró su vuelta. Se dejó así, que es
el comportamiento correcto, en vez de ajustar los números para que cerraran.

Otro hallazgo: al recibir del laboratorio, una selección que mezcla trabajos
vencidos (*Contactar*) con trabajos en plazo (*Recibir*) se rechaza. Es la
misma regla que impide dar por recibido lo que todavía no llamaste.

---

## Evidencia

| Archivo | Qué muestra |
|---|---|
| `rc25-1920x1080.png` | Seguimiento: conciliación, discrepancias, grupos |
| `rc25-1366x768.png` | Lo mismo sin desborde ni scroll horizontal |
| `rc25-1920x1080-caja-principal.png` | Alerta en la pantalla de Caja, seis importes intactos |
| `rc25-1366x768-caja-principal.png` | Alerta a 1366 |
| `baseline-caja-1366x768.png` | Cabecera antes de la misión: el recorte a 1366 es previo |
| `smoke-rc19-1920x1080.png` | RC19 sigue verde |

### Validación UX

En 1920×1080 y 1366×768, verificado sobre los widgets reales:

- máximo 3 botones principales (`Acción siguiente`, `Novedad`, `Más ▾`);
- sin overlays — todo chip cuelga de su fila, verificado recorriendo la
  cadena de `master` hasta `_bc_fila_seguimiento`;
- discrepancias comprensibles en la fila;
- alerta principal accionable, y el clic abre tantos trabajos como anuncia;
- observaciones legibles sin abrir el detalle.

### Gates

| Gate | Resultado |
|---|---|
| Focused (RC25) | 56 PASS |
| E2E 15 TEST | 1 PASS |
| Regresión completa | **497 PASS / 0 FAIL** |
| Smoke GUI 1920×1080 | PASS |
| Smoke GUI 1366×768 | PASS |
| Smoke GUI RC19 (no regresión) | PASS |
| Correos enviados | 0 |
| Cierres nuevos | 0 |

### Tests actualizados a propósito

| Test | Motivo |
|---|---|
| `test_rc11` · `test_rc13` · `test_recovery_drill` · `test_sqlite_*` | La migración 020 extiende el esquema |
| `test_rc22_caja_sucursal` | `P2` pasa a estar sembrada; el principio se verifica ahora con `CAJA-NUEVA` |
| `test_rc24` observación | El formato pasa a días relativos y `Vence`/`Debía`, por Misión 3 |

Producción sigue en **rc.23**. No se instaló ninguna versión intermedia.
