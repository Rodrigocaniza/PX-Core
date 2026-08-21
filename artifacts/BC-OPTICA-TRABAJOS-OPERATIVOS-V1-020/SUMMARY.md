# BC-OPTICA-TRABAJOS-OPERATIVOS-V1-020

**Composturas y trabajos de taller.** Lo que la óptica hace todos los días y no
estaba en ningún lado: alguien deja los lentes para que le pongan un tornillo, y
hasta hoy eso vivía en un cuaderno.

Hecho desde Casa. Sin apply productivo.

---

## Lo que se decidió antes de escribir código

### No se reutilizó `tracked_works`, y esa es la decisión principal

La 016 ya sigue trabajos. Sigue **otro** trabajo: el circuito físico
Pilar → Asunción → laboratorio → Pilar. Sus siete estados son lugares donde está
el sobre, y su `CHECK` es cerrado. Una compostura que se arregla en el mostrador
de Asunción no está en ninguno de esos siete lugares.

Meterla ahí obligaba a abrir ese `CHECK` y a que una misma tabla contestara dos
preguntas distintas —dónde está físicamente, y en qué etapa del taller está—,
que es exactamente como se rompe un modelo. Son dos circuitos. `order_id` y
`cash_entry_id` quedan como costura para el día que un trabajo de taller tenga
que ir al laboratorio, sin fundir las dos cosas.

Se revisaron también `orders`, `laboratories` y `sale_items` antes de decidir.

### El invariante de inventario ya estaba resuelto aguas arriba

Se buscó la evidencia antes de tocar nada, y apareció: **V1-010 ya corrigió**
Hilo (2000070), Tornillo (2000071), Plaqueta (2000072) y Par de patillas
(2000056) a `SERVICIO_NO_STOCKEABLE`, con su `NATURE_CORRECTION` auditado y su
historia preservada. Y la 023 tiene el trigger
`stock_movements_solo_articulos_stockeables`, que rechaza en la base cualquier
movimiento de un artículo cuya naturaleza no mueva stock.

Así que este slice **no vuelve a corregir nada**. Volver a hacerlo sería
reescribir una decisión ya tomada y auditada. Lo que agrega es la prueba de que
sigue siendo cierto, que es lo que un slice nuevo puede romper sin darse cuenta.

### La comisión de compostura no es la comisión comercial

La del 1% remunera **vender** y se calcula sobre el monto; ésta remunera
**arreglar**, es un monto fijo por trabajo, y la cobra quien lo hizo —que muchas
veces no es quien vendió—. Viven en tablas distintas y no se suman en ningún
lado. Se verificó además que el modelo del 1% vive en otra línea
(`mission/bc-gestion-central-comision-policy-1pct-001`, que **no** es ancestro de
ésta): no hay una segunda lógica incompatible porque no se tocó la primera.

---

## Base

| | |
|---|---|
| branch | `feature/bc-optica-trabajos-operativos-v1-020` |
| parte de | `feature/bc-optica-login-operadora-v1-019b @ de767d9` |
| contiene | V1-019A `4717acf`, V1-018, V1-017, `origin/main 7db56a0` — verificado con `merge-base --is-ancestor` |
| worktree | `.worktrees/optica-trabajos-020` |
| `main` | no se tocó |

---

## Migración 031

`031_trabajos_operativos.sql`. Se verificó primero que `030` seguía siendo la
última en esta línea.

**Estrictamente aditiva.** No tiene un solo `ALTER TABLE`, `UPDATE`, `DELETE` ni
`DROP`: no modifica ninguna tabla existente, así que ninguna fila productiva
puede perderse. Lo único que escribe es su propio catálogo de tipos. Hay una
prueba que lo verifica **leyendo el `.sql`**, no confiando en él.

| tabla | qué es |
|---|---|
| `service_job_types` | Compostura, Hilo, Tornillo, Plaqueta, Patilla, Ajuste, Armado, Otro |
| `service_jobs` | el trabajo |
| `service_job_events` | su historia, append-only |
| `service_commission_policy` | cuánto cobra cada persona, sin nombres sembrados |
| `service_job_commissions` | los devengos, append-only con compensación |
| `service_commission_balance` | vista: lo adeudado, derivado |

`service_job_types.stockeable` está clavado en `0` por `CHECK`. Parece una
columna inútil y es justo al revés: es el invariante escrito en el esquema. El
día que alguien intente dar de alta un tipo de trabajo que mueva stock, la base
lo rechaza sola, sin depender de que el código se acuerde.

