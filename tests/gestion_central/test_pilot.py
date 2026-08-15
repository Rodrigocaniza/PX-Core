from datetime import timedelta

import pytest

from modulos.gestion_central.models import CashSnapshot, Principal, Role, Unit, utc_now
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied, CentralManagementService


@pytest.fixture
def service(tmp_path):
    return CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))


def snapshot(unit=Unit.OPTICA_ASUNCION, event_id="event-1", **changes):
    values = dict(
        event_id=event_id, unit=unit, business_date="2099-01-15", status="OPEN",
        opening_cash=500_000, income=800_000, cash=500_000, card_check=300_000,
        expenses=50_000, withdrawals=25_000, expected_cash=925_000,
        counted_cash=None, entry_count=5, source_updated_at=utc_now(),
    )
    values.update(changes)
    return CashSnapshot(**values)


def test_pilot_bootstrap_has_exactly_four_synthetic_units(service):
    service.bootstrap_synthetic_pilot()
    admin = service.authenticate("admin.piloto", "Piloto-Temporal-2026")
    dashboard = service.dashboard(admin)
    assert [card["unit"] for card in dashboard["cards"]] == list(Unit)
    assert all(card["snapshot"]["business_date"] == "2099-01-15" for card in dashboard["cards"])


def test_sync_is_idempotent_and_rejects_event_mutation(service):
    operator = Principal("operador", Role.OPERADOR_LOCAL, Unit.OPTICA_ASUNCION)
    assert service.ingest_snapshot(operator, snapshot()) is True
    assert service.ingest_snapshot(operator, snapshot()) is False
    with pytest.raises(ValueError, match="event_id reutilizado"):
        service.ingest_snapshot(operator, snapshot(income=999))


def test_local_operator_cannot_write_or_view_other_unit(service):
    operator = Principal("operador", Role.OPERADOR_LOCAL, Unit.OPTICA_ASUNCION)
    with pytest.raises(AccessDenied):
        service.ingest_snapshot(operator, snapshot(Unit.OPTICA_PILAR))
    assert [card["unit"] for card in service.dashboard(operator)["cards"]] == [Unit.OPTICA_ASUNCION]


def test_auditor_is_read_only(service):
    auditor = Principal("auditor", Role.AUDITOR)
    with pytest.raises(AccessDenied):
        service.acknowledge_alert(auditor, "missing")
    with pytest.raises(AccessDenied):
        service.create_user(auditor, "nuevo", "Password-Temporal", Role.SUPERVISOR)


def test_stale_and_cash_difference_alerts_are_generated_and_acknowledged(service):
    admin = Principal("admin", Role.ADMIN_CENTRAL)
    old = utc_now() - timedelta(minutes=20)
    service.ingest_snapshot(admin, snapshot(source_updated_at=old, counted_cash=900_000))
    service.refresh_alerts(admin)
    alerts = service.repository.alerts()
    kinds = {(alert.unit, alert.kind) for alert in alerts}
    assert (Unit.OPTICA_ASUNCION, "SYNC_STALE") in kinds
    assert (Unit.OPTICA_ASUNCION, "CASH_DIFFERENCE") in kinds
    selected = next(alert for alert in alerts if alert.kind == "CASH_DIFFERENCE")
    service.acknowledge_alert(admin, selected.id)
    assert selected.id not in {alert.id for alert in service.repository.alerts()}


def test_users_are_hashed_and_actions_audited(service):
    admin = Principal("admin", Role.ADMIN_CENTRAL)
    service.create_user(admin, "supervisor", "Clave-Segura-2026", Role.SUPERVISOR)
    assert service.authenticate("supervisor", "Clave-Segura-2026").role == Role.SUPERVISOR
    with service.repository.connection() as con:
        row = con.execute("SELECT password_hash FROM central_users WHERE username='supervisor'").fetchone()
    assert row["password_hash"] != "Clave-Segura-2026"
    assert {entry["action"] for entry in service.repository.audit_log()} >= {"USER_CREATE", "LOGIN"}
