"""Sellado local del secreto de instalacion.

El secreto nunca se guarda tal cual. Se guarda sellado por el sistema
operativo, de modo que el archivo sellado por si solo no vale nada fuera de la
maquina que lo sello. En Windows eso es DPAPI (`CryptProtectData`), invocado
por ctypes contra `crypt32.dll`: no hay una dependencia nueva y es el mecanismo
que el propio sistema usa para las credenciales.

Ambito: `CRYPTPROTECT_LOCAL_MACHINE`. Ver ADR-0001 — resumido, la Optica tiene
varios usuarios de Windows sobre la misma instalacion y el ambito de usuario
habria roto BC al iniciar sesion con otra cuenta, sin agregar defensa contra la
amenaza que importa, que es llevarse los archivos a otra PC.

Entropia secundaria: se pasa siempre y se deriva de la huella de la maquina.
Windows ya no descifra el blob en otra PC; la entropia agrega que tampoco lo
descifre un proceso de la misma PC que no sepa reconstruirla.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Protocol

from ..errors import PlatformUnsupportedError, SealedStoreError


class LocalSealer(Protocol):
    """Sella y abre material local. La implementacion real es del sistema operativo."""

    name: str

    def seal(self, plaintext: bytes, entropy: bytes) -> bytes: ...

    def open(self, sealed: bytes, entropy: bytes) -> bytes: ...


# --------------------------------------------------------------------------
# Windows DPAPI
# --------------------------------------------------------------------------
CRYPTPROTECT_UI_FORBIDDEN = 0x1
CRYPTPROTECT_LOCAL_MACHINE = 0x4


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(payload: bytes) -> tuple[_DataBlob, ctypes.Array]:
    """Devuelve tambien el buffer: si se pierde, el recolector lo libera antes de usarlo."""
    buffer = ctypes.create_string_buffer(payload, len(payload))
    return _DataBlob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


class WindowsDPAPISealer:
    """`CryptProtectData` / `CryptUnprotectData` con ambito de maquina."""

    name = "windows-dpapi-local-machine"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise PlatformUnsupportedError("DPAPI solo existe en Windows")
        self._crypt32 = ctypes.WinDLL("crypt32.dll")
        self._kernel32 = ctypes.WinDLL("kernel32.dll")

    def _call(self, function, payload: bytes, entropy: bytes, flags: int, what: str) -> bytes:
        data, _data_buffer = _blob(payload)
        salt, _salt_buffer = _blob(entropy)
        out = _DataBlob()
        ok = function(
            ctypes.byref(data), None, ctypes.byref(salt), None, None, flags, ctypes.byref(out)
        )
        if not ok:
            # El codigo de error de Windows se omite a proposito: no aporta a
            # quien opera y en algunos casos distingue "clave equivocada" de
            # "blob corrupto", que es informacion para quien esta probando.
            raise SealedStoreError(f"el sistema no pudo {what} el material local")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            self._kernel32.LocalFree(out.pbData)

    def seal(self, plaintext: bytes, entropy: bytes) -> bytes:
        return self._call(
            self._crypt32.CryptProtectData,
            plaintext,
            entropy,
            CRYPTPROTECT_LOCAL_MACHINE | CRYPTPROTECT_UI_FORBIDDEN,
            "sellar",
        )

    def open(self, sealed: bytes, entropy: bytes) -> bytes:
        return self._call(
            self._crypt32.CryptUnprotectData,
            sealed,
            entropy,
            CRYPTPROTECT_UI_FORBIDDEN,
            "abrir",
        )


# --------------------------------------------------------------------------
# Simulacion para pruebas
# --------------------------------------------------------------------------
class SimulatedMachineSealer:
    """Sellador de laboratorio: reproduce la propiedad que importa, no DPAPI.

    Existe para poder ejercer "copiar la instalacion a otra PC" dentro de una
    prueba, que es imposible con DPAPI real desde una sola maquina. La
    propiedad reproducida es exactamente una: lo sellado con una identidad de
    maquina no se abre con otra.

    No es criptografia de produccion y no debe usarse fuera de pruebas: la
    clave sale de la identidad simulada de la maquina, que en Windows real es
    justamente lo que el sistema no deja leer.
    """

    name = "simulated-machine-sealer"

    def __init__(self, machine_key: str) -> None:
        self.machine_key = machine_key

    def _key(self, entropy: bytes) -> bytes:
        from ..crypto.primitives import derive_key

        return derive_key(
            self.machine_key.encode("utf-8"), "test-only/simulated-dpapi", salt=entropy
        )

    def seal(self, plaintext: bytes, entropy: bytes) -> bytes:
        from ..crypto.primitives import aead_seal

        return aead_seal(self._key(entropy), plaintext, b"simulated-dpapi")

    def open(self, sealed: bytes, entropy: bytes) -> bytes:
        from ..crypto.primitives import aead_open
        from ..errors import DataProtectionError

        try:
            return aead_open(self._key(entropy), sealed, b"simulated-dpapi")
        except DataProtectionError as error:
            raise SealedStoreError("el material sellado no abre en esta maquina") from error


def default_sealer() -> LocalSealer:
    """El sellador real de esta plataforma.

    Falla en vez de degradar: un fallback "portable" seria guardar el secreto
    con una clave derivable de lo que esta al lado del secreto, que es
    exactamente la seguridad de ocultar archivos que la mision prohibe.
    """
    if sys.platform != "win32":
        raise PlatformUnsupportedError(
            "BC Seguridad V1 sella el secreto con DPAPI y solo corre en Windows"
        )
    return WindowsDPAPISealer()
