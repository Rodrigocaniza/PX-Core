"""Que el root de Tk siga siendo uno solo, y que nadie cuelgue del global.

`FLAKE-TK-EN-GESTION-CENTRAL` no se reprodujo a pedido: fue un rojo transitorio
en una de siete corridas completas. Un arreglo cuya única evidencia es «no volvió
a pasar» no se distingue de no haber arreglado nada, así que lo que se verifica
acá no es la ausencia del síntoma sino la del mecanismo: dos intérpretes Tcl en
el mismo proceso, y widgets que cuelgan de `tkinter._default_root`, que es una
variable global cuyo valor depende del orden en que corran los módulos.

Se lee el árbol sintáctico y no el texto. Buscar la subcadena `"tk.Tk("` era lo
primero que se escribió y no servía en las dos direcciones: se perdía `ctk.CTk()`
—que es una subclase de `tkinter.Tk` y abre su propio intérprete— y `ttk.Frame()`,
y a la vez se ponía en rojo por nombrar el patrón en un comentario. Con `ast` se
mira lo que el módulo hace, no lo que dice.
"""

import ast
import tkinter as tk
from pathlib import Path

PAQUETE = Path(__file__).parent

#: Los módulos desde los que se construyen widgets. `ttk` y `customtkinter`
#: cuelgan del mismo `_default_root` que `tkinter`: no son un caso aparte.
GRAFICOS = {"tk", "tkinter", "ttk", "ctk", "customtkinter"}

#: Todo lo que abre su propio intérprete Tcl. `CTk` es subclase de `Tk`.
RAICES = {"Tk", "CTk"}


def modulos():
    return sorted(p for p in PAQUETE.glob("test_*.py") if p.name != Path(__file__).name)


def _constructores(ruta: Path):
    """Cada llamada a un constructor gráfico del módulo: (línea, nombre, nodo)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        destino = nodo.func
        if isinstance(destino, ast.Attribute) and isinstance(destino.value, ast.Name):
            if destino.value.id in GRAFICOS:
                yield nodo.lineno, destino.attr, nodo
        elif isinstance(destino, ast.Name) and destino.id in RAICES:
            # `from tkinter import Tk` — el mismo intérprete, sin el prefijo.
            yield nodo.lineno, destino.id, nodo


def _tiene_master(nodo: ast.Call) -> bool:
    if nodo.args:
        return True
    return any(clave.arg in ("master", "parent") and not _es_none(clave.value)
               for clave in nodo.keywords if clave.arg)


def _es_none(valor) -> bool:
    return isinstance(valor, ast.Constant) and valor.value is None


def test_el_root_lo_crea_el_conftest_y_nadie_mas():
    culpables = [f"{ruta.name}:{linea} → {nombre}()"
                 for ruta in modulos()
                 for linea, nombre, _ in _constructores(ruta) if nombre in RAICES]
    assert culpables == [], (
        "esto abre un segundo intérprete Tcl en el proceso; el root del paquete "
        f"vive en conftest.py y es uno solo — {culpables}")


def test_ningun_widget_del_paquete_cuelga_del_default_root():
    culpables = [f"{ruta.name}:{linea} → {nombre}()"
                 for ruta in modulos()
                 for linea, nombre, nodo in _constructores(ruta)
                 if nombre not in RAICES and not _tiene_master(nodo)]
    assert culpables == [], (
        "estos se construyen sin master y quedan atados a tkinter._default_root, "
        f"que depende del orden de los módulos — {culpables}")


def test_el_root_del_paquete_es_el_default_mientras_vive(tk_session):
    # Mira una global del proceso, no del paquete, y eso es a propósito: lo que
    # se quiere saber es si algún widget sin master de acá terminaría colgado de
    # otro root. Si falla, el culpable puede estar fuera de este paquete —una
    # raíz de sesión, o una que quedó viva— y el mensaje lo dice para no mandar
    # a buscar donde no es.
    assert tk._default_root is tk_session, (
        "otro tk.Tk() del proceso se quedó con tkinter._default_root; puede no "
        "ser de este paquete: buscar raíces de sesión o sin destruir")
    assert tk_session.winfo_exists()
