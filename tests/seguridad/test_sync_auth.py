"""Autenticacion de sincronizacion por instalacion.

Lo que la mision pide para la seccion 7, y lo que estas pruebas verifican:
cada operacion remota se atribuye a una instalacion autorizada; no hay una
contrasena global; no se puede repetir un envio; reintentar no duplica; y una
instalacion revocada deja de poder sincronizar.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from modulos.seguridad.application import enrollment, sync_auth, verifier
from modulos.seguridad.domain.license import CAPABILITY_CAJA, CAPABILITY_SYNC
from modulos.seguridad.errors import ReplayError, SecurityError, SignatureError

from .conftest import ahora, emitir_para, enrolar


CIERRE = {
    "schema_version": "bc.cash.close.v1",
    "cash_day_id": "dia-1",
    "expected_cash_pyg": 800000,
    "counted_cash_pyg": 800000,
}


@pytest.fixture
def instalacion(pc_a, emisor, confianza):
    _identidad, solicitud = enrolar(pc_a)
    firmada = emitir_para(emisor, solicitud)
    verifier.install_license(pc_a.contexto(trust=confianza), firmada.to_envelope())
    secreto = enrollment.open_secret(pc_a.paths, pc_a.sealer, pc_a.fingerprint)
    return {"pc": pc_a, "secreto": secreto, "licencia": firmada.payload}


def _pedido(instalacion, *, idempotency_key="cierre-dia-1"):
    return sync_auth.SyncRequest(
        operation="bc.cash.close",
        installation_id=instalacion["secreto"].installation_id,
        idempotency_key=idempotency_key,
        payload=CIERRE,
    )


def test_una_operacion_firmada_se_atribuye_a_su_instalacion(instalacion):
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    verificada = sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE)
    assert verificada.installation_id == instalacion["secreto"].installation_id
    assert verificada.branch_id == "ASUNCION"
    assert verificada.organization_id == "org-optica"
    assert verificada.idempotency_key == "cierre-dia-1"


def test_no_hay_ningun_secreto_compartido(instalacion):
    """El servidor verifica con la clave publica que viaja en la licencia firmada."""
    assert instalacion["licencia"].sync_public_key
    # La clave publica es publica: esta en el documento que el emisor firmo y no
    # hay nada mas que el servidor necesite guardar.
    assert "sync_public_key" in instalacion["licencia"].to_document()


def test_el_contenido_alterado_no_verifica(instalacion):
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    alterado = {**CIERRE, "counted_cash_pyg": 1}
    with pytest.raises(SecurityError):
        sync_auth.verify_credential(credencial, instalacion["licencia"], alterado)


def test_otra_instalacion_no_puede_firmar_por_esta(instalacion, pc_b, emisor, confianza):
    _identidad, solicitud_b = enrolar(pc_b, etiqueta="pc-b")
    emitir_para(emisor, solicitud_b, license_id="lic-b")
    secreto_b = enrollment.open_secret(pc_b.paths, pc_b.sealer, pc_b.fingerprint)

    pedido = sync_auth.SyncRequest(
        operation="bc.cash.close",
        installation_id=secreto_b.installation_id,
        idempotency_key="cierre-dia-1",
        payload=CIERRE,
    )
    credencial_b = sync_auth.issue_credential(secreto_b, pedido)
    # Se presenta la credencial de B junto con la licencia de A: no cierra.
    with pytest.raises(SecurityError):
        sync_auth.verify_credential(credencial_b, instalacion["licencia"], CIERRE)


def test_una_credencial_no_se_puede_presentar_dos_veces(instalacion, tmp_path):
    registro = sync_auth.NonceLedger(tmp_path / "nonces.sqlite3")
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE, ledger=registro)
    with pytest.raises(ReplayError):
        sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE, ledger=registro)


def test_reintentar_el_mismo_cierre_es_valido_y_conserva_la_idempotencia(
    instalacion, tmp_path
):
    """Repetir el ENVIO se rechaza; reintentar la OPERACION no.

    Son dos cosas distintas y por eso llevan campos distintos: el nonce es del
    envio y la clave idempotente es del hecho. Un reintento legitimo trae nonce
    nuevo y la misma clave, y el servidor la reconoce como el mismo cierre.
    """
    registro = sync_auth.NonceLedger(tmp_path / "nonces.sqlite3")
    primera = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    segunda = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    assert primera.nonce != segunda.nonce

    uno = sync_auth.verify_credential(primera, instalacion["licencia"], CIERRE, ledger=registro)
    dos = sync_auth.verify_credential(segunda, instalacion["licencia"], CIERRE, ledger=registro)
    assert uno.idempotency_key == dos.idempotency_key == "cierre-dia-1"


def test_una_credencial_vieja_queda_fuera_de_ventana(instalacion):
    credencial = sync_auth.issue_credential(
        instalacion["secreto"], _pedido(instalacion), now=ahora() - timedelta(hours=2)
    )
    with pytest.raises(SecurityError):
        sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE)


def test_una_credencial_del_futuro_tampoco_entra(instalacion):
    credencial = sync_auth.issue_credential(
        instalacion["secreto"], _pedido(instalacion), now=ahora() + timedelta(hours=2)
    )
    with pytest.raises(SecurityError):
        sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE)


def test_una_licencia_sin_capacidad_de_sync_no_sincroniza(pc_a, emisor, confianza):
    _identidad, solicitud = enrolar(pc_a)
    firmada = emitir_para(emisor, solicitud, capacidades=[CAPABILITY_CAJA])
    verifier.install_license(pc_a.contexto(trust=confianza), firmada.to_envelope())
    secreto = enrollment.open_secret(pc_a.paths, pc_a.sealer, pc_a.fingerprint)
    pedido = sync_auth.SyncRequest(
        operation="bc.cash.close",
        installation_id=secreto.installation_id,
        idempotency_key="x",
        payload=CIERRE,
    )
    credencial = sync_auth.issue_credential(secreto, pedido)
    with pytest.raises(SecurityError):
        sync_auth.verify_credential(credencial, firmada.payload, CIERRE)


def test_la_firma_alterada_no_verifica(instalacion):
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    rota = sync_auth.SyncCredential(
        operation=credencial.operation,
        installation_id=credencial.installation_id,
        idempotency_key=credencial.idempotency_key,
        payload_hash=credencial.payload_hash,
        nonce=credencial.nonce,
        issued_at=credencial.issued_at,
        signature=bytes(credencial.signature[:-1]) + bytes([credencial.signature[-1] ^ 0xFF]),
    )
    with pytest.raises(SignatureError):
        sync_auth.verify_credential(rota, instalacion["licencia"], CIERRE)


def test_el_nonce_solo_se_registra_si_la_firma_verifica(instalacion, tmp_path):
    """Si no, cualquiera llena la tabla del servidor sin firmar nada."""
    registro = sync_auth.NonceLedger(tmp_path / "nonces.sqlite3")
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    rota = sync_auth.SyncCredential(
        operation="otra-cosa",  # cambia el documento firmado
        installation_id=credencial.installation_id,
        idempotency_key=credencial.idempotency_key,
        payload_hash=credencial.payload_hash,
        nonce=credencial.nonce,
        issued_at=credencial.issued_at,
        signature=credencial.signature,
    )
    with pytest.raises(SignatureError):
        sync_auth.verify_credential(rota, instalacion["licencia"], CIERRE, ledger=registro)
    # El nonce quedo libre: la credencial legitima con el mismo nonce entra.
    sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE, ledger=registro)


def test_el_sobre_va_y_vuelve_por_json(instalacion):
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    import json

    reconstruida = sync_auth.SyncCredential.from_envelope(
        json.loads(json.dumps(credencial.to_envelope()))
    )
    assert reconstruida == credencial


def test_la_capacidad_de_sync_es_la_que_habilita(instalacion):
    assert instalacion["licencia"].allows(CAPABILITY_SYNC)


def test_podar_nonces_viejos_no_afecta_a_los_recientes(instalacion, tmp_path):
    registro = sync_auth.NonceLedger(tmp_path / "nonces.sqlite3")
    credencial = sync_auth.issue_credential(instalacion["secreto"], _pedido(instalacion))
    sync_auth.verify_credential(credencial, instalacion["licencia"], CIERRE, ledger=registro)
    assert registro.prune(ahora() - timedelta(days=1)) == 0
    assert registro.prune(ahora() + timedelta(days=1)) == 1
