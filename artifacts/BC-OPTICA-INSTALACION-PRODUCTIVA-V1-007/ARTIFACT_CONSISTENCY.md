# Artifact Consistency — BC-OPTICA-INSTALACION-PRODUCTIVA-V1-007

Cada afirmación de los artefactos de esta misión contra lo que la máquina, el
repositorio y las corridas realmente dicen. Lo que no se verificó está declarado
como tal, no dado por bueno.

## Estado canónico

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| `origin/main` = `7db56a0` | `git rev-parse origin/main`, después de `fetch --all --prune` | ✔ |
| Slice 6 HEAD = `5bc1540faa54…` | `git rev-parse origin/feature/…-006` | ✔ |
| `5bc1540` desciende de `7db56a0` | `git log` de la rama: cadena `ed0dbba → 54f5f06 → ecc0c7b → b580e50 → a8443a3 → 5bc1540` | ✔ |
| El slice 6 no está en `main` | `origin/main` sigue en `7db56a0` tras el fetch | ✔ |
| BC Caja instalada era rc.31 | `VERSION.txt` del ejecutable instalado | ✔ |
| Producción tenía 21 migraciones | `schema_migrations` de la base real | ✔ 21 → `021` |
| 022–027 no estaban instaladas | ninguna de las seis en `schema_migrations` | ✔ |

**Corrección sobre el estado declarado en la orden.** La rama del slice 6 *no
existía en esta PC* al empezar: ni local ni como rama remota conocida. Apareció
con el `fetch`. El SHA declarado resultó exacto, pero de no haber hecho fetch la
misión habría arrancado creyendo que la rama no existe.

## Base productiva

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| La base productiva está en esta PC | `resolve_data_paths().database`, archivo existente de 413.696 bytes | ✔ |
| Es distinta de la de PC Casa | 12 entradas y suma 6.400.000 aquí, 8 y 2.115.000 allá | ✔ |
| Backup consistente | API de backup de SQLite, no copia de archivo | ✔ |
| El backup tiene lo mismo | tablas, migraciones, entradas, suma, líneas, `integrity_check`, FK | ✔ |
| La base quedó intacta durante el gate | sha256 idéntico antes y después | ✔ |

El sha256 del backup **no** coincide con el de la base viva. No es una
inconsistencia: la base tenía WAL abierto y el backup es su imagen consolidada.
La equivalencia se verificó por contenido, no por hash del archivo, y así está
escrito en `BACKUP_Y_ROLLBACK.txt`.

## Gate sobre la base real

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| El gate corrió sobre la base **de la Óptica** | `RELEASE_GATE_022_027_OPTICA_REAL.txt` declara 12 entradas y suma 6.400.000 | ✔ |
| Cadena 21 → 27 | `schema_migrations` sobre la copia | ✔ |
| `integrity_check` ok | `PRAGMA integrity_check` | ✔ |
| Sin violaciones de FK | `PRAGMA foreign_key_check` | ✔ 0 |
| Ninguna fila existente cambió | huella por tabla sobre columnas preexistentes, 24 tablas | ✔ |
| Escenario comercial completo | 14 comprobaciones, incluida la anulación compensatoria | ✔ |
| Rollback | restaurar el backup da el mismo sha256 y vuelve a `021` | ✔ |

Este es el gate que la misión 006 declaró **pendiente y bloqueante**, y es la
razón por la que la instalación no se autorizaba sólo con las pruebas de Casa.
Ahora existe.

## Paquete

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| El zip de rc.32 de PC Casa no está aquí | `releases/` tiene rc.1…rc.26, no rc.32 | ✔ |
| El slice 6 ya lo declaraba local | `"zip_en_el_remoto": false`, `"zip_gitignored": true` | ✔ |
| Se reconstruyó del mismo commit | worktree en `5bc1540`, `pilot/build_pilot.ps1` sin modificar | ✔ |
| Versión correcta | `BC_CAJA_BUILD_OK version=1.0.0-rc.32` | ✔ |
| Las 27 migraciones viajan adentro | conteo dentro del paquete | ✔ |
| El ejecutable migra solo | copia de la base real llega a `027` sin intervención | ✔ |