---

## El trabajo

Origen, responsable, estado, causa y traza. Número legible (`T-00001`,
correlativo derivado de lo guardado y no de un contador aparte, así sobrevive a
un restore), fecha y hora de recepción, sucursal, cliente, teléfono,
descripción, tipo, observación, quién recibió, responsable de taller, quién
entregó, estado, fecha prevista, retorno de taller, fecha de entrega, importe,
cobro y pedido asociados.

`responsible` es texto y no clave foránea —igual que `cash_entries.saleswoman` y
por la misma razón: si mañana se corrige cómo se escribe el nombre de una
persona, los trabajos de agosto no se reescriben—. `responsible_user_id` guarda
la identidad para lo único que la necesita: la comisión.

### Estados

```
RECIBIDO ──→ EN_TALLER ──→ LISTO ──→ ENTREGADO
    │            │           │            │
    └─→ LISTO    └─→ RECIBIDO└─→ EN_TALLER└─→ EN_TALLER
                                (reabrir)    (reabrir)
    ANULADO desde cualquiera de los tres abiertos
```

`RECIBIDO → LISTO` está permitido a propósito: un tornillo se pone en el
mostrador en dos minutos y no pasa por ningún taller. Obligar a un paso
intermedio ficticio sería pedirle a la operadora que mienta para poder avanzar,
y a los diez días nadie sabría cuáles pasaron de verdad por taller.

Volver atrás **exige motivo**, siempre. Y volver desde `LISTO` o `ENTREGADO` se
registra como `REABIERTO`, no como `ENVIADO_A_TALLER`: la diferencia importa
cuando alguien pregunta cuántos hubo que rehacer, que es otra pregunta que
cuántos fueron al taller.

Lo que no está en `ALLOWED_TRANSITIONS` no pasa, y no pasa en silencio.

---

## Responsables

Del catálogo real de V1-019 (`admin_users`). **No hay una segunda lista y no hay
un solo nombre cableado.** Un nombre que no está en el catálogo se rechaza.

Se distinguen los tres papeles, que muchas veces son tres personas: quien
recibe (`received_by`, de la sesión), quien hace (`responsible`) y quien entrega
(`delivered_by`). Una persona inactiva no puede quedar de responsable de un
trabajo nuevo — pero **sí** se pueden ver los trabajos que ya hizo: dar de baja
a alguien no borra lo que hizo.

---

## Comisión

**Devenga al llegar a `LISTO`**, y la razón sale del flujo real: la comisión de
compostura remunera **hacer** el trabajo, no venderlo ni entregarlo. Cuando el
trabajo llega a `LISTO`, quien lo hizo ya lo hizo; que el cliente pase a
retirarlo mañana, la semana que viene o nunca es una circunstancia del cliente,
y hacerla condición del pago dejaría trabajo hecho sin remunerar por un motivo
ajeno a quien lo hizo. Está declarado en un solo lugar: `ESTADO_DE_DEVENGO`.

**La política no trae nombres sembrados.** Que una persona cobre 5.000 por
compostura y otra no cobre nada es una decisión de la Óptica sobre personas
reales, y las personas reales viven en `admin_users` desde la 030. Sembrar un
nombre acá sería volver a cablear en el esquema la lista que la 030 terminó de
sacar de la pantalla. **Sin política cargada, un trabajo no devenga: cero, no un
default inventado.** Eso es exactamente lo que corresponde a quien dirige.

**No se duplica**, y la garantía no es que el código se acuerde: cada asiento
cuelga de un hecho (`event_id UNIQUE`), y un hecho paga una vez. Reprocesar,
reintentar o reabrir no puede pagar dos veces lo mismo.

Rehacer un trabajo sí devenga de nuevo, y está bien: si volvió al taller y se
hizo otra vez, se hizo otra vez.

**Anular compensa.** No borra el devengo: asienta su contrario, y el saldo queda
en cero. El histórico sigue diciendo que se devengó y que después se compensó,
que es lo que pasó. Un devengo se compensa una sola vez (índice único).

---

## Caja

Un trabajo puede tener o no cobro. **Este módulo no crea movimientos de caja y
no puede crearlos**: el dinero entra por el circuito normal de venta y el
trabajo sólo deja la referencia. `cash_entry_id` es clave foránea a
`cash_entries`, así que tampoco se puede referenciar un cobro que no ocurrió.

