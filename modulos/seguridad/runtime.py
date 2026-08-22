"""Que cifrador esta activo para que base, en este proceso.

Es estado global, y es deliberado. La alternativa era pasar el cifrador como
parametro por seis constructores, cada script de `tools/` y cada camino que
abre la base — y alcanzaba con olvidarse en uno para escribir en claro.

La clave del registro es la ruta resuelta de la base, no un nombre: dos bases
distintas en el mismo proceso (la real y una copia de trabajo) no comparten
clave, y una prueba que abre una base temporal no hereda la de otra.

Por defecto el registro esta vacio y `cipher_for` devuelve `None`, con lo cual
todo BC se comporta exactamente como antes de que existiera esta capa.
"""

from __future__ import annotations

import threading
from pathlib import Path

from .application.field_protection import FieldCipher

_lock = threading.RLock()
_ciphers: dict[str, FieldCipher] = {}


def _key(database_path: str | Path) -> str:
    text = str(database_path)
    if text == ":memory:":
        return text
    try:
        return str(Path(text).resolve())
    except OSError:  # pragma: no cover - rutas invalidas de Windows
        return text


def activate(database_path: str | Path, cipher: FieldCipher) -> None:
    with _lock:
        _ciphers[_key(database_path)] = cipher


def deactivate(database_path: str | Path) -> None:
    with _lock:
        _ciphers.pop(_key(database_path), None)


def cipher_for(database_path: str | Path) -> FieldCipher | None:
    with _lock:
        return _ciphers.get(_key(database_path))


def clear() -> None:
    """Vacia el registro. Existe para el aislamiento entre pruebas."""
    with _lock:
        _ciphers.clear()
