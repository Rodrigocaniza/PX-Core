# Install Evidence — BC Caja 1.0.0-rc.24

Instalación autorizada de la versión consolidada de las Misiones 1, 2 y 3.

## Precheck

| Comprobación | Resultado |
|---|---|
| HEAD | `893792c` ✓ el autorizado (`dfd1514 → ad9cd4e → 893792c`) |
| Worktree / sync | limpio, `0/0` contra `origin` |
| Instancias de BC Caja | **0** (revalidado inmediatamente antes del reemplazo) |
| Versión instalada | `BC Caja 1.0.0-rc.23` |
| Programa | `%LOCALAPPDATA%\Programs\BC-Caja-Pilot` |
| Data root | `%LOCALAPPDATA%\BC\Caja` (1 archivo, 401.408 bytes) |
| `integrity_check` | ok |
| `foreign_key_check` | ok |
| Esquema | 001–018, 24 tablas |
| Bindings previos | `P2 → PILAR`, `PC → ASUNCION`, `PILAR → PILAR` |
| Mission Leases | **0** (`.git/command-center/mission-execution-leases` vacío) |
| Rollbacks previos | rc.22, rc.21, rc.20, rc.17, rc.16, rc.15 |
| Backups de datos previos | RC23, RC22, RC21, RC17, INTEGRATION, ESCENARIO-TEST |

`SHA256` base productiva pre-instalación:
`6AB667B4AEFB4398CF97861930CDDADD7CA361C108CB1714BDB60B070A0EC1DC`

### Artifact

| Item | Valor |
|---|---|
| ZIP | `releases/BC-CAJA-1.0.0-rc.24-win64.zip`, 34.667.832 bytes |
| SHA256 ZIP | `4C5E385774BD79F2297447C7FBC34BE3B60D864F735DC76DF5D5D1870358FB44` |
| SHA256 EXE | `A8960365EC27430E810A08E394145A90FB2F48359427C02139C47EE71102E264` |
| Entradas | 1160 |
| Migraciones en el paquete | 20, incluida `020_branch_bindings_canonicas.sql` |
| `VERSION.txt` dentro del ZIP | `BC Caja 1.0.0-rc.24` |

## Backup y rollback

- Data root → `%LOCALAPPDATA%\BC\Caja-RC24-preinstall-20260816e`
  (33 archivos; la copia abre con `integrity_check=ok`, esquema 001–018,
  `cash_entries=8`).
- Rollback rc.23 → `BC-Caja-Pilot.rollback-rc23-20260816e`, con `BC-Caja.exe`
  y `VERSION.txt` verificados.
- Carpeta vigente apartada → `BC-Caja-Pilot.replaced-rc23-20260816e`.
- Preservados: rollbacks rc.22, rc.21, rc.20, rc.17, rc.16, rc.15; todas las
  carpetas `replaced-*`; todos los backups de datos históricos.

## Instalación

Transaccional. Extracción a staging y **verificación antes de tocar nada**:
versión, presencia del ejecutable y recuento de migraciones. La carpeta
vigente se aparta en lugar de borrarse, y el reemplazo restaura la anterior si
falla. Se reemplazó **únicamente la carpeta del programa**.

```
instancias_pre_reemplazo=0
staging_version=BC Caja 1.0.0-rc.24
staging_migraciones=20
reemplazo=OK
```

## Migración 020

Aplicada en el primer arranque, junto con la 019 que rc.23 no tenía.

| Requisito | Resultado |
|---|---|
| `PC → ASUNCIÓN` | ✓ |
| `P2 → PILAR` | ✓ |
| `PILAR → PILAR` | ✓ |
| No inventa branch para cajas desconocidas | ✓ `CAJA-NUEVA` → `NULL` |

**Comprobación relevante:** los tres vínculos ya existían en producción,
asignados por `Rodrigo Cañiza`, `MIGRACION-018` y `SMOKE RC22`. Tras la
migración **conservan su `assigned_by` original**, lo que demuestra que el
`INSERT OR IGNORE` respetó las asignaciones previas en vez de pisarlas. Que la
020 siembra sobre una base nueva quedó verificado por separado, arrancando el
ejecutable empaquetado contra un directorio temporal.

