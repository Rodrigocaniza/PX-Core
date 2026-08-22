from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from modulos.bc_sync.history_reader import SyncedHistoryReader
from modulos.bc_sync.security import SignedMessage
from modulos.bc_sync.service import SyncNode
from modulos.bc_sync.store import ReplayDetected, SyncStore
from modulos.historial_externo.global_history import GlobalHistoryService, HistoryPrincipal, VIEW_GLOBAL
from modulos.historial_externo.history import HistoryQuery


class TestSecurityAdapter:
    __test__ = False
    def __init__(self, installation_keys):
        self.keys = installation_keys
        self.revoked = set()

    @staticmethod
    def _data(installation_id, nonce, timestamp, body):
        return json.dumps([installation_id, nonce, timestamp, body], sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False).encode()

    def sign(self, installation_id, body):
        nonce, timestamp = str(uuid4()), datetime.now(timezone.utc).isoformat()
        signature = hmac.new(self.keys[installation_id], self._data(
            installation_id, nonce, timestamp, body), hashlib.sha256).hexdigest()
        return SignedMessage(installation_id, nonce, timestamp, body, signature)

    def verify(self, message):
        expected = hmac.new(self.keys[message.installation_id], self._data(
            message.installation_id, message.nonce, message.timestamp, message.body),
            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, message.signature):
            raise PermissionError("firma inválida")

    def is_revoked(self, installation_id):
        return installation_id in self.revoked


class Network:
    def __init__(self):
        self.nodes = {}
        self.online = True
        self.lose_next_response = False

    def send(self, target, message):
        if not self.online:
            raise ConnectionError("offline")
        self.nodes[target].receive(message)
        if self.lose_next_response:
            self.lose_next_response = False
            raise TimeoutError("respuesta perdida")


@pytest.fixture
def network_pair(tmp_path):
    security = TestSecurityAdapter({"inst-asu": b"key-asu", "inst-pil": b"key-pil"})
    asu_store = SyncStore(tmp_path / "asu-sync.sqlite3")
    pil_store = SyncStore(tmp_path / "pil-sync.sqlite3")
    asu = SyncNode("inst-asu", "ASUNCION", asu_store, security)
    pil = SyncNode("inst-pil", "PILAR", pil_store, security)
    network = Network(); network.nodes = {"asu": asu, "pil": pil}
    return asu, pil, network


def sale_payload(reference, document="1234567"):
    return {"customer_document": document, "customer_name": "Ana López",
            "customer_phone": "0981000000", "envelope": reference,
            "description": "Compra", "items": ["Armazón", "Cristales"],
            "prescription": ["OD -1.00"], "total": 500000,
            "source_reference": reference}


def test_a_b_c_d_e_f_g_h_i_j_offline_restart_retry_and_global_history(network_pair, tmp_path):
    asu, pil, network = network_pair
    network.online = False
    event_id = asu.publish("COMPRA", sale_payload("A-1"), "sale:A-1")  # A, B
    assert [event.event_id for event in asu.store.pending()] == [event_id]

    restarted = SyncNode("inst-asu", "ASUNCION", SyncStore(tmp_path / "asu-sync.sqlite3"), asu.security)
    network.nodes["asu"] = restarted                              # C
    assert restarted.store.pending()[0].event_id == event_id
    assert restarted.resume("pil", network) == 0

    network.online = True                                         # D
    assert restarted.resume("pil", network) == 1                 # E, F
    assert len(pil.store.events()) == 1
    assert restarted.resume("pil", network) == 0                 # G

    second_id = restarted.publish("RECETA", sale_payload("A-2"), "rx:A-2")
    network.lose_next_response = True
    assert restarted.resume("pil", network) == 0                 # H: entregó, perdió ACK
    assert second_id in {event.event_id for event in pil.store.events()}
    assert restarted.resume("pil", network) == 1
    assert len({event.event_id for event in pil.store.events()}) == 2

    pil.publish("SOBRE", sale_payload("P-1"), "envelope:P-1")     # I
    assert pil.resume("asu", network) == 1
    reader = SyncedHistoryReader(restarted.store)
    principal = HistoryPrincipal("director", "ADMIN", "ASUNCION", frozenset({VIEW_GLOBAL}))
    result = GlobalHistoryService([reader]).search(principal, HistoryQuery(document="1234567"))
    assert {event.branch for event in result.selected.events} == {"ASUNCION", "PILAR"}  # J
    assert {event.kind for event in result.selected.events} >= {"COMPRA", "RECETA", "SOBRE"}


def test_event_and_idempotency_keys_prevent_duplicates(network_pair):
    asu, pil, network = network_pair
    first = asu.publish("EVENTO", sale_payload("A-1"), "stable-key")
    assert asu.publish("EVENTO", sale_payload("A-1"), "stable-key") == first
    asu.resume("pil", network)
    assert len(pil.store.events()) == 1


def test_replay_nonce_and_revocation_are_enforced(network_pair):
    asu, pil, _ = network_pair
    event_id = asu.publish("EVENTO", sale_payload("A-1"), "event:A-1")
    event = asu.store.pending()[0]
    signed = asu.security.sign("inst-asu", event.wire_dict())
    assert pil.receive(signed)
    with pytest.raises(ReplayDetected):
        pil.receive(signed)
    asu.security.revoked.add("inst-asu")
    newer = asu.security.sign("inst-asu", {**event.wire_dict(), "event_id": str(uuid4()),
                                            "idempotency_key": event_id + ":new"})
    with pytest.raises(PermissionError, match="revocada"):
        pil.receive(newer)


def test_distinct_facts_are_preserved_and_real_conflict_is_explicit(network_pair):
    asu, pil, network = network_pair
    asu.publish("COMPRA", sale_payload("A-1"), "sale:A-1")
    pil.publish("COMPRA", sale_payload("P-1"), "sale:P-1")
    asu.resume("pil", network); pil.resume("asu", network)
    assert len(asu.store.events()) == len(pil.store.events()) == 2
    asu.store.record_conflict("customer:1234567", asu.store.events()[0].event_id,
                              asu.store.events()[1].event_id)
    with asu.store.connect() as db:
        conflict = db.execute("SELECT * FROM sync_conflicts").fetchone()
    assert conflict["state"] == "OPEN" and conflict["resolution"] is None
    asu.store.resolve_conflict(conflict["conflict_id"], "conservar ambos y corregir identidad")
    with asu.store.connect() as db:
        resolved = db.execute("SELECT * FROM sync_conflicts").fetchone()
    assert resolved["state"] == "RESOLVED"
    assert "CONFLICT_RESOLVED" in {row["action"] for row in asu.store.audit()}


def test_audit_covers_send_receive_failure_and_ack(network_pair):
    asu, pil, network = network_pair
    asu.publish("EVENTO", sale_payload("A-1"), "event:A-1")
    network.online = False; asu.resume("pil", network)
    network.online = True; asu.resume("pil", network)
    assert {row["action"] for row in asu.store.audit()} >= {
        "OUTBOX_ENQUEUED", "SEND_ATTEMPT", "SEND_FAILED", "SEND_ACKNOWLEDGED"}
    assert "RECEIVED" in {row["action"] for row in pil.store.audit()}
