"""Quién firma una acción auditada: la sesión, y si no hay, nadie.

`OTROS-ACTORES-SIGUEN-SIENDO-TEXTO` lo dejó anotado V1-019B, y V1-020 y V1-021
lo repitieron: «hay flujos que todavía piden Usuario responsable por diálogo».
Al mirarlos, el problema resultó ser el contrario del que decía la nota. Dos de
los cuatro **casi nunca preguntaban**: tomaban `USERNAME`, la cuenta de Windows,
y el diálogo era el respaldo de algo que en Windows siempre está definido. O
sea, código muerto.

En la Óptica esa cuenta es una sola —la comparten todas—, así que toda edición
auditada y toda anulación quedaba firmada con el mismo nombre. No era una
atribución: era una constante disfrazada de persona. Y la corrección de caja
inicial, que es plata, pedía el nombre por teclado: cualquiera podía firmarla
por cualquier otra.

El arreglo no inventa nada. `responsable_actual`, de V1-019B, ya registraba
«Sin sesión» para los pedidos y está en producción desde entonces. Lo único que
faltaba era que las otras cuatro hicieran lo mismo.
"""

import ast
from pathlib import Path

from CajaDiaria import SIN_SESION, actor_de_una_accion_auditada

CAJA = Path(__file__).resolve().parents[2] / "CajaDiaria.py"


class SesionFalsa:
    def __init__(self, display_name="", username=""):
        self.display_name = display_name
        self.username = username


def test_con_sesion_firma_la_persona():
    assert actor_de_una_accion_auditada(SesionFalsa("Leti", "leti")) == "Leti"


def test_sin_nombre_visible_firma_el_usuario():
    assert actor_de_una_accion_auditada(SesionFalsa("   ", "leti")) == "leti"


def test_sin_sesion_no_firma_nadie():
    """«Sin sesión» y no la máquina, y tampoco un nombre escrito a mano.

    No identifica a nadie, que es exactamente lo que pasó. Las dos alternativas
    que había eran peores: una constante que parece un nombre propio, o un
    nombre que puede poner cualquiera por cualquier otra.
    """
    assert actor_de_una_accion_auditada(None) == SIN_SESION
    assert actor_de_una_accion_auditada(SesionFalsa("", "")) == SIN_SESION


def test_una_sesion_vencida_es_lo_mismo_que_no_tener_ninguna():
    """No hay degradación silenciosa.

    `operadora_actual()` devuelve `None` tanto si nadie entró como si la sesión
    venció o desactivaron a la persona. Antes eso importaba, porque el respaldo
    era la cuenta de Windows y una sesión vencida terminaba firmando con ella.
    Ahora los dos casos dan «Sin sesión», que es cierto en los dos.
    """
    assert actor_de_una_accion_auditada(None) == SIN_SESION


def test_la_identidad_no_sale_del_entorno_en_ningun_lado():
    """Que no vuelva a haber una identidad sacada de la cuenta de la máquina."""
    arbol = ast.parse(CAJA.read_text(encoding="utf-8"))
    lecturas = [n.lineno for n in ast.walk(arbol)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get"
                and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "environ"
                and n.args and isinstance(n.args[0], ast.Constant)
                and n.args[0].value in ("USERNAME", "USER")]
    assert lecturas == [], (
        f"la identidad volvió a salir de la cuenta de Windows, en {lecturas}")


def test_ningun_flujo_auditado_pide_el_responsable_por_teclado():
    fuente = CAJA.read_text(encoding="utf-8")
    assert "Usuario responsable" not in fuente, (
        "un flujo auditado volvió a pedir el responsable por teclado; escrito a "
        "mano, cualquiera puede firmar por cualquier otra")


def test_responsable_actual_esta_definida_una_sola_vez():
    """Había dos, y la primera estaba muerta.

    Las dos vivían en el mismo `abrir_caja_diaria`, así que la segunda pisaba a
    la primera y las 17 referencias resolvían a la de abajo. La de arriba
    parecía activa, se podía editar entera, y no corría nunca. Lo levantó la
    revisión adversarial de esta misión, después de que yo editara justamente
    la muerta.
    """
    fuente = CAJA.read_text(encoding="utf-8")
    assert fuente.count("def responsable_actual(") == 1
