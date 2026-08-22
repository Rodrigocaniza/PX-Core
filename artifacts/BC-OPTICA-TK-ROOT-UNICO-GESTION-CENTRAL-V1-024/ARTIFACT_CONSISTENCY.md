# Consistencia de artifacts — BC-OPTICA-TK-ROOT-UNICO-GESTION-CENTRAL-V1-024

## El mecanismo, verificado en el intérprete y no de memoria

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| `Tk.destroy` limpia el global sólo si es el default | `python -c "import tkinter, inspect; print(inspect.getsource(tkinter.Tk.destroy))"` | `if _support_default_root and _default_root is self: _default_root = None` |
| había un `Toplevel` sin master | `grep -n "tk.Toplevel()" tests/gestion_central/` | `test_ui_interactions.py:106` |
| eran dos roots, uno por módulo | `grep -rn "tk.Tk()" tests/gestion_central/` | dos, en `test_ui_interactions.py:14` y `test_review_ui_interactions.py:15` |

## Que las guardas no son decorativas

Se reintrodujo el defecto a propósito y se comprobó cada caso. Un módulo
temporal en el paquete, la guarda corrida, el módulo borrado:

| Lo que se metió | Detectado | Veredicto |
| --- | --- | --- |
| `ctk.CTk()` | `test_zz_guarda.py:2 → CTk` | rojo, segundo intérprete |
| `ttk.Frame()` | `test_zz_guarda.py:2 → Frame` | rojo, sin master |
| `tk.StringVar()` | `test_zz_guarda.py:2 → StringVar` | rojo, sin master |
| `tk.Toplevel(master=None)` | `test_zz_guarda.py:2 → Toplevel` | rojo, `master=None` no es master |
| `tk.Toplevel(otro)` | — | **verde**, y así tiene que ser |
| el patrón nombrado en un comentario | — | **verde**: no da falso rojo por prosa |

Las dos últimas filas importan tanto como las cuatro primeras: una guarda que da
rojo por todo no es una guarda.

## Suite

| Afirmación | Comando | Resultado |
| --- | --- | --- |
| antes de esta misión | `python -m pytest -q` | `1380 passed, 0 failed` |
| con el arreglo y las 3 guardas | `python -m pytest -q` | `1383 passed in 207.53s` |
| tras corregir la revisión | `python -m pytest -q` | `1383 passed in 226.60s` |
| el paquete tocado | `python -m pytest tests/gestion_central -q` | `32 passed` |

Borrar la prueba duplicada **no** cambia el conteo: estaba definida dos veces en
el mismo módulo, así que Python se quedaba con una y pytest recogía una.

## Lo que este archivo no puede afirmar

**El flake no se reprodujo.** Se lanzó un loop de 12 corridas dirigidas sobre el
paquete y quedó contaminado a mitad por el propio arreglo —las corridas 3 a 6 ya
eran del código corregido—, así que se descartó entero en vez de presentarlo como
baseline. Doce verdes de un fallo que aparece una vez cada siete corridas
**completas** tampoco habrían probado nada.

Lo que se arregló es el mecanismo. La evidencia de que está arreglado es la tabla
de arriba, no el color de la suite.

## Cierre

Se registra abajo, después del push, con la salida real de los comandos.
