from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, CashDay
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository


ASUNCION = BUSINESS_TIMEZONE


class SessionHoursTests(unittest.TestCase):
    def make_day(self, business_date: str, opened: tuple[int, int]) -> CashDay:
        parsed = datetime.strptime(business_date, "%Y-%m-%d").date()
        return CashDay(
            business_date=parsed,
            unit="PC",
            opening_cash=0,
            opened_at=datetime(parsed.year, parsed.month, parsed.day, *opened, tzinfo=ASUNCION),
        )

    def test_weekday_tolerance_does_not_trigger_overtime(self):
        day = self.make_day("2026-08-10", (8, 0))
        day.close(closed_at=datetime(2026, 8, 10, 18, 10, tzinfo=ASUNCION))
        self.assertEqual(day.session_duration_seconds, 10 * 60 * 60 + 10 * 60)
        self.assertFalse(day.overtime_triggered)
        self.assertEqual(day.overtime_minutes, 0)

    def test_weekday_after_tolerance_records_confirmed_minimum_only(self):
        day = self.make_day("2026-08-10", (8, 0))
        day.close(closed_at=datetime(2026, 8, 10, 18, 11, tzinfo=ASUNCION))
        self.assertTrue(day.overtime_triggered)
        self.assertEqual(day.overtime_minutes, 60)

    def test_saturday_uses_1210_tolerance(self):
        at_limit = self.make_day("2026-08-15", (8, 0))
        at_limit.close(closed_at=datetime(2026, 8, 15, 12, 10, tzinfo=ASUNCION))
        after = self.make_day("2026-08-22", (8, 0))
        after.close(closed_at=datetime(2026, 8, 22, 12, 11, tzinfo=ASUNCION))
        self.assertFalse(at_limit.overtime_triggered)
        self.assertTrue(after.overtime_triggered)
        self.assertEqual(after.overtime_minutes, 60)

    def test_sunday_is_explicitly_pending_policy(self):
        day = self.make_day("2026-08-16", (8, 0))
        day.close(closed_at=datetime(2026, 8, 16, 13, 0, tzinfo=ASUNCION))
        self.assertIsNone(day.overtime_triggered)
        self.assertIsNone(day.overtime_minutes)

    def test_session_hours_survive_sqlite_reload(self):
        with tempfile.TemporaryDirectory() as tempdir:
            repository = SQLiteCashDayRepository(Path(tempdir) / "caja.sqlite3")
            day = self.make_day("2026-08-10", (8, 0))
            day.close(closed_at=datetime(2026, 8, 10, 18, 11, tzinfo=ASUNCION))
            repository.save(day)
            loaded = repository.get(day.id)
            repository.close()
        self.assertEqual(loaded.opened_at, day.opened_at)
        self.assertEqual(loaded.closed_at, day.closed_at)
        self.assertEqual(loaded.session_duration_seconds, day.session_duration_seconds)
        self.assertTrue(loaded.overtime_triggered)
        self.assertEqual(loaded.overtime_minutes, 60)


if __name__ == "__main__":
    unittest.main()
