# INSTALL_EVIDENCE — BC Caja 1.0.0-rc.31 instalada en la Óptica

**Instalación ejecutada y validada. 100% PASS. Sin pérdida de datos, sin rollback necesario.**

Equipo: PC de la Óptica (`C:\Users\Striker`). Stamp de la operación: `20260818-123848`.
Fecha: 18-08-2026.

## 0. Verificación del punto de partida

| Comprobación | Esperado | Encontrado |
| --- | --- | --- |
| `VERSION.txt` vigente | `BC Caja 1.0.0-rc.30` | `BC Caja 1.0.0-rc.30` ✅ |
| Backup preinstall de rc.30 | presente | `bc-caja-preinstall-1.0.0-rc.30-20260817-181556-179677.sqlite3` ✅ |
| `gh auth status` | autenticado | cuenta `Rodrigocaniza`, scopes `repo` ✅ |
| Procesos `BC-Caja` | ninguno | ninguno ✅ |
| `startup-error.log` previo | no existe | no existe ✅ |

Esta máquina **sí** es el destino: tiene rc.30 instalada y su backup preinstall. La serie de
rollbacks local (`previous-rc5` … `previous-rc15`) es distinta a la del equipo de casa
(`rollback-rc26-20260816h`), lo que confirma que son dos equipos diferentes.

### Línea base de la DB productiva, antes de tocar nada

```
sha256            1c4fcc406904fe3eebc62e209a56c4e273192a27912331a43dbd0e4d9fde98ec
bytes             413696
integrity_check   ok
foreign_key_check 0 violaciones
schema_migrations 21 (001-021)
cash_days 2 · cash_entries 12 · orders 8 · sale_items 10 · cash_entry_revisions 22
cash_entries.total 6.400.000
mail_outbox 0 · mail_history 0
```

## 1. Recuperación del artefacto — NO se reconstruyó

Descargado del release privado, no rebuildeado:

```
gh release download bc-caja-1.0.0-rc.31 --repo Rodrigocaniza/PX-Core-releases \
  --pattern BC-CAJA-1.0.0-rc.31-win64.zip
```

| | Esperado | Obtenido | |
| --- | --- | --- | --- |
| bytes del zip | 34 111 433 | 34 111 433 | ✅ |
| sha256 del zip | `95e9148a…c2948` | `95e9148a2c712ccb6622f2fb89cc0dcc4e7547c002308ba532988217f95c2948` | ✅ |
| sha256 del exe | `62e8f1d8…2152f` | `62e8f1d87206b31b428892dc60266dde3394ef30a8b530b41f53563fe892152f` | ✅ |
| `VERSION.txt` del paquete | rc.31 | `BC Caja 1.0.0-rc.31` | ✅ |

El exe se verificó **extraído en temporal, antes de mover nada** de la instalación vigente.

## 2. Backup productivo preinstall, con hash verificado

```
C:\Users\Striker\AppData\Local\BC\Caja\Backups\bc-caja-preinstall-1.0.0-rc.31-20260818-123848.sqlite3
hash origen  1c4fcc406904fe3eebc62e209a56c4e273192a27912331a43dbd0e4d9fde98ec
hash backup  1c4fcc406904fe3eebc62e209a56c4e273192a27912331a43dbd0e4d9fde98ec   BACKUP_OK ✅
```

## 3. Rollback verificable, apartado antes de instalar

```
C:\Users\Striker\AppData\Local\Programs\BC-Caja-Pilot.rollback-rc30-20260818-123848
VERSION.txt        BC Caja 1.0.0-rc.30                                             ✅
exe sha256         a38262a540ef59ea6be02ccb6a2db20242dfd791c11c79bc79c1cbadac52adc2
                   idéntico al de la instalación original                          ✅
archivos           1136 copiados vs 1136 originales                                ✅
```

No se borró nada: rc.30 quedó además apartada entera como
`BC-Caja-Pilot.replaced-rc30-20260818-123848`. Hay dos copias independientes de rc.30.

## 4. Instalación transaccional

`Move-Item` de la vigente a `.replaced-rc30-<stamp>`, luego `Move-Item` del staging a su lugar.
En ningún momento hubo un estado con la instalación borrada y la nueva sin poner.

```
VERSION.txt instalado   BC Caja 1.0.0-rc.31                                        ✅
exe instalado sha256    62e8f1d87206b31b428892dc60266dde3394ef30a8b530b41f53563fe892152f
                        coincide con el hash canónico del MANIFEST                 ✅
```

