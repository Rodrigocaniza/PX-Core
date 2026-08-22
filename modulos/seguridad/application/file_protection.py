"""Proteccion de archivos que BC deja en disco fuera de la base.

Cifrar las columnas de la base y dejar al lado una carpeta de PDFs con el
nombre, el telefono y la receta de cada paciente no protege a nadie: quien
copia la carpeta se lleva lo mismo, en un formato mas comodo de leer. Este
modulo cierra ese camino.

**No es un segundo sistema criptografico.** Usa la misma DEK, el mismo
AES-256-GCM y el mismo `FieldCipher` que las columnas. Lo unico propio es el
encabezado que permite reconocer un archivo sellado y el dato asociado, que ata
el criptograma a su nombre de archivo.

Formato:

    BCX1FILE\\n  ||  nonce || ciphertexto || tag

El nombre del archivo **no cambia**: `cierre-abc.pdf` sigue llamandose asi.
Cambiarlo habria roto las filas de `mail_outbox` que ya apuntan a esa ruta, y
habria convertido una mejora de seguridad en una migracion de datos.

Que se pierde: el PDF deja de abrirse con doble clic. Se abre con
`bc_security.py abrir-informe`, que escribe una copia legible donde se le pida.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..crypto.primitives import aead_open, aead_seal
from ..errors import DataProtectionError
from .field_protection import FieldCipher

MAGIC = b"BCX1FILE\n"

# Carpetas de la raiz de datos cuyos archivos se sellan. `Backups` NO entra: son
# copias de la base, que ya viajan cifradas por dentro; sellarlas encima las
# volveria irrestaurables con las herramientas de siempre sin ganar nada.
PROTECTED_DIRECTORIES = ("Reports",)


def _associated_data(cipher: FieldCipher, name: str) -> bytes:
    return f"bc.file.v1|{cipher.dek_id}|{name.lower()}".encode("utf-8")


def is_sealed(path: str | Path) -> bool:
    ruta = Path(path)
    if not ruta.is_file():
        return False
    try:
        with open(ruta, "rb") as handle:
            return handle.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def seal_bytes(cipher: FieldCipher, name: str, payload: bytes) -> bytes:
    return MAGIC + aead_seal(cipher.key, payload, _associated_data(cipher, name))


def open_bytes(cipher: FieldCipher, name: str, sealed: bytes) -> bytes:
    if not sealed.startswith(MAGIC):
        raise DataProtectionError("ese archivo no esta sellado por BC")
    return aead_open(cipher.key, sealed[len(MAGIC):], _associated_data(cipher, name))


def write_sealed(cipher: FieldCipher, destination: str | Path, payload: bytes) -> Path:
    ruta = Path(destination)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    from ..infrastructure.store import write_atomic

    write_atomic(ruta, seal_bytes(cipher, ruta.name, payload))
    return ruta


def read_maybe_sealed(cipher: FieldCipher | None, path: str | Path) -> bytes:
    """Lee un archivo, sellado o no.

    Tolera el archivo en claro a proposito: en una instalacion que todavia no
    aplico la proteccion —o justo despues de revertirla— los informes viejos
    siguen ahi y tienen que poder mandarse por correo igual.
    """
    ruta = Path(path)
    crudo = ruta.read_bytes()
    if not crudo.startswith(MAGIC):
        return crudo
    if cipher is None:
        raise DataProtectionError(
            f"{ruta.name} esta sellado y esta instalacion no tiene la clave de datos"
        )
    return open_bytes(cipher, ruta.name, crudo)


@dataclass
class GeneracionProtegida:
    """Genera un archivo en un temporal privado y lo deja sellado en su destino.

    El generador de PDF de BC escribe a una ruta, no a un buffer, y reescribirlo
    para que trabaje en memoria habria tocado el informe —y sus pruebas de
    contrato visual— por un motivo que no es el suyo. En vez de eso, se genera
    en un directorio temporal propio y solo el resultado sellado llega al
    destino definitivo.

    Limitacion declarada: el PDF en claro existe unos milisegundos en `%TEMP%`.
    Es la misma exposicion que produce abrirlo con cualquier visor, y esta en
    ADR-0007.
    """

    cipher: FieldCipher | None
    destination: Path
    _temporary: Path | None = field(default=None, init=False)

    def __enter__(self) -> Path:
        if self.cipher is None:
            return self.destination
        self._temporary = Path(tempfile.mkdtemp(prefix="bc-informe-"))
        return self._temporary / self.destination.name

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._temporary is None:
            return
        try:
            if exc_type is None:
                generado = self._temporary / self.destination.name
                if generado.is_file():
                    assert self.cipher is not None
                    write_sealed(self.cipher, self.destination, generado.read_bytes())
        finally:
            shutil.rmtree(self._temporary, ignore_errors=True)
            self._temporary = None


# --------------------------------------------------------------------------
# Migracion de los archivos que ya estan en disco
# --------------------------------------------------------------------------
def _archivos(data_root: str | Path) -> Iterator[Path]:
    raiz = Path(data_root)
    for carpeta in PROTECTED_DIRECTORIES:
        directorio = raiz / carpeta
        if not directorio.is_dir():
            continue
        for archivo in sorted(directorio.iterdir()):
            if archivo.is_file() and not archivo.name.endswith(".tmp"):
                yield archivo


def survey(data_root: str | Path) -> dict[str, int]:
    """Cuantos archivos hay en claro y cuantos sellados."""
    en_claro = sellados = 0
    for archivo in _archivos(data_root):
        if is_sealed(archivo):
            sellados += 1
        else:
            en_claro += 1
    return {"en_claro": en_claro, "sellados": sellados}


def protect_files(data_root: str | Path, cipher: FieldCipher) -> int:
    """Sella los archivos que ya estan en disco. Idempotente."""
    convertidos = 0
    for archivo in _archivos(data_root):
        if is_sealed(archivo):
            continue
        write_sealed(cipher, archivo, archivo.read_bytes())
        convertidos += 1
    return convertidos


def rollback_files(data_root: str | Path, cipher: FieldCipher) -> int:
    """Devuelve los archivos sellados a su forma legible. Es el camino de vuelta."""
    from ..infrastructure.store import write_atomic

    convertidos = 0
    for archivo in _archivos(data_root):
        if not is_sealed(archivo):
            continue
        write_atomic(archivo, open_bytes(cipher, archivo.name, archivo.read_bytes()))
        convertidos += 1
    return convertidos


def plaintext_leftovers(data_root: str | Path) -> list[str]:
    return [str(archivo) for archivo in _archivos(data_root) if not is_sealed(archivo)]


def sealed_environment() -> dict[str, str]:  # pragma: no cover - utilidad de diagnostico
    return {"tmp": os.environ.get("TEMP", ""), "magic": MAGIC.decode("ascii").strip()}
