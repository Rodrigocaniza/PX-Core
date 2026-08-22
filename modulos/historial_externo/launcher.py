"""Lanzador de BC Historial desde BC Caja.

La UI de Caja no consulta ni escribe datos históricos: solamente arma una
línea de comandos y abre un proceso separado. Ese proceso puede ser una
instalación dedicada o el lector integrado, que consulta la misma base
canónica de Caja en modo de solo lectura.

Este módulo tampoco interpreta identidades; pasa CI/RUC y nombre tal como
están en pantalla. La ruta dedicada se puede sobrescribir con
``BC_HISTORIAL_EXE`` y el fallback integrado queda centralizado aquí.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

#: Variable de entorno para instalaciones fuera de la ruta habitual.
VARIABLE_ENTORNO = "BC_HISTORIAL_EXE"

#: Ubicacion estandar de BC Historial en las PC de la optica.
RUTA_PREDETERMINADA = Path(r"C:\BC\factufacil-history\bc-historial\dist\BC Historial.exe")
SCRIPT_INTEGRADO = Path(__file__).resolve().parents[2] / "bc_historial.py"

MENSAJE_NO_DISPONIBLE = (
    "BC Historial no esta disponible en esta PC.\n\n"
    "Pedi a soporte tecnico que lo instale. BC Caja sigue funcionando normalmente."
)


class HistorialNoDisponible(RuntimeError):
    """No se encontro el ejecutable. Trae un mensaje apto para mostrar."""

    titulo = "Historial no disponible"

    def __init__(self, mensaje: str = MENSAJE_NO_DISPONIBLE, detalle: str = ""):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


def ruta_ejecutable() -> Path | None:
    """Ruta de "BC Historial.exe", o ``None`` si no esta instalado."""
    configurada = os.environ.get(VARIABLE_ENTORNO, "").strip()
    candidatas = [Path(configurada)] if configurada else []
    candidatas.append(RUTA_PREDETERMINADA)
    for candidata in candidatas:
        if candidata.is_file():
            return candidata
    return None


def _limpiar(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def hay_datos_de_cliente(nombre: object = "", documento: object = "") -> bool:
    """¿Hay algo con que buscar? Sin esto el boton no tiene sentido."""
    return bool(_limpiar(nombre) or _limpiar(documento))


def construir_argumentos(nombre: object = "", documento: object = "") -> list:
    """Argumentos para BC Historial a partir del cliente en pantalla.

    Caja tiene un unico campo "CI / RUC". Lo unico que se decide aca es en cual
    de las dos banderas mandarlo: con guion es RUC, sin guion es CI. El nombre
    siempre viaja como respaldo, y BC Historial elige el mejor de los tres.
    """
    documento = _limpiar(documento)
    nombre = _limpiar(nombre)
    argumentos: list = []
    if documento:
        argumentos += ["--ruc" if "-" in documento else "--ci", documento]
    if nombre:
        argumentos += ["--name", nombre]
    return argumentos


def comando_historial(nombre: object = "", documento: object = "") -> tuple[list, Path]:
    """Prefiere la instalación dedicada y cae al lector integrado de PX-Core."""
    ejecutable = ruta_ejecutable()
    if ejecutable is not None:
        return [str(ejecutable)] + construir_argumentos(nombre, documento), ejecutable.parent
    if SCRIPT_INTEGRADO.is_file():
        return ([sys.executable, str(SCRIPT_INTEGRADO)]
                + construir_argumentos(nombre, documento), SCRIPT_INTEGRADO.parent)
    raise HistorialNoDisponible(detalle="sin ejecutable ni script integrado")


def abrir_historial(nombre: object = "", documento: object = "", lanzar=None) -> Path:
    """Abre BC Historial prefiltrado, sin bloquear a Caja.

    `lanzar` existe para poder verificar en tests que el proceso se dispara sin
    esperarlo. En produccion es ``subprocess.Popen``, que retorna de inmediato:
    Caja nunca queda esperando a que el operador cierre el historial.
    """
    comando, directorio = comando_historial(nombre, documento)
    arranque = {}
    if sys.platform.startswith("win"):
        # Sin consola parpadeando y desprendido de Caja: si Caja se cierra, el
        # historial abierto no se cae con ella.
        arranque["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    ejecutor = lanzar or subprocess.Popen
    try:
        ejecutor(comando, cwd=str(directorio), close_fds=True, **arranque)
    except OSError as exc:
        raise HistorialNoDisponible(
            "No se pudo abrir BC Historial en esta PC.\n\n"
            "BC Caja sigue funcionando normalmente.",
            detalle="popen: " + str(exc),
        ) from exc
    return Path(comando[0])
