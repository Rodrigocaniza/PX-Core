from __future__ import annotations

from dataclasses import dataclass
import json

import pytest

from modulos.bc_sync.factufacil import (
    AssistedFactuFacilAdapter, BillingQueue, DisabledFactuFacilAdapter,
)
from modulos.bc_sync.history_reader import SyncedHistoryReader
from modulos.bc_sync.security import AuthenticatedMessage, SecurityAuthorizationError
from modulos.bc_sync.security_bc import BCSecurityIdentityProvider, BCSecuritySyncAuthProvider
from modulos.bc_sync.service import SyncNode
from modulos.bc_sync.store import SyncStore
from modulos.gestion_central.models import Unit
from modulos.gestion_central.sync_receiver import (
    CentralHistoryReader, CentralSyncInbox, DurableVerifiedRemoteLicenseProvider,
)
from modulos.historial_externo.global_history import (
    GlobalHistoryService, HistoryAccessPolicy, HistoryPrincipal, VIEW_GLOBAL,
)
from modulos.historial_externo.history import HistoryQuery
from modulos.seguridad.application import enrollment, sync_auth, verifier
from modulos.seguridad.domain.license import CAPABILITY_HISTORIAL, CAPABILITY_SYNC
from modulos.seguridad.infrastructure.fingerprint import MachineFingerprint
from modulos.seguridad.infrastructure.store import SecurityPaths
from modulos.seguridad.issuer import issuer
from modulos.seguridad.trust import parse as parse_trust


class PilotSealer:
    """Reemplaza únicamente DPAPI en el sandbox; todo lo firmado usa Ed25519 real."""
    name = "pilot-memory-sealer"

    def __init__(self, local_key: bytes):
        self.local_key = local_key

    def _apply(self, value: bytes, entropy: bytes) -> bytes:
        mask = self.local_key + entropy
        return bytes(byte ^ mask[index % len(mask)] for index, byte in enumerate(value))

    def seal(self, value: bytes, entropy: bytes) -> bytes:
        return self._apply(value, entropy)

    def open(self, value: bytes, entropy: bytes) -> bytes:
        return self._apply(value, entropy)


@dataclass
class Installation:
    branch: str
    context: verifier.VerificationContext
    identity: BCSecurityIdentityProvider
    signer: BCSecuritySyncAuthProvider | None
    license_envelope: dict


class CentralTransport:
    def __init__(self, receiver):
        self.receiver, self.online, self.lose_ack = receiver, True, False

    def send(self, _target, message):
        if not self.online:
            raise ConnectionError("piloto offline")
        self.receiver.receive(message)
        if self.lose_ack:
            self.lose_ack = False
            raise TimeoutError("ACK perdido simulado")