El eje operativo y el económico están separados y se leen aparte: una compostura
puede estar `LISTO` y sin cobrar, y una cobrada puede seguir sin entregar. Se
rechaza vincular un segundo cobro distinto: eso duplicaría el importe.

---

## Sucursal

La decide **la caja**, no la persona. Se delega en `effective_branch` de
V1-019B, que ya es la autoridad canónica; acá no se re-decide nada ni se corrige
en silencio. Asunción y Pilar quedan diferenciadas y no se contaminan: hay
prueba de que una operadora de Asunción atendiendo en la caja de Pilar registra
en Pilar.

---

## UI

Pestaña **Composturas**, en su propio módulo (`ui/service_jobs_panel.py`), como
FactuFácil y por la misma razón: `CajaDiaria.py` ya tiene seis mil líneas. El
enganche en la pantalla grande son once líneas.

Abre en **«Listos para entregar»**, que es la pregunta que el mostrador hace
veinte veces por día. Vistas: Listos, Pendientes, En taller, Entregados,
Anulados, Todos, más «solo mi sucursal» y filtro por responsable y por fecha.

Acciones: Nuevo, Enviar a taller, Marcar listo, Entregar, Responsable, Ver
historial, Anular. Se habilita **sólo lo que el trabajo admite de verdad**, y el
permitido sale de `allowed_transitions()`: si mañana cambia una regla, la
pantalla la sigue sola y no queda ofreciendo un botón que después falla. Cuando
enviar a taller es en realidad reabrir, el botón lo dice antes de apretarlo.

El alta no pregunta sucursal ni quién recibe: las dos salen de la caja y de la
sesión. Volver a preguntarlas sería pedirle a la operadora que confirme lo que
el sistema ya sabe, y abrir la puerta a que se conteste distinto.

Chips de estado con los mismos colores que Pedidos. Que `LISTO` sea del mismo
azul en las dos pantallas no es cosmética: es lo que permite leerlas sin
releerlas.

---

## Sesión

Se aprovecha la identidad de V1-019B. No se reimplementó autenticación y no se
cambió la política de sesiones. `actor` y `sucursal` llegan al panel como
funciones y no como texto, porque la operadora puede cambiar sin cerrar la
ventana: se registra a la que está ahora, no a la que estaba cuando se construyó
la pestaña. **No hay operación anónima**: sin actor, se rechaza.

---

## Pruebas

**88 dirigidas** (77 de dominio/servicio/persistencia + 11 de UI).
**Suite completa: 1288 verdes, 0 rojas.**

El invariante crítico se prueba de tres maneras distintas, que es a propósito:

1. **Por conteo**, para Hilo, Tornillo, Plaqueta y Compostura, contando
   `stock_movements` *después de cada paso* del ciclo —crear, enviar a taller,
   marcar listo, entregar, anular— y no sólo al final: un movimiento que se
   creara y se revirtiera también sería un movimiento.
2. **Por estructura**: ningún artículo, ningún `domain_event`, ningún
   `event_effect`.
3. **Por imposibilidad**: los tres archivos del módulo no importan
   `modulos.comercial` ni nombran `stock_movements`. No puede mover stock porque
   no sabe quién lo mueve. Aunque alguien escriba mañana un camino nuevo, no
   tiene con qué.

Y una foto antes/después de nueve tablas —`cash_days`, `cash_entries`,
`cash_counts`, `orders`, `sale_items`, `stock_movements`, `articles`,
`tracked_works`, `domain_events`— sobre el ciclo completo incluida una anulación
con compensación: idénticas.

---

## Lo que encontró la revisión

Tres defectos reales, corregidos antes del commit, cada uno con su prueba. Están
en `FINDINGS.json`. El primero era el más serio: el trabajo y su comisión se
guardaban en dos transacciones seguidas, y un corte en el medio dejaba un
trabajo que decía haber devengado y una comisión que no existía. Ahora van
juntos, y hay una prueba que simula la falla y verifica que el trabajo tampoco
avanza.

---

## No se hizo, a propósito

- No se aplicó nada en la Óptica. Ni 029, ni 030, ni la 031.
- No se cargaron personas reales ni políticas de comisión reales.
- No se tocó `main` ni se mergeó nada.
- No se tocó Telegram, Gestión Central ni la comisión del 1%.
