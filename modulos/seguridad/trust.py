"""Anclas de confianza: las claves publicas con las que se verifica una licencia.

**El almacen de confianza es el que viene dentro del paquete y ninguno mas.**
No se lee una clave de confianza desde `%LOCALAPPDATA%`, ni desde la carpeta de
instalacion, ni desde una variable de entorno en produccion. La razon es
directa: un cliente que acepta anclas nuevas desde un archivo que esta al lado
suyo no esta atado a nada — quien copia la carpeta tambien puede dejar ahi su
propia clave y firmarse la licencia que quiera. Ver ADR-0004.

La unica puerta es `BC_SECURITY_TEST_TRUST`, y esta cerrada por construccion en
el paquete: si el ejecutable esta congelado (PyInstaller) se ignora. Existe
para que las pruebas puedan emitir con una clave propia sin firmar nada con la
de produccion.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .canonical import b64u_decode
from .crypto.primitives import key_id as compute_key_id
from .errors import TrustStoreError

TRUST_FORMAT = "bc.trust.v1"
TEST_TRUST_ENV = "BC_SECURITY_TEST_TRUST"

BUILTIN_TRUST_FILE = Path(__file__).with_name("trusted_issuers.json")


@dataclass(frozen=True)
class TrustedIssuer:
    key_id: str
    public_key: bytes
    label: str
    active: bool


@dataclass(frozen=True)
class TrustStore:
    issuers: tuple[TrustedIssuer, ...]
    source: str

    def find(self, key_id: str) -> TrustedIssuer | None:
        for issuer in self.issuers:
            if issuer.key_id == key_id and issuer.active:
                return issuer
        return None

    @property
    def active_key_ids(self) -> tuple[str, ...]:
        return tuple(issuer.key_id for issuer in self.issuers if issuer.active)


def parse(document: Mapping[str, Any], *, source: str) -> TrustStore:
    if not isinstance(document, Mapping) or document.get("format") != TRUST_FORMAT:
        raise TrustStoreError(f"{source}: formato de almacen de confianza desconocido")
    raw_issuers = document.get("issuers")
    if not isinstance(raw_issuers, list):
        raise TrustStoreError(f"{source}: el almacen no lista emisores")
    issuers: list[TrustedIssuer] = []
    for entry in raw_issuers:
        try:
            public_key = b64u_decode(str(entry["public_key"]))
        except (KeyError, TypeError, ValueError) as error:
            raise TrustStoreError(f"{source}: clave publica ilegible") from error
        if len(public_key) != 32:
            raise TrustStoreError(f"{source}: una clave Ed25519 mide 32 bytes")
        declared = str(entry.get("key_id", ""))
        derived = compute_key_id(public_key)
        if declared and declared != derived:
            # El key_id se recalcula siempre. Aceptar el declarado permitiria
            # que una entrada apunte con un nombre a una clave que es otra.
            raise TrustStoreError(f"{source}: el key_id declarado no corresponde a la clave")
        issuers.append(
            TrustedIssuer(
                key_id=derived,
                public_key=public_key,
                label=str(entry.get("label", "")),
                active=bool(entry.get("active", True)),
            )
        )
    if not issuers:
        raise TrustStoreError(f"{source}: almacen de confianza vacio")
    return TrustStore(issuers=tuple(issuers), source=source)


def _frozen() -> bool:
    """True dentro del ejecutable empaquetado. PyInstaller pone estos atributos."""
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def load(environ: Mapping[str, str] | None = None) -> TrustStore:
    values = os.environ if environ is None else environ
    override = values.get(TEST_TRUST_ENV, "").strip()
    if override and not _frozen():
        path = Path(override)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise TrustStoreError(f"{path}: no se pudo leer el almacen de pruebas") from error
        return parse(document, source=f"test:{path.name}")
    try:
        document = json.loads(BUILTIN_TRUST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TrustStoreError("el almacen de confianza del paquete falta o es ilegible") from error
    return parse(document, source="builtin")
