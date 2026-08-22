from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from .models import CashSnapshot, Principal, Role, Unit, utc_now
from .repository import CentralRepository


class AccessDenied(PermissionError):
    pass


class CentralManagementService:
    """Application service for the offline, synthetic-only central pilot."""

    STALE_AFTER = timedelta(minutes=15)
    PBKDF2_ITERATIONS = 310_000

    def __init__(self, repository: CentralRepository):
        self.repository = repository

    @staticmethod
    def _require(principal: Principal, permission: str, unit: Unit | None = None):
        if not principal.allows(permission, unit):
            raise AccessDenied(f"{principal.role.value} no tiene permiso {permission}")

    @classmethod
    def _password(cls, password: str, salt: bytes) -> str:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, cls.PBKDF2_ITERATIONS)
        return base64.b64encode(digest).decode("ascii")

    def create_user(self, actor: Principal, username: str, password: str, role: Role, unit: Unit | None = None):
        self._require(actor, "users.manage")
        username = username.strip()
        if len(username) < 3 or len(password) < 10:
            raise ValueError("Usuario inválido o contraseña menor a 10 caracteres")
        if role == Role.OPERADOR_LOCAL and unit is None:
            raise ValueError("El operador local requiere unidad")
        if role != Role.OPERADOR_LOCAL and unit is not None:
            raise ValueError("Sólo el operador local puede limitarse a una unidad")
        salt = secrets.token_bytes(24)
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO central_users(username,password_hash,salt,role,unit,created_at) VALUES(?,?,?,?,?,?)",
                (username, self._password(password, salt), base64.b64encode(salt).decode(), role.value, unit.value if unit else None, utc_now().isoformat()),
            )
            self.repository.audit(con, actor.username, "USER_CREATE", username, details={"role": role.value, "unit": unit.value if unit else None})
            con.commit()

    def authenticate(self, username: str, password: str) -> Principal:
        with self.repository.connection() as con:
            row = con.execute("SELECT * FROM central_users WHERE username=? COLLATE NOCASE AND active=1", (username.strip(),)).fetchone()
            valid = bool(row) and hmac.compare_digest(
                self._password(password, base64.b64decode(row["salt"])), row["password_hash"]
            )
            self.repository.audit(con, username or "UNKNOWN", "LOGIN", "central", "SUCCESS" if valid else "FAIL")
            con.commit()
        if not valid:
            raise AccessDenied("Credenciales inválidas")
        return Principal(row["username"], Role(row["role"]), Unit(row["unit"]) if row["unit"] else None)

    def bootstrap_synthetic_pilot(self, *, source_updated_at: datetime | None = None):
        """Creates an explicitly synthetic admin and sample snapshots once.

        `source_updated_at` es una costura, no una opción de producto: por
        omisión sigue siendo `utc_now()` y el piloto se comporta igual que
        siempre. Existe porque las pruebas de UI construían su escenario con el
        reloj de pared, y las alertas que salen de ese escenario dependen de la
        hora: `refresh_alerts` marca `LATE_OPEN` cuando la caja sigue abierta y
        la hora del snapshot es 22 o más. Corrida la suite entre las 22:00 y las
        23:59 UTC, aparecían cuatro alertas que a las 21:00 no existen, y dos
        pruebas se ponían en rojo sin que nada hubiera cambiado.

        `refresh_alerts` ya recibe su propio `now` por la misma razón.
        """
        with self.repository.connection() as con:
            exists = con.execute("SELECT 1 FROM central_users LIMIT 1").fetchone()
            usernames = {row[0] for row in con.execute("SELECT username FROM central_users")}
        system = Principal("SYSTEM", Role.ADMIN_CENTRAL)
        if "admin.piloto" not in usernames:
            self.create_user(system, "admin.piloto", "Piloto-Temporal-2026", Role.ADMIN_CENTRAL)
        if "sol.piloto" not in usernames:
            self.create_user(system, "sol.piloto", "Piloto-Temporal-2026", Role.ADMIN_CENTRAL)
        if exists:
            return
        for index, unit in enumerate(Unit):
            principal = Principal(f"operador.{index + 1}", Role.OPERADOR_LOCAL, unit)
            self.ingest_snapshot(principal, CashSnapshot(
                event_id=f"synthetic-{unit.value.lower()}-001", unit=unit,
                business_date="2099-01-15", status="OPEN",
                opening_cash=500_000, income=1_200_000 + index * 175_000,
                cash=700_000 + index * 100_000, card_check=500_000 + index * 75_000,
                expenses=80_000 + index * 10_000, withdrawals=100_000,
                expected_cash=1_020_000 + index * 90_000, counted_cash=None,
                entry_count=8 + index * 2,
                source_updated_at=source_updated_at or utc_now(),
            ))

    def ingest_snapshot(self, actor: Principal, snapshot: CashSnapshot) -> bool:
        self._require(actor, "sync.write", snapshot.unit)
        payload = {
            name: (value.isoformat() if isinstance(value, datetime) else value.value if isinstance(value, Unit) else value)
            for name, value in snapshot.__dict__.items()
        }
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            prior = con.execute("SELECT payload_json FROM cash_snapshots WHERE event_id=?", (snapshot.event_id,)).fetchone()
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if prior:
                if prior["payload_json"] != encoded:
                    self.repository.audit(con, actor.username, "SYNC_CONFLICT", snapshot.event_id, "REJECTED")
                    con.commit()
                    raise ValueError("event_id reutilizado con contenido diferente")
                con.rollback()
                return False
            con.execute("""INSERT INTO cash_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                snapshot.event_id, snapshot.unit.value, snapshot.business_date, snapshot.status,
                snapshot.opening_cash, snapshot.income, snapshot.cash, snapshot.card_check,
                snapshot.expenses, snapshot.withdrawals, snapshot.expected_cash,
                snapshot.counted_cash, snapshot.entry_count, snapshot.source_updated_at.isoformat(),
                utc_now().isoformat(), encoded,
            ))
            self.repository.audit(con, actor.username, "SYNC_ACCEPT", snapshot.event_id, details={"unit": snapshot.unit.value})
            con.commit()
        self.refresh_alerts(Principal("SYSTEM", Role.ADMIN_CENTRAL))
        return True

    def refresh_alerts(self, actor: Principal, now: datetime | None = None):
        self._require(actor, "alerts.manage")
        now = now or utc_now()
        latest = self.repository.latest_snapshots()
        desired = {}
        for unit in Unit:
            row = latest.get(unit)
            if row is None or now - datetime.fromisoformat(row["source_updated_at"]).astimezone(timezone.utc) > self.STALE_AFTER:
                desired[(unit, "SYNC_STALE")] = ("CRITICAL", "Sin sincronización reciente (más de 15 minutos).")
            if row and row["counted_cash"] is not None and row["counted_cash"] != row["expected_cash"]:
                difference = row["counted_cash"] - row["expected_cash"]
                desired[(unit, "CASH_DIFFERENCE")] = ("CRITICAL", f"Diferencia de caja: {difference:+,} Gs.")
            if row and row["status"] == "OPEN" and datetime.fromisoformat(row["source_updated_at"]).hour >= 22:
                desired[(unit, "LATE_OPEN")] = ("WARNING", "Caja aún abierta fuera del horario del piloto.")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            open_alerts = {
                (Unit(r["unit"]), r["kind"]): r
                for r in con.execute("SELECT * FROM central_alerts WHERE status IN ('ACTIVE','ACKNOWLEDGED')")
            }
            for key, (severity, message) in desired.items():
                if key not in open_alerts:
                    con.execute("INSERT INTO central_alerts(id,unit,kind,severity,message,status,created_at) VALUES(?,?,?,?,?,'ACTIVE',?)",
                                (str(uuid.uuid4()), key[0].value, key[1], severity, message, now.isoformat()))
            for key, row in open_alerts.items():
                if key not in desired:
                    con.execute("UPDATE central_alerts SET status='RESOLVED' WHERE id=?", (row["id"],))
            self.repository.audit(con, actor.username, "ALERT_REFRESH", "all", details={"active": len(desired)})
            con.commit()

    def acknowledge_alert(self, actor: Principal, alert_id: str):
        self._require(actor, "alerts.manage")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT unit FROM central_alerts WHERE id=? AND status='ACTIVE'", (alert_id,)).fetchone()
            if not row:
                raise ValueError("Alerta activa inexistente")
            self._require(actor, "alerts.manage", Unit(row["unit"]))
            con.execute("UPDATE central_alerts SET status='ACKNOWLEDGED',acknowledged_at=?,acknowledged_by=? WHERE id=?",
                        (utc_now().isoformat(), actor.username, alert_id))
            self.repository.audit(con, actor.username, "ALERT_ACK", alert_id)
            con.commit()

    def dashboard(self, actor: Principal, now: datetime | None = None):
        self._require(actor, "dashboard.read")
        now = now or utc_now()
        latest = self.repository.latest_snapshots()
        alerts = self.repository.alerts()
        visible_units = [unit for unit in Unit if actor.unit in (None, unit)]
        cards = []
        for unit in visible_units:
            row = latest.get(unit)
            cards.append({
                "unit": unit, "label": unit.label, "snapshot": dict(row) if row else None,
                "sync": "SIN DATOS" if row is None else ("DEMORADA" if now - datetime.fromisoformat(row["source_updated_at"]) > self.STALE_AFTER else "AL DÍA"),
                "alerts": sum(1 for alert in alerts if alert.unit == unit),
            })
        return {"cards": cards, "alerts": [a for a in alerts if a.unit in visible_units], "generated_at": now}
