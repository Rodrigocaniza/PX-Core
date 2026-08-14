"""Seguridad administrativa, arqueos tipados y outbox durable de RC.13."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from ..domain.errors import CashDayClosedError, CashDayNotFoundError, InvalidCashDayError
from ..domain.models import CashDay, DENOMINATIONS, parse_business_date, utc_now


UTC = timezone.utc
PBKDF2_ITERATIONS = 390_000


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _quantities(values: Mapping[int, int]) -> tuple[dict[int, int], int]:
    normalized = {}
    for denomination, quantity in values.items():
        denomination = int(denomination)
        if denomination not in DENOMINATIONS or isinstance(quantity, bool) or int(quantity) < 0:
            raise InvalidCashDayError("El conteo contiene una denominación o cantidad inválida.")
        normalized[denomination] = int(quantity)
    return normalized, sum(key * value for key, value in normalized.items())


@dataclass(frozen=True)
class AdminSession:
    token: str
    username: str
    expires_at: datetime


@dataclass(frozen=True)
class CountResult:
    id: str
    cash_day_id: str
    count_type: str
    quantities: dict[int, int]
    counted_total: int
    expected_total: int | None
    difference: int | None
    reason: str
    responsible: str
    recorded_at: datetime


class DPAPISecretStore:
    """Blob CurrentUser fuera de SQLite; nunca devuelve ni registra secretos crudos."""

    def __init__(self, root: Path):
        self.root = root / "Secrets"

    def _path(self, name: str) -> Path:
        safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_")
        if not safe:
            raise ValueError("referencia de secreto inválida")
        return self.root / f"{safe}.dpapi"

    @staticmethod
    def _crypt(data: bytes, protect: bool) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI CurrentUser sólo está disponible en Windows")
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(data)
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        target = Blob()
        function = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        if protect:
            ok = function(ctypes.byref(source), "BC Caja SMTP", None, None, None, 0, ctypes.byref(target))
        else:
            ok = function(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target))
        if not ok:
            raise OSError("Windows no pudo proteger la credencial")
        try:
            return ctypes.string_at(target.pbData, target.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(target.pbData)

    def set(self, name: str, secret: str) -> None:
        if not secret:
            raise ValueError("secreto vacío")
        self.root.mkdir(parents=True, exist_ok=True)
        protected = self._crypt(secret.encode("utf-8"), True)
        destination = self._path(name)
        temporary = destination.with_suffix(".tmp")
        temporary.write_bytes(base64.b64encode(protected))
        temporary.replace(destination)

    def get(self, name: str) -> str | None:
        path = self._path(name)
        if not path.exists():
            return None
        return self._crypt(base64.b64decode(path.read_bytes()), False).decode("utf-8")

    def configured(self, name: str) -> bool:
        return self._path(name).is_file()


class AdminOperations:
    SETTINGS = {"counting", "branch", "mail"}

    def __init__(self, repository, data_root: Path):
        self.repository = repository
        self.data_root = Path(data_root)
        self.secret_store = DPAPISecretStore(self.data_root)
        self._sessions: dict[str, AdminSession] = {}

    def _audit(self, connection, actor: str, action: str, target_type: str,
               result: str, target_id: str = "", details=None) -> None:
        connection.execute(
            "INSERT INTO admin_audit_log(id,actor,action,target_type,target_id,result,details_json,recorded_at) VALUES(?,?,?,?,?,?,?,?)",
            (_id(), actor or "UNKNOWN", action, target_type, target_id, result,
             _json(details or {}), _now().isoformat()),
        )

    def has_admin(self) -> bool:
        with self.repository._connection() as connection:
            return connection.execute("SELECT 1 FROM admin_users WHERE active=1 LIMIT 1").fetchone() is not None

    def create_initial_admin(self, username: str, password: str) -> AdminSession:
        username = str(username).strip()
        if len(username) < 3 or len(password) < 10:
            raise InvalidCashDayError("Use un administrador y una contraseña de al menos 10 caracteres.")
        salt = secrets.token_bytes(24)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        now = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM admin_users LIMIT 1").fetchone():
                connection.rollback()
                raise InvalidCashDayError("La credencial administrativa ya fue configurada.")
            connection.execute(
                "INSERT INTO admin_users(id,username,password_hash,salt,iterations,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (_id(), username, base64.b64encode(digest).decode(), base64.b64encode(salt).decode(),
                 PBKDF2_ITERATIONS, now, now),
            )
            self._audit(connection, username, "ADMIN_BOOTSTRAP", "admin_user", "SUCCESS")
            connection.commit()
        return self.authenticate(username, password)

    def authenticate(self, username: str, password: str) -> AdminSession:
        username = str(username).strip()
        now = _now()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM admin_users WHERE username=? COLLATE NOCASE AND active=1", (username,)
            ).fetchone()
            locked = row and row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now
            valid = False
            if row and not locked:
                actual = hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"), base64.b64decode(row["salt"]), row["iterations"]
                )
                valid = hmac.compare_digest(actual, base64.b64decode(row["password_hash"]))
            if not valid:
                if row and not locked:
                    failures = row["failed_attempts"] + 1
                    delay = min(900, 2 ** min(failures, 10))
                    connection.execute(
                        "UPDATE admin_users SET failed_attempts=?,locked_until=?,updated_at=? WHERE id=?",
                        (failures, (now + timedelta(seconds=delay)).isoformat(), now.isoformat(), row["id"]),
                    )
                self._audit(connection, username or "UNKNOWN", "ADMIN_LOGIN", "session",
                            "LOCKED" if locked else "FAIL")
                connection.commit()
                raise InvalidCashDayError("Credenciales inválidas o acceso temporalmente bloqueado.")
            connection.execute(
                "UPDATE admin_users SET failed_attempts=0,locked_until=NULL,updated_at=? WHERE id=?",
                (now.isoformat(), row["id"]),
            )
            self._audit(connection, row["username"], "ADMIN_LOGIN", "session", "SUCCESS")
            connection.commit()
        session = AdminSession(secrets.token_urlsafe(32), row["username"], now + timedelta(minutes=20))
        self._sessions[session.token] = session
        return session

    def require(self, token: str) -> AdminSession:
        session = self._sessions.get(token)
        if session is None or session.expires_at <= _now():
            self._sessions.pop(token, None)
            raise InvalidCashDayError("La sesión administrativa venció.")
        return session

    def setting(self, key: str) -> dict:
        if key not in self.SETTINGS:
            raise KeyError(key)
        with self.repository._connection() as connection:
            row = connection.execute("SELECT value_json FROM app_settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else {}

    def update_setting(self, token: str, key: str, value: dict) -> None:
        session = self.require(token)
        if key not in self.SETTINGS:
            raise InvalidCashDayError("Configuración no permitida.")
        safe = dict(value)
        for forbidden in ("password", "secret", "token", "pin"):
            if any(forbidden in str(item).lower() for item in safe):
                raise InvalidCashDayError("Los secretos deben guardarse en el almacén protegido.")
        now = _now().isoformat()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO app_settings(key,value_json,updated_by,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                (key, _json(safe), session.username, now),
            )
            self._audit(connection, session.username, "SETTING_UPDATE", "app_setting", "SUCCESS", key)
            connection.commit()

    def set_mail_secret(self, token: str, secret: str) -> None:
        session = self.require(token)
        self.secret_store.set("smtp", secret)
        with self.repository._connection() as connection:
            self._audit(connection, session.username, "MAIL_SECRET_UPDATE", "credential", "SUCCESS", "smtp")
            connection.commit()

    def register_import(self, token: str, file_path: Path, summary, unit: str) -> str:
        session = self.require(token)
        digest = hashlib.sha256()
        with Path(file_path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result = "SUCCESS" if not getattr(summary, "errors", 0) else "PARTIAL"
        run_id = _id()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO import_runs(id,administrator,file_name,file_sha256,unit,rows_processed,rows_imported,rows_skipped,error_count,result,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, session.username, Path(file_path).name, digest.hexdigest(), unit,
                 getattr(summary, "entries", 0), getattr(summary, "entries", 0), 0,
                 getattr(summary, "errors", 0), result, _now().isoformat()),
            )
            self._audit(connection, session.username, "EXCEL_IMPORT", "import_run", result, run_id,
                        {"file": Path(file_path).name, "sha256": digest.hexdigest(), "rows": getattr(summary, "entries", 0)})
            connection.commit()
        return run_id

    def audit_rows(self, token: str, limit: int = 100):
        self.require(token)
        with self.repository._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT actor,action,target_type,result,recorded_at FROM admin_audit_log ORDER BY recorded_at DESC LIMIT ?",
                (int(limit),),
            )]

    def open_from_count(self, business_date: str, unit: str, quantities: Mapping[int, int],
                        responsible: str, operation_id: str) -> CashDay:
        values, total = _quantities(quantities)
        parsed = parse_business_date(business_date)
        unit = unit.strip().upper()
        responsible = responsible.strip() or f"Caja {unit}"
        day_id, count_id, now = _id(), _id(), utc_now()
        key = f"opening:{operation_id}"
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id FROM cash_days WHERE business_date=? AND unit=?", (parsed.isoformat(), unit)
            ).fetchone()
            if existing:
                connection.rollback()
                return self.repository.get(existing["id"])
            connection.execute(
                "INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at,version,opened_by,initial_cash_source_kind) VALUES(?,?,?,?,?,?,?,?,?)",
                (day_id, parsed.isoformat(), unit, total, "OPEN", now.isoformat(), 0, responsible, "OPENING_COUNT"),
            )
            connection.execute(
                "INSERT INTO cash_count_snapshots(id,cash_day_id,count_type,sequence,quantities_json,counted_total,expected_total,difference,reason,responsible,status,idempotency_key,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (count_id, day_id, "OPENING", 1, _json(values), total, total, 0, "", responsible,
                 "CONFIRMED", key, now.isoformat()),
            )
            self._audit(connection, responsible, "CASH_OPEN", "cash_day", "SUCCESS", day_id,
                        {"count_id": count_id, "total": total})
            connection.commit()
        return self.repository.get(day_id)

    def record_count(self, cash_day_id: str, count_type: str, quantities: Mapping[int, int],
                     responsible: str, operation_id: str, reason: str = "") -> CountResult:
        values, total = _quantities(quantities)
        if count_type != "INTERMEDIATE":
            raise InvalidCashDayError("Tipo de arqueo inválido.")
        key = f"intermediate:{operation_id}"
        now = utc_now()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM cash_count_snapshots WHERE idempotency_key=?", (key,)
            ).fetchone()
            if existing:
                connection.rollback()
                return self._count(existing)
            day = connection.execute("SELECT status FROM cash_days WHERE id=?", (cash_day_id,)).fetchone()
            if not day:
                connection.rollback(); raise CashDayNotFoundError(cash_day_id)
            if day["status"] != "OPEN":
                connection.rollback(); raise CashDayClosedError("la Caja está cerrada")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM cash_count_snapshots WHERE cash_day_id=? AND count_type='INTERMEDIATE'",
                (cash_day_id,),
            ).fetchone()[0]
            snapshot_id = _id()
            connection.execute(
                "INSERT INTO cash_count_snapshots(id,cash_day_id,count_type,sequence,quantities_json,counted_total,expected_total,difference,reason,responsible,status,idempotency_key,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (snapshot_id, cash_day_id, "INTERMEDIATE", sequence, _json(values), total, None, None,
                 reason.strip(), responsible.strip(), "CONFIRMED", key, now.isoformat()),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM cash_count_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return self._count(row)

    @staticmethod
    def _count(row) -> CountResult:
        return CountResult(row["id"], row["cash_day_id"], row["count_type"],
                           {int(k): int(v) for k, v in json.loads(row["quantities_json"]).items()},
                           row["counted_total"], row["expected_total"], row["difference"],
                           row["reason"], row["responsible"], datetime.fromisoformat(row["recorded_at"]))

    def close_with_count(self, cash_day_id: str, quantities: Mapping[int, int], responsible: str,
                         operation_id: str, reason: str = "", admin_token: str = "") -> tuple[CashDay, CountResult, str]:
        values, counted = _quantities(quantities)
        key = f"closing:{operation_id}"
        with self.repository._connection() as connection:
            existing = connection.execute(
                "SELECT id FROM cash_count_snapshots WHERE idempotency_key=?", (key,)
            ).fetchone()
        if existing:
            return self.repository.get(cash_day_id), self._count_by_id(existing["id"]), self.mail_status(cash_day_id)
        day = self.repository.get(cash_day_id)
        if day is None:
            raise CashDayNotFoundError(cash_day_id)
        totals = day.totals()
        difference = counted - totals.expected_cash
        policy = self.setting("counting")
        tolerance = int(policy.get("tolerance", 0))
        require_reason = policy.get("reason_mode", "ANY_DIFFERENCE") == "ANY_DIFFERENCE" and difference != 0
        require_reason = require_reason or abs(difference) > tolerance
        if require_reason and not reason.strip():
            raise InvalidCashDayError("El motivo de la diferencia es obligatorio.")
        admin_limit = int(policy.get("admin_limit", 0))
        if admin_limit > 0 and abs(difference) > admin_limit:
            self.require(admin_token)
        closed_at = utc_now()
        day.close(closed_at=closed_at)
        count_id, closure_id = _id(), _id()
        outbox_key = f"cash-close:{cash_day_id}:v1"
        mail = self.setting("mail")
        mail_status = "PENDING" if mail.get("enabled") and mail.get("recipient") else "NOT_CONFIGURED"
        report_path = str(self.data_root / "Reports" / f"cierre-{closure_id}.pdf")
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT id FROM cash_count_snapshots WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                connection.rollback()
                existing_day = self.repository.get(cash_day_id)
                return existing_day, self._count_by_id(existing["id"]), self.mail_status(cash_day_id)
            cursor = connection.execute(
                "UPDATE cash_days SET status='CLOSED',closed_at=?,closing_total=?,closing_cash=?,closing_card_check=?,closing_expenses=?,closing_expected_cash=?,closing_entry_count=?,closing_withdrawals=?,session_duration_seconds=?,overtime_triggered=?,overtime_minutes=?,version=version+1 WHERE id=? AND status='OPEN'",
                (closed_at.isoformat(), totals.total, totals.cash, totals.card_check, totals.expenses,
                 totals.expected_cash, totals.entry_count, totals.withdrawals, day.session_duration_seconds,
                 None if day.overtime_triggered is None else int(day.overtime_triggered), day.overtime_minutes, cash_day_id),
            )
            if cursor.rowcount != 1:
                connection.rollback(); raise CashDayClosedError("la Caja ya fue cerrada")
            connection.execute(
                "INSERT INTO cash_count_snapshots(id,cash_day_id,count_type,sequence,quantities_json,counted_total,expected_total,difference,reason,responsible,status,idempotency_key,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (count_id, cash_day_id, "CLOSING", 1, _json(values), counted, totals.expected_cash,
                 difference, reason.strip(), responsible.strip(), "CONFIRMED", key, closed_at.isoformat()),
            )
            connection.execute(
                "INSERT INTO mail_outbox(id,cash_day_id,closure_id,idempotency_key,report_path,recipient,subject,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_id(), cash_day_id, closure_id, outbox_key, report_path, str(mail.get("recipient", "")),
                 self._subject(mail, day), mail_status, closed_at.isoformat(), closed_at.isoformat()),
            )
            self._audit(connection, responsible, "CASH_CLOSE", "cash_day", "SUCCESS", cash_day_id,
                        {"closure_id": closure_id, "difference": difference, "count_id": count_id})
            connection.commit()
        closed = self.repository.get(cash_day_id)
        count = self._count_by_id(count_id)
        self.generate_close_pdf(closed, count, closure_id, Path(report_path))
        if mail_status == "PENDING":
            self.process_outbox(limit=1)
        return closed, count, self.mail_status(cash_day_id)

    def _count_by_id(self, count_id: str) -> CountResult:
        with self.repository._connection() as connection:
            row = connection.execute("SELECT * FROM cash_count_snapshots WHERE id=?", (count_id,)).fetchone()
        return self._count(row)

    @staticmethod
    def _subject(mail: dict, day: CashDay) -> str:
        template = str(mail.get("subject", "Cierre {fecha} - {sucursal}"))[:180]
        return template.replace("{fecha}", day.business_date.strftime("%d-%m-%Y")).replace("{sucursal}", day.unit)

    def generate_close_pdf(self, day: CashDay, count: CountResult, closure_id: str, destination: Path) -> Path:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_suffix(".tmp")
        pdf = canvas.Canvas(str(temp), pagesize=A4)
        y = 810
        totals = day.totals()
        lines = [
            ("BC Caja - Caja + Arqueo", closure_id), ("Sucursal / caja", day.unit),
            ("Fecha", day.business_date.strftime("%d-%m-%Y")), ("Responsable", count.responsible),
            ("Apertura", day.opened_at.isoformat()), ("Cierre", day.closed_at.isoformat()),
            ("Caja inicial", day.opening_cash), ("Total ventas", totals.total),
            ("Efectivo", totals.cash), ("Tarjeta / transferencia", totals.card_check),
            ("Gastos", totals.expenses), ("Entregas administración", totals.withdrawals),
            ("Efectivo esperado", count.expected_total), ("Efectivo contado", count.counted_total),
            ("Diferencia", count.difference), ("Motivo diferencia", count.reason or "Sin diferencia"),
        ]
        pdf.setFont("Helvetica-Bold", 14); pdf.drawString(42, y, lines[0][0]); y -= 24
        pdf.setFont("Helvetica", 9)
        for label, value in lines[1:]:
            pdf.drawString(42, y, f"{label}: {value}"); y -= 15
        y -= 8; pdf.setFont("Helvetica-Bold", 10); pdf.drawString(42, y, "Resumen de movimientos"); y -= 16
        pdf.setFont("Helvetica", 8)
        for entry in day.entries:
            if entry.status.value != "ACTIVE":
                continue
            safe = f"{entry.created_at.strftime('%H:%M')} | {entry.description[:45]} | Total {entry.total or 0} | Efectivo {entry.cash or 0} | Gasto {entry.expenses or 0} | Entrega {entry.withdrawal or 0}"
            pdf.drawString(42, y, safe); y -= 12
            if y < 50: pdf.showPage(); y = 810; pdf.setFont("Helvetica", 8)
        pdf.save(); temp.replace(destination)
        return destination

    def mail_status(self, cash_day_id: str) -> str:
        with self.repository._connection() as connection:
            row = connection.execute("SELECT status FROM mail_outbox WHERE cash_day_id=?", (cash_day_id,)).fetchone()
        return row["status"] if row else "NOT_CONFIGURED"

    @staticmethod
    def _sanitize_error(error: Exception) -> str:
        if isinstance(error, (TimeoutError, smtplib.SMTPConnectError)):
            return "NETWORK_TIMEOUT"
        if isinstance(error, smtplib.SMTPAuthenticationError):
            return "AUTHENTICATION_FAILED"
        return "DELIVERY_FAILED"

    def process_outbox(self, limit: int = 10) -> int:
        mail = self.setting("mail")
        if not mail.get("enabled") or not mail.get("recipient"):
            return 0
        secret = self.secret_store.get(str(mail.get("secret_ref", "smtp")))
        if not secret:
            return 0
        with self.repository._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM mail_outbox WHERE status IN ('PENDING','ERROR') AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY created_at LIMIT ?",
                (_now().isoformat(), int(limit)),
            ).fetchall()
        sent = 0
        for row in rows:
            try:
                from email.message import EmailMessage
                message = EmailMessage()
                message["To"] = row["recipient"]
                message["From"] = str(mail.get("username", ""))
                message["Subject"] = row["subject"]
                message.set_content("Se adjunta el cierre de Caja y Arqueo.")
                report = Path(row["report_path"])
                message.add_attachment(report.read_bytes(), maintype="application", subtype="pdf", filename=report.name)
                context = ssl.create_default_context()
                with smtplib.SMTP(str(mail.get("host", "")), int(mail.get("port", 587)), timeout=15) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(str(mail.get("username", "")), secret)
                    smtp.send_message(message)
                self._mail_result(row["id"], "SENT", "SENT")
                sent += 1
            except Exception as error:
                self._mail_result(row["id"], "ERROR", self._sanitize_error(error))
        return sent

    def _mail_result(self, outbox_id: str, status: str, detail: str) -> None:
        now = _now()
        with self.repository._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT attempts FROM mail_outbox WHERE id=?", (outbox_id,)).fetchone()
            attempts = (row["attempts"] if row else 0) + 1
            next_attempt = None if status == "SENT" else (now + timedelta(minutes=min(60, 2 ** attempts))).isoformat()
            connection.execute(
                "UPDATE mail_outbox SET status=?,attempts=?,next_attempt_at=?,last_error=?,updated_at=?,sent_at=? WHERE id=?",
                (status, attempts, next_attempt, "" if status == "SENT" else detail, now.isoformat(),
                 now.isoformat() if status == "SENT" else None, outbox_id),
            )
            connection.execute(
                "INSERT INTO mail_history(id,outbox_id,result,sanitized_detail,recorded_at) VALUES(?,?,?,?,?)",
                (_id(), outbox_id, status, detail, now.isoformat()),
            )
            connection.commit()
