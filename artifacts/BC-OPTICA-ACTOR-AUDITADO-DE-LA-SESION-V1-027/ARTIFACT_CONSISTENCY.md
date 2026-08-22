# Consistencia de artifacts — BC-OPTICA-ACTOR-AUDITADO-DE-LA-SESION-V1-027

## Que el diálogo era código muerto

| Afirmación | Comprobación |
| --- | --- |
| el actor salía del entorno antes del diálogo | `CajaDiaria.py:2919` (antes): `responsable = os.environ.get("USERNAME") or ... ; if not responsable: askstring(...)` |
| `USERNAME` siempre está definido en Windows | es la variable de la sesión de la cuenta; por eso la rama del diálogo no se alcanzaba |
| eran cuatro sitios | `grep -n 'environ.get("USERNAME")'` daba `2919`, `3880`, `3900` (texto libre) y `4228` |
| ahora son cero | el mismo `grep` no devuelve nada, y hay una prueba con `ast` que lo exige |

## Que yo edité código muerto, y cómo se supo

| Afirmación | Comprobación |
| --- | --- |
| había dos `def responsable_actual()` | `grep -c "def responsable_actual"` daba `2`, en las líneas 4282 y 4848 |
| las dos en el mismo `abrir_caja_diaria` | la segunda rebindea el nombre en el mismo scope: las 17 referencias resolvían a la de abajo |
| la de abajo ya estaba bien desde V1-019B | su docstring: «Ya no se pregunta ni se adivina del entorno» |
| ahora hay una | `grep -c` da `1`, y `test_responsable_actual_esta_definida_una_sola_vez` lo fija |

El primer intento de esta misión parcheó la definición muerta y **la prueba
pasaba**, porque miraba el texto del archivo y no el comportamiento. Lo levantó
la revisión adversarial. El intento se descartó entero y se rehízo siguiendo el
precedente de V1-019B; salió 6 líneas más corto que el original, no más largo.

## Que las guardas no son vacías

Se reintrodujo la lectura del entorno en la anulación y se corrió la prueba:

```
E  AssertionError: la cuenta de Windows tiene que leerse en un solo lugar ... y se lee en [1105, 1105, 3930, 3930]
2 failed, 3 passed
```

Restaurado: `5 passed`. (Esa versión de la guarda permitía un sitio rotulado; la
final exige cero, que es más estricto y es lo que hay.)

## El contrato que decía lo contrario

`test_rc5_operational_ux.py:38` fijaba literalmente
`user=os.environ.get("USERNAME") or os.environ.get("USER") or ""`. Con el cambio
quedó en rojo: `1 failed, 1391 passed`.

No se borró ni se aflojó: RC5 protegía que el responsable **no fuera un campo
del formulario**, y eso sigue vigente y sigue verificado en la misma prueba. Lo
que fijó de más fue *de dónde* salía la identidad, con la mejor opción que había
antes de que existieran las sesiones. Se actualizó al contrato nuevo con el
motivo escrito en el docstring, para que no se lea como una prueba que se
ablandó.

## Suite

| Momento | Comando | Resultado |
| --- | --- | --- |
| antes de esta misión | `python -m pytest -q` | `1387 passed` |
| primer intento (descartado) | `python -m pytest -q` | `1 failed, 1391 passed` |
| después | `python -m pytest -q` | `1394 passed in 239.42s` |

## Lo que este archivo no afirma

**No se probó la interfaz.** Las siete pruebas nuevas verifican la decisión
—`actor_de_una_accion_auditada`, que por eso se sacó del closure— y verifican
por `ast` y por texto que ningún sitio auditado se salga del carril. Que el
diálogo desaparezca de la pantalla de corrección de caja inicial se sigue del
código eliminado, no de una prueba que abra la ventana.

Y el cambio **no llega a la Óptica hasta el próximo binario**, que no está
pendiente ni se construyó acá.

## Cierre

Tomado después del push, con la salida real:

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| commit de la misión | `git log -1 --format=%H` | `b8c253e03984bf04282e7f861610f4cdb1450a58` |
| local y origin son el mismo commit | `git rev-parse HEAD` y `git rev-parse @{u}` tras `git fetch` | ambos `b8c253e03984bf04282e7f861610f4cdb1450a58` |
| sin divergencia | `git rev-list --left-right --count @{u}...HEAD` | `0  0` |
| árbol limpio | `git status --porcelain` | vacío |

Esta sección se agrega en el commit siguiente a `b8c253e`, así que describe
la publicación de `b8c253e`, ya ocurrida y verificada con los comandos de arriba.
