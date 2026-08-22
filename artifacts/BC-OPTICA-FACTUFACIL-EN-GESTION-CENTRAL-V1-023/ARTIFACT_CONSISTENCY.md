# Consistencia de artifacts — BC-OPTICA-FACTUFACIL-EN-GESTION-CENTRAL-V1-023

Cada número, hash y frase citada en los artifacts de esta misión, al lado del
comando que la produce. Lo que no se pudo verificar está dicho como tal.

## Estado canónico de partida

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| el worktree estaba **atrás** de origin, no adelante | `git rev-list --left-right --count @{u}...HEAD` | `2  0` |
| era fast-forward limpio, sin divergencia | `git merge-base --is-ancestor HEAD @{u}` | exit 0 |
| punto canónico real | `git log -1 --format="%h %ci %s"` tras el FF | `38ef01b 2026-08-20 13:26:43 -0300` |
| la worktree de Seguridad BC es otra | `git worktree list` | `C:/PX/SEC1 [feature/bc-security-installation-binding-v1-001]` |

El fast-forward trajo 14 archivos y 3777 líneas que este worktree no tenía,
incluida la misión `BC-OPTICA-DESPLIEGUE-PRODUCTIVO-029-032-V1-022` entera. La
siguiente misión salió de leer su `NEXT_ACTION_CAJA.json`, no de elegirla.

## Suite

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| baseline del commit canónico, con F1 ya corregido y F2 todavía no | `python -m pytest -q` | `1 failed, 1375 passed in 218.10s` |
| el failed no era nuestro | `python -m pytest tests/caja_diaria/test_rc18_rc20_integration.py::VersionDelPaqueteTests -q` | `AssertionError: '1.0.0-rc.32' != '1.0.0-rc.33'` |
| y venía del commit canónico | `git log --oneline -1 -S'1.0.0-rc.32' -- CajaDiaria.py` | `5bc1540`, anterior al bump de VERSION.txt en 38ef01b |
| final, con los tres arreglos | `python -m pytest -q` | `1380 passed in 212.79s` |
| dirigidas nuevas | `python -m pytest tests/gestion_central tests/herramientas -q` | `33 passed` (29 previas + 4 de F2; las 4+1 de F1 están dentro de las 29) |

1376 recolectadas antes, 1380 después: +4 son las de `tests/herramientas/`. Las
de F1 ya estaban dentro de la baseline porque se escribieron antes de lanzarla.

## F2, verificado end-to-end y no sólo por prueba unitaria

Sobre una base desechable construida en 028 en el scratchpad, nunca sobre nada
productivo:

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| la 029 aplica una y sólo una | `python tools/factufacil_migracion_029_optica.py --base <copia> --confirmar` | `OK  migraciones: 28 -> 29` · `OK  no aparecio ninguna otra tabla ({'factufacil_history', 'factufacil_loads'})` |
| y volver a correrla no reaplica | mismo comando, chequeo de idempotencia | `OK  volver a correrlo no reaplica la migracion` |
| la 030 sobre esa misma base | `python tools/usuarios_migracion_030_optica.py --base <copia> --confirmar` | `OK  migraciones: 29 -> 30` · `OK  exactamente cuatro columnas nuevas` |

Antes de este arreglo, ese mismo primer comando reportaba `migraciones 28 -> 32`.

## Que `outflow_type` se puede leer sin guardas

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| existe desde la 012, mucho antes que la 029 | `grep -rn "outflow_type" modulos/caja_diaria/infrastructure/migrations/*.sql` | `012_cash_outflow_type.sql:1: ALTER TABLE cash_entries ADD COLUMN outflow_type ...` |

Aun así, `_factufacil_status` consulta `entry.keys()` antes de leerla: un
snapshot anterior a la 012 no existe en ninguna máquina conocida, pero la
lectura no depende de esa creencia.

## Que Gestión Central no se acopló a Caja

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| no importa el módulo de Caja | `grep -rn "caja_diaria" modulos/gestion_central/*.py` | sin resultados, antes y después |
| y sigue sin poder escribir el snapshot | `real_sync.py:_source` | `mode=ro` + `PRAGMA query_only=ON`, y el sha256 se compara antes y después de leer |

## El paquete HUMAN_GATE

| Archivo | sha256 |
| --- | --- |
| `BC-OPTICA-PERSONAS-Y-TARIFAS.zip` (7706 bytes) | `43cf1bc2ee65f6704a042d4c95606babc6ce186698912554a87d8b6b6971273c` |
| `personas.json` (dentro del ZIP) | `6a9ddf78ee0e5cdc38b3721454def40806d7e69a61ecc733adbce714f06663b4` |
| `alta_personas_y_comisiones_optica.py` (dentro del ZIP) | `355843183b87dfc13a32b2e588b6ffc0774b8a3590bdd3960492de40bd6833a6` |
| `INSTRUCCIONES.txt` (dentro del ZIP) | `7ef8be117e37bad40831966f1d34d00406dcef40f0e5efd47455e6d6b4abd07d` |

El `.py` del ZIP es idéntico al de `tools/`, y el ZIP **no** es autosuficiente:
la herramienta importa `modulos.caja_diaria`. Corre desde el checkout de la
Óptica; la copia va para poder comparar ese sha256 contra la del checkout. Esto
se corrigió tras la revisión adversarial, que encontró la contradicción entre el
PROMPT y el MANIFEST.

Los cuatro números de la base productiva que cita el MANIFEST —esquema 032,
sha256 `484d5638…`, el backup `d325fba5…` y el binario rc.33— **no se
reverificaron en esta sesión**: se copian de
`BC-OPTICA-DESPLIEGUE-PRODUCTIVO-029-032-V1-022/NEXT_ACTION_CAJA.json`, que los
midió en la máquina. Desde casa no hay forma de comprobarlos, y decir que sí la
hubo sería exactamente el tipo de afirmación que este archivo existe para
impedir.

## Cierre

Tomado después de commitear, con la salida real:

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| árbol limpio, nada suelto | `git status --porcelain` | vacío |
| commit de la misión | `git log -1 --format=%H` | `0d76b32fbc81c71333b7d1e0d75b3bfe490968c4` |
| un commit local por encima de origin | `git rev-list --left-right --count @{u}...HEAD` | `0  1` |

**El push no está hecho.** El `git push` a
`origin/feature/bc-optica-comision-composturas-v1-021` fue denegado por el
clasificador de auto mode de la sesión, no por un fallo de git. No se intentó
rodearlo. El commit está entero y verificado en local, y el frente queda a un
solo comando autorizado de estar arriba. Mientras eso no pase, el `0  1` de la
tabla es la lectura correcta y este archivo no dice otra cosa.
