# BC Caja RC26 — Desbloqueo del circuito, Teléfono y parpadeo

Tres correcciones sobre `1.0.0-rc.24`, en el orden de prioridad pedido. Todas
con causa reproducida antes de tocar nada.

---

## 1. El flujo quedaba trabado — BUG PRIORITARIO

### Reproducción

Contra el estado canónico, sin tocar la UI:

```
1) En laboratorio, vencido ayer:  etapa='EN LABORATORIO' atrasado=True accion=CONTACT_LABORATORY
2) La operadora usa CONTACTAR:    etapa='EN LABORATORIO' atrasado=True accion=CONTACT_LABORATORY
3) Intenta avanzar:               -> BLOQUEADO
4) Vuelve a contactar:            -> BLOQUEADO OTRA VEZ
5) Única salida existente:        registrar un plazo futuro
```

### Causa exacta

`domain/tracking.next_action()`:

```python
if etapa is TrackingStatus.IN_LABORATORY:
    return (NextAction.CONTACT_LABORATORY if overdue
            else NextAction.RECEIVE_FROM_LABORATORY)
```

El atraso **reemplazaba** la transición física. Y `CONTACT_LABORATORY` mapea a
`None` en `TRANSICION_DE_ACCION`, así que `apply_next_action` lo rechazaba. El
trabajo quedaba con una única acción ofrecida que, por definición, no lo movía.

La única salida era comprometer un plazo futuro **que el laboratorio no había
dado**: para destrabar el sistema había que falsear un dato operativo.

### Segundo caso, el mismo patrón

Encontrado al auditar la causa, no reportado: **`NO LLEGÓ` tenía el mismo
defecto.** `next_action` devolvía `RESOLVE_RECEPTION`, que también mapeaba a
`None`, y la UI mostraba *"Recibilos cuando aparezcan"* sin ofrecer ninguna
forma de recibirlos. Se anunciaba una salida que no existía.

### Corrección

`next_action()` devuelve siempre **la transición física**. El atraso se acepta
como parámetro y deliberadamente no decide.

Se agrega `complementary_action(status, overdue)`: lo que conviene hacer
*además*, sin reemplazar ni bloquear. Hoy tiene un solo caso, contactar al
laboratorio vencido, y sigue siendo útil aunque el trabajo ya pueda recibirse.

`RESOLVE_RECEPTION` pasa a transicionar a `RECIBIDO EN ASUNCIÓN`: resolver que
algo no había llegado es, precisamente, recibirlo cuando aparece. Sigue sin
poder saltar al laboratorio, porque esa transición no existe desde
`ENVIADO DESDE PILAR` — el bloqueo estructural se conserva, la trampa no.

| Antes | Ahora |
|---|---|
| `EN LABORATORIO` + atrasado → solo `CONTACTAR` | → `RECIBIR DEL LABORATORIO`, y se sugiere contactar |
| `NO LLEGÓ` → mensaje sin acción | → `RESOLVER RECEPCIÓN`, que recibe y limpia la marca |

En la UI, la sugerencia se muestra en el botón que ya la ejecuta: `Novedad`
pasa a decir **`Contactar laboratorio`** cuando corresponde. **Siguen siendo
tres botones**, y el principal nunca se deshabilita por atraso.

### Verificación

```
1) 'ATRASADO · EN LABORATORIO' | accion=RECEIVE_FROM_LABORATORY | complementaria=CONTACT_LABORATORY
2) tras CONTACTAR: 'ATRASADO · EN LABORATORIO' | accion=RECEIVE_FROM_LABORATORY
3) avanza -> 'RECIBIDO DEL LABORATORIO'
4) sigue  -> 'RECIBIDO EN PILAR'
5) CERRADO alcanzable
```

Sobre la ventana real, marcando una fila atrasada:
`atrasado_ofrece="Recibir del laboratorio"` en 1920×1080 y 1366×768.

Pruebas en `test_rc26_flujo_no_se_traba.py` (26), incluido un barrido que
verifica que **ninguna etapa del circuito queda sin transición** en ninguna
combinación de atraso, y que ninguna acción complementaria puede ocupar el
lugar de una transición.

---

## 2. Teléfono en Seguimiento

Orden nuevo: `Sobre · Cliente · Teléfono · Tipo de trabajo · Laboratorio ·
Estado · Observación`.

El número **no se duplica**: se resuelve desde el pedido o la venta que
originaron el trabajo (`customer_phones`, una consulta por lote, no una por
fila). `tracked_works` no gana columna de teléfono, así que no puede haber dos
copias diciendo cosas distintas.