## 5. Apertura y smoke sobre datos reales

Arrancó a la primera. Ventana `Caja diaria - Óptica`, barra de estado
`BC Caja 1.0.0-rc.31 · Datos: C:\Users\Striker\AppData\Local\BC\Caja`.

| Pantalla | Resultado | Evidencia |
| --- | --- | --- |
| Caja diaria | 3 pasos, VENTA EN CURSO, SALIDA DE CAJA, Movimientos del día, `Trabajos 7`, sucursal PC | `install-rc31-caja-1920x1080.png` |
| **Pedidos** | slice rc.31 completo: `Requieren atención · Hoy · Atrasados · Próximos · Todos`, `Más ▾`, `Contactar`, `Acción siguiente`, agrupación `ATRASADOS · 7` / `PARA HOY · 0`, columnas Cliente/Sobre/Trabajo/Laboratorio/Estado/Atraso/Última novedad, y **el resaltado de navegación queda en Pedidos** — el punto 10 del gate, verificado en producción | `install-rc31-pedidos-1920x1080.png` |
| Seguimiento | contadores Atrasados/Por recibir/En laboratorio/Confirmados/Listos p/Pilar/En tránsito, `+ Nuevo envío desde Pilar`, filtro por laboratorio, `Sucursal: ASUNCION` | `install-rc31-seguimiento-1920x1080.png` |
| Laboratorios | ABM abre y cierra; vacío, consistente con `laboratories = 0` | `install-rc31-laboratorios-1920x1080.png` |
| Historial | rango de fechas + `Este mes / 7 días / Hoy`; consulta real devuelve las 2 jornadas | `install-rc31-historial-1920x1080.png` |

El modal `Configuración inicial administrativa` aparece al abrir porque `admin_users = 0`.
Ya era así bajo rc.30 (la línea base lo registra): **no es una regresión de rc.31**, y no se
configuró credencial alguna — es una decisión del dueño, no del instalador.

Cierre limpio por `CloseMainWindow`. **0 procesos residuales. Sin `startup-error.log`.**

## 6. Validación post-install contra el backup del paso 2

```
integrity_check       ok                                    ✅
foreign_key_check     0 violaciones                         ✅
schema_migrations     21, pre 21 — 0 nuevas, 0 perdidas     ✅
DIFF filas por tabla  SIN CAMBIOS                           ✅
DIFF montos           SIN CAMBIOS                           ✅
cash_entries.total    6.400.000 (idéntico)                  ✅
mail_outbox 0 · mail_history 0 — sin envíos                 ✅
sha256 pre  1c4fcc406904fe3eebc62e209a56c4e273192a27912331a43dbd0e4d9fde98ec
sha256 post 1c4fcc406904fe3eebc62e209a56c4e273192a27912331a43dbd0e4d9fde98ec
IDÉNTICO: la base productiva es byte a byte la misma                ✅
```

Los 10 puntos de validación quedaron cubiertos: `integrity_check`, `foreign_key_check`,
21 migraciones sin agregar ninguna, datos y montos sin cambios contra el backup, Pedidos,
Seguimiento, Historial, Arqueo/Caja diaria, Administrador (modal preexistente), correo y
outbox sin envíos.

### Comprobación aritmética independiente de la preservación de datos

Historial "Este mes" muestra 2 jornadas con `2.220.000 + 3.350.000` en ventas más una
venta `ANULADO` de `830.000` en el 13-08. Suman **6.400.000**, exactamente el
`SUM(cash_entries.total)` de la línea base. Los datos reales están enteros y la anulación
histórica se conserva como tal.

## 7. Rollback: no se necesitó

rc.31 no escribió una sola vez en la base durante el smoke (sha256 idéntico), así que ni
siquiera el paso 4 de `ROLLBACK.md` haría falta. El procedimiento queda armado y con sus
dos insumos presentes en disco por si apareciera un problema en uso normal:

- `…\BC\Caja\Backups\bc-caja-preinstall-1.0.0-rc.31-20260818-123848.sqlite3`
- `…\Programs\BC-Caja-Pilot.rollback-rc30-20260818-123848`

## 8. Lo que NO se tocó

- La base productiva: byte a byte idéntica.
- `main`: promovido por fast-forward desde la rama de la misión, sin `--force`.
- Otras ramas, worktrees y misiones ajenas: sin tocar.
- Credenciales de administrador: no configuradas.
- Deuda registrada (`BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001`, `CajaDiaria.py:3253`): sigue
  abierta, fuera de este slice.
