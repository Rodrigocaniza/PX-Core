"""Laboratorio de dos PCs.

Lo unico que se simula es el hardware: la identidad de la maquina y el sellado
del sistema operativo. Todo lo demas —firma, cifrado, licencia, lease,
revocacion, base— es el codigo de produccion tal cual.

Se simula porque no hay otra forma: "copiar la instalacion de la PC A a la PC B"
no se puede ejercer desde una sola computadora con DPAPI real. La propiedad que
la simulacion reproduce es exactamente una, y es la que importa: lo sellado con
una identidad de maquina no se abre con otra. Hay ademas pruebas contra el DPAPI
real de Windows en `test_dpapi_real.py`, para que la simulacion no sea la unica
evidencia de que el mecanismo verdadero se comporta asi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modulos.seguridad import runtime
from modulos.seguridad.application import enrollment, keyring, verifier
from modulos.seguridad.application.field_protection import FieldCipher
from modulos.seguridad.application.verifier import VerificationContext
from modulos.seguridad.domain.license import KNOWN_CAPABILITIES
from modulos.seguridad.infrastructure.dpapi import SimulatedMachineSealer
from modulos.seguridad.infrastructure.fingerprint import MachineFingerprint
from modulos.seguridad.infrastructure.store import SecurityPaths
from modulos.seguridad.issuer import issuer as issuer_module
from modulos.seguridad.trust import TEST_TRUST_ENV, parse as parse_trust


def maquina(nombre: str) -> tuple[SimulatedMachineSealer, MachineFingerprint]:
    """Una PC: su sellador y su huella. Dos nombres distintos son dos PCs distintas."""
    return (
        SimulatedMachineSealer(f"machine-key::{nombre}"),
        MachineFingerprint(
            {
                "machine_guid": f"guid-{nombre}",
                "volume_serial": f"vol-{nombre}",
                "windows_install": f"win-{nombre}",
                "computer_name": nombre.upper(),
            }
        ),
    )


@dataclass
class PC:
    """Una computadora del laboratorio: sus archivos, su hardware y su base."""

    nombre: str
    paths: SecurityPaths
    sealer: SimulatedMachineSealer
    fingerprint: MachineFingerprint
    database: Path

    def contexto(self, *, trust=None, ahora: datetime | None = None) -> VerificationContext:
        return VerificationContext(
            paths=self.paths,
            sealer=self.sealer,
            fingerprint=self.fingerprint,
            database_path=self.database,
            trust=trust,
            now=ahora,
        )


@pytest.fixture(autouse=True)
def registro_limpio():
    """Ningun cifrador sobrevive de una prueba a la siguiente."""
    runtime.clear()
    yield
    runtime.clear()


@pytest.fixture
def emisor():
    return issuer_module.generate("emisor de pruebas")


@pytest.fixture
def confianza(emisor, tmp_path, monkeypatch):
    """Almacen de confianza de pruebas, con la clave del emisor de pruebas.

    Se apunta con `BC_SECURITY_TEST_TRUST` en vez de tocar el del paquete: las
    pruebas no firman nada con la clave de produccion, y el almacen que se
    empaqueta queda intacto.
    """
    documento = issuer_module.trust_document([emisor])
    archivo = tmp_path / "trusted_issuers_test.json"
    archivo.write_text(json.dumps(documento), encoding="utf-8")
    monkeypatch.setenv(TEST_TRUST_ENV, str(archivo))
    return parse_trust(documento, source="test")


def _base_de_caja(ruta: Path) -> Path:
    """Base real de BC Caja, con la cadena entera de migraciones aplicada."""
    from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

    repositorio = SQLiteCashDayRepository(ruta)
    repositorio.close()
    return ruta


@pytest.fixture
def pc_a(tmp_path) -> PC:
    sealer, huella = maquina("pc-a")
    return PC(
        nombre="pc-a",
        paths=SecurityPaths(tmp_path / "pc-a" / "Security").ensure(),
        sealer=sealer,
        fingerprint=huella,
        database=_base_de_caja(tmp_path / "pc-a" / "Caja" / "bc_caja.sqlite3"),
    )


@pytest.fixture
def pc_b(tmp_path) -> PC:
    """La segunda PC. Arranca sin archivos: el clon se copia en cada prueba."""
    sealer, huella = maquina("pc-b")
    return PC(
        nombre="pc-b",
        paths=SecurityPaths(tmp_path / "pc-b" / "Security").ensure(),
        sealer=sealer,
        fingerprint=huella,
        database=tmp_path / "pc-b" / "Caja" / "bc_caja.sqlite3",
    )


def enrolar(pc: PC, *, etiqueta: str = "prueba"):
    return enrollment.enroll(pc.paths, pc.sealer, pc.fingerprint, label=etiqueta)


def emitir_para(
    emisor_key,
    solicitud,
    *,
    lease_days: int = 30,
    grace_days: int = 14,
    valid_days: int | None = None,
    capacidades=KNOWN_CAPABILITIES,
    license_id: str = "lic-1",
    issued_at: datetime | None = None,
):
    return issuer_module.issue_license(
        emisor_key,
        license_id=license_id,
        installation_id=solicitud.installation_id,
        organization_id="org-optica",
        branch_id="ASUNCION",
        business_name="Optica de prueba",
        binding=solicitud.binding,
        secondary_required=solicitud.secondary_required,
        capabilities=capacidades,
        sync_public_key=solicitud.sync_public_key,
        lease_days=lease_days,
        grace_days=grace_days,
        valid_days=valid_days,
        issued_at=issued_at,
    )


@pytest.fixture
def instalacion_valida(pc_a, emisor, confianza):
    """PC A enrolada, con licencia instalada, clave de datos creada y ALLOW."""
    _identidad, solicitud = enrolar(pc_a)
    firmada = emitir_para(emisor, solicitud)
    contexto = pc_a.contexto(trust=confianza)
    verifier.install_license(contexto, firmada.to_envelope())
    secreto = enrollment.open_secret(pc_a.paths, pc_a.sealer, pc_a.fingerprint)
    clave, frase = keyring.create_data_key(pc_a.database, secreto)
    return {
        "pc": pc_a,
        "solicitud": solicitud,
        "licencia": firmada,
        "frase": frase,
        "cifrador": FieldCipher(key=clave.raw, dek_id=clave.dek_id),
    }


def ahora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
