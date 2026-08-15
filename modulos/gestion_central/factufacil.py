from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Protocol

from .models import Principal, Role, utc_now
from .service import AccessDenied, CentralManagementService


FACTUFACIL_STATES = ("PARA_CARGAR", "EN_PROCESO", "CARGADO", "OBSERVADO", "REVERTIDO")
FIELD_ORDER = (
    "customer", "document", "receipt_number", "date", "cashbox", "envelope",
    "prescription", "items", "total", "payment_method", "paid", "balance", "branch", "saleswoman",
)


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return utc_now().isoformat()


@dataclass(frozen=True)
class FactuFacilSale:
    branch: str
    source_sale_id: str
    customer: str
    document: str
    receipt_number: str
    date: str
    cashbox: str
    envelope: str
    prescription: str
    items: tuple[dict, ...]
    total: int
    payment_method: str
    paid: int
    balance: int
    saleswoman: str

    def __post_init__(self):
        for name in ("branch", "source_sale_id", "customer", "date", "cashbox", "envelope", "saleswoman"):
            if not str(getattr(self, name)).strip(): raise ValueError(f"{name} obligatorio")
        if any(isinstance(value, bool) or value < 0 for value in (self.total, self.paid, self.balance)):
            raise ValueError("montos inválidos")
        for item in self.items:
            if not str(item.get("description", "")).strip() or int(item.get("price", -1)) < 0:
                raise ValueError("artículo/precio inválido")

    def payload(self):
        value = asdict(self); value["items"] = list(self.items); return value


class FactuFacilExportPort(Protocol):
    def export(self, structured_record: dict) -> None: ...


