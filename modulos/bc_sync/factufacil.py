"""Frontera transitoria de facturación. BC conserva la verdad de la venta."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Mapping, Protocol, Any, Callable
from uuid import uuid4


NO_REQUIERE_FACTURA = "NO_REQUIERE_FACTURA"
PENDIENTE = "PENDIENTE_FACTU_FACIL"
EN_PROCESO = "EN_PROCESO"
CARGADA = "CARGADA"
ERROR = "ERROR"
REINTENTAR = "REINTENTAR"
ANULADA = "ANULADA"
CORREGIDA = "CORREGIDA"
STATES = frozenset({NO_REQUIERE_FACTURA, PENDIENTE, EN_PROCESO, CARGADA,
                    ERROR, REINTENTAR, ANULADA, CORREGIDA})


@dataclass(frozen=True)
class InvoiceRequest:
    billing_id: str
    sale_id: str
    branch_id: str
    envelope: str
    customer_name: str
    tax_id: str
    sold_at: str
    totals: Mapping[str, Any]
    tax: Mapping[str, Any]
    invoice_mode: str
    responsible: str
    idempotency_key: str
    state: str = PENDIENTE
    invoice_number: str = ""


class FactuFacilAdapter(Protocol):
    def submit(self, request: InvoiceRequest) -> Mapping[str, Any]: ...


class DisabledFactuFacilAdapter:
    def submit(self, request: InvoiceRequest) -> Mapping[str, Any]:
        raise RuntimeError("adaptador FactuFácil desactivado")


class AssistedFactuFacilAdapter:
    """Sin API: entrega datos validados para carga humana, nunca maneja la UI externa."""
    def submit(self, request: InvoiceRequest) -> Mapping[str, Any]:
        return {"mode": "ASSISTED", "billing_id": request.billing_id,
                "sale_id": request.sale_id, "branch_id": request.branch_id,
                "envelope": request.envelope, "customer": request.customer_name,
                "tax_id": request.tax_id, "sold_at": request.sold_at,
                "totals": dict(request.totals), "tax": dict(request.tax),
                "invoice_mode": request.invoice_mode}


class BillingQueue:
    def __init__(self, path: str | Path, *, state_publisher: Callable[[str, dict, str], str] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state_publisher = state_publisher
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS billing_queue(
              billing_id TEXT PRIMARY KEY, sale_id TEXT NOT NULL, branch_id TEXT NOT NULL,
              envelope TEXT NOT NULL, customer_name TEXT NOT NULL, tax_id TEXT NOT NULL,
              sold_at TEXT NOT NULL, totals_json TEXT NOT NULL, tax_json TEXT NOT NULL,
              invoice_mode TEXT NOT NULL, responsible TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
              state TEXT NOT NULL, invoice_number TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, external_result TEXT NOT NULL DEFAULT '',
              last_error TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS billing_audit(
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, billing_id TEXT NOT NULL,
              occurred_at TEXT NOT NULL, action TEXT NOT NULL, responsible TEXT NOT NULL, detail TEXT NOT NULL);
            """)

    def _connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def register(self, *, sale_id: str, branch_id: str, envelope: str,
                 customer_name: str, tax_id: str, sold_at: str, totals: Mapping[str, Any],
                 tax: Mapping[str, Any], invoice_mode: str, responsible: str,
                 idempotency_key: str, required: bool = True) -> str:
        if not sale_id or not branch_id or not idempotency_key:
            raise ValueError("venta, sucursal e idempotency_key son obligatorios")
        state, now, billing_id = (PENDIENTE if required else NO_REQUIERE_FACTURA), self._now(), str(uuid4())
        with self._connect() as db:
            existing = db.execute("SELECT billing_id FROM billing_queue WHERE idempotency_key=?",
                                  (idempotency_key,)).fetchone()
            if existing:
                return existing["billing_id"]
            db.execute("INSERT INTO billing_queue VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?)",
                       (billing_id, sale_id, branch_id.upper(), envelope, customer_name, tax_id,
                        sold_at, json.dumps(dict(totals), sort_keys=True),
                        json.dumps(dict(tax), sort_keys=True), invoice_mode, responsible,
                        idempotency_key, state, "", now, now, "", ""))
            self._audit(db, billing_id, "REGISTERED", responsible, state)
        self._publish(billing_id)
        return billing_id

    def pending(self) -> tuple[InvoiceRequest, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM billing_queue WHERE state IN (?, ?, ?) ORDER BY created_at",
                              (PENDIENTE, ERROR, REINTENTAR)).fetchall()
        return tuple(self._request(row) for row in rows)

    def process(self, billing_id: str, adapter: FactuFacilAdapter) -> Mapping[str, Any]:
        request = self.get(billing_id)
        self.transition(billing_id, EN_PROCESO, request.responsible)
        try:
            result = dict(adapter.submit(request))
        except Exception as exc:
            self.transition(billing_id, ERROR, request.responsible, error=str(exc))
            raise
        with self._connect() as db:
            db.execute("UPDATE billing_queue SET external_result=?,attempts=attempts+1,updated_at=? WHERE billing_id=?",
                       (json.dumps(result, sort_keys=True), self._now(), billing_id))
            self._audit(db, billing_id, "ASSISTED_DATA_READY", request.responsible, json.dumps(result))
        return result

    def mark_loaded(self, billing_id: str, invoice_number: str, responsible: str) -> None:
        if not invoice_number.strip():
            raise ValueError("número de factura obligatorio")
        self.transition(billing_id, CARGADA, responsible, invoice_number=invoice_number.strip())

    def transition(self, billing_id: str, state: str, responsible: str, *,
                   invoice_number: str = "", error: str = "") -> None:
        if state not in STATES:
            raise ValueError("estado de facturación inválido")
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM billing_queue WHERE billing_id=?", (billing_id,)).fetchone():
                raise KeyError(billing_id)
            db.execute("UPDATE billing_queue SET state=?,invoice_number=CASE WHEN ?='' THEN invoice_number ELSE ? END,"
                       "last_error=?,updated_at=? WHERE billing_id=?",
                       (state, invoice_number, invoice_number, error, self._now(), billing_id))
            self._audit(db, billing_id, "STATE_CHANGED", responsible,
                        json.dumps({"state": state, "invoice_number": invoice_number, "error": error}))
        self._publish(billing_id)

    def get(self, billing_id: str) -> InvoiceRequest:
        with self._connect() as db:
            row = db.execute("SELECT * FROM billing_queue WHERE billing_id=?", (billing_id,)).fetchone()
        if not row:
            raise KeyError(billing_id)
        return self._request(row)

    def audit(self, billing_id: str):
        with self._connect() as db:
            return tuple(dict(row) for row in db.execute(
                "SELECT * FROM billing_audit WHERE billing_id=? ORDER BY sequence", (billing_id,)))

    def _publish(self, billing_id: str) -> None:
        if not self.state_publisher:
            return
        request = self.get(billing_id)
        payload = {"billing_id": request.billing_id, "sale_id": request.sale_id,
                   "branch_id": request.branch_id, "envelope": request.envelope,
                   "state": request.state, "invoice_number": request.invoice_number,
                   "customer_name": request.customer_name, "tax_id": request.tax_id,
                   "sold_at": request.sold_at, "totals": dict(request.totals),
                   "invoice_mode": request.invoice_mode, "responsible": request.responsible}
        self.state_publisher("FACTURACION_ESTADO", payload,
                             f"billing:{billing_id}:{request.state}:{request.invoice_number}")

    @staticmethod
    def _request(row) -> InvoiceRequest:
        return InvoiceRequest(row["billing_id"], row["sale_id"], row["branch_id"], row["envelope"],
                              row["customer_name"], row["tax_id"], row["sold_at"],
                              json.loads(row["totals_json"]), json.loads(row["tax_json"]),
                              row["invoice_mode"], row["responsible"], row["idempotency_key"],
                              row["state"], row["invoice_number"])

    @staticmethod
    def _audit(db, billing_id: str, action: str, responsible: str, detail: str) -> None:
        db.execute("INSERT INTO billing_audit(billing_id,occurred_at,action,responsible,detail) VALUES(?,?,?,?,?)",
                   (billing_id, BillingQueue._now(), action, responsible, detail[:4000]))
