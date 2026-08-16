# Install Evidence — BC Caja 1.0.0-rc.21

## Precheck canónico

| Comprobación | Resultado |
|---|---|
| HEAD | `5b88ac5` ✓ el autorizado |
| Worktree / sync | limpio, `0/0` |
| Instancias activas | 0 |
| Versión instalada | `BC Caja 1.0.0-rc.20` |
| `integrity_check` | ok |
| Esquema | 001–017, 24 tablas |
| Mission Leases | 0 |
| Rollback RC17 | presente |

## Build

`1.0.0-rc.21` desde la rama de misión. La versión del ZIP y del paquete se
derivan de `VERSION.txt`, y `VERSION_APLICACION` la acompaña con prueba que
verifica que no diverjan.

| Item | Valor |
|---|---|
| ZIP | `BC-CAJA-1.0.0-rc.21-win64.zip`, 34.045.135 bytes |
| SHA256 ZIP | `4A3D7AF2D58C0330B6C101991448749CE0496509F5DCCAD3DFDA2D598AB53A1D` |
| SHA256 EXE | `DA2ACD23C0063F84A462C64620F792C52157F24FC6EE468B22BFC1476A2F5878` |

**Recuperación automática aplicada**: la compresión falló por acceso denegado
a `_internal/base_library.zip`, que PyInstaller deja tomado un instante al
terminar. Ya había ocurrido en rc.20 y se resolvió a mano; ahora el script
reintenta hasta cinco veces con espera, de modo que el build deja de depender
de esa carrera. El segundo intento completó sin intervención.

Regresión con la versión ya bumpeada: **370 PASS / 0 FAIL**.

## Backup y rollback

- Data root → `%LOCALAPPDATA%\BC\Caja-RC21-preinstall-20260816b`
  (33 archivos, la copia abre con `integrity_check=ok`).
- Versión vigente → `BC-Caja-Pilot.rollback-rc20-20260816b`.
- Preservados: `rollback-rc17-20260816`, `rollback-rc16-20260815`,
  `rollback-rc15-20260815`, las copias `replaced-*` y todos los backups.

## Instalación

Reemplazo transaccional: extracción a staging, verificación de versión antes
de tocar nada, carpeta vigente apartada en lugar de borrada y restauración
inmediata si el reemplazo falla. Solo se reemplazó la carpeta del programa.

## Post-install

| Comprobación | Resultado |
|---|---|
| Versión instalada | `BC Caja 1.0.0-rc.21` |
| Arranque | La aplicación abre y sostiene la ventana |
| Versión en el pie | `BC Caja 1.0.0-rc.21` |
| Migraciones | 001–017, **sin migraciones nuevas** |
| `integrity_check` | ok |
| Datos | **Ninguna diferencia** contra el precheck en las 24 tablas |
| Cierres | 2, iguales → cero cierres nuevos |
| Correo | `outbox=1`, `SENT=1`, `mail_history=5`, iguales → cero correos |
| Configuración | `branch`, `counting`, `mail`, `tracking` preservadas; SMTP intacto |

## Límite declarado

No se pudo **conducir** la interfaz del ejecutable congelado para abrir la
pestaña Seguimiento. Se intentaron dos vías: mensajes sintéticos de ventana y
clic real con la ventana forzada al frente. Ninguna prospera porque los
controles de CustomTkinter se dibujan sobre canvas y no exponen handles
nativos.

En consecuencia, sobre el binario instalado quedan verificados el arranque, la
versión, el esquema, la integridad y la preservación de datos; la tabla nueva
está verificada por la suite y por el smoke GUI real sobre el mismo commit
—`5b88ac5`, el que se empaquetó— en 1920×1080 y 1366×768.

Comprobación visual pendiente, de un minuto: abrir *Seguimiento* y confirmar
las cinco columnas y los chips de estado.

## Rollback

**No utilizado.** Disponibles rc.20, rc.17, rc.16 y rc.15, más el snapshot de
datos previo a esta instalación.
