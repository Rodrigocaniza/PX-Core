# INSTALL_GATE-RC15-001 — el único gate que quedó, y no se pudo consolidar

**Estado:** `AWAITING_INSTALL_AUTHORIZATION`.
La RC está construida, empaquetada, hasheada y con backup y rollback listos.
**No se instaló.**

## Por qué esto no entraba en la sesión de validación consolidada

Los dos gates humanos que pasaron (`HUMAN_GATE-APERTURA-CAJA-001` y
`HUMAN_GATE-PEDIDOS-002`) validaron **Apertura y Pedidos**. La instalación resultó ser
más grande que eso, y eso se descubrió recién al preparar el paquete:

| | |
| --- | --- |
| Versión **instalada** en esta PC | **BC Caja 1.0.0-rc.11** (`%LOCALAPPDATA%\Programs\BC-Caja-Pilot`, VERSION.txt) |
| Último backup previo existente | `bc-caja-pre-1.0.0-rc.11`, del 14/08/2026 |
| Último paquete en `releases/` | `BC-CAJA-1.0.0-rc.11-win64.zip` |
| Migraciones en la base productiva | **14** |
| Versión que instalaría esta RC | **1.0.0-rc.15**, con **15** migraciones |

Es decir: **rc.12, rc.13 y rc.14 nunca se instalaron acá**. Instalar rc.15 no es el salto
de una versión que se validó: promueve a producción, de una sola vez, cuatro líneas de
release.

## Qué entraría a producción además de Apertura y Pedidos

- **rc.12** — arqueo de caja integrado en Caja diaria.
- **rc.13** — administrador protegido y arqueos de cierre por correo (agrega la migración
  **015**, que **no tiene inversa**).
- **rc.14** — recuperación durable de notificaciones de cierre creadas antes de configurar
  el correo.
- Outbox de sincronización y el piloto de Gestión Central.

En el gate de Pedidos se verificó que `Arqueo`, `Administrador` y el cierre por correo
**funcionan** — pero sobre una base de prueba vacía, no sobre los datos reales de la
Óptica, y sin correo real configurado.

## Riesgo concreto

1. La migración **015** se aplica sobre la base real en el primer arranque y **no se puede
   deshacer**: volver atrás exige restaurar el backup, y se pierde lo cargado después.
2. rc.13 introduce **credenciales de administrador** y **envío de correo**. Si el correo
   queda mal configurado, el cierre del día puede comportarse distinto de lo que la chica
   espera. Eso no lo cubre ningún gate pasado.
3. La Óptica salta de una UI conocida (rc.11) a otra con arqueo obligatorio en apertura y
   cierre. Es un cambio de rutina operativa, no sólo visual.

## Lo que sí está listo y verificado

- Backup previo hecho y con sha256 idéntico al original.
- Rollback documentado y ejecutable (`ROLLBACK.md`).
- Paquete construido, con `zip_sha256` y `exe_sha256`, y el ejecutable probado: arranca y
  aplica las 15 migraciones sobre una base temporal.
- 253 pruebas + 4 subpruebas y 7 capturas fail-closed sobre la RC combinada.

## Decisión que hace falta

Una de estas tres:

- **A — Instalar rc.15 completo.** Asumiendo que rc.12/13/14 entran a producción ahora.
  Conviene hacerlo con la caja del día cerrada.
- **B — Instalar y validar rc.12/13/14 primero** en una sesión aparte (arqueo real, admin
  real, correo real) y recién después rc.15.
- **C — No instalar todavía.** La RC queda empaquetada y lista; se instala otro día.

Sin esa decisión no se toca la instalación de la Óptica.
