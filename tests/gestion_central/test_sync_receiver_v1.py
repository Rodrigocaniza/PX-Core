from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from modulos.bc_sync.model import SyncEvent
from modulos.bc_sync.security import AuthenticatedMessage, SecurityAuthorizationError, SecurityIdentity
from modulos.gestion_central.sync_receiver import (
    CentralSyncInbox, DurableVerifiedRemoteLicenseProvider,
)


@dataclass
class LicensePayload:
    installation_id: str
    branch_id: str
    license_id: str
    organization_id: str = "org-optica"
    capabilities: tuple[str, ...] = ("bc.sync",)
    expires_at: datetime | None = None
    security_schema_version: str = "1"

    def allows(self, capability):
        return capability in self.capabilities


@dataclass
class Revocations:
    serial: int
    installations: tuple[str, ...] = ()
    licenses: tuple[str, ...] = ()

    def revokes(self, *, installation_id, license_id):
        return "revocada para test" if (installation_id in self.installations or
                                         license_id in self.licenses) else ""


class SecurityDocumentHarness:
    """Sólo tests: BC Seguridad real reemplaza este harness después de promoción."""
    def verified_license(self, envelope, _trust):
        if not envelope.get("signature_valid", False):
            raise SecurityAuthorizationError("firma de licencia inválida")
        return LicensePayload(envelope["installation_id"], envelope["branch_id"],
                              envelope["license_id"], envelope.get("organization_id", "org-optica"),
                              tuple(envelope.get("capabilities", ("bc.sync",))),
                              datetime.fromisoformat(envelope["expires_at"]) if envelope.get("expires_at") else None)

    def verified_revocations(self, envelope, _trust):
        if not envelope.get("signature_valid", False):
            raise SecurityAuthorizationError("firma de revocación inválida")
        return Revocations(envelope["serial"], tuple(envelope.get("installations", ())),
                           tuple(envelope.get("licenses", ())))

    def capability_sync(self):
        return "bc.sync"


def license_envelope(installation="inst-asu", branch="ASUNCION", license_id="lic-1", **extra):
    return {"signature_valid": True, "installation_id": installation, "branch_id": branch,
            "license_id": license_id, **extra}


def canonical(body, metadata):
    return json.dumps([body, metadata], sort_keys=True, separators=(",", ":")).encode()