class FactuFacilService:
    def __init__(self, core: CentralManagementService):
        self.core, self.repository = core, core.repository

    def _read(self, actor):
        if actor.role == Role.OPERADOR_LOCAL: raise AccessDenied("operador local sin acceso a FactuFácil")
        self.core._require(actor, "dashboard.read")

    def _write(self, actor):
        self.core._require(actor, "reviews.manage")

    def _history(self, con, sale_id, before, after, actor, action, details=None):
        con.execute("INSERT INTO factufacil_history(sale_id,from_state,to_state,actor,action,details_json,recorded_at) VALUES(?,?,?,?,?,?,?)",
                    (sale_id, before, after, actor, action, _canonical(details or {}), _now()))

    def register(self, actor: Principal, sale: FactuFacilSale):
        self._write(actor); payload = sale.payload(); identity = _hash({"branch": sale.branch, "source_sale_id": sale.source_sale_id, "envelope": sale.envelope})
        sale_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-factufacil:{identity}")); content_hash = _hash(payload); now = _now()
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM factufacil_sales WHERE identity_key=?", (identity,)).fetchone()
            if not row:
                duplicate = con.execute("SELECT id,status,receipt_number FROM factufacil_sales WHERE branch=? AND envelope=?", (sale.branch, sale.envelope)).fetchone()
                if duplicate: raise ValueError(f"sobre ya registrado: {duplicate['id']} ({duplicate['status']})")
                con.execute("INSERT INTO factufacil_sales VALUES(?,?,?,?,?,'PARA_CARGAR',?,?,1,NULL,NULL,NULL,?,?)",
                            (sale_id, identity, sale.branch, sale.source_sale_id, sale.envelope, content_hash, _canonical(payload), now, now))
                con.execute("INSERT INTO factufacil_versions VALUES(?,?,?,?,?)", (sale_id, 1, content_hash, _canonical(payload), now))
                self._history(con, sale_id, None, "PARA_CARGAR", actor.username, "SALE_REGISTERED", {"identity_key": identity})
                con.commit(); return sale_id, True
            if row["content_hash"] == content_hash:
                con.rollback(); return row["id"], False
            version = row["version"] + 1
            status = "OBSERVADO" if row["status"] == "CARGADO" else row["status"]
            con.execute("UPDATE factufacil_sales SET content_hash=?,payload_json=?,version=?,status=?,updated_at=? WHERE id=?",
                        (content_hash, _canonical(payload), version, status, now, row["id"]))
            con.execute("INSERT INTO factufacil_versions VALUES(?,?,?,?,?)", (row["id"], version, content_hash, _canonical(payload), now))
            self._history(con, row["id"], row["status"], status, actor.username, "SOURCE_UPDATED", {"before_hash": row["content_hash"], "after_hash": content_hash, "version": version})
            con.commit(); return row["id"], True

    def list_sales(self, actor: Principal, *, start=None, end=None, branch=None, envelope=None, customer=None, status=None):
        self._read(actor); query="SELECT * FROM factufacil_sales WHERE 1=1"; params=[]
        filters=(("json_extract(payload_json,'$.date')>=?",start),("json_extract(payload_json,'$.date')<=?",end),("branch=?",branch),("envelope LIKE ?",f"%{envelope}%" if envelope else None),("json_extract(payload_json,'$.customer') LIKE ?",f"%{customer}%" if customer else None),("status=?",status))
        for clause,value in filters:
            if value: query += " AND " + clause; params.append(value)
        query += " ORDER BY json_extract(payload_json,'$.date') DESC,branch,envelope"
        with self.repository.connection() as con: rows=con.execute(query,params).fetchall()
        result=[]
        for row in rows: item=dict(row); item["payload"]=json.loads(item.pop("payload_json")); result.append(item)
        return result

    def ordered_export(self, actor, sale_id):
        row=self.get(actor,sale_id); fields=[]
        for name in FIELD_ORDER:
            value=row["payload"][name]
            if name=="items": value=[{"description":item["description"],"price":item["price"]} for item in value]
            fields.append({"name":name,"value":value})
        return {"contract_version":1,"sale_id":sale_id,"identity_key":row["identity_key"],"content_hash":row["content_hash"],"fields":fields}

    def get(self, actor, sale_id):
        self._read(actor)
        with self.repository.connection() as con: row=con.execute("SELECT * FROM factufacil_sales WHERE id=?",(sale_id,)).fetchone()
        if not row: raise ValueError("venta inexistente")
        item=dict(row); item["payload"]=json.loads(item.pop("payload_json")); return item

    def start(self, actor, sale_id):
        return self._transition(actor,sale_id,{"PARA_CARGAR"},"EN_PROCESO","PROCESS_STARTED")

    def mark_loaded(self, actor, sale_id, responsible, receipt_number):
        self._write(actor); responsible,receipt_number=responsible.strip(),receipt_number.strip()
        if not responsible or not receipt_number: raise ValueError("responsable y comprobante obligatorios")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row=con.execute("SELECT * FROM factufacil_sales WHERE id=?",(sale_id,)).fetchone()
            if not row: raise ValueError("venta inexistente")
            if row["status"]=="CARGADO":
                if row["loaded_by"]==responsible and row["receipt_number"]==receipt_number: con.rollback(); return False
                raise ValueError(f"venta ya cargada por {row['loaded_by']} con comprobante {row['receipt_number']}")
            if row["status"] not in {"PARA_CARGAR","EN_PROCESO"}: raise ValueError(f"estado no cargable: {row['status']}")
            now=_now(); con.execute("UPDATE factufacil_sales SET status='CARGADO',loaded_by=?,loaded_at=?,receipt_number=?,updated_at=? WHERE id=?",(responsible,now,receipt_number,now,sale_id))
            self._history(con,sale_id,row["status"],"CARGADO",actor.username,"MARKED_LOADED",{"responsible":responsible,"receipt_number":receipt_number,"content_hash":row["content_hash"]}); con.commit(); return True

    def revert(self, actor, sale_id, reason):
        self._write(actor); reason=reason.strip()
        if not reason: raise ValueError("motivo obligatorio")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row=con.execute("SELECT status FROM factufacil_sales WHERE id=?",(sale_id,)).fetchone()
            if not row or row["status"] not in {"CARGADO","OBSERVADO"}: raise ValueError("venta no reversible")
            con.execute("UPDATE factufacil_sales SET status='REVERTIDO',updated_at=? WHERE id=?",(_now(),sale_id)); self._history(con,sale_id,row["status"],"REVERTIDO",actor.username,"LOAD_REVERTED",{"reason":reason}); con.commit()

    def prepare_again(self, actor, sale_id): return self._transition(actor,sale_id,{"REVERTIDO","OBSERVADO"},"PARA_CARGAR","PREPARED_AGAIN")

    def _transition(self,actor,sale_id,allowed,target,action):
        self._write(actor)
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE"); row=con.execute("SELECT status FROM factufacil_sales WHERE id=?",(sale_id,)).fetchone()
            if not row or row["status"] not in allowed: raise ValueError("transición inválida")
            con.execute("UPDATE factufacil_sales SET status=?,updated_at=? WHERE id=?",(target,_now(),sale_id)); self._history(con,sale_id,row["status"],target,actor.username,action); con.commit()

    def history(self,actor,sale_id):
        self._read(actor)
        with self.repository.connection() as con:return [dict(r) for r in con.execute("SELECT * FROM factufacil_history WHERE sale_id=? ORDER BY id",(sale_id,)).fetchall()]

    def sync_review_sales(self, actor, review_service):
        count=0
        for row in review_service.list_sales(actor):
            p=row["payload"]; total=int(p["total"]); paid=int(p["cash"])+int(p["card_transfer"])+int(p["agreement"])
            sale=FactuFacilSale(row["branch"],row["identity"],p["customer_name"],p["customer_document"],p["envelope"],p["date"],row["cashbox"],p["envelope"],p["prescription"],({"description":p["items"],"price":total},),total,"MIXTO",paid,max(total-paid,0),p["saleswoman"])
            count += int(self.register(actor,sale)[1])
        return count