**El sha256 del zip difiere del de PC Casa** (`fca5c05…` vs `11988895…`).
Declarado, no escondido: PyInstaller no es reproducible byte a byte entre
máquinas. Lo que es idéntico es el commit; lo que se verificó del binario es su
comportamiento contra estos datos.

## Instalación y post-instalación

| Afirmación | Verificación | Resultado |
| --- | --- | --- |
| rc.31 conservada como rollback | `BC-Caja-Pilot.rollback-rc31-20260819-1200/VERSION.txt` dice rc.31 | ✔ |
| rc.32 instalada | `VERSION.txt` del destino dice `BC Caja 1.0.0-rc.32` | ✔ |
| 27 migraciones en producción | `schema_migrations` de la base real | ✔ |
| Las aplicó el propio ejecutable | se arrancó el `.exe` y la cadena avanzó sola | ✔ |
| `integrity_check` ok | sobre la base real ya migrada | ✔ |
| Sin violaciones de FK | ídem | ✔ 0 |
| Datos preservados | 12 entradas, 6.400.000, 10 líneas, 2 días, 8 pedidos | ✔ sin cambios |
| Ninguna tabla previa se perdió | conjunto anterior ⊆ posterior | ✔ |
| BC Caja abre sobre datos reales | ventana `Caja diaria - Óptica` | ✔ |
| UI Comercial funciona | tres pestañas y el buscador, contra copia de la base ya migrada | ✔ |
| Stock sin negativos, sin huérfanos | `INVARIANTES_POST_INSTALACION.txt` | ✔ 0 |

## Lo que NO se verificó, y hay que decirlo

- **No hay captura de pantalla de la aplicación.** Se intentó dos veces. La
  ventana quedó tapada por ventanas ajenas y la imagen incluía correo personal
  del usuario, así que se descartó y se borró. La evidencia de que BC Caja abre
  es el proceso vivo, el título de ventana y la cadena de migraciones aplicada
  por el propio ejecutable.
- **No hubo operación real con la operadora.** No se cargó ni una venta, ni una
  compra, ni una anulación sobre datos reales: eso alteraría producción sin un
  hecho de negocio detrás. El circuito completo se ejercitó sobre la copia, en
  el gate.
- **La UI Comercial se abrió desde el árbol de código**, no desde el ejecutable
  congelado — igual que en el slice 6. Del ejecutable se verificó que arranca y
  que lleva las migraciones adentro.
- **La suite completa no se re-corrió.** Esta misión no modifica una sola línea
  de código de producto. Vale la corrida del slice 6 sobre `5bc1540`. Sí se
  corrió la suite comercial en esta máquina: **254 passed**.
- **El catálogo sigue vacío.** 0 artículos, 0 movimientos, 0 hechos. Es lo
  esperado: la carga inicial es una misión aparte y no se empezó.
- **Anular exige que el día esté abierto.** Deuda preexistente heredada del
  slice 6, no introducida aquí.

## Nota sobre la vía canónica de distribución del binario

La convención del proyecto es no reconstruir el binario para otra máquina, sino
bajar el artefacto exacto del repo privado `Rodrigocaniza/PX-Core-releases` y
verificar su sha256.

**No se pudo comprobar si rc.32 estaba publicada ahí:** `gh release list --repo
Rodrigocaniza/PX-Core-releases` fue denegado por permisos en esta sesión, dos
veces. Lo que sí consta es que el propio MANIFEST del slice 6 declara el zip
`"zip_en_el_remoto": false` y `"zip_gitignored": true`, y que `releases/` en esta
PC no lo tiene. Sobre esa base se reconstruyó desde el commit verificado.

Si rc.32 sí estaba publicada como release asset, la instalación sigue siendo
correcta —es el mismo commit— pero el camino usado no fue el canónico. Queda
declarado en vez de dado por resuelto.