@pytest.fixture
def ecosystem(tmp_path):
    issuer_key = issuer.generate("BC piloto temporal")
    trust = parse_trust(issuer.trust_document([issuer_key]), source="pilot-memory")
    central_db = tmp_path / "central.sqlite3"
    remote = DurableVerifiedRemoteLicenseProvider(
        central_db, trust, organization_id="org-optica")

    def create_installation(branch):
        root = tmp_path / branch.lower() / "security"
        paths = SecurityPaths(root)
        fingerprint = MachineFingerprint({
            "machine_guid": f"guid-{branch}", "volume_serial": f"vol-{branch}",
            "windows_install": f"win-{branch}", "computer_name": f"BC-{branch}"})
        sealer = PilotSealer(f"local-{branch}".encode())
        identity, request = enrollment.enroll(paths, sealer, fingerprint, label=branch)
        signed = issuer.issue_license(
            issuer_key, license_id=f"license-{branch}", installation_id=identity.installation_id,
            organization_id="org-optica", branch_id=branch, business_name=f"Óptica {branch}",
            binding=request.binding, secondary_required=request.secondary_required,
            capabilities=[CAPABILITY_SYNC, CAPABILITY_HISTORIAL],
            sync_public_key=request.sync_public_key, valid_days=30)
        context = verifier.VerificationContext(paths, sealer, fingerprint, trust=trust)
        verifier.install_license(context, signed.to_envelope())
        remote.install_verified_license(signed.to_envelope())
        return Installation(branch, context, BCSecurityIdentityProvider(context), None,
                            signed.to_envelope())

    asu, pil = create_installation("ASUNCION"), create_installation("PILAR")
    receiver_auth = BCSecuritySyncAuthProvider(
        asu.identity, remote, tmp_path / "central-nonces.sqlite3")
    asu.signer = BCSecuritySyncAuthProvider(asu.identity, remote, tmp_path / "unused-asu.sqlite3")
    pil.signer = BCSecuritySyncAuthProvider(pil.identity, remote, tmp_path / "unused-pil.sqlite3")
    receiver = CentralSyncInbox(central_db, receiver_auth)
    transport = CentralTransport(receiver)
    asu_node = SyncNode.secured(SyncStore(tmp_path / "asu-sync.sqlite3"), asu.identity, asu.signer)
    pil_node = SyncNode.secured(SyncStore(tmp_path / "pil-sync.sqlite3"), pil.identity, pil.signer)
    return {"tmp": tmp_path, "issuer": issuer_key, "trust": trust, "remote": remote,
            "asu": asu, "pil": pil, "asu_node": asu_node, "pil_node": pil_node,
            "receiver": receiver, "receiver_auth": receiver_auth, "transport": transport,
            "central_db": central_db}


def customer_payload(branch, reference, document="1234567", name="Ana López"):
    return {"customer_document": document, "customer_name": name,
            "customer_phone": "0981000000", "sale_id": f"sale-{reference}",
            "envelope": reference, "description": f"Venta {branch}", "total": 500000,
            "items": ["Armazón", "Cristales"], "prescription": ["OD -1.00", "OI -0.75"],
            "source_reference": reference}


def publish_customer_flow(node, branch, prefix, document="1234567", name="Ana López"):
    payload = customer_payload(branch, prefix, document, name)
    for kind in ("CLIENTE", "VENTA", "SOBRE", "RECETA"):
        node.publish(kind, payload, f"{kind.lower()}:{prefix}")


def test_scenarios_1_2_3_asuncion_pilar_and_global_history(ecosystem):
    publish_customer_flow(ecosystem["asu_node"], "ASUNCION", "A-1")
    publish_customer_flow(ecosystem["pil_node"], "PILAR", "P-1")
    assert ecosystem["asu_node"].resume("central", ecosystem["transport"]) == 4
    assert ecosystem["pil_node"].resume("central", ecosystem["transport"]) == 4
    rows = ecosystem["receiver"].projections()
    assert {row["branch_id"] for row in rows} == {"ASUNCION", "PILAR"}
    assert len(rows) == 8 and all(row["sync_state"] == "RECEIVED" for row in rows)

    reader = CentralHistoryReader(ecosystem["central_db"])
    principal = HistoryPrincipal("direccion", "ADMIN", "ASUNCION", frozenset({VIEW_GLOBAL}))
    result = GlobalHistoryService([reader]).search(principal, HistoryQuery(document="1234567"))
    assert result.identity_resolution == "STRONG_DOCUMENT"
    assert {event.branch for event in result.selected.events} == {"ASUNCION", "PILAR"}

    publish_customer_flow(ecosystem["asu_node"], "ASUNCION", "A-W", "", "Juan Pérez")
    publish_customer_flow(ecosystem["pil_node"], "PILAR", "P-W", "", "Juan Pérez")
    ecosystem["asu_node"].resume("central", ecosystem["transport"])
    ecosystem["pil_node"].resume("central", ecosystem["transport"])
    weak = GlobalHistoryService([reader]).search(principal, HistoryQuery(name="Juan Pérez"))
    assert weak.identity_resolution == "AMBIGUOUS" and weak.selected is None


