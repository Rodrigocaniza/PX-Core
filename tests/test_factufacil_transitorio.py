from __future__ import annotations

import pytest

from modulos.bc_sync.factufacil import (
    AssistedFactuFacilAdapter, BillingQueue, CARGADA, DisabledFactuFacilAdapter,
    ERROR, PENDIENTE,
)
from modulos.bc_sync.service import SyncNode
from modulos.bc_sync.store import SyncStore
from tests.test_bc_sync_v1 import Network, TestSecurityAdapter


def request(queue, key="invoice:sale-1"):
    return queue.register(sale_id="sale-1", branch_id="ASUNCION", envelope="A-1",
                          customer_name="Ana", tax_id="1234567-8",
                          sold_at="2026-08-21T10:00:00Z", totals={"total": 110000},
                          tax={"iva_10": 10000}, invoice_mode="CONTADO",
                          responsible="sol", idempotency_key=key)


def test_a_b_pending_enters_once_and_retry_does_not_duplicate(tmp_path):
    queue = BillingQueue(tmp_path / "billing.sqlite3")
    billing_id = request(queue)
    assert request(queue) == billing_id
    assert len(queue.pending()) == 1 and queue.get(billing_id).state == PENDIENTE
    queue.process(billing_id, AssistedFactuFacilAdapter())
    queue.transition(billing_id, "REINTENTAR", "sol")
    queue.process(billing_id, AssistedFactuFacilAdapter())
    with queue._connect() as db:
        assert db.execute("SELECT count(*) FROM billing_queue").fetchone()[0] == 1


def test_c_d_loaded_state_and_invoice_number_sync_to_central(tmp_path):
    security = TestSecurityAdapter({"asu": b"asu", "central": b"central"})
    asu = SyncNode("asu", "ASUNCION", SyncStore(tmp_path / "asu.sqlite3"), security)
    central = SyncNode("central", "CENTRAL", SyncStore(tmp_path / "central.sqlite3"), security)
    network = Network(); network.nodes = {"central": central}
    queue = BillingQueue(tmp_path / "billing.sqlite3", state_publisher=asu.publish)
    billing_id = request(queue)
    queue.mark_loaded(billing_id, "001-001-0000123", "sol")
    assert asu.resume("central", network) == 2
    loaded = [event for event in central.store.events()
              if event.payload.get("state") == CARGADA][0]
    assert loaded.payload["sale_id"] == "sale-1"
    assert loaded.payload["invoice_number"] == "001-001-0000123"


def test_e_error_is_traced(tmp_path):
    queue = BillingQueue(tmp_path / "billing.sqlite3")
    billing_id = request(queue)
    with pytest.raises(RuntimeError):
        queue.process(billing_id, DisabledFactuFacilAdapter())
    assert queue.get(billing_id).state == ERROR
    assert any("desactivado" in row["detail"] for row in queue.audit(billing_id))


def test_f_offline_billing_state_recovers_from_sync_outbox(tmp_path):
    security = TestSecurityAdapter({"asu": b"asu", "central": b"central"})
    asu = SyncNode("asu", "ASUNCION", SyncStore(tmp_path / "asu.sqlite3"), security)
    central = SyncNode("central", "CENTRAL", SyncStore(tmp_path / "central.sqlite3"), security)
    network = Network(); network.nodes = {"central": central}; network.online = False
    queue = BillingQueue(tmp_path / "billing.sqlite3", state_publisher=asu.publish)
    request(queue)
    assert asu.resume("central", network) == 0 and len(asu.store.pending()) == 1
    network.online = True
    assert asu.resume("central", network) == 1 and len(central.store.events()) == 1


def test_g_disabled_adapter_does_not_break_bc(tmp_path):
    queue = BillingQueue(tmp_path / "billing.sqlite3")
    billing_id = request(queue)
    with pytest.raises(RuntimeError):
        queue.process(billing_id, DisabledFactuFacilAdapter())
    assert queue.get(billing_id).sale_id == "sale-1"
    replacement = queue.process(billing_id, AssistedFactuFacilAdapter())
    assert replacement["mode"] == "ASSISTED"
