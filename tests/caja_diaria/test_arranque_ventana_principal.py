# -*- coding: utf-8 -*-
"""Que `python bc_caja.py` llegue a abrir la ventana.

Existe por un fallo que dejó la Caja sin arrancar: el combo de vendedora se
arma mientras se construye la planilla y llamaba a `vendedoras_disponibles()`,
que estaba definida casi tres mil líneas más abajo, dentro de la misma función.
Para Python eso la vuelve una local de `abrir_caja_diaria` todavía no ligada, y
la ventana moría con `UnboundLocalError` antes de existir.

Lo que no lo detectó a tiempo importa tanto como el fallo. Las pruebas de humo
de la ventana miraban el código con `inspect.getsource` en vez de ejecutarlo, y
`--self-check` no construye interfaz: las dos pasaban en verde con la aplicación
rota. Así que acá se abre la ventana de verdad, que es la única forma de saber
que se abre.

Se cubren los dos caminos porque el que fallaba es justamente el del día de la
actualización: una base recién migrada, sin ninguna persona cargada todavía.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import CajaDiaria
from modulos.caja_diaria.application.admin_ops import ROL_OPERADOR
from modulos.caja_diaria.bootstrap import build_cash_day_controller

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture()
def datos(tmp_path, monkeypatch):
    """Una instalación limpia y aislada. Nunca la base real de la Óptica."""
    monkeypatch.setenv("BC_CAJA_DATA_DIR", str(tmp_path / "bc"))
    # Sin esto, una base sin administradora agenda el diálogo de configuración
    # inicial. No estorba -corre recién con el mainloop- pero declarar que esto
    # es automatizado es lo que ya hace el resto del arranque.
    monkeypatch.setenv("BC_CAJA_AUTOMATED", "1")
    return tmp_path


def _sin_pantalla(error: BaseException) -> bool:
    """Si el intérprete gráfico no existe, y no si existe y algo salió mal."""
    motivo = str(error).lower()
    return any(pista in motivo for pista in (
        "no display name", "display name", "couldn't connect",
        "can't find a usable", "no $display"))


@pytest.fixture(scope="module")
def interprete():
    """Un solo intérprete gráfico para el módulo, y nunca la ventana.

    Crear un `CTk()` por prueba parecía lo natural -`usar_ventana_raiz=True`
    convierte la raíz recibida EN la ventana principal, así que no se puede
    reutilizar- y resultó ser inestable: customtkinter guarda estado global que
    referencia a la raíz, y una segunda raíz después de destruir la primera
    fallaba en algunas corridas. Con orden aleatorio de pruebas eso aparecía y
    desaparecía, que es la peor forma de tener un problema.

    Así que el intérprete es uno solo y vive todo el módulo, y lo que se
    descarta en cada prueba es una ventana suya.
    """
    ctk = pytest.importorskip("customtkinter")
    try:
        raiz = ctk.CTk()
    except Exception as error:  # pragma: no cover - depende del entorno
        # Se saltea SOLO si de verdad no hay pantalla. Un `except Exception`
        # suelto -que es como empezó esto- convertía cualquier falla en un
        # salteo, y un salteo se lee como verde: la prueba que existe para que
        # la ventana no deje de abrir habría dejado de correr sin avisar, que
        # es exactamente el modo en que este fallo llegó hasta la Óptica.
        if not _sin_pantalla(error):
            raise
        pytest.skip(f"sin entorno gráfico: {error}")
    raiz.withdraw()
    try:
        yield raiz
    finally:
        raiz.destroy()


@pytest.fixture()
def raiz(interprete):
    """La ventana que se le entrega al arranque, descartable.

    Es un `CTkToplevel` y no la raíz, y da exactamente la misma cobertura:
    `abrir_caja_diaria` con `usar_ventana_raiz=True` no crea ninguna ventana,
    usa la que recibe. `test_la_ventana_que_se_entrega_es_la_que_se_usa` deja
    eso fijado, así que si algún día dejara de ser cierto esta sustitución se
    entera en vez de tapar el hueco.
    """
    import customtkinter as ctk

    ventana = ctk.CTkToplevel(interprete)
    ventana.withdraw()
    try:
        yield ventana
    finally:
        try:
            ventana.destroy()
        except Exception:  # pragma: no cover - ya cerrada por la prueba
            pass


def abrir(raiz, controller):
    """Exactamente lo que hace `bc_caja.py` en su línea 148.

    No se llama a `mainloop()`: los diálogos de login y de configuración inicial
    se agendan con `after`, así que sin mainloop no se disparan y la prueba no
    queda esperando que alguien escriba una contraseña.
    """
    ventana = CajaDiaria.abrir_caja_diaria(
        raiz, controller=controller, usar_ventana_raiz=True)
    ventana.update_idletasks()
    return ventana


def controlador(datos):
    return build_cash_day_controller(datos / "bc" / "bc_caja.sqlite3")


# ==========================================================================
# El arranque
# ==========================================================================

def test_la_ventana_abre_con_el_catalogo_de_vendedoras_vacio(raiz, datos):
    """El caso que rompía: base migrada y todavía sin ninguna persona cargada.

    Es el estado exacto del día de la actualización en la Óptica, y era el único
    en el que se podía llegar a mirar el combo de vendedora sin haber cargado a
    nadie. Que la ventana llegue a existir es todo lo que se afirma acá.
    """
    controller = controlador(datos)
    try:
        assert list(controller.admin.active_salespeople()) == []
        assert abrir(raiz, controller).winfo_exists()
    finally:
        controller.service.repository.close()


def test_la_ventana_abre_con_vendedoras_cargadas(raiz, datos):
    """El otro camino del mismo combo, para que el arreglo no tape uno solo."""
    controller = controlador(datos)
    try:
        admin = controller.admin
        sol = admin.create_initial_admin("sol", "administradora-2026")
        admin.create_user(sol.token, username="leti", display_name="Leti",
                          role=ROL_OPERADOR, branch="ASUNCION",
                          password="operadora-leti-2026")
        assert list(admin.active_salespeople())
        assert abrir(raiz, controller).winfo_exists()
    finally:
        controller.service.repository.close()


def test_el_combo_de_vendedora_no_trae_nombres_de_maqueta(raiz, datos):
    """Con el catálogo vacío el combo queda editable, no inventa nombres.

    La degradación tiene que ser a «escribilo a mano», nunca a una lista
    alternativa: cuatro nombres de maqueta eligiendo la vendedora de una venta
    real es el defecto que la V1-019A vino a cerrar.
    """
    controller = controlador(datos)
    try:
        valores = combos_de_vendedora(abrir(raiz, controller))
        assert valores, "no se encontró el combo de vendedora"
        for opciones in valores:
            assert opciones == ["Seleccionar..."]
    finally:
        controller.service.repository.close()


def combos_de_vendedora(widget, encontrados=None):
    """Los CTkComboBox cuyo primer valor es el marcador de vendedora."""
    import customtkinter as ctk

    encontrados = [] if encontrados is None else encontrados
    if isinstance(widget, ctk.CTkComboBox):
        opciones = list(widget.cget("values") or [])
        if opciones and opciones[0] == "Seleccionar...":
            encontrados.append(opciones)
    for hijo in widget.winfo_children():
        combos_de_vendedora(hijo, encontrados)
    return encontrados


# ==========================================================================
# La familia entera del defecto, sin necesidad de pantalla
# ==========================================================================

def test_la_ventana_que_se_entrega_es_la_que_se_usa(raiz, datos):
    """`usar_ventana_raiz=True` no crea ventana: usa la que recibe.

    Es lo que permite que estas pruebas entreguen un `CTkToplevel` descartable
    en vez de la raíz del intérprete. Si esto cambiara, la sustitución dejaría
    de ser equivalente y hay que enterarse acá y no en la Óptica.
    """
    controller = controlador(datos)
    try:
        assert abrir(raiz, controller) is raiz
    finally:
        controller.service.repository.close()


def test_ninguna_funcion_de_la_ventana_se_usa_antes_de_definirse():
    """La protección de clase, no la del caso.

    Arreglar la línea que fallaba no impide que el próximo agregado a una
    función de seis mil líneas vuelva a llamar a algo que se define más abajo.
    Esto lee el árbol de `abrir_caja_diaria` y falla si alguna función anidada
    se usa, en el cuerpo del propio arranque, antes de la línea que la define.

    Sólo se miran los usos que corren durante la construcción: los que están
    dentro de otra función anidada se ejecutan después, cuando ya está todo
    ligado, y ahí el orden no importa.
    """
    arbol = ast.parse((RAIZ / "CajaDiaria.py").read_text(encoding="utf-8"))
    objetivo = next(
        nodo for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "abrir_caja_diaria")

    definidas: dict[str, int] = {}
    anidadas = []
    for nodo in ast.walk(objetivo):
        if nodo is objetivo:
            continue
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            anidadas.append(nodo)
            if not isinstance(nodo, ast.Lambda):
                definidas.setdefault(nodo.name, nodo.lineno)

    rangos = [(nodo.lineno,
               max(getattr(hijo, "lineno", nodo.lineno) for hijo in ast.walk(nodo)))
              for nodo in anidadas]

    def dentro_de_otra_funcion(linea: int) -> bool:
        return any(desde <= linea <= hasta for desde, hasta in rangos)

    prematuros = sorted({
        (nodo.lineno, nodo.id, definidas[nodo.id])
        for nodo in ast.walk(objetivo)
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load)
        and nodo.id in definidas and nodo.lineno < definidas[nodo.id]
        and not dentro_de_otra_funcion(nodo.lineno)
    })
    assert not prematuros, "\n".join(
        f"CajaDiaria.py:{linea} usa {nombre}(), que se define recién en la "
        f"línea {origen}: la ventana no va a abrir"
        for linea, nombre, origen in prematuros)


def test_vendedoras_disponibles_se_define_antes_del_combo_que_la_usa():
    """El caso concreto, dicho por su nombre, para que el arreglo no se deshaga."""
    fuente = inspect.getsource(CajaDiaria.abrir_caja_diaria).splitlines()
    definicion = next(indice for indice, linea in enumerate(fuente)
                      if linea.strip().startswith("def vendedoras_disponibles("))
    uso = next(indice for indice, linea in enumerate(fuente)
               if "vendedoras_disponibles()" in linea and indice != definicion)
    assert definicion < uso


# ==========================================================================
# El entrypoint
# ==========================================================================

def test_bc_caja_arma_la_ventana_con_el_controlador_que_construye():
    """La línea que fallaba en producción, tal como está escrita en bc_caja.py.

    Si alguien cambia la forma de arrancar, esta prueba deja de describir la
    realidad y hay que mirarla: es la que ata las de arriba con lo que de verdad
    corre cuando se hace doble clic.
    """
    fuente = (RAIZ / "bc_caja.py").read_text(encoding="utf-8")
    assert ("abrir_caja_diaria(root, controller=controller, usar_ventana_raiz=True)"
            in fuente)