Anchos recalculados para que la tabla siga entrando en 1366 sin scroll
horizontal: el espacio sale de Cliente, Tipo, Estado y Observación, no del
total. Un trabajo sin teléfono cargado muestra `—`; uno sin pedido de origen
tampoco rompe.

**WhatsApp y `Llamar` no se implementaron**, como se pidió. Propuesta para el
slice siguiente al final de este documento.

---

## 3. Parpadeo

### Descartado por medición, no por suposición

El sospechoso habitual era `aplicar_macro_layout`, que llama a
`update_idletasks()` dentro del manejador de `<Configure>` — la receta clásica
de un ciclo de relayout. Se midió la ventana **en reposo**, en ambas pestañas:

```
place()/segundo = [0, 0, 0, 0, 0, 0]   <Configure> = 0
widgets creados = 0   widgets destruidos = 0
VEREDICTO = ESTABLE en reposo
```

No es un ciclo de relayout, ni un timer, ni polling. El debounce que lo evita
sigue en su lugar y queda cubierto por prueba.

### Causa real, medida

El parpadeo no ocurre en reposo: ocurre **en cada refresco**.

```
REFRESCO_FILTRO   destruidos= 440  creados= 440  ms=889
MARCAR_CHECKBOX   destruidos=   0  creados=   0  ms=2
```

Cada refresco destruía y volvía a crear los ~440 widgets Tk de la tabla —unos
29 por fila— con la lista a la vista, durante casi un segundo. Y lo hacía
**aunque la lista fuera exactamente la misma**. Viene de RC22, cuando la tabla
dejó de ser un `Treeview` y pasó a ser widgets por fila para anclar los chips;
RC25 sumó encabezados de grupo y RC26 la columna de teléfono.

Además, `Seleccionar visibles` y `Limpiar selección` disparaban ese
reconstruido completo **solo para cambiar tildes**.

### Corrección

1. **Reuso de filas.** El widget de cada trabajo se crea una vez y después solo
   se repinta: textos, colores y posición. Se crean únicamente los trabajos que
   aparecen y se destruyen únicamente los que dejan de figurar. Los encabezados
   de grupo también se reutilizan; un grupo sin filas se oculta, no se destruye.
2. **Selección sin reconstruir.** `Seleccionar visibles` y `Limpiar selección`
   sincronizan los tildes sobre los widgets existentes.
3. **Un solo repintado.** La lista se descuelga del grid mientras se repinta,
   con `try/finally` para que vuelva aunque algo falle.

| Métrica | Antes | Ahora |
|---|---|---|
| Widgets destruidos por refresco | 440 | **0** |
| Widgets creados por refresco | 440 | **0** |
| Tiempo de refresco | 889 ms | 432 ms |

El tiempo restante es consulta y reconfiguración, no reconstrucción.

Herramientas nuevas: `tools/diagnose_caja_parpadeo.py` (mide reposo) y
`tools/probe_caja_reuso_filas.py` (imprime `BC_CAJA_REUSO_FILAS_OK/_FAIL`).
Contrato fijado en `test_rc26_parpadeo.py` (13 pruebas).

---

## Gates

| Gate | Resultado |
|---|---|
| Regresión completa | **540 PASS / 0 FAIL** |
| Focused RC26 (flujo + parpadeo) | 39 PASS |
| RC19–RC25 sin regresión | 267 PASS |
| Smoke GUI 1920×1080 | PASS |
| Smoke GUI 1366×768 | PASS |
| Smoke GUI RC19 | PASS |
| Sonda de reuso de filas | `BC_CAJA_REUSO_FILAS_OK destruidos=0 creados=0` |
| Sonda de reposo | `ESTABLE en reposo` |
| Correos / cierres nuevos | 0 / 0 |

### Tests actualizados a propósito

| Test | Motivo |
|---|---|
| `test_rc24` · `test_rc25` · `test_rc25_e2e` | Codificaban el bug: que el atraso reemplace la acción y que `NO LLEGÓ` no tenga salida |
| `test_rc21` columnas y anchos | Entra `Teléfono` |
| `test_rc21` chip · `test_rc25` grupos | El reuso renombra widgets; la intención se conserva |

---

## Propuesta para el slice siguiente (no implementada)

`Llamar` y WhatsApp desde la fila. El número ya está resuelto en `BoardRow`, así
que el trabajo es solo de UI. Se deja fuera a propósito: `webbrowser` /
`tel:` / `wa.me` son dependencias de entorno y merecen su propio slice con su
propia evidencia, no mezclarse con un fix de bloqueo. Hay prueba que verifica
que todavía **no** están.

Producción sigue en **rc.24**. No se construyó ni instaló ninguna RC nueva.
