# Install Evidence — BC Caja 1.0.0-rc.27

RC consolidada de `BC-CAJA-RC28-ALERTA-PEDIDOS-001` +
`BC-CAJA-RC29-HISTORIAL-JORNADAS-001`, cerrada en `563c34a`. Instalación
reanudada desde `INSTALLATION WAITING — BC Caja in use` tras el cierre manual
de la aplicación.

**Sin migración nueva**: el esquema permanece en `021`.

## Bloqueo previo

La primera y la segunda pasada se detuvieron en `INSTALLATION WAITING`: BC Caja
seguía abierta con el **mismo PID 9436** (inicio 22:15:37), confirmado por tres
vías independientes (`Get-Process`, `Win32_Process` vía CIM, `tasklist`). No se
la cerró por la fuerza. Producción quedó intacta en rc.26 hasta que el cierre
manual efectivamente terminó el proceso.

## Precheck

| Comprobación | Resultado |
|---|---|
| Instancias activas | **0** (revalidado antes del reemplazo) |
| SHA256 ZIP | `AB2F19AAE6DDD193DB4892E33B8164B34EC583C7CC14AE0AFADB39ADC336D03B` — coincide con el autorizado |
| SHA256 EXE | `A6A494C27685B33501B4823156D459E581A21EAFC27B6430C890FAB4554592F9` — coincide con el autorizado |
| Tamaño / entradas ZIP | 34.681.629 B · 1161 |
| `VERSION.txt` dentro del ZIP | `BC Caja 1.0.0-rc.27` |
| Versión instalada | `BC Caja 1.0.0-rc.26` (EXE `80CD7F76…C18313`) |
| `integrity_check` | ok |
| `foreign_key_check` | ok — 0 violaciones |
| `journal_mode` | wal |
| Esquema | migraciones 001–021 (21 aplicadas) |
| Mission Leases | 0 |

Baseline de la base productiva antes de tocar nada:

```
mail_outbox=1  mail_history=5  cash_days=12 (CLOSED=3 · OPEN=9)
orders=17      tracked_works=15  cash_entries=8
```

## Backup

La base estaba en **WAL**, así que no se copió a mano: se usó la **API de backup
de SQLite**, que produce una copia coherente incluyendo lo pendiente en el WAL
sin depender de copiar `-wal`/`-shm` a tiempo. El resto del data root
(`Secrets/`, `Reports/`, `Logs/`) se copió tal cual.

- Destino: `%LOCALAPPDATA%\BC\Caja\Backups\preinstall-rc27-20260816h`
  — base de 421.888 B.
- Verificado **abriendo la copia**: `integrity_check=ok`,
  `foreign_key_check=ok`, 21 migraciones y **todos los conteos idénticos al
  origen**.

## Rollback

- `rc.26` preservado en `BC-Caja-Pilot.rollback-rc26-20260816h`, con
  `VERSION.txt` y `BC-Caja.exe` (`80CD7F76…C18313`) verificados.
- Carpeta vigente apartada en `BC-Caja-Pilot.replaced-rc26-20260816h`.
- Preservados además: rc.25, rc.24, rc.23, rc.22, rc.21, rc.20, rc.17, rc.16,
  rc.15, todas las carpetas `replaced-*` y todos los backups históricos de
  datos. **No se borró nada.**

## Instalación

Transaccional. Staging verificado **antes de tocar nada**: versión y hash del
EXE contra el autorizado. La carpeta vigente se aparta en lugar de borrarse y se
restaura sola si el reemplazo falla. Se reemplazó **solo la carpeta del
programa**; el data root no se tocó.

```
instancias_pre_reemplazo=0
staging_version=BC Caja 1.0.0-rc.27
staging_SHA256_EXE=A6A494C27685B33501B4823156D459E581A21EAFC27B6430C890FAB4554592F9
reemplazo=OK
```

## Post-install

| Comprobación | Resultado |
|---|---|
| Versión instalada | `BC Caja 1.0.0-rc.27` |
| SHA256 EXE instalado | coincide con el autorizado |
| Arranque sobre datos productivos | ventana `Caja diaria - Óptica` abre, responde y se sostiene |
| `integrity_check` | ok (pre-swap, post-swap y post-arranque) |
| `foreign_key_check` | ok — 0 violaciones en las tres pasadas |
| Esquema | 001–021, sin migración nueva |
| Correos | `outbox=1`, `history=5` → **0 nuevos** |
| Cierres | `CLOSED=3` → **0 nuevos** |
| Deltas de datos | `orders`, `tracked_works`, `cash_entries`, `cash_days` → **delta 0** |

Nota de método: un primer arranque murió a los ~45 s sin escribir
`startup-error.log`, sin escrituras en la base y sin eventos de error. La causa
fue la **limpieza del árbol de procesos del harness**, no un fallo de la app: el
relanzamiento desacoplado (`cmd /c start`) quedó estable con ventana propia.

## Verificación funcional

**Límite declarado — los smokes de GUI no se ejecutaron como clic.** No hay
automatización de interfaz disponible (limitación vigente desde rc.21:
CustomTkinter dibuja sobre canvas sin handles nativos). No se marcó como hecho
lo que no se hizo.

Sustituto ejecutado sobre el **código exacto empaquetado en rc.27**:

```
tests/caja_diaria  ->  622 passed, 0 failed
  test_rc28_alerta_pedidos.py
  test_rc29_historial_jornadas.py
  test_rc21_tabla_seguimiento.py
  test_rc22_seguimiento_visible.py   (95 tests entre los cuatro)
```

Eso cubre la lógica de la alerta de Pedidos, el agrupado por jornada y
Seguimiento sin regresión. **No** cubre alineación de botones ni percepción
visual.

**Validación visual manual: realizada por el usuario.** Pedidos, Historial y
Seguimiento se ven correctos. Con eso quedan cerrados los tres smokes que la
automatización no podía cubrir.

## Rollback

**Rollback usado: NO.**

Disponibles `rc.26` (`BC-Caja-Pilot.rollback-rc26-20260816h`), rc.25, rc.24,
rc.23, rc.22, rc.21, rc.20, rc.17, rc.16, rc.15, más el snapshot de datos
`Backups/preinstall-rc27-20260816h`.
