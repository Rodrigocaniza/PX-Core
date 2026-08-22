"""Recepción durable y autorizada de BC Sync en Gestión Central."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Protocol

from modulos.bc_sync.model import SyncEvent
from modulos.bc_sync.security import AuthenticatedMessage, SecurityAuthorizationError
from modulos.bc_sync.security_bc import VerifiedRemoteLicenseProvider
from .models import Unit


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe(value: Any, limit: int = 500) -> str:
    return str(value or "").replace("\n", " ").replace("\r", " ")[:limit]


class CanonicalBranchCatalog:
    """Traduce el branch de licencia usando el catálogo Unit ya existente."""
    def resolve_optical(self, branch_id: str) -> Unit:
        normalized = str(branch_id or "").strip().upper()
        try:
            unit = Unit[f"OPTICA_{normalized}"]
        except KeyError as exc:
            raise SecurityAuthorizationError("branch no pertenece al catálogo óptico autorizado") from exc
        return unit


class SecurityDocumentBackend(Protocol):
    """Operaciones documentales implementadas por BC Seguridad, no por Central."""
    def verified_license(self, envelope: Mapping[str, Any], trust_store: Any) -> Any: ...
    def verified_revocations(self, envelope: Mapping[str, Any], trust_store: Any) -> Any: ...
    def capability_sync(self) -> str: ...


class NativeBCSecurityDocumentBackend:
    """Conecta con las APIs públicas de la rama BC Seguridad al componerse."""
    @staticmethod
    def _imports():
        try:
            from modulos.seguridad.application import verifier
            from modulos.seguridad.domain.license import (
                CAPABILITY_SYNC, SignedLicense, SignedRevocationList,
            )
        except ImportError as exc:
            raise RuntimeError("BC Seguridad debe promoverse antes del despliegue") from exc
        return verifier, CAPABILITY_SYNC, SignedLicense, SignedRevocationList

    def verified_license(self, envelope, trust_store):
        verifier, _, signed_license, _ = self._imports()
        signed = signed_license.from_envelope(envelope)
        verifier.verify_license(trust_store, signed)
        return signed.payload

    def verified_revocations(self, envelope, trust_store):
        verifier, _, _, signed_revocations = self._imports()
        signed = signed_revocations.from_envelope(envelope)
        verifier.verify_revocations(trust_store, signed)
        return signed.revocations

    def capability_sync(self) -> str:
        return self._imports()[1]


class DurableVerifiedRemoteLicenseProvider(VerifiedRemoteLicenseProvider):
    """Registro durable de documentos remotos, siempre reverificados por Seguridad."""
    def __init__(self, database: str | Path, trust_store: Any, *,
                 organization_id: str, backend: SecurityDocumentBackend | None = None,
                 branches: CanonicalBranchCatalog | None = None, clock=None) -> None:
        self.database, self.trust_store = Path(database), trust_store
        self.organization_id = organization_id
        self.backend = backend or NativeBCSecurityDocumentBackend()
        self.branches, self.clock = branches or CanonicalBranchCatalog(), clock or (
            lambda: datetime.now(timezone.utc))
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS remote_sync_licenses(
              installation_id TEXT PRIMARY KEY, license_id TEXT NOT NULL, branch_id TEXT NOT NULL,
              organization_id TEXT NOT NULL, envelope_json TEXT NOT NULL, installed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS remote_sync_revocations(
              singleton INTEGER PRIMARY KEY CHECK(singleton=1), serial INTEGER NOT NULL,
              envelope_json TEXT NOT NULL, installed_at TEXT NOT NULL);
            """)
            db.commit()

    def _connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def install_verified_license(self, envelope: Mapping[str, Any]) -> str:
        payload = self.backend.verified_license(envelope, self.trust_store)
        self._validate_payload(payload)
        with closing(self._connect()) as db:
            db.execute("INSERT INTO remote_sync_licenses VALUES(?,?,?,?,?,?) "
                       "ON CONFLICT(installation_id) DO UPDATE SET license_id=excluded.license_id,"
                       "branch_id=excluded.branch_id,organization_id=excluded.organization_id,"
                       "envelope_json=excluded.envelope_json,installed_at=excluded.installed_at",
                       (payload.installation_id, payload.license_id, payload.branch_id,
                        payload.organization_id, json.dumps(dict(envelope), sort_keys=True), _now()))
            db.commit()
        return payload.installation_id

    def install_verified_revocations(self, envelope: Mapping[str, Any]) -> int:
        revocations = self.backend.verified_revocations(envelope, self.trust_store)
        with closing(self._connect()) as db:
            previous = db.execute("SELECT serial FROM remote_sync_revocations WHERE singleton=1").fetchone()
            if previous and int(revocations.serial) < int(previous["serial"]):
                raise SecurityAuthorizationError("lista de revocación anterior a la vigente")
            db.execute("INSERT INTO remote_sync_revocations VALUES(1,?,?,?) "
                       "ON CONFLICT(singleton) DO UPDATE SET serial=excluded.serial,"
                       "envelope_json=excluded.envelope_json,installed_at=excluded.installed_at",
                       (int(revocations.serial), json.dumps(dict(envelope), sort_keys=True), _now()))
            db.commit()
        return int(revocations.serial)

    def verified_license_for_sync(self, installation_id: str) -> Any:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM remote_sync_licenses WHERE installation_id=?",
                             (installation_id,)).fetchone()
            revocation_row = db.execute(
                "SELECT envelope_json FROM remote_sync_revocations WHERE singleton=1").fetchone()
        if row is None:
            raise SecurityAuthorizationError("instalación remota no autorizada")
        payload = self.backend.verified_license(json.loads(row["envelope_json"]), self.trust_store)
        self._validate_payload(payload)
        if payload.installation_id != installation_id:
            raise SecurityAuthorizationError("installation_id no coincide con licencia verificada")
        if revocation_row:
            revocations = self.backend.verified_revocations(
                json.loads(revocation_row["envelope_json"]), self.trust_store)
            reason = revocations.revokes(
                installation_id=payload.installation_id, license_id=payload.license_id)
            if reason:
                raise SecurityAuthorizationError(f"instalación revocada: {_safe(reason)}")
        return payload

    def _validate_payload(self, payload: Any) -> None:
        if payload.organization_id != self.organization_id:
            raise SecurityAuthorizationError("licencia fuera del contexto autorizado")
        if not payload.allows(self.backend.capability_sync()):
            raise SecurityAuthorizationError("licencia no autoriza bc.sync")
        self.branches.resolve_optical(payload.branch_id)
        expires = payload.expires_at
        if expires is not None and self.clock().astimezone(timezone.utc) > expires:
            raise SecurityAuthorizationError("licencia remota vencida")


