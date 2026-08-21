# Correccion de arranque — `UnboundLocalError: vendedoras_disponibles`

Correccion corta sobre la linea ya cerrada de V1-021. No amplia alcance: se
corrige el fallo de arranque y nada mas.

---

## El sintoma

```
python bc_caja.py --self-check   ->  BC_CAJA_SELF_CHECK_OK
python bc_caja.py                ->  la ventana no queda abierta
```

`%LOCALAPPDATA%\BC\Caja\Logs\startup-error.log`:

```
File "bc_caja.py", line 148, in main
  window = abrir_caja_diaria(root, controller=controller, usar_ventana_raiz=True)
File "CajaDiaria.py", line 1814, in abrir_caja_diaria
  seccion, values=(["Seleccionar..."] + vendedoras_disponibles()),
UnboundLocalError: cannot access local variable 'vendedoras_disponibles'
where it is not associated with a value
```

## La causa raiz

`abrir_caja_diaria` tiene alrededor de seis mil lineas y **las dos** apariciones
de `vendedoras_disponibles` viven dentro de esa unica funcion:

| | linea (antes) | que hacia |
|---|---|---|
| uso | 1814 | armar el combo de vendedora al construir la planilla |
| definicion | 4774 | `def vendedoras_disponibles():` |

Para Python, el `def` de la linea 4774 convierte el nombre en **una local de
`abrir_caja_diaria`**. No es un global al que se llegue tarde: es una local que
solo queda ligada cuando la ejecucion pasa por su `def`. La planilla se
construye antes, en la linea 1814, y en ese momento la local existe pero no
tiene valor. De ahi el `UnboundLocalError` y no un `NameError`.

Es un defecto de **orden**, no de logica: la funcion es correcta, esta 2.960
lineas mas abajo de donde se la necesita.

### No es un fallo de V1-021

`git blame` sobre las dos lineas devuelve el mismo commit:

```
dcda533  feat(caja): administrar quien usa BC Caja, y que la vendedora sea una persona
```

Eso es **V1-019A**. En `d44785f` (V1-020) el codigo tiene la misma disposicion:
uso en 1807, definicion en 4767. La linea de V1-021 lo hereda y no lo introduce.

### Por que no lo relaciona el fallback del catalogo vacio

La revision pedia comprobar si estaba ligado al fallback de V1-019A cuando el
catalogo de personas esta vacio. **No lo esta.** El `UnboundLocalError` ocurre
al *resolver el nombre*, antes de entrar en la funcion, asi que rompe igual con
el catalogo lleno o vacio: el `try/except` que devuelve `[]` nunca llega a
ejecutarse. El fallback esta sano y quedo intacto.

### Por que nadie lo vio antes

Las dos comprobaciones que existian pasaban en verde con la aplicacion rota:

- `--self-check` valida base, cierre, backup y reinicio. **No construye
  interfaz**, asi que nunca toca la linea 1814.
- `tests/caja_diaria/test_ui_smoke.py` inspecciona el codigo con
  `inspect.getsource` y busca cadenas. **Nunca ejecuta** `abrir_caja_diaria`.

Ninguna prueba del repositorio abria la ventana. Ese era el agujero real.

## La correccion

`CajaDiaria.py`: se mueve `vendedoras_disponibles` de la linea 4774 a la 1057,
junto a `operadora_actual` y el resto de las funciones de identidad, antes de
`pedir_login_operadora`. El cuerpo no cambia; se agregan seis lineas de
docstring que explican por que vive ahi.

Diff: **+19 / -13**, un solo archivo de produccion.

Se verifico ademas, con un recorrido del AST, que `vendedoras_disponibles` era
el **unico** caso de este patron en toda la funcion: no hay otra funcion anidada
que se use antes de su `def`.

## La regresion

`tests/caja_diaria/test_arranque_ventana_principal.py`, 7 pruebas.

Lo importante es que **abre la ventana de verdad** — llama a
`abrir_caja_diaria(root, controller=controller, usar_ventana_raiz=True)`, la
misma linea que corre `bc_caja.py` — sobre una base temporal aislada por
`BC_CAJA_DATA_DIR`. No se llama a `mainloop()`, asi que los dialogos de login y
de configuracion inicial, que se agendan con `after`, no se disparan.

| prueba | que fija |
|---|---|
| `test_la_ventana_abre_con_el_catalogo_de_vendedoras_vacio` | el caso que rompia: base migrada, sin ninguna persona cargada |
| `test_la_ventana_abre_con_vendedoras_cargadas` | el otro camino del mismo combo |
| `test_el_combo_de_vendedora_no_trae_nombres_de_maqueta` | con el catalogo vacio el combo queda editable; no aparece una lista alternativa |
| `test_ninguna_funcion_de_la_ventana_se_usa_antes_de_definirse` | la familia entera del defecto, por AST y sin necesidad de pantalla |
| `test_vendedoras_disponibles_se_define_antes_del_combo_que_la_usa` | el caso concreto, dicho por su nombre |
| `test_la_ventana_que_se_entrega_es_la_que_se_usa` | que `usar_ventana_raiz=True` use la ventana recibida, que es lo que hace equivalente al andamiaje |
| `test_bc_caja_arma_la_ventana_con_el_controlador_que_construye` | que la linea de `bc_caja.py` siga siendo la que se prueba |

**Se comprobo que la regresion reproduce el fallo**: revirtiendo unicamente
`CajaDiaria.py` al codigo roto, 6 de las 7 fallan; con la correccion, las 7
pasan, en cinco corridas seguidas.

## Dos hallazgos del propio andamiaje

Los dos son de las pruebas nuevas, no del producto, y los dos son la misma
clase de problema que el fallo original: algo que se lee como verde sin serlo.

**1. El salteo que tapaba todo.** La primera version del fixture hacia
`except Exception: pytest.skip(...)` al crear el `Tk`, copiando el patron de los
otros modulos de UI. Cualquier falla se convertia en salteo, y un salteo se lee
como verde: la prueba que existe para que la ventana no deje de abrir habria
dejado de correr sin avisar. Se acoto a saltear solo cuando el error dice que no
hay pantalla; cualquier otro se propaga.

**2. Lo que ese salteo tapaba.** Apenas se acoto, aparecio un error real e
intermitente: el fixture creaba un `CTk()` por prueba, porque
`usar_ventana_raiz=True` consume la raiz y no se la puede reutilizar.
customtkinter guarda estado global que referencia a la raiz, y una segunda raiz
despues de destruir la primera fallaba en algunas corridas. Con orden aleatorio
de pruebas aparecia y desaparecia.

Corregido: un unico interprete `CTk` por modulo, que nunca es la ventana, y un
`CTkToplevel` descartable por prueba. La cobertura es la misma porque
`abrir_caja_diaria` con `usar_ventana_raiz=True` no crea ninguna ventana, usa la
que recibe — y eso quedo fijado en su propia prueba, para que la sustitucion no
pueda volverse falsa en silencio. Suite completa: dos corridas seguidas con
1372 verdes, cero salteos y cero errores.

## Invariantes preservados

Ninguno de estos se toco. El cambio es un movimiento de bloque dentro de una
funcion:

catalogo real de personas · cero nombres hardcodeados · fallback editable sin
vendedoras cargadas · V1-019B login · V1-020 composturas · V1-021 comisiones ·
migraciones 030/031/032 · reglas economicas · inventario · ventas historicas ·
sucursal · auditoria.
