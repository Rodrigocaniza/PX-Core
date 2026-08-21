# BC-OPTICA-LOGIN-OPERADORA-V1-019B

Ahora alguien entra a BC Caja, y lo que hace queda a su nombre. Antes quien
operaba salía de una variable de entorno, así que casi todo lo que se registraba
decía «Operadora» — o, en el arqueo de apertura, «Caja PC», que no es nadie.

## Sin migración

**La 030 alcanzaba.** `admin_users` ya tenía usuario, nombre, rol, sucursal,
estado y credenciales; la sesión vive en memoria, que es donde corresponde. Se
verificó que 030 sigue siendo la última y no se creó una 031 por costumbre.

## El modelo de sesión, y por qué son dos

| | dura | para qué |
|---|---|---|
| `AdminSession` | **20 minutos** | el panel: cosas que se hacen una vez y con cuidado |
| `CashSession` | **hasta el fin del día** | la jornada de quien atiende |

Los 20 minutos están bien para lo que protegen y mal para una jornada: pedirle
la contraseña cada veinte minutos a alguien que atiende ocho horas termina con la
contraseña anotada en un papel al lado de la pantalla. No se cambió ese valor:
se agregó una sesión distinta al lado.

La de caja **vence a la medianoche**. No es un número elegido a ojo: es el límite
natural del turno. Se abre a la mañana, se trabaja, y no sobrevive a la noche.

**Entrar a atender no deja abierta una sesión administrativa.** Si la dejara, una
administradora que atiende tendría el panel disponible toda la tarde sin volver a
identificarse. Su token de caja no autoriza nada sensible — hay una prueba por
cada operación administrativa.

## Reautenticación, sin escalación insegura

De ahí sale sola la respuesta a las acciones sensibles: **la sesión de caja nunca
autoriza lo administrativo**, ni siquiera la de una administradora. Para eso hay
que identificarse de nuevo en el panel, que es lo que ya hacía.

Si una operadora intenta algo de administradora, el backend deniega y queda
`ADMIN_DENIED`. Si hace falta autorizar, **una administradora entra con su propia
contraseña** y obtiene su propia sesión corta. Nadie comparte contraseñas y nadie
hereda permisos.

## Login, logout, relevo

Cuatro cosas en pantalla: usuario, contraseña, Entrar. Nada técnico.

**Si se cancela el login, la ventana se cierra.** Dejarla usable «sin sesión»
sería volver a la operación anónima que esta misión vino a terminar, y encima con
la ilusión de que hay control. Vale igual al cerrar sesión.

**Cambiar operadora** está en la barra superior, no adentro de Admin: es una
acción de todos los días. El relevo **no toca la caja ni el arqueo** — el arqueo
pertenece a la caja y a la sucursal, no a quien está parada adelante. Hay una
prueba que compara los totales del día antes y después del cambio. Y si el relevo
falla por contraseña, la que estaba sigue adentro.

Desactivar a alguien la saca de la caja **aunque ya estuviera adentro**: la
sesión se revalida contra la base en cada uso, no sólo al entrar.

## Identidad operativa

La sesión trae `user_id`, `username`, `display_name`, `role`, `branch` y token.
`responsable_actual()` sale de ahí, y con eso todo lo que ya registraba
responsable —seguimiento, pedidos, novedades, arqueo de apertura— pasa a decir
quién fue de verdad. No se agregó ni una pregunta nueva: se dejó de preguntar lo
que la sesión ya sabía.

## Vendedora

Por defecto vende quien está operando. Se puede elegir a otra persona **activa
del catálogo** —pasa que una administrativa cargue la venta que hizo otra chica—
y en ese caso queda `SALESWOMAN_OVERRIDE` con quién cargó y quién vendió. Elegir
a la misma persona no genera ruido.

`cash_entries.saleswoman` **sigue siendo texto y sigue sin ser foreign key**. Hay
prueba de las dos cosas: cambiar el `display_name` de una persona no reescribe
sus ventas anteriores.

## Sucursal

La fuente canónica es **la caja**, vía `cash_register_branches`. El `branch` del
usuario es su ámbito habitual, no una autorización.

Cuando no coinciden —Leti figura en Asunción y está operando la caja de Pilar—
**no se corrige en silencio**: manda la caja, y el chip muestra un aviso. Cuál de
los dos datos está mal no lo puede decidir el sistema. Quien no tiene sucursal
fija, como quien administra, no genera discrepancia.

## UI

En la barra superior: `Operando: Leti · ASUNCION`, con **Cambiar operadora** y
**Salir** al lado.

## Auditoría

`CASH_LOGIN_SUCCESS`, `CASH_LOGOUT`, `CASH_OPERATOR_CHANGED` —con quién salió y
quién entró—, `CASH_SESSION_EXPIRED` y `SALESWOMAN_OVERRIDE`. El login fallido ya
se registraba como `ADMIN_LOGIN`/`FAIL` por el camino que valida credenciales, y
no se duplicó con un evento equivalente.

## Lo que no se tocó

No se construyó autenticación nueva: PBKDF2, sal, 390.000 iteraciones y bloqueo
exponencial son los que ya estaban, y hay una prueba de que el bloqueo sigue
vigente al entrar por el camino nuevo.

Una prueba compara quince tablas —caja, ventas, pagos, movimientos, stock,
artículos, `sale_items`, FactuFácil, Seguimiento, laboratorios, pedidos,
arqueos— antes y después de un ciclo completo de login, override, relevo, logout
e intento fallido. Ninguna cambia. **Autenticar no puede mover un guaraní.**

## Pruebas

46 dirigidas nuevas, verdes. Suite de Caja: 828. Repo: **1200 verdes, ninguna
roja**, en dos corridas seguidas.

## Estado

No requiere migración ni apply productivo. Entra con el próximo empaquetado,
junto con V1-017 y V1-018. Sigue pendiente para la Óptica el **029 → 030** de
V1-016 y V1-019A, que esta misión necesita para funcionar allá.