def test_scenario_4_offline_restart_recovery(ecosystem):
    node, transport = ecosystem["asu_node"], ecosystem["transport"]
    event_id = node.publish("VENTA", customer_payload("ASUNCION", "A-OFF"), "sale:A-OFF")
    transport.online = False
    assert node.resume("central", transport) == 0
    restarted = SyncNode.secured(SyncStore(ecosystem["tmp"] / "asu-sync.sqlite3"),
                                 ecosystem["asu"].identity, ecosystem["asu"].signer)
    assert restarted.store.pending()[0].event_id == event_id
    transport.online = True
    assert restarted.resume("central", transport) == 1
    assert not restarted.store.pending()
    assert ecosystem["receiver"].projections()[0]["event_id"] == event_id


def test_scenario_5_ack_perdido_no_duplica(ecosystem):
    node, transport = ecosystem["asu_node"], ecosystem["transport"]
    event_id = node.publish("VENTA", customer_payload("ASUNCION", "A-ACK"), "sale:A-ACK")
    transport.lose_ack = True
    assert node.resume("central", transport) == 0
    assert len(ecosystem["receiver"].projections()) == 1
    assert node.resume("central", transport) == 1
    assert [row["event_id"] for row in ecosystem["receiver"].projections()] == [event_id]


def _signed_raw(installation, body):
    secret = enrollment.open_secret(
        installation.context.paths, installation.context.sealer, installation.context.fingerprint)
    request = sync_auth.SyncRequest("bc.sync.event.v1", secret.installation_id,
                                    str(body["idempotency_key"]), body)
    credential = sync_auth.issue_credential(secret, request)
    return AuthenticatedMessage(body, credential.to_envelope())


def test_scenario_6_security_a_g(ecosystem):
    node, receiver = ecosystem["asu_node"], ecosystem["receiver"]
    node.publish("VENTA", customer_payload("ASUNCION", "SEC"), "sale:SEC")
    body = node.store.pending()[0].wire_dict()
    valid = ecosystem["asu"].signer.sign_event(body)
    assert receiver.receive(valid) is True                                      # A

    with ecosystem["remote"]._connect() as db:
        row = db.execute("SELECT envelope_json FROM remote_sync_licenses WHERE installation_id=?",
                         (body["installation_id"],)).fetchone()
        broken_license = json.loads(row[0]); broken_license["signature"] = "AA"
        db.execute("UPDATE remote_sync_licenses SET envelope_json=? WHERE installation_id=?",
                   (json.dumps(broken_license), body["installation_id"])); db.commit()
    with pytest.raises(Exception):
        receiver.receive(ecosystem["asu"].signer.sign_event({**body, "event_id": "bad-license"}))  # B
    ecosystem["remote"].install_verified_license(ecosystem["asu"].license_envelope)

    revoked = issuer.issue_revocations(
        ecosystem["issuer"], serial=1, revoked_installations=[body["installation_id"]])
    ecosystem["remote"].install_verified_revocations(revoked.to_envelope())
    with pytest.raises(SecurityAuthorizationError, match="revocada"):
        receiver.receive(ecosystem["asu"].signer.sign_event({**body, "event_id": "revoked"}))       # C
    clean = issuer.issue_revocations(ecosystem["issuer"], serial=2)
    ecosystem["remote"].install_verified_revocations(clean.to_envelope())

    message = ecosystem["asu"].signer.sign_event({**body, "event_id": "tamper"})
    with pytest.raises(Exception):
        receiver.receive(AuthenticatedMessage({**message.body, "payload": {"total": 1}},
                                              message.credential))                 # D/G
    replay = ecosystem["asu"].signer.sign_event({**body, "event_id": "replay", "idempotency_key": "replay"})
    assert receiver.receive(replay)
    with pytest.raises(Exception):
        receiver.receive(replay)                                                   # E
    mismatch = {**body, "event_id": "branch", "idempotency_key": "branch", "branch_id": "PILAR"}
    with pytest.raises(SecurityAuthorizationError, match="branch"):
        receiver.receive(_signed_raw(ecosystem["asu"], mismatch))                 # F
    false_id = {**body, "event_id": "false", "idempotency_key": "false",
                "installation_id": "autodeclarada"}
    with pytest.raises(SecurityAuthorizationError, match="autodeclarado"):
        receiver.receive(_signed_raw(ecosystem["asu"], false_id))                 # G
    assert len({row["event_id"] for row in receiver.projections()}) == len(receiver.projections())


