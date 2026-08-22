"""Un solo Tk para todo el paquete, y no uno por módulo.

`test_ui_interactions.py` y `test_review_ui_interactions.py` tenían cada uno su
propio `tk.Tk()` con `scope="module"`. Dos intérpretes Tcl creados y destruidos
en el mismo proceso, en el orden que pytest decida, es el patrón que dejó un
rojo transitorio en una de siete corridas completas —el `FLAKE-TK-EN-GESTION-CENTRAL`
que anotó `BC-OPTICA-SEGUIMIENTO-CIERRE-PILAR-V1-018`— y es el mismo que V1-016
corrigió del lado de Caja compartiendo el root.

El problema no es que dos roots sean caros: es que `tkinter` guarda un
`_default_root` global y lo pone en `None` sólo cuando el que se destruye **es**
el default. Con dos `tk.Tk()` por proceso, cuál queda de default y cuándo deja de
haberlo depende del orden de los módulos, y cualquier widget creado sin master
—había uno— cuelga de esa variable global.

Con un root por paquete hay uno solo, vive lo que dura `tests/gestion_central`, y
deja de haber orden que pueda salir mal.
"""

import tkinter as tk

import pytest

from tests.entorno_grafico import sin_pantalla


@pytest.fixture(scope="package")
def tk_session():
    """El único `tk.Tk()` del paquete. Se salta si no hay entorno gráfico.

    Se saltea SÓLO si de verdad no hay pantalla. Un `except Exception` suelto
    convertiría cualquier falla en un salteo, y un salteo se lee como verde: en
    Windows, agotar los intérpretes Tcl —que es justo lo que esta misión vino a
    evitar— entra por acá, y taparlo sería apagar la alarma en vez del incendio.
    """
    try:
        root = tk.Tk()
    except Exception as error:  # pragma: no cover - depende del entorno
        if not sin_pantalla(error):
            raise
        pytest.skip(f"sin entorno gráfico: {error}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()
