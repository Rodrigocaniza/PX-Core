from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from modulos.bc_sync.security import (
    AuthenticatedMessage, SecurityAuthorizationError, SecurityIdentity,
)
from modulos.bc_sync.service import SyncNode
from modulos.bc_sync.store import SyncStore


def _canonical(body, metadata):
    return json.dumps([body, metadata], sort_keys=True, separators=(",", ":")).encode()


class SecurityRegistryHarness:
    """Harness temporal: simula decisiones; no forma parte del código desplegable."""
    def __init__(self):
        self.records = {}
        self.nonces = set()

    def add(self, installation, branch, key, license_id="lic-1"):
        self.records[installation] = {"branch": branch, "key": key,
                                      "license": license_id, "valid": True, "revoked": False}


class IdentityHarness:
    def __init__(self, registry, installation):
        self.registry, self.installation = registry, installation

    def current_sync_identity(self):
        record = self.registry.records[self.installation]
        if not record["valid"]:
            raise SecurityAuthorizationError("licencia inválida")
        if record["revoked"]:
            raise SecurityAuthorizationError("instalación revocada")
        return SecurityIdentity(self.installation, record["branch"], record["license"], "1")


class AuthHarness:
    def __init__(self, identity_provider, registry, *, now=None):
        self.identity_provider, self.registry = identity_provider, registry
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.last_license = ""

    def sign_event(self, body):
        identity = self.identity_provider.current_sync_identity()
        metadata = {"installation_id": identity.installation_id,
                    "branch_id": identity.branch_id, "license_id": identity.license_id,
                    "nonce": str(uuid4()), "timestamp": self.now().isoformat(),
                    "auth_schema": "bc.security.sync.v1"}
        key = self.registry.records[identity.installation_id]["key"]
        metadata["signature"] = hmac.new(key, _canonical(body, metadata), hashlib.sha256).hexdigest()
        self.last_license = identity.license_id
        return AuthenticatedMessage(dict(body), metadata)

    def verify_event(self, message):
        metadata = dict(message.credential); signature = metadata.pop("signature", "")
        installation = metadata.get("installation_id", "")
        record = self.registry.records.get(installation)
        if not record or not record["valid"]:
            raise SecurityAuthorizationError("licencia inválida")
        if record["revoked"]:
            raise SecurityAuthorizationError("instalación revocada")
        if installation != message.body.get("installation_id"):
            raise SecurityAuthorizationError("installation_id falso")
        if record["branch"] != message.body.get("branch_id") or metadata["branch_id"] != record["branch"]:
            raise SecurityAuthorizationError("branch mismatch")
        if metadata["license_id"] != record["license"]:
            raise SecurityAuthorizationError("licencia no vigente")
        instant = datetime.fromisoformat(metadata["timestamp"])
        if abs(self.now() - instant) > timedelta(minutes=5):
            raise SecurityAuthorizationError("timestamp fuera de tolerancia")
        expected = hmac.new(record["key"], _canonical(message.body, metadata), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise SecurityAuthorizationError("firma incorrecta")
        nonce_key = (installation, metadata["nonce"])
        if nonce_key in self.registry.nonces:
            raise SecurityAuthorizationError("nonce repetido")
        self.registry.nonces.add(nonce_key)
        return SecurityIdentity(installation, record["branch"], record["license"], "1")


class Network:
    def __init__(self, receiver):
        self.receiver, self.online, self.messages = receiver, True, []

    def send(self, target, message):
        self.messages.append(message)
        if not self.online:
            raise ConnectionError("offline")
        self.receiver.receive(message)


@pytest.fixture
def secured_pair(tmp_path):
    registry = SecurityRegistryHarness()
    registry.add("inst-asu", "ASUNCION", b"asu-key")
    registry.add("inst-pil", "PILAR", b"pil-key")
    asu_identity, pil_identity = IdentityHarness(registry, "inst-asu"), IdentityHarness(registry, "inst-pil")
    asu_auth, pil_auth = AuthHarness(asu_identity, registry), AuthHarness(pil_identity, registry)
    asu = SyncNode.secured(SyncStore(tmp_path / "asu.sqlite3"), asu_identity, asu_auth)
    pil = SyncNode.secured(SyncStore(tmp_path / "pil.sqlite3"), pil_identity, pil_auth)
    return registry, asu, pil, asu_auth, Network(pil)


def payload():
    return {"customer_document": "123", "source_reference": "sale-1"}


def test_a_seguridad_valida_sync_allow(secured_pair):
    _, asu, pil, _, network = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    assert asu.resume("pil", network) == 1
    assert len(pil.store.events()) == 1


def test_b_licencia_invalida_no_emite(secured_pair):
    registry, asu, _, _, network = secured_pair
    registry.records["inst-asu"]["valid"] = False
    with pytest.raises(SecurityAuthorizationError, match="inválida"):
        asu.publish("COMPRA", payload(), "sale:1")
    assert not asu.store.events() and not network.messages


def test_c_revocada_no_emite_y_no_acepta(secured_pair):
    registry, asu, pil, _, network = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    message = asu.auth_provider.sign_event(asu.store.pending()[0].wire_dict())
    registry.records["inst-asu"]["revoked"] = True
    assert asu.resume("pil", network) == 0
    with pytest.raises(SecurityAuthorizationError, match="revocada"):
        pil.receive(message)
    assert not pil.store.events()


def test_d_mensaje_alterado_deny(secured_pair):
    _, asu, pil, _, _ = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    message = asu.auth_provider.sign_event(asu.store.pending()[0].wire_dict())
    altered = AuthenticatedMessage({**message.body, "payload": {"total": 1}}, message.credential)
    with pytest.raises(SecurityAuthorizationError, match="firma"):
        pil.receive(altered)


def test_e_replay_no_produce_segundo_efecto(secured_pair):
    _, asu, pil, _, _ = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    message = asu.auth_provider.sign_event(asu.store.pending()[0].wire_dict())
    assert pil.receive(message)
    with pytest.raises(SecurityAuthorizationError, match="nonce"):
        pil.receive(message)
    assert len(pil.store.events()) == 1


def test_f_installation_id_falso_deny(secured_pair):
    _, asu, pil, _, _ = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    message = asu.auth_provider.sign_event(asu.store.pending()[0].wire_dict())
    false = AuthenticatedMessage({**message.body, "installation_id": "autodeclarado"}, message.credential)
    with pytest.raises(SecurityAuthorizationError, match="installation_id"):
        pil.receive(false)


def test_g_branch_inconsistente_deny(secured_pair):
    _, asu, pil, _, _ = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    message = asu.auth_provider.sign_event(asu.store.pending()[0].wire_dict())
    wrong = AuthenticatedMessage({**message.body, "branch_id": "PILAR"}, message.credential)
    with pytest.raises(SecurityAuthorizationError, match="branch"):
        pil.receive(wrong)


def test_timestamp_fuera_de_tolerancia_deny(secured_pair):
    _, asu, pil, auth, _ = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    auth.now = lambda: datetime.now(timezone.utc) - timedelta(hours=1)
    message = auth.sign_event(asu.store.pending()[0].wire_dict())
    auth.now = lambda: datetime.now(timezone.utc)
    with pytest.raises(SecurityAuthorizationError, match="timestamp"):
        pil.receive(message)


def test_h_offline_conserva_outbox_sin_degradar_auth(secured_pair):
    _, asu, _, _, network = secured_pair
    event_id = asu.publish("COMPRA", payload(), "sale:1")
    network.online = False
    assert asu.resume("pil", network) == 0
    assert asu.store.pending()[0].event_id == event_id


def test_i_reconexion_usa_identidad_vigente(secured_pair):
    registry, asu, pil, auth, network = secured_pair
    asu.publish("COMPRA", payload(), "sale:1")
    network.online = False; asu.resume("pil", network)
    registry.records["inst-asu"]["license"] = "lic-renovada"
    network.online = True
    assert asu.resume("pil", network) == 1
    assert auth.last_license == "lic-renovada" and len(pil.store.events()) == 1


def test_j_rotacion_no_pierde_outbox(secured_pair):
    registry, asu, pil, _, network = secured_pair
    event_id = asu.publish("COMPRA", payload(), "sale:1")
    network.online = False; asu.resume("pil", network)
    registry.records["inst-asu"].update(key=b"rotated-key", license="lic-2")
    network.online = True; asu.resume("pil", network)
    assert pil.store.events()[0].event_id == event_id


def test_adapter_nativo_no_duplica_criptografia_o_revocacion():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "modulos/bc_sync/security_bc.py").read_text(encoding="utf-8")
    assert "modulos.seguridad.application" in source
    for forbidden in ("hmac.new", "private_key", "revoked_installations =", "shared_secret"):
        assert forbidden not in source
