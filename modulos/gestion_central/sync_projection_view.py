"""Lectura supervisada de las proyecciones que BC Sync deja en Gestión Central.

Consume el inbox de `sync_receiver` sin escribir jamás en él ni en las sedes: la
conexión se abre en solo lectura y, si el motor no puede abrir el WAL en ese
modo, se degrada a `PRAGMA query_only=ON`, que rechaza igualmente toda escritura.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3

from modulos.bc_sync.security import SecurityAuthorizationError
from .models import Principal, Unit
from .service import AccessDenied
from .sync_receiver import CanonicalBranchCatalog


CATEGORY_LABELS = {
    "CLIENTE_HISTORIAL": "Cliente / historial",
    "VENTA": "Venta",
    "SOBRE": "Sobre",
    "RECETA": "Receta",
    "FACTUFACIL": "FactuFácil",
    "EVENTO": "Evento",
}
UNKNOWN_BRANCH = "Sucursal no catalogada"


class SyncProjectionView:
    """Vista de solo lectura sobre inbox, proyección y auditoría de Central."""

    def __init__(self, database: str | Path, *, branches: CanonicalBranchCatalog | None = None):
        self.database = Path(database)
        self.branches = branches or CanonicalBranchCatalog()

    # -- acceso ---------------------------------------------------------
    @contextmanager
    def connection(self):
        """Conexión que no admite escrituras; `None` si aún no hay recepciones."""
        if not self.database.exists():
            yield None
            return
        try:
            db = sqlite3.connect(self.database.resolve().as_uri() + "?mode=ro", uri=True)
        except sqlite3.OperationalError:
            db = sqlite3.connect(self.database)
            db.execute("PRAGMA query_only=ON")
        db.row_factory = sqlite3.Row
        with closing(db):
            yield db

    @staticmethod
    def _require(actor: Principal, permission: str) -> None:
        if not actor.allows(permission):
            raise AccessDenied(f"{actor.role.value} no tiene permiso {permission}")

    def _unit(self, branch_id: str) -> Unit | None:
        try:
            return self.branches.resolve_optical(branch_id)
        except SecurityAuthorizationError:
            return None

    def _visible(self, actor: Principal, branch_id: str) -> bool:
        return actor.unit is None or self._unit(branch_id) == actor.unit

    def _row(self, row: sqlite3.Row) -> dict:
        unit = self._unit(row["branch_id"])
        return {
            "event_id": row["event_id"],
            "category": row["category"],
            "category_label": CATEGORY_LABELS.get(row["category"], row["category"]),
            "branch_id": row["branch_id"],
            "unit": unit,
            "unit_label": unit.label if unit else UNKNOWN_BRANCH,
            "sale_id": row["sale_id"],
            "envelope": row["envelope"],
            "customer_document": row["customer_document"],
            "customer_name": row["customer_name"],
            "factufacil_state": row["factufacil_state"],
            "invoice_number": row["invoice_number"],
            "sync_state": row["sync_state"],
            "occurred_at": row["occurred_at"],
            "payload": json.loads(row["payload_json"]),
        }

    # -- consultas ------------------------------------------------------
    def rows(self, actor: Principal, *, category: str | None = None, unit: Unit | None = None,
             state: str | None = None, text: str | None = None) -> tuple[dict, ...]:
        """Proyecciones recibidas, en el mismo orden estable del receptor."""
        self._require(actor, "dashboard.read")
        with self.connection() as db:
            if db is None:
                return ()
            raw = db.execute(
                "SELECT * FROM central_sync_projection ORDER BY occurred_at,event_id").fetchall()
        needle = (text or "").strip().casefold()
        selected = []
        for row in raw:
            if not self._visible(actor, row["branch_id"]):
                continue
            item = self._row(row)
            if category and item["category"] != category:
                continue
            if unit is not None and item["unit"] != unit:
                continue
            if state and item["factufacil_state"].casefold() != state.casefold():
                continue
            if needle and not any(needle in str(item[field]).casefold() for field in (
                    "customer_name", "customer_document", "envelope", "sale_id",
                    "invoice_number", "event_id")):
                continue
            selected.append(item)
        return tuple(selected)

    def factufacil(self, actor: Principal, *, state: str | None = None) -> tuple[dict, ...]:
        return self.rows(actor, category="FACTUFACIL", state=state)

    def summary(self, actor: Principal) -> dict:
        """Totales por categoría y sucursal más el pulso de recepción y rechazo."""
        rows = self.rows(actor)
        categories = {key: 0 for key in CATEGORY_LABELS}
        units: dict[str, int] = {}
        for row in rows:
            categories[row["category"]] = categories.get(row["category"], 0) + 1
            units[row["unit_label"]] = units.get(row["unit_label"], 0) + 1
        outcomes = self._outcomes(actor)
        return {
            "total": len(rows),
            "categories": categories,
            "units": units,
            "last_occurred_at": rows[-1]["occurred_at"] if rows else "",
            "rejected": outcomes.get("REJECTED", 0),
            "duplicated": outcomes.get("DUPLICATE", 0),
        }

    def _outcomes(self, actor: Principal) -> dict[str, int]:
        if not actor.allows("audit.read"):
            return {}
        with self.connection() as db:
            if db is None:
                return {}
            rows = db.execute(
                "SELECT outcome,branch_id,COUNT(*) total FROM central_sync_audit "
                "GROUP BY outcome,branch_id").fetchall()
        totals: dict[str, int] = {}
        for row in rows:
            if not self._visible(actor, row["branch_id"]):
                continue
            totals[row["outcome"]] = totals.get(row["outcome"], 0) + int(row["total"])
        return totals

    def rejections(self, actor: Principal, *, limit: int = 200) -> tuple[dict, ...]:
        """Intentos no aceptados, con el motivo ya saneado por el receptor."""
        self._require(actor, "audit.read")
        with self.connection() as db:
            if db is None:
                return ()
            rows = db.execute(
                "SELECT * FROM central_sync_audit WHERE outcome<>'RECEIVED' "
                "ORDER BY sequence DESC LIMIT ?", (max(int(limit), 0),)).fetchall()
        selected = []
        for row in rows:
            if not self._visible(actor, row["branch_id"]):
                continue
            unit = self._unit(row["branch_id"])
            selected.append({
                "sequence": row["sequence"], "audit_at": row["audit_at"],
                "outcome": row["outcome"], "installation_id": row["installation_id"],
                "branch_id": row["branch_id"], "unit_label": unit.label if unit else UNKNOWN_BRANCH,
                "event_id": row["event_id"], "reason": row["reason"],
            })
        return tuple(selected)
