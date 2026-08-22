# BC-OPTICA-ACTOR-AUDITADO-DE-LA-SESION-V1-027

**Estado:** COMPLETADA_EN_CASA · sin migración, sin binario, sin la PC de la Óptica

Cierra `OTROS-ACTORES-SIGUEN-SIENDO-TEXTO`, que dejó anotado V1-019B y que
V1-020 y V1-021 repitieron con la misma frase: «hay flujos que todavía piden
*Usuario responsable* por diálogo… revisarlos es otra misión».

## Lo que la nota decía, y lo que había en realidad

La nota decía que preguntaban de más. Al abrirlos, dos de los cuatro **casi
nunca preguntaban**:

```python
responsable = os.environ.get("USERNAME") or os.environ.get("USER") or ""
if not responsable:
    responsable = simpledialog.askstring("Edición auditada", "Usuario responsable:", ...)
```

`USERNAME` en Windows siempre está definido. El diálogo era el respaldo de algo
que nunca falta: **código muerto**. Lo que se registraba era la cuenta de
Windows, y en la Óptica esa cuenta es una sola y la comparten todas. Así que
toda edición auditada y toda anulación de movimiento quedaba firmada con el
mismo nombre, sin importar quién la hubiera hecho.

No era una atribución. Era una constante disfrazada de persona, en el único
lugar del sistema cuyo trabajo es decir quién hizo qué.

Y el cuarto sitio era peor en otro sentido: la corrección de la caja inicial
—que es plata— pedía el nombre por teclado. Escrito a mano, cualquiera podía
firmar una corrección con el nombre de otra.

## El arreglo no inventa nada

V1-019B ya había resuelto esto para los pedidos, y está en producción desde
entonces:

```python
def responsable_actual():
    """Quien esta operando. Ya no se pregunta ni se adivina del entorno."""
    sesion = operadora_actual()
    return sesion.display_name if sesion is not None else "Sin sesión"
```

Lo único que faltaba era que las otras cuatro hicieran lo mismo. Ahora hay una
sola función, a nivel de módulo para poder probarla sin abrir Tk, y las cinco
pasan por ella.

**«Sin sesión» es deliberado.** Las dos alternativas eran peores: una constante
que parece un nombre propio, o un nombre que puede poner cualquiera por
cualquier otra. «Sin sesión» no identifica a nadie, que es exactamente lo que
pasó, y se lee como lo que es. Además crea la presión correcta: los registros
dirán «Sin sesión» hasta que se complete el alta de personas, que es el
HUMAN_GATE que sigue abierto.

## Lo que la revisión adversarial encontró, y que cambió el arreglo

Tres hallazgos, y el primero invalidó parte de lo que yo había hecho:

1. **Yo edité código muerto.** Había **dos** `def responsable_actual()` en el
   mismo `abrir_caja_diaria`. La segunda pisaba a la primera y las 17
   referencias resolvían a la de abajo —la que V1-019B ya había arreglado—. Yo
   parcheé la de arriba, que no corre nunca, y mi prueba pasaba porque miraba el
   texto del archivo. La borré, y hay una prueba que exige que haya una sola.
2. **Un contrato existente decía lo contrario.** `test_rc5_operational_ux.py`
   fijaba literalmente la expresión del entorno. RC5 protegía que el responsable
   no fuera un campo del formulario —eso sigue vigente y sigue verificado—; lo
   que fijó de más fue *de dónde* salía. Se actualizó explicando por qué.
3. **Degradación silenciosa al vencer la sesión.** Con el respaldo puesto en la
   cuenta de Windows, una sesión vencida terminaba firmando con ella y sin
   avisar. Al pasar el respaldo a «Sin sesión» el problema desaparece por
   construcción: sesión vencida y sesión inexistente dan lo mismo, y las dos
   veces es cierto.

El primer intento se descartó entero y se rehízo siguiendo el precedente. Salió
más corto: **6 líneas menos** en `CajaDiaria.py`, no más.

## Lo que cambia en la Óptica

El diálogo «Usuario responsable» de la corrección de caja inicial **deja de
aparecer**. En su lugar, el registro dice quién estaba operando; y hasta que se
carguen las personas, «Sin sesión».

Es un cambio visible y conviene decirlo: se pierde un campo que se llenaba a
mano y se gana que el registro no mienta. El diálogo de la edición auditada no
se pierde porque nunca aparecía.