class CentralAuthHarness:
    def __init__(self, licenses, keys, *, now=None):
        self.licenses, self.keys, self.nonces = licenses, keys, set()
        self.now = now or (lambda: datetime.now(timezone.utc))

    def sign(self, body, *, installation=None, branch=None, timestamp=None, nonce=None):
        installation = installation or body["installation_id"]
        payload = self.licenses.verified_license_for_sync(installation)
        metadata = {"installation_id": installation, "branch_id": branch or payload.branch_id,
                    "license_id": payload.license_id, "nonce": nonce or str(uuid4()),
                    "timestamp": timestamp or self.now().isoformat(), "auth_schema": "bc.security.sync.v1"}
        metadata["signature"] = hmac.new(self.keys[installation], canonical(body, metadata),
                                          hashlib.sha256).hexdigest()
        return AuthenticatedMessage(dict(body), metadata)

    def verify_event(self, message):
        metadata = dict(message.credential); signature = metadata.pop("signature", "")
        installation = metadata.get("installation_id", "")
        payload = self.licenses.verified_license_for_sync(installation)
        if installation != message.body.get("installation_id"):
            raise SecurityAuthorizationError("installation_id falso")
        if metadata.get("branch_id") != payload.branch_id or message.body.get("branch_id") != payload.branch_id:
            raise SecurityAuthorizationError("branch mismatch")
        issued = datetime.fromisoformat(metadata["timestamp"])
        if abs(self.now() - issued) > timedelta(minutes=5):
            raise SecurityAuthorizationError("timestamp fuera de tolerancia")
        expected = hmac.new(self.keys[installation], canonical(message.body, metadata),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise SecurityAuthorizationError("firma alterada")
        nonce_key = installation, metadata["nonce"]
        if nonce_key in self.nonces:
            raise SecurityAuthorizationError("replay: nonce repetido")
        self.nonces.add(nonce_key)
        return SecurityIdentity(installation, payload.branch_id, payload.license_id, "1")


@pytest.fixture
def receiver(tmp_path):
    provider = DurableVerifiedRemoteLicenseProvider(
        tmp_path / "central.sqlite3", object(), organization_id="org-optica",
        backend=SecurityDocumentHarness())
    provider.install_verified_license(license_envelope())
    provider.install_verified_license(license_envelope("inst-pil", "PILAR", "lic-pil"))
    auth = CentralAuthHarness(provider, {"inst-asu": b"asu-test-key", "inst-pil": b"pil-test-key"})
    inbox = CentralSyncInbox(tmp_path / "central.sqlite3", auth)
    return provider, auth, inbox, tmp_path / "central.sqlite3"


def wire(event_type="VENTA", *, event_id="event-1", installation="inst-asu",
         branch="ASUNCION", idem="sale:1", payload=None, occurred="2026-08-21T12:00:00+00:00"):
    event = SyncEvent(event_id, installation, branch, event_type, occurred, 1,
                      payload or {"sale_id": "sale-1", "envelope": "A-1",
                                  "customer_document": "123", "customer_name": "Ana"}, idem)
    return event.wire_dict()


def test_a_instalacion_no_autorizada(receiver):
    _, auth, inbox, _ = receiver
    body = wire(installation="inst-x")
    message = AuthenticatedMessage(body, {"installation_id": "inst-x"})
    with pytest.raises(SecurityAuthorizationError, match="no autorizada"):
        inbox.receive(message)


def test_b_licencia_invalida(receiver):
    provider, auth, inbox, _ = receiver
    with provider._connect() as db:
        row = db.execute("SELECT envelope_json FROM remote_sync_licenses WHERE installation_id='inst-asu'").fetchone()
        envelope = json.loads(row[0]); envelope["signature_valid"] = False
        db.execute("UPDATE remote_sync_licenses SET envelope_json=? WHERE installation_id='inst-asu'",
                   (json.dumps(envelope),)); db.commit()
    with pytest.raises(SecurityAuthorizationError, match="licencia inválida"):
        inbox.receive(AuthenticatedMessage(wire(), {"installation_id": "inst-asu"}))


def test_c_instalacion_revocada(receiver):
    provider, auth, inbox, _ = receiver
    provider.install_verified_revocations(
        {"signature_valid": True, "serial": 1, "installations": ["inst-asu"]})
    with pytest.raises(SecurityAuthorizationError, match="revocada"):
        inbox.receive(AuthenticatedMessage(wire(), {"installation_id": "inst-asu"}))


def test_d_firma_alterada(receiver):
    _, auth, inbox, _ = receiver
    message = auth.sign(wire()); broken = dict(message.credential); broken["signature"] = "00"
    with pytest.raises(SecurityAuthorizationError, match="firma"):
        inbox.receive(AuthenticatedMessage(message.body, broken))


def test_e_replay(receiver):
    _, auth, inbox, _ = receiver
    message = auth.sign(wire())
    assert inbox.receive(message)
    with pytest.raises(SecurityAuthorizationError, match="replay"):
        inbox.receive(message)
    assert len(inbox.projections()) == 1


def test_f_branch_mismatch(receiver):
    _, auth, inbox, _ = receiver
    message = auth.sign(wire(branch="PILAR"))
    with pytest.raises(SecurityAuthorizationError, match="branch"):
        inbox.receive(message)


def test_g_mensaje_manipulado(receiver):
    _, auth, inbox, _ = receiver
    message = auth.sign(wire()); altered = {**message.body, "payload": {"total": 1}}
    with pytest.raises(SecurityAuthorizationError, match="firma"):
        inbox.receive(AuthenticatedMessage(altered, message.credential))


def test_h_retry_no_duplica(receiver):
    _, auth, inbox, _ = receiver
    body = wire()
    assert inbox.receive(auth.sign(body))
    assert inbox.receive(auth.sign(body)) is False
    assert len(inbox.projections()) == 1


def test_i_ack_perdido_no_duplica(receiver):
    _, auth, inbox, _ = receiver
    body = wire()
    assert inbox.receive(auth.sign(body))  # efecto aplicado; ACK se pierde afuera
    assert inbox.receive(auth.sign(body)) is False
    assert len(inbox.projections()) == 1


def test_j_reinicio_no_pierde_inbox(receiver):
    _, auth, inbox, database = receiver
    assert inbox.receive(auth.sign(wire()))
    restarted = CentralSyncInbox(database, auth)
    assert restarted.projections()[0]["event_id"] == "event-1"


def test_k_misma_instalacion_un_solo_efecto_por_idempotencia(receiver):
    _, auth, inbox, _ = receiver
    assert inbox.receive(auth.sign(wire(event_id="event-1", idem="stable")))
    assert inbox.receive(auth.sign(wire(event_id="event-2", idem="stable"))) is False
    assert len(inbox.projections()) == 1


def test_datos_iniciales_y_factufacil_quedan_proyectados(receiver):
    _, auth, inbox, _ = receiver
    kinds = ["CLIENTE", "VENTA", "SOBRE", "RECETA"]
    for position, kind in enumerate(kinds):
        inbox.receive(auth.sign(wire(kind, event_id=f"e-{position}", idem=f"i-{position}")))
    billing = {"sale_id": "sale-9", "envelope": "P-9", "state": "CARGADA",
               "invoice_number": "001-001-9", "customer_name": "Ana"}
    inbox.receive(auth.sign(wire("FACTURACION_ESTADO", event_id="billing", idem="billing:9",
                                payload=billing)))
    assert {row["category"] for row in inbox.projections()} == {
        "CLIENTE_HISTORIAL", "VENTA", "SOBRE", "RECETA", "FACTUFACIL"}
    fact = inbox.factufacil()[0]
    assert (fact["factufacil_state"], fact["invoice_number"], fact["branch_id"],
            fact["sale_id"], fact["envelope"]) == (
                "CARGADA", "001-001-9", "ASUNCION", "sale-9", "P-9")
    assert all(row["sync_state"] == "RECEIVED" for row in inbox.projections())


@pytest.mark.parametrize("state", ["PENDIENTE_FACTU_FACIL", "CARGADA", "ERROR", "REINTENTAR"])
def test_estados_factufacil_consultables(receiver, state):
    _, auth, inbox, _ = receiver
    payload = {"sale_id": f"sale-{state}", "envelope": "A-2", "state": state,
               "invoice_number": "001-1" if state == "CARGADA" else ""}
    inbox.receive(auth.sign(wire("FACTURACION_ESTADO", event_id=f"event-{state}",
                                idem=f"billing:{state}", payload=payload)))
    assert inbox.factufacil()[0]["factufacil_state"] == state


def test_auditoria_registra_origen_y_rechazo_sin_secretos(receiver):
    _, auth, inbox, _ = receiver
    inbox.receive(auth.sign(wire()))
    broken = auth.sign(wire(event_id="bad", idem="bad")); credential = dict(broken.credential)
    credential["signature"] = "private-test-secret-must-not-leak"
    with pytest.raises(SecurityAuthorizationError):
        inbox.receive(AuthenticatedMessage(broken.body, credential))
    rows = inbox.audit()
    assert {row["outcome"] for row in rows} >= {"RECEIVED", "REJECTED"}
    assert rows[0]["installation_id"] == "inst-asu" and rows[0]["branch_id"] == "ASUNCION"
    assert "private-test-secret" not in json.dumps(rows)
