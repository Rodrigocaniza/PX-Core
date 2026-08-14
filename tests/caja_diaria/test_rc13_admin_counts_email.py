import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import CashEntry


SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_operator_navigation_and_mandatory_count_contracts():
    assert 'if nombre in ("Arqueo", "Importar Excel"):' in SOURCE
    assert 'text="Administrador"' in SOURCE
    assert 'La importación requiere una sesión administrativa.' in SOURCE
    assert 'solicitar_conteo_obligatorio("Arqueo de apertura")' in SOURCE
    assert '"Arqueo de cierre", esperado=totales.expected_cash' in SOURCE
    assert 'campos_manual["caja_inicial"].bind("<Key>"' in SOURCE
    assert 'controller.admin.close_with_count(' in SOURCE


class RC13AdminCountsEmailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.controller = build_cash_day_controller(self.root / "bc_caja.sqlite3")

    def tearDown(self):
        self.controller.service.repository.close()
        self.temp.cleanup()

    def test_015_upgrade_is_idempotent_wal_full_and_integrity_ok(self):
        self.controller.service.repository.migrate()
        with self.controller.service.repository._connection() as connection:
            versions = [row[0] for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )]
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(versions[-1], "015")
        self.assertEqual(len(versions), 15)
        self.assertTrue({"admin_users", "admin_audit_log", "cash_count_snapshots", "mail_outbox"} <= tables)
        self.assertEqual(journal.lower(), "wal")
        self.assertEqual(synchronous, 2)
        self.assertEqual(integrity, "ok")

    def test_admin_hash_login_lockout_settings_and_no_plaintext_secret(self):
        self.assertFalse(self.controller.admin.has_admin())
        session = self.controller.admin.create_initial_admin("adminlocal", "Clave-Segura-2026")
        self.assertTrue(self.controller.admin.require(session.token))
        with self.controller.service.repository._connection() as connection:
            row = connection.execute("SELECT * FROM admin_users").fetchone()
        self.assertNotIn("Clave-Segura-2026", row["password_hash"])
        self.assertGreaterEqual(row["iterations"], 100_000)
        with self.assertRaises(InvalidCashDayError):
            self.controller.admin.authenticate("adminlocal", "incorrecta")
        with self.controller.service.repository._connection() as connection:
            row = connection.execute("SELECT failed_attempts,locked_until FROM admin_users").fetchone()
        self.assertEqual(row["failed_attempts"], 1)
        self.assertTrue(row["locked_until"])
        self.controller.admin.update_setting(session.token, "counting", {
            "blind_close": True, "tolerance": 1000, "reason_mode": "ANY_DIFFERENCE", "admin_limit": 5000,
        })
        self.assertEqual(self.controller.admin.setting("counting")["tolerance"], 1000)
        database_bytes = (self.root / "bc_caja.sqlite3").read_bytes()
        self.assertNotIn(b"Clave-Segura-2026", database_bytes)

    def test_mandatory_open_intermediate_close_pdf_and_outbox_are_idempotent(self):
        day = self.controller.admin.open_from_count(
            "14-08-2026", "PC", {100_000: 2, 50_000: 1}, "Operadora Central", "open-1"
        )
        self.assertEqual(day.opening_cash, 250_000)
        same = self.controller.admin.open_from_count(
            "14-08-2026", "PC", {100_000: 9}, "Operadora Central", "open-1"
        )
        self.assertEqual(same.id, day.id)
        self.controller.service.add_entry(day.id, CashEntry(
            description="Cliente privado", total=120_000, cash=100_000,
            customer_document="1234567", customer_phone="0981000000",
            observations="OD receta secreta", source_reference="Historia clínica",
        ))
        first = self.controller.admin.record_count(
            day.id, "INTERMEDIATE", {100_000: 3}, "Operadora Central", "middle-click"
        )
        duplicate = self.controller.admin.record_count(
            day.id, "INTERMEDIATE", {50_000: 9}, "Operadora Central", "middle-click"
        )
        self.assertEqual(first.id, duplicate.id)
        self.assertEqual(self.controller.load_day("14-08-2026", "PC").opening_cash, 250_000)

        closed, count, mail_status = self.controller.admin.close_with_count(
            day.id, {100_000: 3, 50_000: 1}, "Operadora Central", "close-click"
        )
        self.assertEqual(closed.status.value, "CLOSED")
        self.assertEqual(count.difference, 0)
        self.assertEqual(mail_status, "NOT_CONFIGURED")
        with self.controller.service.repository._connection() as connection:
            counts = connection.execute(
                "SELECT count_type,COUNT(*) FROM cash_count_snapshots GROUP BY count_type"
            ).fetchall()
            outbox = connection.execute("SELECT * FROM mail_outbox").fetchall()
        self.assertEqual(dict(counts), {"OPENING": 1, "INTERMEDIATE": 1, "CLOSING": 1})
        self.assertEqual(len(outbox), 1)
        report = Path(outbox[0]["report_path"])
        self.assertTrue(report.is_file())
        raw = report.read_bytes()
        for private in (b"1234567", b"0981000000", b"receta secreta", b"Historia cl\xc3\xadnica"):
            self.assertNotIn(private, raw)
        again, again_count, _ = self.controller.admin.close_with_count(
            day.id, {100_000: 3, 50_000: 1}, "Operadora Central", "close-click"
        )
        self.assertEqual(again.id, closed.id)
        self.assertEqual(again_count.id, count.id)

    def test_difference_requires_reason_and_cancel_equivalent_writes_nothing(self):
        day = self.controller.admin.open_from_count(
            "15-08-2026", "PC", {100_000: 1}, "Caja PC", "open-2"
        )
        with self.assertRaises(InvalidCashDayError):
            self.controller.admin.close_with_count(day.id, {50_000: 1}, "Caja PC", "close-2")
        self.assertEqual(self.controller.load_day("15-08-2026", "PC").status.value, "OPEN")
        with self.controller.service.repository._connection() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM cash_count_snapshots WHERE count_type='CLOSING'"
            ).fetchone()[0], 0)
        closed, count, _ = self.controller.admin.close_with_count(
            day.id, {50_000: 1}, "Caja PC", "close-3", reason="Faltante real auditado"
        )
        self.assertEqual(count.difference, -50_000)
        self.assertEqual(closed.status.value, "CLOSED")

    def _configured_mail_day(self, date_text="16-08-2026"):
        session = self.controller.admin.create_initial_admin("adminmail", "Clave-Mail-Segura")
        self.controller.admin.update_setting(session.token, "mail", {
            "enabled": True, "recipient": "cierre@example.com", "cc": [],
            "subject": "Cierre {fecha} - {sucursal}", "host": "smtp.example.com",
            "port": 587, "username": "sender@example.com", "secret_ref": "smtp",
        })
        self.controller.admin.secret_store = type("Secrets", (), {"get": lambda _self, _name: "app-secret"})()
        day = self.controller.admin.open_from_count(
            date_text, "PC", {100_000: 1}, "Operadora Central", f"open-{date_text}"
        )
        return day

    def test_mail_success_is_sent_once_and_contains_no_secret(self):
        day = self._configured_mail_day()
        sent = []
        class SMTP:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def starttls(self, context): pass
            def login(self, username, password): self.password = password
            def send_message(self, message): sent.append(message)
        with patch("smtplib.SMTP", SMTP):
            closed, _, status = self.controller.admin.close_with_count(
                day.id, {100_000: 1}, "Operadora Central", "close-mail-ok"
            )
        self.assertEqual(closed.status.value, "CLOSED")
        self.assertEqual(status, "SENT")
        self.assertEqual(len(sent), 1)
        self.controller.admin.retry_outbox()
        self.assertEqual(len(sent), 1)
        with self.controller.service.repository._connection() as connection:
            row = connection.execute("SELECT status,attempts,last_error FROM mail_outbox").fetchone()
        self.assertEqual(tuple(row), ("SENT", 1, ""))
        self.assertNotIn(b"app-secret", (self.root / "bc_caja.sqlite3").read_bytes())

    def test_network_failure_stays_pending_and_retry_succeeds(self):
        day = self._configured_mail_day("17-08-2026")
        class TimeoutSMTP:
            def __init__(self, *args, **kwargs): raise TimeoutError("private host details")
        with patch("smtplib.SMTP", TimeoutSMTP):
            closed, _, status = self.controller.admin.close_with_count(
                day.id, {100_000: 1}, "Operadora Central", "close-mail-timeout"
            )
        self.assertEqual(closed.status.value, "CLOSED")
        self.assertEqual(status, "PENDING")
        with self.controller.service.repository._connection() as connection:
            row = connection.execute("SELECT id,status,last_error FROM mail_outbox").fetchone()
        self.assertEqual(row["last_error"], "NETWORK_TIMEOUT")
        self.assertNotIn("private", row["last_error"])
        class SMTP:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def starttls(self, context): pass
            def login(self, username, password): pass
            def send_message(self, message): pass
        with patch("smtplib.SMTP", SMTP):
            self.assertEqual(self.controller.admin.retry_outbox(row["id"]), 1)
        self.assertEqual(self.controller.admin.mail_status(day.id), "SENT")


if __name__ == "__main__":
    unittest.main()
