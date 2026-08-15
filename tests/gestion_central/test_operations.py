from datetime import timedelta

import pytest

from modulos.gestion_central.models import CashSnapshot, Principal, Role, Unit, utc_now
from modulos.gestion_central.operations import ALERT_STATES, DateRange, OperationsService
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied, CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)


@pytest.fixture
def operations(tmp_path):
    core = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    for index, day in enumerate(("2099-03-01", "2099-03-02")):
        core.ingest_snapshot(SOL, CashSnapshot(
            f"event-{index}", Unit.OPTICA_ASUNCION, day, "CLOSED", 500000,
            1000000 + index, 600000, 400000, 50000, 25000, 1025000,
            1024000 if index else 1025000, 4, utc_now() - (timedelta(minutes=20) if index else timedelta()),
        ))
    return core, OperationsService(core)


def test_range_summary_and_daily_statuses(operations):
    _, service = operations
    period = DateRange("2099-03-01", "2099-03-02")
    card = service.summary(SOL, period)[0]
    assert (card["days"], card["income"], card["differences"]) == (2, 2000001, 1)
    daily = service.daily(SOL, Unit.OPTICA_ASUNCION, period)
    assert {row["completeness"] for row in daily} == {"COMPLETO"}
    assert any(row["conflict"] for row in daily)


def test_alert_state_machine_and_audit(operations):
    core, service = operations
    alert = service.alerts(SOL, include_closed=False)[0]
    for state in ("VISTO", "CORREGIDO", "VERIFICADO"):
        service.transition_alert(SOL, alert["id"], state)
    assert set(ALERT_STATES) == {"PENDIENTE", "VISTO", "CORREGIDO", "VERIFICADO", "DESCARTADO"}
    assert alert["id"] not in {row["id"] for row in service.alerts(SOL, include_closed=False)}
    assert any(row["action"] == "ALERT_TRANSITION" for row in core.repository.audit_log())


def test_messages_are_local_idempotent_outbox_and_permission_bound(operations):
    core, service = operations
    first = service.queue_message(SOL, Unit.OPTICA_ASUNCION, "Revisar arqueo", "CAJA-01")
    second = service.queue_message(SOL, Unit.OPTICA_ASUNCION, "Revisar arqueo", "CAJA-01")
    assert first == second
    with core.repository.connection() as con:
        assert con.execute("SELECT count(*) FROM central_messages").fetchone()[0] == 1
        assert con.execute("SELECT status FROM central_outbox").fetchone()[0] == "PENDING"
    with pytest.raises(AccessDenied):
        service.queue_message(Principal("audit", Role.AUDITOR), Unit.OPTICA_ASUNCION, "No")


def test_invalid_range_and_transition_are_rejected(operations):
    _, service = operations
    with pytest.raises(ValueError): DateRange("2099-03-02", "2099-03-01")
    alert = service.alerts(SOL)[0]
    with pytest.raises(ValueError): service.transition_alert(SOL, alert["id"], "VERIFICADO")


def test_daily_review_covers_closure_sales_outflows_cash_and_pdf(operations):
    _, service = operations
    fields = {"CIERRE", "VENTAS_SOBRES", "SALIDAS", "ARQUEO", "PDF"}
    assert service.mark_daily_fields(SOL, Unit.OPTICA_ASUNCION, "2099-03-02", fields) == fields
    assert service.reviewed_daily_fields(SOL, Unit.OPTICA_ASUNCION, "2099-03-02") == fields
