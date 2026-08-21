# BC-OPTICA-USUARIOS-ROLES-V1-019

La lista de personas ya existía a medias y en dos lugares. Lo que faltaba era que
se pudiera administrar, que el rol significara algo, y que la vendedora de cada
venta dejara de salir de cuatro nombres cableados en la pantalla.

## Lo que había, antes de crear nada

| | |
|---|---|
| `admin_users` | **credenciales reales**: PBKDF2-SHA256 con sal, 390.000 iteraciones, bloqueo exponencial por intentos, sesiones con vencimiento a 20 minutos y login auditado. Y una columna `role` con `DEFAULT 'ADMIN'` que **nadie leía**. |
| `authorized_responsibles` | creada por la 015 y **nunca usada por una sola línea de código**. Tabla muerta. |
| identidad de la operadora | no hay login: es `BC_CAJA_RESPONSABLE` / `USERNAME` / `"Operadora"`. |
| lista de vendedoras | **cableada en la pantalla**: `"Ana", "Belén", "Carla", "Diana"`. |

Eso último es lo más serio de todo el hallazgo. Cuatro nombres de maqueta
estuvieron eligiendo la vendedora de cada venta real de la Óptica.

**No se creó una tercera lista.** `admin_users` ya era la tabla de usuarios y
roles; sólo le faltaba cómo se llama la persona, dónde trabaja y quién la cargó.

## Modelo

Migración **030** —verificada contra el repo, la última aplicada era la 029—
agrega a `admin_users`: `display_name`, `branch`, `created_by`, `updated_by`. Y
le pone `display_name = username` al administrador que ya existía, para que nadie
tenga que actualizar nada a mano.

No relaja `password_hash`, `salt` ni `iterations`. Una persona **sin credencial**
se guarda con el hash vacío, y un hash vacío no puede coincidir con ningún
PBKDF2: existe para tener rol y para ser nombrada en una venta, pero no puede
entrar. Ésa es exactamente la línea entre este slice y el login de operadora.

## Roles

Dos, derivados de lo que la Óptica hace: **OPERADOR** (Operadora) y **ADMIN**
(Administradora). No se inventó un RBAC: dos alcanzan, y un tercero tendría
sentido el día que exista una responsabilidad que hoy no existe. `role` ya traía
`DEFAULT 'ADMIN'`, así que quien hoy entra al panel sigue entrando.

## Usuario ≠ vendedora

Son dos columnas y dos conceptos:

- `username` es con lo que se entra.
- `display_name` es cómo se la nombra en una venta.
- `cash_entries.saleswoman` sigue siendo **texto**, y **sigue sin ser foreign
  key a propósito**. Hay una prueba que lo verifica: si lo fuera, corregir el
  nombre de una persona reescribiría agosto.

Una administrativa puede estar en la caja y registrar correctamente que la venta
la hizo otra. El modelo ya lo permitía y se conserva.

## Permisos, en el backend

`require()` sólo comprobaba que hubiera sesión. Como todos los usuarios eran
ADMIN por defecto, tener sesión y ser administradora eran lo mismo — desde que
hay dos roles dejan de serlo.

Se agregó `require_admin()`, y lo sensible pasó a usarlo: usuarios, auditoría,
configuración, secreto de correo, importaciones, y la autorización de una
diferencia de arqueo por encima del límite. Un intento denegado queda registrado
como `ADMIN_DENIED`.

Hay siete pruebas que llaman al servicio **directamente con el token de una
operadora**, sin pasar por ninguna pantalla. Es la única forma de comprobar que
el permiso no depende de esconder un botón.

## UI

La pestaña «Usuarios y permisos» del panel de Administrador era un cartel
estático. Ahora tiene la lista real —nombre, usuario, rol, sucursal, estado, si
puede entrar— y tres acciones: **Nueva persona**, **Editar**, **Activar /
desactivar**. Las inactivas se ven en gris; no hay ningún botón de borrar, y
tampoco existe el método.

Y el desplegable de vendedora lee el catálogo. Si todavía no hay nadie cargado
queda editable y la operadora escribe el nombre: se degrada a lo que había antes
del catálogo en vez de dejar la caja sin poder vender el día de la actualización.

## Desactivar, nunca borrar

Una venta de agosto guarda el nombre de quien la hizo. Borrar a la persona
dejaría ese nombre sin nadie detrás, y reusar el `id` haría que la historia
apunte a otra. Desactivar deja las dos cosas en su lugar: sale de la lista de
vendedoras y no puede entrar, y sigue apareciendo en lo que ya hizo.

Un candado que agregué: **no se puede desactivar a la última administradora que
puede entrar**. Sin él, la Óptica se quedaba afuera del panel sin forma de
volver. Y tener el rol no alcanza: hay que poder entrar, o nombrar a alguien sin
contraseña serviría para saltar el candado.

## Auditoría

`USER_CREATED`, `USER_UPDATED`, `USER_DEACTIVATED`, `USER_ACTIVATED`,
`USER_PASSWORD_SET` y `ADMIN_DENIED`, cada uno con actor, timestamp y detalle —
en el cambio de rol, el anterior y el nuevo. Nada se reescribe. Y hay una prueba
que vuelca la tabla entera y la bitácora buscando la contraseña en texto plano:
no está en ninguna de las dos.

## Autenticación: lo que existe y lo que no

**Existe y es seria**, pero sólo para el panel de Administrador. Para la caja no
hay login: quien opera es una variable de entorno.

Este slice es el **V1-019A** del planteo: catálogo, roles, estado, auditoría y
permisos. El login de operadora —**V1-019B**— queda fuera, y el modelo ya está
listo para recibirlo: alcanza con darle contraseña a quien la necesite.

## Pruebas

38 dirigidas nuevas, verdes. Cubren los 19 casos pedidos y algunos más.

Suite de Caja: **784 verdes**. Repo completo: **1154 verdes, ninguna roja**, en
dos corridas seguidas.

## Migración

**Sí, la 030.** Aditiva: cuatro columnas, ninguna tabla nueva, ningún dato de
operación tocado. Probada sobre una base local en estado 029 con dos días de
caja, cinco ventas y una administradora: 29 → 30 migraciones, exactamente cuatro
columnas nuevas, el administrador conserva su rol y gana nombre, e idempotente.

**Esto no es validación contra producción.** La base es local.

## Invariantes

Hay una prueba que compara diez tablas —caja, ventas, movimientos, stock,
artículos, FactuFácil, Seguimiento, laboratorios, pedidos— antes y después de
crear, editar y desactivar usuarios. Ninguna cambia.

## Estado

`READY_FOR_PRODUCTIVE_APPLY_AT_OPTICA` por la migración 030, con backup
verificable, pre-guards, rollback y post-checks.
