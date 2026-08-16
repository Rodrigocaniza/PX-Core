# Install Evidence — BC Caja 1.0.0-rc.25

Instalación protegida del fix cerrado en `551f68c`. Reanudada desde
`INSTALLATION WAITING — BC Caja in use` tras el cierre manual de la aplicación.

## Versión

Determinada desde el versionado canónico, no asumida: `rc.24` era la instalada,
la de `VERSION.txt` y la última en `releases/`. Se verificó que **`rc.25` estaba
libre** (sin zip y sin commits previos) antes de construir.

**Sin migración nueva**: el teléfono se resuelve desde el pedido de origen, así
que el esquema permanece en `020`.

## Precheck

| Comprobación | Resultado |
|---|---|
| Instancias activas | **0** (revalidado antes del reemplazo) |
| SHA256 ZIP | `8C95…B8CF` — coincide con el autorizado |
| Tamaño / entradas / migraciones | 34.672.476 B · 1160 · 20 |
| `VERSION.txt` dentro del ZIP | `BC Caja 1.0.0-rc.25` |
| Versión instalada | `BC Caja 1.0.0-rc.24` |
| `integrity_check` | ok |
| `foreign_key_check` | ok |
| `journal_mode` | wal |
| Esquema / tablas | 001–020 · 24 |
| Bindings | `P2→PILAR` · `PC→ASUNCION` · `PILAR→PILAR` |
| Mission Leases | 0 |

`SHA256` base pre-instalación:
`51AC99CB38D19012E472E5170E407668655D3011A9315896E7ED84A78F1E4769`

Huella de los 15 trabajos (id + etapa + nº de transiciones):
`cfb065ecccc0ec32`

## Backup

La base estaba en **WAL**, así que no se copió a mano: se usó la **API de backup
de SQLite**, que produce una copia coherente incluyendo lo pendiente en el WAL
sin depender de copiar `-wal`/`-shm` a tiempo. El resto del data root
(`Backups/`, `Logs/`, `Reports/`, `Secrets/`) se copió tal cual.

- Destino: `%LOCALAPPDATA%\BC\Caja-RC25-preinstall-20260816f` — 33 archivos.
- Verificado **abriendo la copia**: `integrity_check=ok`,
  `foreign_key_check=ok`, esquema 001–020, `cash_entries=8`, `CLOSED=3`,
  y **huella de los 15 trabajos idéntica al original**.

## Rollback

- `rc.24` preservado en `BC-Caja-Pilot.rollback-rc24-20260816f`, con `BC-Caja.exe`
  y `VERSION.txt` verificados.
- Carpeta vigente apartada en `BC-Caja-Pilot.replaced-rc24-20260816f`.
- Preservados además: rc.23, rc.22, rc.21, rc.20, rc.17, rc.16, rc.15, todas las
  carpetas `replaced-*` y todos los backups de datos. **No se borró nada.**

## Instalación

Transaccional. Staging verificado **antes de tocar nada**: versión, presencia
del ejecutable, recuento de migraciones y **hash del EXE contra el ya
verificado**. La carpeta vigente se aparta en lugar de borrarse y se restaura
sola si el reemplazo falla. Se reemplazó **solo la carpeta del programa**.

```
instancias_pre_reemplazo=0
staging_version=BC Caja 1.0.0-rc.25
staging_migraciones=20
staging_SHA256_EXE=BA17940C3660553E105741128417B8984DF45103711ED6D39347ED814259F957
reemplazo=OK
```

## Post-install

| Comprobación | Resultado |
|---|---|
| Versión instalada | `BC Caja 1.0.0-rc.25` |
| SHA256 EXE instalado | coincide con el verificado |
| Arranque sobre datos productivos | ventana abre y se sostiene |
| `integrity_check` | ok |
| `foreign_key_check` | ok |
| Esquema | 001–020, sin migración nueva |
| Bindings | `P2→PILAR` · `PC→ASUNCION` · `PILAR→PILAR` |
| Diff de las 24 tablas vs precheck | **ninguna diferencia** |
| Correos | `outbox=1`, `history=5` → **0 nuevos** |
| Cierres | `CLOSED=3` → **0 nuevos** |

### Los 15 trabajos reales

| | |
|---|---|
| Cantidad | 15 |
| Estado | `EN_LABORATORIO`, todos `ATRASADO · EN LABORATORIO` |
| Transiciones | 30, intactas |
| Huella | `cfb065ecccc0ec32` — **idéntica al precheck** |

Verificación funcional **sobre esos mismos registros**, ejecutada en una copia
de la base productiva para no mutarla:

```
Ejemplo real: TEST-P-001
  estado           = 'ATRASADO · EN LABORATORIO'
  ACCION SIGUIENTE = RECEIVE_FROM_LABORATORY -> 'Recibir del laboratorio'
  RECOMENDACION    = CONTACT_LABORATORY      -> 'Contactar laboratorio'

Seleccion de los 15:
  boton principal  = 'Recibir 15 del laboratorio'
  recomendacion    = 'Contactar laboratorio'

1) CONTACTAR no mueve la etapa ni bloquea:
   EN_LABORATORIO -> EN_LABORATORIO | accion sigue = RECEIVE_FROM_LABORATORY
2) RECIBIR sobre los 15 atrasados  -> RECIBIDO_DEL_LABORATORIO: 15
3) el circuito sigue sin inventar plazos -> ENVIADO_A_PILAR: 15 -> RECIBIDO_EN_PILAR: 15
4) NO LLEGO: accion = RESOLVE_RECEPTION -> RECIBIDO_EN_ASUNCION, issue = None
```

El bloqueo que motivó la misión está resuelto sobre los registros que lo
sufrieron: los 15 avanzan de punta a punta **sin comprometer ningún plazo**.

### Teléfono

La columna está y funciona. **Sobre estos 15 muestra `—`**, porque sus pedidos
se sembraron sin teléfono (0/15 tienen `customer_phone` cargado). Es el
comportamiento correcto, no un defecto: el dato se lee del pedido y no se
inventa. Las capturas del smoke, con pedidos que sí lo traen, muestran los
números reales.

### Estabilidad visual

| Gate | Resultado |
|---|---|
| Smoke GUI 1920×1080 | PASS · `atrasado_ofrece="Recibir del laboratorio"` |
| Smoke GUI 1366×768 | PASS · ídem |
| Reuso de filas | `BC_CAJA_REUSO_FILAS_OK destruidos=0 creados=0` |
| Estabilidad en reposo | `ESTABLE en reposo` |
| Tres botones · sin overlays | PASS |

### Límite declarado

La UI del ejecutable congelado **no se puede conducir por automatización**
(limitación vigente desde rc.21: CustomTkinter dibuja sobre canvas sin handles
nativos). Sobre el binario instalado quedan verificados versión, hash, arranque,
esquema, integridad, bindings y preservación de datos. La conducta funcional
está verificada sobre los **datos productivos reales** (en copia) y sobre el
**mismo commit empaquetado** vía smoke GUI.

## Rollback

**Rollback usado: NO.**

Disponibles `rc.24` (`BC-Caja-Pilot.rollback-rc24-20260816f`), rc.23, rc.22,
rc.21, rc.20, rc.17, rc.16, rc.15, más el snapshot
`Caja-RC25-preinstall-20260816f`.
