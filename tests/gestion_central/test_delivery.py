from datetime import timedelta
from pathlib import Path

import pytest

from modulos.gestion_central.delivery import DELIVERY_STATES, DeliveryService, DeterministicLocalTransport
from modulos.gestion_central.models import Principal, Role, Unit, utc_now
from modulos.gestion_central.operations import OperationsService
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied, CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)
AUDITOR = Principal("audit", Role.AUDITOR)


@pytest.fixture
def delivery(tmp_path):
    core = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    return core, DeliveryService(core)


def test_complete_delivery_and_ack_are_idempotent(delivery):
    core, service = delivery
    first = service.queue(SOL, Unit.OPTICA_ASUNCION, "Confirmar cierre", "CAJA-01")
    second = service.queue(SOL, Unit.OPTICA_ASUNCION, "Confirmar cierre", "CAJA-01")
    assert first == second
    processed = service.process_due(SOL, auto_ack=False)
    receipt = processed[0][1].receipt
    assert service.list_messages(SOL)[0]["state"] == "ENTREGADO"
    assert service.accept_ack(SOL, receipt) is True
    assert service.accept_ack(SOL, receipt) is False
    row = service.list_messages(SOL)[0]
    assert row["state"] == "CONFIRMADO" and row["attempts"] == 1
    history = service.history(SOL, row["id"])
    assert [event["to_state"] for event in history] == ["PENDIENTE", "ENVIANDO", "ENTREGADO", "CONFIRMADO"]
    with core.repository.connection() as con:
        assert con.execute("SELECT count(*) FROM simulated_receiver_inbox").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM message_receipts").fetchone()[0] == 1
        envelope = con.execute("SELECT envelope_json FROM simulated_receiver_inbox").fetchone()[0]
    assert '"target":{"pc":"CAJA-01","unit":"OPTICA_ASUNCION"}' in envelope
    assert '"unit":"OPTICA_ASUNCION","pc"' not in envelope


def test_transient_retries_backoff_without_receiver_duplicates(delivery):
    _, service = delivery
    message_id, _ = service.queue(SOL, Unit.OPTICA_PILAR, "Esperar equipo", "OFFLINE-01")
    start = utc_now()
    for attempt, seconds in enumerate((0, 5, 20, 80), start=1):
        service.process_due(SOL, now=start + timedelta(seconds=seconds))
        row = service.list_messages(SOL)[0]
        assert row["attempts"] == attempt
    assert row["state"] == "FALLIDO" and row["error_code"] == "TRANSIENT_OFFLINE"
    assert len(service.history(SOL, message_id)) == 9  # queue + 4 sending + 4 outcomes


def test_permanent_failure_and_audited_manual_cancellation(delivery):
    core, service = delivery
    failed, _ = service.queue(SOL, Unit.CONSULTORIO_ASUNCION, "Destino inválido", "UNKNOWN-01")
    service.process_due(SOL)
    assert service.list_messages(SOL)[0]["state"] == "FALLIDO"
    service.cancel(SOL, failed, "PC sintética retirada")
    row = service.list_messages(SOL)[0]
    assert row["state"] == "CANCELADO" and row["cancel_reason"] == "PC sintética retirada"
    assert service.history(SOL, failed)[-1]["to_state"] == "CANCELADO"
    with core.repository.connection() as con:
        assert con.execute("SELECT status FROM central_outbox WHERE aggregate_id=?", (failed,)).fetchone()[0] == "CANCELLED"


def test_abandoned_send_recovers_and_deduplicates_after_restart(delivery):
    core, service = delivery
    message_id, _ = service.queue(SOL, Unit.OPTICA_ASUNCION, "Recuperar", "CAJA-02")
    old = utc_now() - timedelta(minutes=5)
    with core.repository.connection() as con:
        con.execute("UPDATE message_delivery SET state='ENVIANDO',attempts=1,last_attempt_at=? WHERE message_id=?", (old.isoformat(), message_id)); con.commit()
    restarted = DeliveryService(CentralManagementService(CentralRepository(core.repository.database_path)), DeterministicLocalTransport(core.repository))
    assert restarted.recover_abandoned(SOL) == 1
    assert restarted.list_messages(SOL)[0]["state"] == "REINTENTO"
    restarted.process_due(SOL)
    assert restarted.list_messages(SOL)[0]["state"] == "CONFIRMADO"
    with core.repository.connection() as con: assert con.execute("SELECT count(*) FROM simulated_receiver_inbox").fetchone()[0] == 1


def test_filters_permissions_and_state_contract(delivery):
    _, service = delivery
    service.queue(SOL, Unit.OPTICA_ASUNCION, "Uno", "CAJA-01")
    service.queue(SOL, Unit.OPTICA_PILAR, "Dos", "CAJA-02")
    assert set(DELIVERY_STATES) == {"PENDIENTE", "ENVIANDO", "ENTREGADO", "CONFIRMADO", "REINTENTO", "FALLIDO", "CANCELADO"}
    assert len(service.list_messages(SOL, unit=Unit.OPTICA_PILAR, pc="02", state="PENDIENTE")) == 1
    assert len(service.list_messages(AUDITOR)) == 2
    with pytest.raises(AccessDenied): service.process_due(AUDITOR)
    with pytest.raises(AccessDenied): service.list_messages(Principal("local", Role.OPERADOR_LOCAL, Unit.OPTICA_ASUNCION))


def test_transport_module_has_no_external_network_or_secrets():
    source = Path("modulos/gestion_central/delivery.py").read_text(encoding="utf-8").lower()
    for forbidden in ("requests", "smtplib", "telegram", "http://", "https://", "password", "token"):
        assert forbidden not in source


def test_queue_is_atomic_under_fault_injection(delivery, monkeypatch):
    core, service = delivery
    original = core.repository.audit
    def fail_before_commit(*args, **kwargs):
        raise RuntimeError("synthetic abrupt stop")
    monkeypatch.setattr(core.repository, "audit", fail_before_commit)
    with pytest.raises(RuntimeError, match="abrupt stop"):
        service.queue(SOL, Unit.OPTICA_ASUNCION, "No debe quedar parcial", "CAJA-09")
    monkeypatch.setattr(core.repository, "audit", original)
    with core.repository.connection() as con:
        assert con.execute("SELECT count(*) FROM central_messages").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM central_outbox").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM message_delivery").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM message_delivery_history").fetchone()[0] == 0


def test_preexisting_message_is_reconciled_and_visible(tmp_path):
    core = CentralManagementService(CentralRepository(tmp_path / "legacy.sqlite3"))
    message_id, _ = OperationsService(core).queue_message(SOL, Unit.OPTICA_PILAR, "Fila heredada", "CAJA-LEGACY")
    with core.repository.connection() as con:
        assert not con.execute("SELECT 1 FROM message_delivery WHERE message_id=?", (message_id,)).fetchone()
    service = DeliveryService(core)
    row = service.list_messages(SOL)[0]
    assert row["id"] == message_id and row["state"] == "PENDIENTE"
    assert service.history(SOL, message_id)[0]["actor"] == "SYSTEM_RECOVERY"
