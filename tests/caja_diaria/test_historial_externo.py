"""BC Caja -> BC Historial: integracion V1 por proceso externo.

Verifica que Caja arme bien la invocacion, no bloquee, degrade con un mensaje
legible cuando el historial no esta instalado y no toque el historico.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modulos.historial_externo import launcher
from modulos.historial_externo.launcher import (
    HistorialNoDisponible,
    abrir_historial,
    construir_argumentos,
    hay_datos_de_cliente,
    ruta_ejecutable,
)

RAIZ = Path(__file__).resolve().parents[2]


class LanzadorFalso:
    """Sustituto de subprocess.Popen que registra la invocacion."""

    def __init__(self):
        self.llamadas = []

    def __call__(self, comando, **kwargs):
        self.llamadas.append((comando, kwargs))
        return object()


@pytest.fixture
def ejecutable_falso(tmp_path, monkeypatch):
    destino = tmp_path / "BC Historial.exe"
    destino.write_bytes(b"")
    monkeypatch.setenv(launcher.VARIABLE_ENTORNO, str(destino))
    return destino


# -- seleccion de identificador --------------------------------------------
def test_ci_valida_viaja_como_ci():
    assert construir_argumentos("Fernando Gonzalez Leon", "1203712") == [
        "--ci", "1203712", "--name", "Fernando Gonzalez Leon",
    ]


def test_documento_con_guion_viaja_como_ruc():
    assert construir_argumentos("Fernando Gonzalez Leon", "1203712-5") == [
        "--ruc", "1203712-5", "--name", "Fernando Gonzalez Leon",
    ]


def test_sin_documento_queda_solo_el_nombre():
    assert construir_argumentos("Lilian Abdala", "") == ["--name", "Lilian Abdala"]


def test_sin_nombre_queda_solo_el_documento():
    assert construir_argumentos("", "1203712") == ["--ci", "1203712"]


def test_el_nombre_siempre_viaja_como_respaldo():
    """Caja no valida documentos: manda los dos y BC Historial elige.

    Asi un relleno como 111 no filtra por un documento inexistente; el
    historial lo descarta y usa el nombre.
    """
    argumentos = construir_argumentos("Pedro Franco", "111")
    assert "--name" in argumentos and "Pedro Franco" in argumentos


def test_se_recortan_espacios():
    assert construir_argumentos("  Ana Lopez  ", "  1234567  ") == [
        "--ci", "1234567", "--name", "Ana Lopez",
    ]


def test_sin_datos_no_hay_nada_que_buscar():
    assert construir_argumentos("", "") == []
    assert not hay_datos_de_cliente("", "")
    assert not hay_datos_de_cliente("   ", None)
    assert hay_datos_de_cliente("Ana", "")
    assert hay_datos_de_cliente("", "1234567")


def test_tolera_none():
    assert construir_argumentos(None, None) == []


# -- lanzamiento ------------------------------------------------------------
def test_lanza_el_ejecutable_con_los_argumentos(ejecutable_falso):
    lanzador = LanzadorFalso()
    abrir_historial("Fernando Gonzalez Leon", "1203712", lanzar=lanzador)
    (comando, _kwargs), = lanzador.llamadas
    assert comando[0] == str(ejecutable_falso)
    assert comando[1:] == ["--ci", "1203712", "--name", "Fernando Gonzalez Leon"]


def test_no_bloquea_la_caja(ejecutable_falso):
    """Se dispara el proceso y se vuelve: nunca se espera a que cierre."""
    lanzador = LanzadorFalso()
    abrir_historial("Ana", "1234567", lanzar=lanzador)
    _comando, kwargs = lanzador.llamadas[0]
    assert "timeout" not in kwargs
    for prohibido in ("wait", "communicate", "check"):
        assert prohibido not in kwargs
    fuente = Path(launcher.__file__).read_text(encoding="utf-8")
    for bloqueante in ("subprocess.run", "subprocess.call", "check_output",
                       ".wait()", ".communicate("):
        assert bloqueante not in fuente, bloqueante


def test_se_lanza_desprendido_y_sin_consola(ejecutable_falso, monkeypatch):
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    lanzador = LanzadorFalso()
    abrir_historial("Ana", "1234567", lanzar=lanzador)
    _comando, kwargs = lanzador.llamadas[0]
    assert kwargs.get("creationflags")


def test_ejecutable_faltante_da_mensaje_amigable(monkeypatch, tmp_path):
    monkeypatch.setenv(launcher.VARIABLE_ENTORNO, str(tmp_path / "no-existe.exe"))
    monkeypatch.setattr(launcher, "RUTA_PREDETERMINADA", tmp_path / "tampoco.exe")
    assert ruta_ejecutable() is None
    with pytest.raises(HistorialNoDisponible) as error:
        abrir_historial("Ana", "1234567")
    assert "BC Historial no esta disponible" in error.value.mensaje
    assert "Traceback" not in error.value.mensaje
    assert error.value.titulo


def test_error_del_sistema_operativo_no_rompe_caja(ejecutable_falso):
    def explota(*_args, **_kwargs):
        raise OSError("acceso denegado")

    with pytest.raises(HistorialNoDisponible) as error:
        abrir_historial("Ana", "1234567", lanzar=explota)
    assert "sigue funcionando" in error.value.mensaje
    assert "Traceback" not in error.value.mensaje


def test_la_ruta_es_configurable_y_centralizada(tmp_path, monkeypatch):
    destino = tmp_path / "BC Historial.exe"
    destino.write_bytes(b"")
    monkeypatch.setenv(launcher.VARIABLE_ENTORNO, str(destino))
    assert ruta_ejecutable() == destino
    monkeypatch.delenv(launcher.VARIABLE_ENTORNO)
    monkeypatch.setattr(launcher, "RUTA_PREDETERMINADA", destino)
    assert ruta_ejecutable() == destino


def test_la_ruta_no_esta_hardcodeada_en_la_ui():
    fuente = (RAIZ / "CajaDiaria.py").read_text(encoding="utf-8")
    assert "bc-historial" not in fuente.lower()
    assert "BC Historial.exe" not in fuente


# -- acoplamiento -----------------------------------------------------------
def test_caja_no_toca_el_historico():
    """Ni SQLite historico, ni SQL, ni RAW, ni logica de identidad copiada."""
    fuente = Path(launcher.__file__).read_text(encoding="utf-8")
    for prohibido in ("sqlite3", "SELECT ", "observaciones_raw", "bc_historial.sqlite3",
                      "search_text", "is_placeholder", "ruc_base", "parse_observation"):
        assert prohibido not in fuente, prohibido


def test_caja_no_importa_bc_historial():
    """Integracion V1 = proceso externo, no dependencia entre repos."""
    for archivo in (Path(launcher.__file__), RAIZ / "CajaDiaria.py"):
        fuente = archivo.read_text(encoding="utf-8")
        assert "import bc_historial" not in fuente
        assert "from bc_historial" not in fuente


def test_el_boton_no_modifica_la_venta_ni_el_cliente():
    """El handler solo lee los campos y lanza; no guarda nada."""
    fuente = (RAIZ / "CajaDiaria.py").read_text(encoding="utf-8")
    inicio = fuente.index("def abrir_historial_del_cliente()")
    cuerpo = fuente[inicio:fuente.index("boton_historial = ctk.CTkButton", inicio)]
    assert ".get()" in cuerpo
    for escritura in ("guardar", "insert(", "delete(", "registrar", "repositorio",
                      "commit", "save"):
        assert escritura not in cuerpo, escritura


def test_el_boton_esta_en_la_seccion_de_cliente():
    fuente = (RAIZ / "CajaDiaria.py").read_text(encoding="utf-8")
    assert 'secciones_widgets["CLIENTE Y COMPROBANTE"]' in fuente
    assert 'text="Ver historial"' in fuente
    assert "command=abrir_historial_del_cliente" in fuente


def test_el_handler_avisa_si_no_hay_cliente_cargado():
    fuente = (RAIZ / "CajaDiaria.py").read_text(encoding="utf-8")
    inicio = fuente.index("def abrir_historial_del_cliente()")
    cuerpo = fuente[inicio:fuente.index("boton_historial = ctk.CTkButton", inicio)]
    assert "hay_datos_de_cliente" in cuerpo
    assert "HistorialNoDisponible" in cuerpo


def test_lanzador_real_es_popen():
    """Por defecto se usa Popen, que retorna de inmediato."""
    assert launcher.subprocess.Popen is subprocess.Popen
