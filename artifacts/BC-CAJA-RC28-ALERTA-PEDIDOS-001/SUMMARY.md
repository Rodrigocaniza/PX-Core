# BC Caja RC28 — La alerta de Pedidos transporta su contexto

Bug funcional detectado en la prueba manual sobre producción.

## Causa exacta

No hubo que suponer nada: el código lo dice.

```python
# controller.order_counts()  -> lo que cuenta la alerta
len(self.list_orders("Hoy")) + len(self.list_orders("Atrasados"))

# el clic en la alerta                       -> lo que abre
command=lambda: (seleccionar_pestaña("Pedidos"), refrescar_pedidos("Hoy"))
```

**La alerta suma dos grupos y el clic filtra uno solo.** Con los pendientes
vencidos —el caso normal, porque los atrasados se acumulan— el filtro `Hoy`
devuelve cero y la pantalla abre en blanco.

Reproducido contra la base productiva real:

```
HOY = 2026-08-16
   PC  PENDIENTE  2026-08-13  ATRASADO  2999
   PC  PENDIENTE  2026-08-14  ATRASADO  0239

ALERTA = Hoy(0) + Atrasados(2) = 2
clic aplica filtro 'Hoy' -> 0 pedidos      <-- pantalla en blanco
```

El grupo real que origina `Trabajos 2` **no es `Atrasados`**: es la unión de
*vencidos* y *de hoy sin entregar*.

## Corrección

Una sola consulta canónica, `FILTRO_REQUIEREN_ATENCION`, que responde a la vez
cuánto vale la alerta y qué abre el clic. Es el mismo principio que ya rige
Seguimiento con `next_action`: si dos capas contestan por separado, tarde o
temprano discrepan.

```
Requieren atención = delivery_date <= hoy  AND  status != ENTREGADO
```

`controller.orders_alert(branch)` devuelve `cantidad`, `filtro` e `ids`. La
alerta guarda ese filtro y el clic navega con él.

**Corrección incluida:** el filtro `Hoy` no excluía `ENTREGADO`, así que un
pedido ya entregado hoy inflaba el contador de *"Trabajos a entregar"*. El
grupo canónico lo excluye, que es lo que el rótulo siempre prometió.

## UI

Al abrir desde la alerta, de forma compacta:

```
Mostrando: Requieren atención (2)  ·  Caja PC        [ Ver todos ]
```

- El contexto aparece solo cuando hay filtro; con `Todos` se retira.
- `Ver todos` quita el filtro **y** el alcance de sucursal.
- Entrada normal a Pedidos: abre en `Requieren atención`, no en una hoja en
  blanco. Si no hay nada: **`No hay pedidos pendientes.`**
- La caja se atiende a sí misma: por defecto se muestran los pedidos de su
  propia sucursal, y el contexto lo dice (`Caja PC`).

Se sumó `Requieren atención` a la barra de filtros; los cuatro anteriores
conservan su semántica exacta.

## Validación

| # | Punto | Resultado |
|---|---|---|
| 1 | Alerta `Trabajos N` abre N pedidos | PASS · `abre=['2999','0239']` |
| 2 | Ningún pedido ajeno aparece | PASS · sin `FUTURO`, `YA-ENTREGADO`, `OTRO-LOCAL` |
| 3 | Filtro/contexto visible | PASS · `Mostrando: Requieren atención (2) · Caja PC` |
| 4 | `Ver todos` elimina el filtro | PASS · pasa de 2 a 5 |
| 5 | Entrada normal no abre vacía | PASS · `entrada_normal=['2999','0239']` |
| 6 | Vacío explicativo | PASS · `No hay pedidos pendientes.` |
| 7 | Sucursal/caja respetada | PASS · PC ve 2, Pilar ve 1 |
| 8 | Seguimiento sin regresión | PASS · smokes RC27, RC25 y RC19 |
| 9 | Smoke GUI 1920×1080 | PASS |
| 10 | Smoke GUI 1366×768 | PASS |

### Gates

| Gate | Resultado |
|---|---|
| Regresión completa | **601 PASS / 0 FAIL** |
| Focused RC28 | 22 PASS |
| Smoke GUI RC28 1920×1080 y 1366×768 | PASS |
| Smoke GUI RC27 · RC25 · RC19 | PASS |
| Reuso de filas | `0 destruidos / 0 creados` |
| Estabilidad en reposo | `ESTABLE en reposo` |
| Correos / cierres nuevos | 0 / 0 |
| Lógica económica | sin tocar |

### Defecto de la propia sonda, corregido

La primera corrida del smoke falló con `la alerta anuncia 2 y la grilla abre
0`. No era el fix: **la grilla de Movimientos también tiene una columna
`sobre`** y aparece antes en el árbol de widgets, así que la sonda estaba
leyendo la tabla equivocada —y vacía—. Ahora identifica la de Pedidos por su
juego completo de columnas. Vale la pena registrarlo: el síntoma era idéntico
al bug que se estaba arreglando.

## Estado

Producción sigue en **`1.0.0-rc.26`**. No se construyó ni instaló build nueva:
el fix queda listo para validación visual. FactuFácil y DatePicker global no
iniciados.
