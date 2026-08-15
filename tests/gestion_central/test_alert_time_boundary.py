from datetime import datetime, timezone

from modulos.gestion_central.models import CashSnapshot, Principal, Role, Unit
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


def test_late_open_applies_only_to_current_business_day(tmp_path):
    service = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    actor = Principal("admin", Role.ADMIN_CENTRAL)
    at_night = datetime(2026, 8, 15, 22, 30, tzinfo=timezone.utc)
    service.ingest_snapshot(actor, CashSnapshot("future", Unit.OPTICA_ASUNCION, "2099-01-15", "OPEN", 1, 1, 1, 0, 0, 0, 2, None, 1, at_night))
    service.refresh_alerts(actor, now=at_night)
    assert "LATE_OPEN" not in {alert.kind for alert in service.repository.alerts()}
