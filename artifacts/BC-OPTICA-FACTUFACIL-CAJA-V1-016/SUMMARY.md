# BC-OPTICA-FACTUFACIL-CAJA-V1-016

La chica que atiende ya no tiene que preguntar cuáles ventas faltan cargar en
FactuFácil. Le aparecen en una pestaña de BC Caja, con los datos listos para
copiar y un botón para decir que ya está.

## El problema, dicho como es

FactuFácil es un sistema externo y no tiene integración oficial. La carga la
hace una persona, a mano, y va a seguir haciéndola. Lo que faltaba no era
automatizar eso —no se puede— sino que la operadora **supiera cuáles le faltan**
sin entrar a la consola administrativa de Sol ni preguntarle a nadie.

## Lo que ya existía, y qué se reusó

`BC-GESTION-CENTRAL-FACTUFACIL-BANDEJA-001` (rama `mission/…`, 15/08) ya había
construido una bandeja FactuFácil **en Gestión Central**. Sirve, y su contrato se
respetó — pero no resuelve esto, por dos razones que están en su propio código:

- vive en `modulos/gestion_central/`, que es exactamente la consola a la que la
  operadora no debe entrar;
- su servicio hace `raise AccessDenied("operador local sin acceso a FactuFácil")`.
  El rol de la chica del mostrador está explícitamente excluido.

Además se alimenta del circuito de revisión —un snapshot que se importa— y no de
la caja del día. Para el mostrador llegaría tarde.

Lo que **sí** se reusó:

- el **orden de los campos** del contrato v1, para que copiar desde Caja y copiar
  desde Gestión Central den lo mismo;
- los nombres de estado `PARA_CARGAR` / `CARGADA`;
- el hallazgo de `real_sync.py`, donde el campo `factufacil_status` viajaba a
  Gestión Central con el valor literal `"NO DISPONIBLE PILOTO"`. Ahora hay un
  estado real que ese puente podrá leer, cuando alguien decida conectarlo.

## Modelo: lo que NO se creó

**No hay tabla de ventas de FactuFácil.** La venta ya está en `cash_entries` con
el cliente, el sobre, la vendedora, el importe, el CI/RUC, el teléfono y las
observaciones. Copiarla sería cargar el mismo hecho dos veces, y el día que se
corrija en Caja la copia quedaría mintiendo.

**«PARA CARGAR» tampoco se guarda: se deduce.** Es una consulta, no un estado que
alguien tenga que mantener al día.

Lo único que no se puede deducir de ningún lado es que una persona entró a
FactuFácil y la cargó. Eso, y sólo eso, guarda la migración **029**: dos tablas
—`factufacil_loads` y `factufacil_history`— que no tocan ninguna existente.

## La regla de PARA CARGAR

Está escrita en un solo lugar y probada:

> venta activa · que no sea gasto ni entrega a administración · con importe · sin
> marca de cargada

- **anulada** → fuera. Si se anula después de cargarla, sale de las dos listas y
  su historia queda.
- **gasto / entrega a administración** → no son ventas: no tienen cliente ni
  sobre que facturar.
- **importe cero** → es la única línea que es política y no un hecho del modelo:
  sin importe no hay nada que facturar. Separa un borrador de una venta.

## La pantalla

Pestaña `FactuFácil`, al lado de Seguimiento. Dos chips con el conteo vivo:
**PARA CARGAR (n)** y **CARGADA (n)**. Una grilla con estado, fecha, sucursal,
sobre, cliente, CI/RUC, teléfono, vendedora, total y quién la cargó.

Las **observaciones no van en la grilla**: son dos renglones de graduación por
ojo y ahí no entran. Van completas, abajo, en su propio recuadro, y cambian al
elegir una fila. No se cortan nunca.

Tres botones grandes, y sólo se habilita el que corresponde a lo elegido:
**Copiar datos**, **Marcar como cargada**, **Volver a Para cargar**. Filtros en
una línea: desde, hasta, sucursal, sobre, cliente, vendedora, más un atajo
«Hoy» que resuelve el caso de todos los días. Ningún código interno llega a la
pantalla — hay una prueba que lo verifica.

## Las tres acciones

**Copiar** deja los datos en el portapapeles, un campo por línea y en el orden
del contrato. FactuFácil se carga campo por campo en un formulario web: no hay
import ni pegar-todo, así que una línea por campo es lo que se puede ir copiando
de a pedazos. Copiar no escribe nada: ni la marca, ni la venta, ni la historia.

**Marcar como cargada** guarda quién y cuándo. Marcar dos veces devuelve «ya
estaba» y **no reescribe quién hizo el trabajo**: un doble clic, o dos personas a
la vez, no pueden robarle la firma a la primera.

**Volver a Para cargar** exige motivo. Cancelar el diálogo y dejarlo vacío son lo
mismo: no se revierte. La marca vigente se limpia, pero la historia queda entera
— sigue diciendo que rosa la había cargado, y por qué volvió.

## Un aviso que no estaba pedido, y que hacía falta

Si alguien corrige la venta **después** de cargarla en FactuFácil, lo que se
cargó allá deja de coincidir con lo que dice Caja. Sin nada, eso se descubre al
cerrar el mes.

La marca guarda en qué revisión de la venta se hizo. Cuando dejan de coincidir,
la fila se pinta y arriba dice cuántas se editaron después de cargarse. **No es
un estado nuevo, no bloquea nada, y no convierte esto en Gestión Central**: es
que la información esté antes y no después.

## Lo que no cambia

Marcar una venta en FactuFácil no toca la caja del día. Ni el total, ni el
efectivo, ni la cantidad de entradas, ni la revisión de la venta. Son dos hechos
distintos y el cierre económico no se entera de este — por eso la marca vive en
su propia tabla y no en una columna de `cash_entries`.

## Probado desde Casa, sin producción

Se armó una base local **en el estado 028** —el que hay hoy en la Óptica— con dos
días de caja, cinco ventas, un gasto y una anulada. Sobre ella:

- la migración 029 sube de 28 a 29, crea exactamente dos tablas y ninguna otra;
- días, entradas, importes, `sale_items`, artículos y movimientos, sin cambio;
- las tablas nuevas nacen vacías: no se inventó una sola marca;
- volver a migrar no cambia nada;
- el circuito completo —listar, copiar, marcar, filtrar, revertir, reiniciar—
  termina con la caja del día idéntica a como entró.

**Esto no es validación contra producción.** La base es local y no tiene los
datos de la Óptica. Lo que prueba es que el upgrade y el flujo funcionan sobre
una base con esa forma.

## Pruebas

43 dirigidas nuevas: 30 del servicio y 13 de la pestaña, manejada como la maneja
la operadora. Cubren los 17 casos pedidos y algunos más: anular después de
cargar, marcar sin responsable, filtros combinados, y que ningún id de base
llegue a una celda.

Suite de Caja completa: **701 verdes, ninguna roja**. Repo: 1069 verdes y las 2
rojas de Gestión Central ya clasificadas `PREEXISTING_OUT_OF_SCOPE` en V1-015.

Una prueba de RC15 cambió, y está dicho por qué: afirmaba que la palabra
«FactuFácil» no aparecía en toda la pantalla de Caja. Servía cuando FactuFácil no
existía ahí. Ahora tiene su pestaña, así que la prueba comprueba lo mismo de
antes —que la apertura del día y FactuFácil no se mezclen— de la manera que
todavía tiene sentido.

## Estado

`READY_FOR_PRODUCTIVE_APPLY_AT_OPTICA`, sólo por la migración 029. La herramienta
va con backup verificable, pre-guards, rollback y post-checks.
