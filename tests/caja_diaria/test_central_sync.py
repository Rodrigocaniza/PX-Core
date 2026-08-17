import tempfile
from pathlib import Path

import pytest

from modulos.caja_diaria.central_sync import CentralSyncOutbox, SyncConflict


def close_event(**changes):
    payload = {
        "schema_version": "bc.cash.close.v1",
        "event_id": "close-demo-001",
        "organization_id": "org-demo-001",
        "branch_id": "branch-demo-001",
        "cashbox_id": "cashbox-demo-001",
        "device_id": "device-demo-001",
        "cash_day_id": "cash-day-demo-001",
        "operator_id": "operator-demo-001",
        "closed_at": "2026-08-15T20:00:00Z",
        "expected_cash_pyg": 600000,
        "counted_cash_pyg": 590000,
        "difference_pyg": -10000,
        "document_id": "document-demo-001",
    }
    payload.update(changes)
    return payload


def test_outbox_is_durable_idempotent_and_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "outbox.sqlite3"
        first = CentralSyncOutbox(path)
        assert first.enqueue_close(close_event()) is True
        assert first.enqueue_close(close_event()) is False
        first.record_attempt("close-demo-001")
        restarted = CentralSyncOutbox(path)
        assert restarted.pending()[0].attempts == 1
        with pytest.raises(SyncConflict):
            restarted.enqueue_close(close_event(difference_pyg=-20000))
        restarted.mark_delivered("close-demo-001", "2026-08-15T20:01:00Z")
        assert restarted.pending() == []