class CentralSyncInbox:
    """Inbox y proyección durable: autentica antes de producir cualquier efecto."""
    def __init__(self, database: str | Path, auth_provider: Any,
                 *, branches: CanonicalBranchCatalog | None = None) -> None:
        self.database, self.auth_provider = Path(database), auth_provider
        self.branches = branches or CanonicalBranchCatalog()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS central_sync_inbox(
              event_id TEXT PRIMARY KEY, installation_id TEXT NOT NULL, branch_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
              body_json TEXT NOT NULL, received_at TEXT NOT NULL,
              UNIQUE(installation_id,idempotency_key));
            CREATE TABLE IF NOT EXISTS central_sync_projection(
              event_id TEXT PRIMARY KEY REFERENCES central_sync_inbox(event_id), category TEXT NOT NULL,
              branch_id TEXT NOT NULL, sale_id TEXT NOT NULL DEFAULT '', envelope TEXT NOT NULL DEFAULT '',
              customer_document TEXT NOT NULL DEFAULT '', customer_name TEXT NOT NULL DEFAULT '',
              factufacil_state TEXT NOT NULL DEFAULT '', invoice_number TEXT NOT NULL DEFAULT '',
              sync_state TEXT NOT NULL DEFAULT 'RECEIVED', payload_json TEXT NOT NULL,
              occurred_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS central_sync_audit(
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, audit_at TEXT NOT NULL, outcome TEXT NOT NULL,
              installation_id TEXT NOT NULL DEFAULT '', branch_id TEXT NOT NULL DEFAULT '',
              event_id TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '');
            """)
            db.commit()

    def _connect(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def receive(self, message: AuthenticatedMessage) -> bool:
        body = message.body if isinstance(message.body, Mapping) else {}
        try:
            identity = self.auth_provider.verify_event(message)
            event = SyncEvent.from_wire(body)
            if event.installation_id != identity.installation_id:
                raise SecurityAuthorizationError("installation_id verificado no coincide")
            if event.branch_id.upper() != identity.branch_id.upper():
                raise SecurityAuthorizationError("branch mismatch")
            self.branches.resolve_optical(event.branch_id)
        except Exception as exc:
            self._audit("REJECTED", body, _safe(exc))
            raise
        with closing(self._connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO central_sync_inbox VALUES(?,?,?,?,?,?,?,?)",
                           (event.event_id, event.installation_id, event.branch_id,
                            event.idempotency_key, event.event_type, event.occurred_at,
                            json.dumps(event.wire_dict(), sort_keys=True, ensure_ascii=False), _now()))
            except sqlite3.IntegrityError:
                db.rollback()
                self._audit("DUPLICATE", event.wire_dict(), "evento ya aplicado")
                return False
            payload = dict(event.payload)
            db.execute("INSERT INTO central_sync_projection VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (event.event_id, self._category(event.event_type), event.branch_id,
                        _safe(payload.get("sale_id")), _safe(payload.get("envelope")),
                        _safe(payload.get("customer_document")), _safe(payload.get("customer_name")),
                        _safe(payload.get("state") or payload.get("factufacil_status")),
                        _safe(payload.get("invoice_number")), "RECEIVED",
                        json.dumps(payload, sort_keys=True, ensure_ascii=False), event.occurred_at))
            db.execute("INSERT INTO central_sync_audit(audit_at,outcome,installation_id,branch_id,event_id,reason) "
                       "VALUES(?,?,?,?,?,?)", (_now(), "RECEIVED", event.installation_id,
                                               event.branch_id, event.event_id, ""))
            db.commit()
        return True

    def _audit(self, outcome: str, body: Mapping[str, Any], reason: str) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT INTO central_sync_audit(audit_at,outcome,installation_id,branch_id,event_id,reason) "
                       "VALUES(?,?,?,?,?,?)", (_now(), outcome, _safe(body.get("installation_id")),
                                               _safe(body.get("branch_id")), _safe(body.get("event_id")),
                                               _safe(reason)))
            db.commit()

    @staticmethod
    def _category(event_type: str) -> str:
        value = event_type.upper()
        if value in {"CLIENTE", "HISTORIAL"}: return "CLIENTE_HISTORIAL"
        if value in {"VENTA", "COMPRA"}: return "VENTA"
        if value == "SOBRE": return "SOBRE"
        if value == "RECETA": return "RECETA"
        if value == "FACTURACION_ESTADO": return "FACTUFACIL"
        return "EVENTO"

    def projections(self):
        with closing(self._connect()) as db:
            return tuple(dict(row) for row in db.execute(
                "SELECT * FROM central_sync_projection ORDER BY occurred_at,event_id"))

    def factufacil(self):
        return tuple(row for row in self.projections() if row["category"] == "FACTUFACIL")

    def audit(self):
        with closing(self._connect()) as db:
            return tuple(dict(row) for row in db.execute(
                "SELECT * FROM central_sync_audit ORDER BY sequence"))
