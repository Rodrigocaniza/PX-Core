# BC-OPTICA-TK-ROOT-UNICO-GESTION-CENTRAL-V1-024

**Estado:** COMPLETADA_EN_CASA · sólo pruebas · no toca código de producción · no requiere migración ni la PC de la Óptica

Cierra `FLAKE-TK-EN-GESTION-CENTRAL`, que dejó anotado
`BC-OPTICA-SEGUIMIENTO-CIERRE-PILAR-V1-018` con una recomendación explícita:
«aplicar el mismo arreglo del lado de Gestión Central, en su propia misión».
Esta es esa misión.

## El síntoma, y por qué no alcanzaba con mirarlo

En una de siete corridas completas apareció un tercer rojo transitorio, no
reproducible en las tres siguientes ni en cuatro corridas dirigidas. Un fallo
así no se arregla persiguiéndolo: se arregla quitándole el mecanismo.

`test_ui_interactions.py` y `test_review_ui_interactions.py` tenían cada uno su
propio `tk.Tk()` con `scope="module"`. Dos intérpretes Tcl en el mismo proceso,
creados y destruidos en el orden que pytest decida.

## El mecanismo, que sí es determinista

`tkinter` guarda un `_default_root` global. Mirando el fuente de la propia
biblioteca:

- `Tk.__init__` se queda con el global **sólo si estaba vacío**: el segundo
  `tk.Tk()` de un proceso no llega a ser el default.
- `Tk.destroy` pone el global en `None` **sólo si el que se destruye es** el
  default.

Con dos roots por proceso, cuál es el default y en qué momento deja de haberlo
depende del orden de los módulos. Y había un widget colgando de esa variable:

```python
reopened_root = tk.Toplevel()   # sin master: usa _default_root, sea cual sea
```

Eso es todo lo que hace falta para un rojo que aparece una vez cada siete y
después no se deja encontrar.

## Lo que se hizo

1. **Un root por paquete, no uno por módulo.** El fixture se movió a
   `tests/gestion_central/conftest.py` con `scope="package"`. Hay un solo
   `tk.Tk()` para todo `tests/gestion_central`, y vive lo que dura el paquete.
2. **Guarda de entorno gráfico**, la misma que ya usaban las pruebas de UI de
   Caja: sin display, `pytest.skip` en vez de un rojo que no dice nada del
   código.
3. **Master explícito** en el `Toplevel` que no lo tenía.

## Lo que se agregó para que no vuelva

Tres pruebas en `test_tk_root_unico.py`. No verifican la ausencia del síntoma
—eso sería indistinguible de no haber arreglado nada— sino la del mecanismo:
que ningún módulo del paquete cree su propio `tk.Tk()`, que ningún widget se
construya sin master, y que el root del paquete sea el default mientras vive.

**Se comprobó que fallan.** Se reintrodujo el defecto a propósito en
`test_ui_contract.py` y las dos guardas estáticas se pusieron en rojo nombrando
al culpable (`assert ['test_ui_contract.py'] == []`); revertido, verde otra vez.
Una prueba de regresión que nunca se vio fallar no es una prueba de regresión.

## Lo que levantó la revisión adversarial

Cinco hallazgos, los cinco corregidos antes de commitear. Tres eran sobre las
guardas mismas, que es lo que pasa cuando se escribe una red y no se la prueba:

- La guarda de entorno gráfico nació con un `except Exception` suelto. Caja ya
  había estrechado el suyo tras un incidente concreto —un salteo se lee como
  verde, y así llegó un fallo hasta la Óptica—, así que el docstring que decía
  usar «la misma guarda que Caja» sólo era cierto de las copias que nadie había
  arreglado. Se extrajo a `tests/entorno_grafico.py` y ahora hay una sola.
- Las dos guardas buscaban subcadenas. Se perdían `ctk.CTk()` —subclase de
  `tkinter.Tk`, abre su propio intérprete— y `ttk.Frame()` y `tk.StringVar()`,
  y a la vez daban rojo por nombrar el patrón en un comentario. Se reescribieron
  sobre `ast`: miran lo que el módulo hace, no lo que dice.
- La afirmación sobre `_default_root` mira una global del proceso y no del
  paquete. Se dejó a propósito —es justo lo que se quiere saber— con el mensaje
  diciendo que el culpable puede estar fuera de acá.

Y una duplicación real: `test_detail_uses_horizontal_full_hd_layout_without_primary_vertical_scroll`
estaba definida dos veces, byte a byte igual. La segunda pisaba a la primera, así
que quien editara la de arriba habría estado editando código muerto. Se verificó
por programa que eran idénticas antes de borrar una.

Cada caso nombrado se comprobó contra las guardas nuevas: `ctk.CTk()`,
`ttk.Frame()`, `tk.StringVar()` y `tk.Toplevel(master=None)` dan rojo;
`tk.Toplevel(otro)` y una mención en prosa, no.

## Lo que esta misión no puede afirmar

**El flake no se reprodujo.** Era una de siete corridas completas y no se logró
provocarlo a pedido. Lo que se arregló es el mecanismo, verificado leyendo el
fuente de `tkinter` y con guardas que fallan cuando el mecanismo vuelve. Decir
«el flake está corregido» porque la suite quedó verde sería exactamente el tipo
de afirmación que este párrafo existe para no hacer.
