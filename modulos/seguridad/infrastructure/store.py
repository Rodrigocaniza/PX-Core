"""Los archivos de seguridad en disco y como se leen sin romperse.

Regla que gobierna todo este archivo: **la ausencia o la corrupcion de estos
archivos nunca destruye datos**. Una lectura fallida devuelve "no hay" o
levanta un error de seguridad; ninguna borra, trunca ni reescribe la base.
Esa es la prueba J de la mision, y es un requisito de diseno, no una
consecuencia feliz.

Escritura atomica en todos los casos: se escribe un `.tmp` al lado y se
reemplaza. Un corte de luz a mitad de una renovacion de lease dejaria, si no,
un archivo a medias — y un lease ilegible es una optica que no abre.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import SecurityError

SECURITY_DIR_ENV = "BC_SECURITY_DIR"

IDENTITY_FILE = "installation.json"
SECRET_FILE = "installation.secret"
LICENSE_FILE = "license.bclic"
REVOCATION_FILE = "revocations.bcrl"
LEASE_FILE = "lease.state"
TRUST_FILE = "trusted_issuers.json"


@dataclass(frozen=True)
class SecurityPaths:
    """Donde vive el material de seguridad.

    Carpeta propia, separada de la base: los respaldos de la base se copian, se
    mandan por correo y se llevan en pendrive, y el material de seguridad no
    tiene por que viajar con ellos. Que igual viaje no rompe nada — el secreto
    sellado no abre afuera — pero no darle la oportunidad es gratis.
    """

    root: Path

    @property
    def identity(self) -> Path:
        return self.root / IDENTITY_FILE

    @property
    def secret(self) -> Path:
        return self.root / SECRET_FILE

    @property
    def license(self) -> Path:
        return self.root / LICENSE_FILE

    @property
    def revocations(self) -> Path:
        return self.root / REVOCATION_FILE

    @property
    def lease(self) -> Path:
        return self.root / LEASE_FILE

    @property
    def trust(self) -> Path:
        return self.root / TRUST_FILE

    def ensure(self) -> "SecurityPaths":
        self.root.mkdir(parents=True, exist_ok=True)
        return self


def resolve_security_paths(environ: dict[str, str] | None = None) -> SecurityPaths:
    values = os.environ if environ is None else environ
    configured = values.get(SECURITY_DIR_ENV, "").strip()
    if configured:
        return SecurityPaths(Path(configured).expanduser().resolve())
    if values.get("LOCALAPPDATA"):
        return SecurityPaths(Path(values["LOCALAPPDATA"]) / "BC" / "Security")
    if values.get("XDG_DATA_HOME"):
        return SecurityPaths(Path(values["XDG_DATA_HOME"]) / "bc-security")
    return SecurityPaths(Path.home() / ".local" / "share" / "bc-security")


# --------------------------------------------------------------------------
# Escritura y lectura
# --------------------------------------------------------------------------
def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json(path: Path, document: Any) -> None:
    write_atomic(path, json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8"))


def read_json(path: Path) -> Any | None:
    """`None` si no existe. Error explicito si existe y no se puede leer.

    La distincion importa: "todavia no enrolado" es un estado normal, "el
    archivo esta ahi y es basura" es una manipulacion o un disco enfermo, y
    tratarlos igual haria que corromper un archivo equivalga a desinstalar la
    seguridad.
    """
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as error:
        raise SecurityError(f"{path.name} existe pero no se puede leer") from error


def read_bytes(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError as error:
        raise SecurityError(f"{path.name} existe pero no se puede leer") from error
