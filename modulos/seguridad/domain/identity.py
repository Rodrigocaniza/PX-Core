"""Identidad de la instalacion.

`installation_id` es un identificador aleatorio de 128 bits, no una funcion del
nombre de la PC ni del usuario de Windows ni de una MAC. Derivarlo del hardware
tendria dos defectos: se puede recalcular en otra maquina si se conocen los
insumos, y dos instalaciones legitimas en la misma PC serian la misma cosa.

Que el archivo diga un `installation_id` no prueba nada — se copia igual que
cualquier archivo. Lo que lo convierte en identidad es lo que hay que tener
ademas para usarlo: el secreto sellado por el sistema operativo y una licencia
firmada que nombre justamente ese identificador y esa maquina.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from ..errors import SecurityError
from .license import format_instant, parse_instant

IDENTITY_FORMAT = "bc.installation.v1"


def new_installation_id() -> str:
    """128 bits del CSPRNG del sistema, en la forma canonica de UUID."""
    return str(uuid4())


@dataclass(frozen=True)
class InstallationIdentity:
    """Parte publica de la identidad. No contiene ni deriva material secreto."""

    installation_id: str
    enrolled_at: datetime
    sealer: str
    security_schema_version: str
    fingerprint_components: tuple[str, ...]
    label: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "format": IDENTITY_FORMAT,
            "installation_id": self.installation_id,
            "enrolled_at": format_instant(self.enrolled_at),
            "sealer": self.sealer,
            "security_schema_version": self.security_schema_version,
            "fingerprint_components": sorted(self.fingerprint_components),
            "label": self.label,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "InstallationIdentity":
        if not isinstance(document, Mapping) or document.get("format") != IDENTITY_FORMAT:
            raise SecurityError("archivo de identidad desconocido")
        try:
            return cls(
                installation_id=str(document["installation_id"]),
                enrolled_at=parse_instant(document["enrolled_at"]),
                sealer=str(document["sealer"]),
                security_schema_version=str(document["security_schema_version"]),
                fingerprint_components=tuple(document.get("fingerprint_components", ())),
                label=str(document.get("label", "")),
            )
        except (KeyError, TypeError) as error:
            raise SecurityError("archivo de identidad incompleto") from error
