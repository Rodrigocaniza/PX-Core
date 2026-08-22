"""DPAPI de verdad, en la Windows que esta corriendo la prueba.

El resto de la suite usa un sellador simulado porque no hay forma de ejercer
"otra PC" desde una sola computadora. Estas pruebas existen para que la
simulacion no sea la unica evidencia: comprueban contra `crypt32.dll` que el
mecanismo real se comporta como la simulacion supone.

Lo que NO se puede probar desde aca, y queda declarado como tal: que el blob
sellado en esta maquina no abra en otra. Eso se verifica fisicamente en la
Optica, y es uno de los pasos del HUMAN_GATE.
"""

from __future__ import annotations

import sys

import pytest

from modulos.seguridad.crypto.primitives import random_bytes
from modulos.seguridad.errors import SealedStoreError
from modulos.seguridad.infrastructure.dpapi import (
    WindowsDPAPISealer,
    default_sealer,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI es de Windows")


@pytest.fixture
def sellador() -> WindowsDPAPISealer:
    return WindowsDPAPISealer()


def test_lo_sellado_vuelve_igual(sellador):
    secreto = random_bytes(32)
    entropia = random_bytes(32)
    assert sellador.open(sellador.seal(secreto, entropia), entropia) == secreto


def test_el_blob_no_contiene_el_secreto(sellador):
    secreto = random_bytes(32)
    sellado = sellador.seal(secreto, random_bytes(32))
    assert secreto not in sellado


def test_con_otra_entropia_no_abre(sellador):
    """La entropia secundaria es la segunda cerradura, ademas de la maquina."""
    sellado = sellador.seal(b"secreto", random_bytes(32))
    with pytest.raises(SealedStoreError):
        sellador.open(sellado, random_bytes(32))


def test_un_blob_corrupto_no_abre_y_no_rompe_el_proceso(sellador):
    entropia = random_bytes(32)
    sellado = bytearray(sellador.seal(b"secreto", entropia))
    sellado[len(sellado) // 2] ^= 0xFF
    with pytest.raises(SealedStoreError):
        sellador.open(bytes(sellado), entropia)


def test_dos_sellados_del_mismo_secreto_no_son_iguales(sellador):
    """Si fueran iguales, comparar blobs diria si dos PCs guardan lo mismo."""
    entropia = random_bytes(32)
    assert sellador.seal(b"secreto", entropia) != sellador.seal(b"secreto", entropia)


def test_el_sellador_por_defecto_es_el_de_maquina(sellador):
    por_defecto = default_sealer()
    assert por_defecto.name == "windows-dpapi-local-machine"


def test_el_ambito_es_de_maquina_y_no_de_usuario():
    """Decision de ADR-0001, verificada contra la constante que se le pasa a Windows.

    Ambito de usuario habria roto BC al iniciar sesion con otra cuenta de
    Windows sobre la misma instalacion, sin agregar defensa contra llevarse los
    archivos a otra PC, que es la amenaza real.
    """
    from modulos.seguridad.infrastructure import dpapi

    assert dpapi.CRYPTPROTECT_LOCAL_MACHINE == 0x4
    assert dpapi.CRYPTPROTECT_UI_FORBIDDEN == 0x1


def test_la_huella_real_de_esta_maquina_tiene_el_componente_obligatorio():
    from modulos.seguridad.infrastructure import fingerprint as fingerprint_module

    huella = fingerprint_module.collect()
    assert huella.components["machine_guid"], "sin MachineGuid no hay binding posible"
    assert len(huella.entropy("cualquier-instalacion")) == 32


def test_enrolar_de_verdad_y_recuperar_el_secreto(tmp_path):
    """Camino completo con DPAPI real: enrolar, cerrar, volver a abrir el secreto."""
    from modulos.seguridad.application import enrollment
    from modulos.seguridad.infrastructure import fingerprint as fingerprint_module
    from modulos.seguridad.infrastructure.store import SecurityPaths

    paths = SecurityPaths(tmp_path / "Security").ensure()
    huella = fingerprint_module.collect()
    identidad, solicitud = enrollment.enroll(paths, default_sealer(), huella, label="prueba real")

    secreto = enrollment.open_secret(paths, default_sealer(), huella)
    assert secreto.installation_id == identidad.installation_id
    assert len(secreto.raw) == 32
    assert secreto.raw not in paths.secret.read_bytes()
    assert solicitud.binding["machine_guid"]
    # El binding guarda hashes, nunca el valor: el MachineGuid no sale de aca.
    assert huella.components["machine_guid"] not in str(solicitud.to_document())