def test_scenario_7_factufacil_transitorio(ecosystem):
    node = ecosystem["asu_node"]
    queue = BillingQueue(ecosystem["tmp"] / "billing.sqlite3", state_publisher=node.publish)
    billing_id = queue.register(
        sale_id="sale-f1", branch_id="ASUNCION", envelope="A-F1", customer_name="Ana",
        tax_id="1234567-8", sold_at="2026-08-21T10:00:00+00:00", totals={"total": 550000},
        tax={"iva_10": 50000}, invoice_mode="CONTADO", responsible="sol",
        idempotency_key="invoice:sale-f1")
    node.resume("central", ecosystem["transport"])
    assert any(row["factufacil_state"] == "PENDIENTE_FACTU_FACIL"
               for row in ecosystem["receiver"].factufacil())
    queue.process(billing_id, AssistedFactuFacilAdapter())
    queue.mark_loaded(billing_id, "001-001-0000999", "sol")
    node.resume("central", ecosystem["transport"])
    loaded = [row for row in ecosystem["receiver"].factufacil()
              if row["factufacil_state"] == "CARGADA"]
    assert loaded[0]["invoice_number"] == "001-001-0000999"
    assert node.resume("central", ecosystem["transport"]) == 0

    retry_id = queue.register(
        sale_id="sale-f2", branch_id="ASUNCION", envelope="A-F2", customer_name="Ana",
        tax_id="1234567-8", sold_at="2026-08-21T11:00:00+00:00", totals={"total": 110000},
        tax={"iva_10": 10000}, invoice_mode="CONTADO", responsible="sol",
        idempotency_key="invoice:sale-f2")
    with pytest.raises(RuntimeError):
        queue.process(retry_id, DisabledFactuFacilAdapter())
    queue.transition(retry_id, "REINTENTAR", "sol")
    queue.process(retry_id, AssistedFactuFacilAdapter())
    queue.mark_loaded(retry_id, "001-001-0001000", "sol")
    node.resume("central", ecosystem["transport"])
    states = {row["factufacil_state"] for row in ecosystem["receiver"].factufacil()}
    assert {"ERROR", "REINTENTAR", "CARGADA"} <= states
    assert len({row["event_id"] for row in ecosystem["receiver"].factufacil()}) == len(
        ecosystem["receiver"].factufacil())


def test_scenarios_8_9_full_restart_and_privileges(ecosystem):
    node, transport = ecosystem["pil_node"], ecosystem["transport"]
    publish_customer_flow(node, "PILAR", "P-RESTART")
    transport.online = False; node.resume("central", transport)
    restarted_node = SyncNode.secured(SyncStore(ecosystem["tmp"] / "pil-sync.sqlite3"),
                                      ecosystem["pil"].identity, ecosystem["pil"].signer)
    restarted_receiver = CentralSyncInbox(ecosystem["central_db"], ecosystem["receiver_auth"])
    restarted_transport = CentralTransport(restarted_receiver)
    assert restarted_node.resume("central", restarted_transport) == 4
    assert len(restarted_receiver.projections()) == 4

    reader = CentralHistoryReader(ecosystem["central_db"])
    service = GlobalHistoryService([reader])
    admin = HistoryPrincipal("direccion", "ADMIN", "ASUNCION", frozenset({VIEW_GLOBAL}))
    assert service.search(admin, HistoryQuery(document="1234567")).selected is not None
    policy = HistoryAccessPolicy()
    operator = HistoryPrincipal("operador", "OPERADOR", "ASUNCION", frozenset({VIEW_GLOBAL}))
    assert policy.can_modify_branch(operator, "ASUNCION")
    assert not policy.can_modify_branch(operator, "PILAR")
    assert policy.can_modify_branch(admin, "PILAR")
    assert any("mode=ro" in value for value in CentralHistoryReader.search.__code__.co_consts
               if isinstance(value, str))
