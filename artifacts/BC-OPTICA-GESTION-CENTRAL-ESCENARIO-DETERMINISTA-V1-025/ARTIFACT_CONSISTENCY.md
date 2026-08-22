# Consistencia de artifacts — BC-OPTICA-GESTION-CENTRAL-ESCENARIO-DETERMINISTA-V1-025

## La causa, reproducida y no deducida

El escenario se sembró a cada hora del día sobre bases desechables:

| `source_updated_at` | alertas |
| --- | --- |
| 21:00 UTC | ninguna |
| 22:00 UTC | 4 × `LATE_OPEN` |
| 23:00 UTC | 4 × `LATE_OPEN` |

Y después las pruebas reales, con `utc_now` parcheado desde un plugin temporal
que se borró al terminar:

| | reloj normal | reloj a las 22:30 UTC |
| --- | --- | --- |
| antes del arreglo | `32 passed` | **`2 failed, 30 passed`** |
| después | `35 passed` | `35 passed` |

Las dos rojas eran `test_refresh_and_filters_have_visible_feedback` y
`test_alert_selection_acknowledgement_and_restart_persistence`, las dos por lo
mismo: `assert not service.repository.alerts()` con cuatro `LATE_OPEN` vivas.

Es el mismo experimento antes y después, no dos experimentos distintos.

## Que la costura no cambió el piloto

| Afirmación | Comprobación |
| --- | --- |
| por omisión sigue usando `utc_now()` | `test_la_hora_por_defecto_sigue_siendo_el_reloj`, que compara contra el reloj **del módulo** y no contra `datetime.now()`, para no romperse cuando alguien fija el reloj para probar otra cosa |
| el argumento es sólo por nombre | `def bootstrap_synthetic_pilot(self, *, source_updated_at=None)` |
| ninguna llamada existente cambia | las 4 de `bc_gestion_central.py` la siguen llamando sin argumentos |

La única llamada que **sí** se cambió es `tools/capture_gestion_central_detail.py`,
y a propósito: su docstring dice «Captura reproducible» y era el último lugar que
seguía sembrando con el reloj, así que la misma orden daba PNGs distintos según
la hora. Lo levantó la revisión adversarial.

## Suite

| Momento | Comando | Resultado |
| --- | --- | --- |
| antes de esta misión | `python -m pytest -q` | `1383 passed` |
| después | `python -m pytest -q` | `1386 passed in 216.73s` |
| el paquete tocado | `python -m pytest tests/gestion_central -q` | `35 passed` |

## Lo que este archivo no afirma

`LATE_OPEN` sigue leyendo `.hour` sin normalizar el huso. **No se arregló**, y
está anotado como `LATE-OPEN-LEE-LA-HORA-SIN-HUSO` con el motivo: es decisión de
negocio, y hoy no toca a la Óptica porque `ingest_snapshot` no tiene productor
real —el camino productivo es `real_sync.import_snapshot`, que no pasa por ahí—.
Lo que sí quedó hecho es que la regla, que no tenía ni una prueba, ahora tiene
una que la deja escrita tal como se comporta.

## Cierre

Tomado después del push, con la salida real:

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| commit de la misión | `git log -1 --format=%H` | `d8b9ed6b4e1e6fde62e58bbb8aa1a37479cb6024` |
| local y origin son el mismo commit | `git rev-parse HEAD` y `git rev-parse @{u}` tras `git fetch` | ambos `d8b9ed6b4e1e6fde62e58bbb8aa1a37479cb6024` |
| sin divergencia | `git rev-list --left-right --count @{u}...HEAD` | `0  0` |
| árbol limpio | `git status --porcelain` | vacío |

Esta sección se agrega en el commit siguiente a `d8b9ed6`, así que describe la
publicación de `d8b9ed6`, ya ocurrida y verificada con los comandos de arriba.