## Post-install

| Comprobación | Resultado |
|---|---|
| Versión instalada | `BC Caja 1.0.0-rc.24` |
| SHA256 EXE instalado | coincide con el del paquete |
| Arranque | dos arranques, la ventana abre y se sostiene |
| Migraciones | 001–020 (nuevas: 019 y 020) |
| `integrity_check` | ok |
| `foreign_key_check` | ok |
| Correos | `outbox=1`, `history=5` — iguales → **0 nuevos** |
| Cierres | `CLOSED=3`, `closed_at≠NULL=3` — iguales → **0 nuevos** |

### Datos económicos preservados

Diff de las 24 tablas contra el backup pre-instalación, inmediatamente después
de instalar: **la única diferencia fue `schema_migrations: 18 → 20`.**
`cash_entries`, `cash_days`, `orders`, `sale_items`, `cash_counts`,
`cash_entry_revisions`, `admin_*`, `mail_*` y `app_settings` sin cambios.

Las diferencias posteriores (`tracked_works`, `tracked_work_transitions` y
`pilar_shipments` a 0) son el reinicio deliberado del escenario TEST, descrito
abajo, y no tocan ninguna tabla económica.

### Verificación funcional

| Ítem | Resultado |
|---|---|
| Tres botones principales | PASS |
| Selección múltiple | PASS |
| Observaciones visibles | PASS |
| `NO LLEGÓ` | PASS |
| `NO ESTABA EN LISTA` | PASS |
| Línea de conciliación | PASS |
| Alerta principal por sucursal | PASS |
| Agrupación compacta | PASS |
| Chips anclados | PASS |
| Sin overlays | PASS |

Evidencia en `postinstall/`:

```
1920x1080  filas=16  alerta="⚠ 4 atrasados — contactar laboratorios — clic para ver"
           conciliacion="Declarados 15 · Recibidos 12 · No llegó 2 · Extra 1"
           grupos=['En laboratorio · 13', 'Por recibir · 3']
           botones=['Acción siguiente', 'Novedad', 'Más ▾']
1366x768   idéntico, sin desborde
RC19       15 filas, sonda de chips huérfanos en verde
```

Regresión post-install **497 PASS / 0 FAIL**; focused RC25 + E2E **58 PASS**.

### Límite declarado

**La interfaz del ejecutable congelado no se puede conducir por automatización.**
Es la misma limitación declarada desde rc.21: los controles de CustomTkinter se
dibujan sobre canvas y no exponen handles nativos.

Sobre el binario instalado quedan verificados el arranque, la versión, el hash,
el esquema, la integridad, los bindings y la preservación de datos. Los diez
ítems funcionales de arriba están verificados por smoke GUI real **sobre el
mismo commit que se empaquetó** (`893792c`, árbol limpio), en 1920×1080 y
1366×768, sondando los widgets reales. Es evidencia del mismo código, no del
mismo proceso.

## Escenario TEST

Devuelto a su punto inicial con `tools/cleanup_escenario_test.py
--reset-circuito --aplicar`, que borra por id exacto del manifiesto y no por
patrón. **No se sembró ningún dato nuevo.**

| | |
|---|---|
| Pedidos TEST candidatos | 15 |
| Trabajos en circuito | 0 |
| Envíos | 0 |
| Laboratorios | LAB PRUEBA ALFA · BETA · GAMMA |
| `integrity_check` tras el reinicio | ok |

Listo para que la prueba manual arranque en el paso 1 (*Pilar envía 15*).

## Rollback

**Rollback usado: NO.**

Disponibles rc.23 (`BC-Caja-Pilot.rollback-rc23-20260816e`), rc.22, rc.21,
rc.20, rc.17, rc.16 y rc.15, más el snapshot de datos
`Caja-RC24-preinstall-20260816e`.

Para revertir: cerrar BC Caja, reemplazar la carpeta del programa por el
rollback rc.23 y, solo si hiciera falta deshacer la migración, restaurar el
data root desde el backup. No parchear producción a mano.
