"""Comisiones por vendedora y local: reglas económicas aprobadas, cálculo local-first.

La lógica vive separada de la interfaz. Los importes son enteros de guaraníes;
no se usan floats monetarios en ningún punto del cálculo.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from typing import Protocol

from .models import Principal, Role, utc_now
from .service import AccessDenied, CentralManagementService


COMMISSION_STATES = (
    "PENDIENTE_SALDO", "ELEGIBLE", "CALCULADA", "REVISADA",
    "APROBADA", "PAGADA", "OBSERVADA", "REVERTIDA",
)
SALE_KINDS = ("COMUN", "CONVENIO")

# Regla aprobada 4: el convenio deduce exactamente 5% del total de la venta.
AGREEMENT_DISCOUNT_BP = 500
BASIS_POINTS = 10_000

# Estados que no pueden recalcularse ni revertirse en silencio.
FROZEN_STATES = frozenset({"PAGADA"})
RECALCULABLE_STATES = frozenset({"ELEGIBLE", "CALCULADA"})
OPEN_STATES = frozenset({"ELEGIBLE", "CALCULADA", "REVISADA", "APROBADA"})
# Ya pasaron por revisión humana: una corrección de origen no puede recalcularlos en silencio.
REVIEWED_STATES = frozenset({"REVISADA", "APROBADA", "PAGADA"})

ENTRY_EXPORT_FIELDS = (
    "entry_id", "period", "branch", "saleswoman", "sale_kind", "status",
    "sale_date", "cancelled_date", "gross_amount", "agreement_discount",
    "commissionable_base", "rate_bp", "commission_amount", "policy_status",
    "balance_amount", "observation",
)

# La política de porcentaje NO es una regla productiva aprobada todavía.
POLICY_PENDING = "SINTETICA_PENDIENTE_APROBACION"
POLICY_ABSENT = "SIN_POLITICA_CONFIGURADA"


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return utc_now().isoformat()


def _month(value: str) -> str:
    """Devuelve el período AAAA-MM de una fecha ISO realmente válida.

    El período de liquidación se deriva de esta función, así que una fecha mal formada
    jamás debe producir un período: se rechaza en el borde en lugar de generar un mes
    inexistente que haría desaparecer la comisión de todos los reportes.
    """
    text = str(value).strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"fecha inválida: se espera AAAA-MM-DD, se recibió {text!r}") from error
    return f"{parsed.year:04d}-{parsed.month:02d}"


def _was_paid(entry) -> bool:
    """Una liquidación que ya movió dinero, esté como esté hoy, no puede revertirse."""
    return entry["status"] == "PAGADA" or bool(entry["paid_at"])


def _reject_paid(entry) -> None:
    if _was_paid(entry):
        raise ValueError(
            f"liquidación ya pagada el {entry['paid_at']} con referencia {entry['payment_reference']}: "
            "no admite reversión; corríjala como OBSERVADA"
        )


def apply_basis_points(amount: int, points: int) -> int:
    """Aplica puntos básicos sobre enteros con redondeo half-up y sin floats."""
    return (int(amount) * int(points) + BASIS_POINTS // 2) // BASIS_POINTS


def agreement_discount(total: int) -> int:
    """Descuento del convenio: exactamente 5% del total de la venta."""
    return apply_basis_points(total, AGREEMENT_DISCOUNT_BP)


def commissionable_base(kind: str, total: int) -> int:
    """Base comisionable: total para venta común, total − 5% para convenio."""
    if kind == "CONVENIO":
        return int(total) - agreement_discount(total)
    return int(total)


@dataclass(frozen=True)
class CommissionSaleInput:
    """Entrada de venta al libro de comisiones. Gastos y entregas nunca ingresan."""

    branch: str
    source_sale_id: str
    saleswoman: str
    sale_date: str
    kind: str
    total_amount: int
    initial_paid: int = 0
    envelope: str = ""  # referencia operativa; el libro no guarda datos del cliente

    def __post_init__(self):
        for name in ("branch", "source_sale_id", "saleswoman", "sale_date"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} obligatorio")
        if self.kind not in SALE_KINDS:
            raise ValueError(f"tipo de venta inválido: {self.kind}")
        for name in ("total_amount", "initial_paid"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} debe ser entero no negativo")
        if self.total_amount <= 0:
            raise ValueError("una venta comisionable requiere total positivo")
        if self.initial_paid > self.total_amount:
            raise ValueError("el cobro inicial no puede superar el total")
        # Regla aprobada 6: el convenio no genera saldo cliente.
        if self.kind == "CONVENIO" and self.initial_paid not in (0, self.total_amount):
            raise ValueError("el convenio no admite saldo cliente parcial")
        _month(self.sale_date)

    def payload(self) -> dict:
        return asdict(self)


class CommissionPolicyPort(Protocol):
    """Puerto para políticas configurables de comisión (pendiente de aprobación)."""

    def rate_for(self, *, branch: str, saleswoman: str, period: str) -> tuple[int | None, str]: ...


class StoredCommissionPolicy:
    """Política leída de la base local. Nunca se afirma como regla productiva."""

    def __init__(self, repository):
        self.repository = repository

    def rate_for(self, *, branch: str, saleswoman: str, period: str) -> tuple[int | None, str]:
        candidates = (("VENDEDORA", saleswoman), ("LOCAL", branch), ("GENERAL", ""))
        with self.repository.connection() as con:
            for scope, value in candidates:
                row = con.execute(
                    "SELECT rate_bp,approval_status FROM commission_policies WHERE scope=? AND scope_value=?",
                    (scope, value),
                ).fetchone()
                if row:
                    return int(row["rate_bp"]), row["approval_status"]
        return None, POLICY_ABSENT


class CommissionService:
    """Bandeja y reporte mensual de comisiones. No altera las reglas de BC Caja."""

    def __init__(self, core: CentralManagementService, policy: CommissionPolicyPort | None = None):
        self.core = core
        self.repository = core.repository
        self.policy = policy or StoredCommissionPolicy(core.repository)

    # ---------------------------------------------------------------- acceso
    def _read(self, actor: Principal):
        if actor.role == Role.OPERADOR_LOCAL:
            raise AccessDenied("operador local sin acceso a comisiones")
        self.core._require(actor, "dashboard.read")

    def _write(self, actor: Principal):
        self.core._require(actor, "reviews.manage")

    # -------------------------------------------------------------- historia
    def _history(self, con, entry_id, sale_id, before, after, actor, action, details=None):
        con.execute(
            "INSERT INTO commission_entry_history(entry_id,sale_id,from_state,to_state,actor,action,details_json,recorded_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (entry_id, sale_id, before, after, actor, action, _canonical(details or {}), _now()),
        )

    @staticmethod
    def _active_entry(con, sale_id):
        return con.execute(
            "SELECT * FROM commission_entries WHERE sale_id=? AND status<>'REVERTIDA'", (sale_id,)
        ).fetchone()

    def _create_entry(self, con, sale, status, period, actor, action, details=None):
        sequence = (con.execute(
            "SELECT COALESCE(MAX(sequence),0) FROM commission_entries WHERE sale_id=?", (sale["id"],)
        ).fetchone()[0]) + 1
        entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-comision:{sale['id']}:{sequence}"))
        kind, total = sale["sale_kind"], int(sale["total_amount"])
        discount = agreement_discount(total) if kind == "CONVENIO" else 0
        base = commissionable_base(kind, total) if status != "PENDIENTE_SALDO" else 0
        now = _now()
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "eligible_date,reviewed_by,reviewed_at,approved_by,approved_at,paid_at,payment_reference,observation,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,?,?)",
            (entry_id, sale["id"], sequence, period, sale["branch"], sale["saleswoman"], kind, status,
             total, discount if status != "PENDIENTE_SALDO" else 0, base, POLICY_ABSENT,
             sale["cancelled_date"], now, now),
        )
        self._history(con, entry_id, sale["id"], None, status, actor, action, details)
        return entry_id

    # -------------------------------------------------------------- registro
    def register_sale(self, actor: Principal, sale: CommissionSaleInput):
        """Alta idempotente por identidad estable (local + venta de origen)."""
        self._write(actor)
        identity = _hash({"branch": sale.branch, "source_sale_id": sale.source_sale_id})
        sale_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-comision-venta:{identity}"))
        payload = sale.payload()
        content_hash = _hash(payload)
        if sale.kind == "CONVENIO":
            # Regla aprobada 3 y 6: el convenio queda finalizado y nunca crea saldo cliente.
            paid, balance, cancelled = sale.total_amount, 0, sale.sale_date
        else:
            paid, balance = sale.initial_paid, sale.total_amount - sale.initial_paid
            cancelled = sale.sale_date if balance == 0 else None
        now = _now()
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM commission_sales WHERE identity_key=?", (identity,)).fetchone()
            if row is None:
                con.execute(
                    "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
                    "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,envelope,"
                    "content_hash,payload_json,version,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,0,NULL,?,?,?,1,?,?)",
                    (sale_id, identity, sale.branch, sale.source_sale_id, sale.saleswoman, sale.kind,
                     sale.sale_date, sale.total_amount, paid, balance, cancelled, sale.envelope,
                     content_hash, _canonical(payload), now, now),
                )
                if sale.kind == "CONVENIO":
                    # El convenio no es un cobro de cliente, pero sí liquida la venta: va al libro.
                    self._insert_payment(con, sale_id, sale.total_amount, sale.sale_date,
                                         "CONVENIO", "liquidación por convenio", actor.username)
                elif sale.initial_paid:
                    self._insert_payment(con, sale_id, sale.initial_paid, sale.sale_date,
                                         "COBRO", "alta", actor.username)
                stored = con.execute("SELECT * FROM commission_sales WHERE id=?", (sale_id,)).fetchone()
                status = "PENDIENTE_SALDO" if balance > 0 else "ELEGIBLE"
                period = None if balance > 0 else _month(cancelled)
                self._create_entry(con, stored, status, period, actor.username, "SALE_REGISTERED",
                                   {"identity_key": identity, "kind": sale.kind, "total": sale.total_amount})
                con.commit()
                return sale_id, True
            if row["content_hash"] == content_hash:
                con.rollback()
                return row["id"], False
            self._apply_source_update(con, row, sale, payload, content_hash, actor)
            con.commit()
            return row["id"], True

    def _apply_source_update(self, con, row, sale, payload, content_hash, actor):
        """Una corrección de origen nunca modifica en silencio una liquidación cerrada.

        Lo cobrado sale siempre del libro append-only: toda diferencia declarada por el origen
        se asienta como una fila más, nunca como una asignación suelta de `paid_amount`.
        """
        if row["voided"]:
            raise ValueError("venta anulada: no admite corrección de origen")
        if row["sale_kind"] == "CONVENIO" and sale.kind != "CONVENIO":
            # Deja de ser convenio: la liquidación por convenio ya no sostiene la venta y se
            # revierte en el libro. El saldo vuelve a ser el total menos los cobros reales.
            self._reverse_agreement_settlement(con, row["id"], actor.username)
        settled = self._settled_amount(con, row["id"])
        if sale.total_amount < settled:
            raise ValueError("el total corregido es menor a lo ya cobrado")
        if sale.kind == "CONVENIO":
            # El convenio liquida la venta completa; la diferencia se asienta en el libro.
            if sale.total_amount > settled:
                self._insert_payment(con, row["id"], sale.total_amount - settled, sale.sale_date,
                                     "CONVENIO", "liquidación por convenio", actor.username)
            cancelled = row["cancelled_date"] or sale.sale_date
        elif sale.initial_paid > settled:
            # El origen declara más cobrado que el libro: se asienta el cobro faltante.
            self._insert_payment(con, row["id"], sale.initial_paid - settled, sale.sale_date,
                                 "COBRO", "conciliación de origen", actor.username)
        paid = self._settled_amount(con, row["id"])
        balance = sale.total_amount - paid
        if sale.kind != "CONVENIO":
            cancelled = (row["cancelled_date"] or sale.sale_date) if balance == 0 else None
        con.execute(
            "UPDATE commission_sales SET saleswoman=?,sale_kind=?,sale_date=?,total_amount=?,paid_amount=?,"
            "balance_amount=?,cancelled_date=?,envelope=?,content_hash=?,payload_json=?,version=version+1,"
            "updated_at=? WHERE id=?",
            (sale.saleswoman, sale.kind, sale.sale_date, sale.total_amount, paid, balance, cancelled,
             sale.envelope, content_hash, _canonical(payload), _now(), row["id"]),
        )
        details = {"before_hash": row["content_hash"], "after_hash": content_hash,
                   "total": sale.total_amount, "balance": balance}
        entry = self._active_entry(con, row["id"])
        if entry is None:
            if balance == 0:
                self._promote_to_eligible(con, row["id"], cancelled, actor.username)
            return
        if _was_paid(entry) or entry["status"] in REVIEWED_STATES:
            # Nada revisado, aprobado o pagado se recalcula solo: exige corrección manual.
            self._set_status(con, entry, "OBSERVADA", actor.username, "SOURCE_UPDATED_AFTER_CLOSE", details,
                             observation="Origen corregido tras la revisión, aprobación o pago: "
                                         "requiere corrección manual.")
            return
        # Antes de la revisión sí se recalcula, pero la base completa: nunca sólo el total.
        pending = entry["status"] == "PENDIENTE_SALDO"
        discount = 0 if pending else (agreement_discount(sale.total_amount) if sale.kind == "CONVENIO" else 0)
        base = 0 if pending else commissionable_base(sale.kind, sale.total_amount)
        target = "ELEGIBLE" if entry["status"] == "CALCULADA" else entry["status"]
        con.execute(
            "UPDATE commission_entries SET saleswoman=?,sale_kind=?,gross_amount=?,agreement_discount=?,"
            "commissionable_base=?,rate_bp=NULL,commission_amount=NULL,policy_status=?,status=?,updated_at=?"
            " WHERE id=?",
            (sale.saleswoman, sale.kind, sale.total_amount, discount, base, POLICY_ABSENT, target,
             _now(), entry["id"]),
        )
        self._history(con, entry["id"], row["id"], entry["status"], target, actor.username,
                      "SOURCE_UPDATED", {**details, "commissionable_base": base, "agreement_discount": discount})
        if balance == 0 and entry["status"] == "PENDIENTE_SALDO":
            self._promote_to_eligible(con, row["id"], cancelled, actor.username)
        elif balance > 0 and entry["status"] != "PENDIENTE_SALDO":
            refreshed = con.execute("SELECT * FROM commission_sales WHERE id=?", (row["id"],)).fetchone()
            self._revert_commission_effect(con, refreshed, actor.username, "SOURCE_UPDATED_REOPENED_BALANCE",
                                           {**details, "reason": "corrección de origen reabrió el saldo"})

    def _reverse_agreement_settlement(self, con, sale_id, actor):
        """Revierte en el libro las liquidaciones por convenio que siguen vigentes."""
        pending = con.execute(
            "SELECT p.id,p.amount,p.payment_date FROM commission_payments p"
            " WHERE p.sale_id=? AND p.kind='CONVENIO'"
            " AND NOT EXISTS(SELECT 1 FROM commission_payments r WHERE r.reverses_id=p.id)",
            (sale_id,),
        ).fetchall()
        for agreement in pending:
            self._insert_payment(con, sale_id, int(agreement["amount"]), agreement["payment_date"],
                                 "REVERSA", "convenio revertido por corrección de origen", actor,
                                 reverses=agreement["id"])
        return len(pending)

    @staticmethod
    def _settled_amount(con, sale_id) -> int:
        """Liquidado neto según el libro append-only: cobros y convenios menos reversas.

        Es la única fuente de verdad de `paid_amount`; nada lo asigna por fuera del libro.
        """
        row = con.execute(
            "SELECT COALESCE(SUM(CASE WHEN kind='REVERSA' THEN -amount ELSE amount END),0)"
            " FROM commission_payments WHERE sale_id=?", (sale_id,)
        ).fetchone()
        return int(row[0])

    # --------------------------------------------------------------- cobros
    @staticmethod
    def _insert_payment(con, sale_id, amount, payment_date, kind, reference, actor,
                        reverses=None, client_key=None):
        # Cada cobro es un hecho propio del libro append-only: identidad interna siempre nueva.
        # La clave del llamador, si existe, se guarda aparte y sólo sirve para su idempotencia.
        payment_id = str(uuid.uuid4())
        con.execute(
            "INSERT INTO commission_payments(id,sale_id,amount,payment_date,kind,reference,reverses_id,"
            "idempotency_key,client_key,actor,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (payment_id, sale_id, amount, payment_date, kind, reference, reverses, payment_id,
             client_key, actor, _now()),
        )
        return payment_id

    def register_payment(self, actor: Principal, sale_id: str, amount: int, payment_date: str,
                         reference: str = "", idempotency_key: str | None = None):
        """Cobro parcial o final. Sólo la cancelación total vuelve comisionable la venta.

        La idempotencia es explícita y del llamador: `idempotency_key` protege el reintento de
        una integración. Sin clave, cada llamada es un cobro real distinto. Un cobro ya revertido
        deja de bloquear su clave, porque una reversa deshace el hecho que la clave representaba.
        """
        self._write(actor)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("el cobro debe ser un entero positivo")
        _month(payment_date)
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            sale = con.execute("SELECT * FROM commission_sales WHERE id=?", (sale_id,)).fetchone()
            if sale is None:
                raise ValueError("venta inexistente")
            if sale["voided"]:
                raise ValueError("venta anulada: no admite cobros")
            if sale["sale_kind"] == "CONVENIO":
                raise ValueError("el convenio no registra saldo cliente")
            # El reintento se reconoce ANTES de validar importes: si no, el reintento del cobro
            # que cancela la venta explotaría por saldo en vez de descartarse limpiamente.
            if idempotency_key and con.execute(
                "SELECT 1 FROM commission_payments p WHERE p.client_key=? AND p.sale_id=? AND p.kind='COBRO'"
                " AND NOT EXISTS(SELECT 1 FROM commission_payments r WHERE r.reverses_id=p.id)",
                (idempotency_key, sale_id),
            ).fetchone():
                con.rollback()
                return None, False
            if amount > int(sale["balance_amount"]):
                raise ValueError("el cobro supera el saldo pendiente")
            payment_id = self._insert_payment(con, sale_id, amount, payment_date, "COBRO", reference,
                                              actor.username, client_key=idempotency_key)
            paid = self._settled_amount(con, sale_id)
            balance = int(sale["total_amount"]) - paid
            cancelled = payment_date if balance == 0 else None
            con.execute(
                "UPDATE commission_sales SET paid_amount=?,balance_amount=?,cancelled_date=?,updated_at=? WHERE id=?",
                (paid, balance, cancelled, _now(), sale_id),
            )
            if balance == 0:
                self._promote_to_eligible(con, sale_id, payment_date, actor.username, payment_id)
            else:
                entry = self._active_entry(con, sale_id)
                if entry is not None:
                    self._history(con, entry["id"], sale_id, entry["status"], entry["status"], actor.username,
                                  "PARTIAL_PAYMENT_INFORMATIVE",
                                  {"amount": amount, "balance": balance, "payment_date": payment_date})
            con.commit()
        return payment_id, True

    def _promote_to_eligible(self, con, sale_id, cancellation_date, actor, payment_id=None):
        """La venta común entra a la comisión del período en que queda cancelada."""
        sale = con.execute("SELECT * FROM commission_sales WHERE id=?", (sale_id,)).fetchone()
        entry = self._active_entry(con, sale_id)
        period = _month(cancellation_date)
        details = {"cancellation_date": cancellation_date, "period": period, "payment_id": payment_id}
        if entry is None:
            self._create_entry(con, sale, "ELEGIBLE", period, actor, "SALE_CANCELLED", details)
            return
        if entry["status"] == "PENDIENTE_SALDO":
            base = commissionable_base(sale["sale_kind"], int(sale["total_amount"]))
            discount = agreement_discount(int(sale["total_amount"])) if sale["sale_kind"] == "CONVENIO" else 0
            con.execute(
                "UPDATE commission_entries SET status='ELEGIBLE',period=?,eligible_date=?,agreement_discount=?,"
                "commissionable_base=?,updated_at=? WHERE id=?",
                (period, cancellation_date, discount, base, _now(), entry["id"]),
            )
            self._history(con, entry["id"], sale_id, "PENDIENTE_SALDO", "ELEGIBLE", actor, "SALE_CANCELLED", details)
            return
        # Existe una liquidación observada previa: no se reabre en silencio.
        self._history(con, entry["id"], sale_id, entry["status"], entry["status"], actor,
                      "RECANCELLED_WHILE_OPEN_ENTRY", details)

    def revert_payment(self, actor: Principal, payment_id: str, reason: str):
        """Revierte un cobro; si deshace la cancelación revierte también su efecto comisionable."""
        self._write(actor)
        reason = reason.strip()
        if not reason:
            raise ValueError("motivo obligatorio")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            payment = con.execute(
                "SELECT * FROM commission_payments WHERE id=? AND kind='COBRO'", (payment_id,)
            ).fetchone()
            if payment is None:
                raise ValueError("cobro inexistente")
            if con.execute("SELECT 1 FROM commission_payments WHERE reverses_id=?", (payment_id,)).fetchone():
                raise ValueError("cobro ya revertido")
            sale_id, amount = payment["sale_id"], int(payment["amount"])
            sale = con.execute("SELECT * FROM commission_sales WHERE id=?", (sale_id,)).fetchone()
            if sale["voided"]:
                raise ValueError("venta anulada: no admite reversión de cobros")
            if sale["sale_kind"] == "CONVENIO":
                raise ValueError("la venta es hoy un convenio: el cobro ya no participa de su liquidación")
            self._insert_payment(con, sale_id, amount, payment["payment_date"], "REVERSA", reason,
                                 actor.username, reverses=payment_id)
            paid = self._settled_amount(con, sale_id)
            balance = int(sale["total_amount"]) - paid
            con.execute(
                "UPDATE commission_sales SET paid_amount=?,balance_amount=?,cancelled_date=NULL,updated_at=? WHERE id=?",
                (paid, balance, _now(), sale_id),
            )
            self._revert_commission_effect(con, sale, actor.username, "PAYMENT_REVERTED",
                                           {"reason": reason, "payment_id": payment_id, "balance": balance})
            con.commit()

    def _revert_commission_effect(self, con, sale, actor, action, details):
        entry = self._active_entry(con, sale["id"])
        if entry is None:
            return
        if _was_paid(entry):
            # Una liquidación con dinero ya pagado nunca se revierte: queda OBSERVADA.
            self._set_status(con, entry, "OBSERVADA", actor, action, details,
                             observation=f"Reversión posterior al pago ({details.get('reason', '')}). Requiere corrección manual.")
            return
        if entry["status"] == "OBSERVADA":
            self._history(con, entry["id"], sale["id"], "OBSERVADA", "OBSERVADA", actor, action, details)
            return
        self._set_status(con, entry, "REVERTIDA", actor, action, details)
        refreshed = con.execute("SELECT * FROM commission_sales WHERE id=?", (sale["id"],)).fetchone()
        if not refreshed["voided"] and int(refreshed["balance_amount"]) > 0:
            self._create_entry(con, refreshed, "PENDIENTE_SALDO", None, actor, "PENDING_AFTER_REVERSAL", details)

    def void_sale(self, actor: Principal, sale_id: str, reason: str):
        """Regla aprobada 8: una venta anulada no genera comisión."""
        self._write(actor)
        reason = reason.strip()
        if not reason:
            raise ValueError("motivo obligatorio")
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            sale = con.execute("SELECT * FROM commission_sales WHERE id=?", (sale_id,)).fetchone()
            if sale is None:
                raise ValueError("venta inexistente")
            if sale["voided"]:
                con.rollback()
                return False
            con.execute("UPDATE commission_sales SET voided=1,void_reason=?,updated_at=? WHERE id=?",
                        (reason, _now(), sale_id))
            entry = self._active_entry(con, sale_id)
            if entry is not None:
                if _was_paid(entry):
                    self._set_status(con, entry, "OBSERVADA", actor.username, "SALE_VOIDED", {"reason": reason},
                                     observation=f"Venta anulada tras el pago de la comisión: {reason}")
                else:
                    self._set_status(con, entry, "REVERTIDA", actor.username, "SALE_VOIDED", {"reason": reason})
            con.commit()
        return True

    # ------------------------------------------------------------ transición
    def _set_status(self, con, entry, target, actor, action, details=None, **columns):
        assignments = ["status=?", "updated_at=?"]
        values = [target, _now()]
        for name, value in columns.items():
            assignments.append(f"{name}=?")
            values.append(value)
        values.append(entry["id"])
        con.execute(f"UPDATE commission_entries SET {','.join(assignments)} WHERE id=?", values)
        self._history(con, entry["id"], entry["sale_id"], entry["status"], target, actor, action, details)

    def _transition(self, actor, entry_id, allowed, target, action, details=None, guard=None, **columns):
        self._write(actor)
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            entry = con.execute("SELECT * FROM commission_entries WHERE id=?", (entry_id,)).fetchone()
            if entry is None:
                raise ValueError("liquidación inexistente")
            if entry["status"] not in allowed:
                raise ValueError(
                    f"transición inválida: {entry['status']} → {target}; requiere {'/'.join(sorted(allowed))}"
                )
            if guard is not None:
                guard(entry)
            self._set_status(con, entry, target, actor.username, action, details, **columns)
            con.commit()
        return True

    def review(self, actor: Principal, entry_id: str, note: str = ""):
        """Revisar el cálculo antes de cualquier aprobación."""
        return self._transition(actor, entry_id, {"CALCULADA"}, "REVISADA", "CALCULATION_REVIEWED",
                                {"note": note}, reviewed_by=actor.username, reviewed_at=_now())

    def approve(self, actor: Principal, entry_id: str, responsible: str):
        responsible = responsible.strip()
        if not responsible:
            raise ValueError("responsable obligatorio")
        return self._transition(actor, entry_id, {"REVISADA"}, "APROBADA", "COMMISSION_APPROVED",
                                {"responsible": responsible}, approved_by=responsible, approved_at=_now())

    def mark_paid(self, actor: Principal, entry_id: str, payment_date: str, reference: str):
        """Sólo se paga lo revisado y aprobado; nunca se salta la aprobación."""
        reference = reference.strip()
        if not reference:
            raise ValueError("referencia de pago obligatoria")
        _month(payment_date)
        return self._transition(actor, entry_id, {"APROBADA"}, "PAGADA", "COMMISSION_PAID",
                                {"payment_date": payment_date, "reference": reference},
                                paid_at=payment_date, payment_reference=reference)

    def observe(self, actor: Principal, entry_id: str, reason: str):
        reason = reason.strip()
        if not reason:
            raise ValueError("motivo obligatorio")
        return self._transition(actor, entry_id, OPEN_STATES | {"PAGADA"}, "OBSERVADA",
                                "COMMISSION_OBSERVED", {"reason": reason}, observation=reason)

    def revert(self, actor: Principal, entry_id: str, reason: str):
        """Una liquidación con dinero ya pagado nunca se revierte, ni pasando por OBSERVADA."""
        reason = reason.strip()
        if not reason:
            raise ValueError("motivo obligatorio")
        return self._transition(actor, entry_id, OPEN_STATES | {"OBSERVADA"}, "REVERTIDA",
                                "COMMISSION_REVERTED", {"reason": reason},
                                guard=_reject_paid, observation=reason)

    # ------------------------------------------------------------- política
    def set_policy(self, actor: Principal, scope: str, rate_bp: int, scope_value: str = ""):
        """Configuración sintética de porcentaje: NO es una regla productiva aprobada."""
        self._write(actor)
        if scope not in {"GENERAL", "LOCAL", "VENDEDORA"}:
            raise ValueError("alcance de política inválido")
        if isinstance(rate_bp, bool) or not isinstance(rate_bp, int) or not 0 <= rate_bp <= BASIS_POINTS:
            raise ValueError("porcentaje inválido: use puntos básicos enteros de 0 a 10000")
        if scope != "GENERAL" and not scope_value.strip():
            raise ValueError("el alcance requiere un valor")
        scope_value = "" if scope == "GENERAL" else scope_value.strip()
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO commission_policies(id,scope,scope_value,rate_bp,approval_status,created_by,created_at)"
                " VALUES(?,?,?,?,?,?,?) ON CONFLICT(scope,scope_value) DO UPDATE SET rate_bp=excluded.rate_bp,"
                "approval_status=excluded.approval_status,created_by=excluded.created_by,created_at=excluded.created_at",
                (str(uuid.uuid5(uuid.NAMESPACE_URL, f"bc-comision-politica:{scope}:{scope_value}")),
                 scope, scope_value, rate_bp, POLICY_PENDING, actor.username, _now()),
            )
            self.repository.audit(con, actor.username, "COMMISSION_POLICY_SET", f"{scope}:{scope_value}",
                                  details={"rate_bp": rate_bp, "approval_status": POLICY_PENDING})
            con.commit()

    def policies(self, actor: Principal):
        self._read(actor)
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM commission_policies ORDER BY scope,scope_value")]

    # ------------------------------------------------------------- recálculo
    def recalculate(self, actor: Principal, *, period: str | None = None, branch: str | None = None):
        """Recalcula base y comisión de forma segura e idempotente."""
        self._write(actor)
        query = "SELECT * FROM commission_entries WHERE status IN ('ELEGIBLE','CALCULADA')"
        params: list = []
        if period:
            query += " AND period=?"
            params.append(period)
        if branch:
            query += " AND branch=?"
            params.append(branch)
        evaluated = changed = 0
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            for entry in con.execute(query, params).fetchall():
                evaluated += 1
                sale = con.execute("SELECT * FROM commission_sales WHERE id=?", (entry["sale_id"],)).fetchone()
                total = int(sale["total_amount"])
                discount = agreement_discount(total) if sale["sale_kind"] == "CONVENIO" else 0
                base = commissionable_base(sale["sale_kind"], total)
                rate, policy_status = self.policy.rate_for(
                    branch=sale["branch"], saleswoman=sale["saleswoman"], period=entry["period"] or "")
                commission = None if rate is None else apply_basis_points(base, rate)
                current = (entry["status"], int(entry["gross_amount"]), int(entry["agreement_discount"]),
                           int(entry["commissionable_base"]), entry["rate_bp"], entry["commission_amount"],
                           entry["policy_status"])
                target = ("CALCULADA", total, discount, base, rate, commission, policy_status)
                if current == target:
                    continue
                changed += 1
                con.execute(
                    "UPDATE commission_entries SET status='CALCULADA',gross_amount=?,agreement_discount=?,"
                    "commissionable_base=?,rate_bp=?,commission_amount=?,policy_status=?,updated_at=? WHERE id=?",
                    (total, discount, base, rate, commission, policy_status, _now(), entry["id"]),
                )
                self._history(con, entry["id"], entry["sale_id"], entry["status"], "CALCULADA", actor.username,
                              "COMMISSION_RECALCULATED",
                              {"commissionable_base": base, "agreement_discount": discount,
                               "rate_bp": rate, "commission_amount": commission, "policy_status": policy_status})
            con.commit()
        return {"evaluated": evaluated, "changed": changed}

    # ------------------------------------------------------------- consultas
    def list_entries(self, actor: Principal, *, period=None, branch=None, saleswoman=None, status=None,
                     kind=None, include_reverted=True):
        """Un período incluye lo liquidado en él y lo aún pendiente de saldo de ese mes."""
        self._read(actor)
        query = (
            "SELECT e.*, s.sale_date, s.balance_amount, s.paid_amount, s.voided, s.envelope,"
            " s.cancelled_date AS sale_cancelled_date"
            " FROM commission_entries e JOIN commission_sales s ON s.id=e.sale_id WHERE 1=1"
        )
        params: list = []
        if period:
            query += " AND (e.period=? OR (e.period IS NULL AND substr(s.sale_date,1,7)=?))"
            params += [period, period]
        for clause, value in (("e.branch=?", branch), ("e.saleswoman=?", saleswoman),
                              ("e.status=?", status), ("e.sale_kind=?", kind)):
            if value:
                query += " AND " + clause
                params.append(value)
        if not include_reverted:
            query += " AND e.status<>'REVERTIDA'"
        query += " ORDER BY e.branch,e.saleswoman,s.sale_date,e.sequence"
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(query, params).fetchall()]

    def get_entry(self, actor: Principal, entry_id: str):
        self._read(actor)
        with self.repository.connection() as con:
            row = con.execute(
                "SELECT e.*, s.sale_date, s.balance_amount, s.paid_amount, s.voided, s.total_amount AS sale_total,"
                " s.envelope, s.source_sale_id"
                " FROM commission_entries e JOIN commission_sales s ON s.id=e.sale_id WHERE e.id=?", (entry_id,)
            ).fetchone()
        if row is None:
            raise ValueError("liquidación inexistente")
        return dict(row)

    def breakdown(self, actor: Principal, entry_id: str):
        """Explica en texto por qué la venta comisiona, aún no comisiona u observó."""
        entry = self.get_entry(actor, entry_id)
        lines = [
            {"label": "Total de la venta", "amount": int(entry["gross_amount"]), "sign": ""},
        ]
        if entry["sale_kind"] == "CONVENIO":
            lines.append({"label": f"Descuento de convenio ({AGREEMENT_DISCOUNT_BP / 100:.0f}%)",
                          "amount": int(entry["agreement_discount"]), "sign": "−"})
        lines.append({"label": "Base comisionable", "amount": int(entry["commissionable_base"]), "sign": "="})
        if entry["rate_bp"] is not None:
            lines.append({"label": f"Porcentaje configurado ({entry['rate_bp'] / 100:.2f}%)",
                          "amount": int(entry["commission_amount"] or 0), "sign": "×"})
        reasons = {
            "PENDIENTE_SALDO": f"Todavía no comisiona: saldo pendiente de {int(entry['balance_amount'])} Gs.",
            "ELEGIBLE": "Elegible: la venta quedó totalmente cancelada.",
            "CALCULADA": "Cálculo hecho y pendiente de revisión.",
            "REVISADA": "Cálculo revisado y pendiente de aprobación.",
            "APROBADA": f"Aprobada por {entry['approved_by']}; pendiente de pago.",
            "PAGADA": f"Pagada el {entry['paid_at']} con referencia {entry['payment_reference']}.",
            "OBSERVADA": f"Observada: {entry['observation']}",
            "REVERTIDA": f"Revertida: {entry['observation'] or 'ver historial'}",
        }
        reason = reasons[entry["status"]]
        if entry["sale_kind"] == "CONVENIO":
            # El motivo del convenio acompaña a la liquidación en todos sus estados.
            reason = ("Convenio: venta finalizada para comisión aunque la empresa pague después; "
                      f"base con descuento del {AGREEMENT_DISCOUNT_BP // 100}%. " + reason)
        return {
            "entry_id": entry_id, "status": entry["status"], "reason": reason,
            "lines": lines,
            "policy_status": entry["policy_status"],
            "policy_note": "Porcentaje sintético pendiente de aprobación." if entry["policy_status"] == POLICY_PENDING
            else "Sin porcentaje canónico configurado: se informa sólo la base comisionable.",
        }

    def history(self, actor: Principal, entry_id: str):
        self._read(actor)
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM commission_entry_history WHERE entry_id=? ORDER BY id", (entry_id,))]

    def sale_history(self, actor: Principal, sale_id: str):
        self._read(actor)
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM commission_entry_history WHERE sale_id=? ORDER BY id", (sale_id,))]

    def payments(self, actor: Principal, sale_id: str):
        self._read(actor)
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM commission_payments WHERE sale_id=? ORDER BY recorded_at,id", (sale_id,))]

    # --------------------------------------------------------------- reporte
    def report(self, actor: Principal, period: str, *, branch=None, saleswoman=None, status=None):
        """Resumen mensual con KPIs y detalle por vendedora."""
        rows = self.list_entries(actor, period=period, branch=branch, saleswoman=saleswoman, status=status)
        with self.repository.connection() as con:
            partials = con.execute(
                "SELECT count(*) count, COALESCE(SUM(p.amount),0) total FROM commission_payments p"
                " JOIN commission_sales s ON s.id=p.sale_id"
                " WHERE p.kind='COBRO' AND substr(p.payment_date,1,7)=? AND s.balance_amount>0 AND s.voided=0"
                # Un cobro revertido no es dinero en caja: nunca se informa como cobrado.
                " AND NOT EXISTS(SELECT 1 FROM commission_payments r WHERE r.reverses_id=p.id)"
                + (" AND s.branch=?" if branch else "") + (" AND s.saleswoman=?" if saleswoman else ""),
                [period] + [value for value in (branch, saleswoman) if value],
            ).fetchone()
        countable = [row for row in rows if row["status"] != "REVERTIDA"]
        eligible = [row for row in countable if row["status"] != "PENDIENTE_SALDO"]
        kpi = {
            "sales_in_period": sum(1 for row in countable if row["sale_date"][:7] == period),
            "cancelled_sales": sum(1 for row in eligible if row["sale_kind"] == "COMUN"),
            "pending_balance_sales": sum(1 for row in countable if row["status"] == "PENDIENTE_SALDO"),
            "partial_payments_count": int(partials["count"]),
            "partial_payments_amount": int(partials["total"]),
            "agreements": sum(1 for row in eligible if row["sale_kind"] == "CONVENIO"),
            "gross_informative": sum(int(row["gross_amount"]) for row in countable),
            "agreement_discount": sum(int(row["agreement_discount"]) for row in eligible),
            "commissionable_base": sum(int(row["commissionable_base"]) for row in eligible),
            "commission_amount": sum(int(row["commission_amount"] or 0) for row in eligible),
            "pending_approval": sum(1 for row in eligible if row["status"] in {"ELEGIBLE", "CALCULADA", "REVISADA"}),
            "observed": sum(1 for row in countable if row["status"] == "OBSERVADA"),
            "paid_entries": sum(1 for row in eligible if row["status"] == "PAGADA"),
            "paid_amount": sum(int(row["commission_amount"] or 0) for row in eligible if row["status"] == "PAGADA"),
        }
        grouped: dict[tuple[str, str], dict] = {}
        for row in countable:
            key = (row["branch"], row["saleswoman"])
            bucket = grouped.setdefault(key, {
                "branch": row["branch"], "saleswoman": row["saleswoman"], "sales": 0, "pending_balance": 0,
                "cancelled": 0, "agreements": 0, "gross_informative": 0, "agreement_discount": 0,
                "commissionable_base": 0, "commission_amount": 0, "paid_amount": 0,
            })
            bucket["sales"] += 1
            bucket["gross_informative"] += int(row["gross_amount"])
            if row["status"] == "PENDIENTE_SALDO":
                bucket["pending_balance"] += 1
                continue
            bucket["cancelled" if row["sale_kind"] == "COMUN" else "agreements"] += 1
            bucket["agreement_discount"] += int(row["agreement_discount"])
            bucket["commissionable_base"] += int(row["commissionable_base"])
            bucket["commission_amount"] += int(row["commission_amount"] or 0)
            if row["status"] == "PAGADA":
                bucket["paid_amount"] += int(row["commission_amount"] or 0)
        return {
            "period": period,
            "filters": {"branch": branch, "saleswoman": saleswoman, "status": status},
            "kpi": kpi,
            "by_saleswoman": sorted(grouped.values(), key=lambda item: (item["branch"], item["saleswoman"])),
            "entries": rows,
        }

    def export_summary(self, actor: Principal, period: str, *, branch=None, saleswoman=None):
        """Resumen estructurado y estable, sin datos sensibles del cliente."""
        data = self.report(actor, period, branch=branch, saleswoman=saleswoman)
        entries = []
        for row in data["entries"]:
            entries.append({name: row.get(name if name != "entry_id" else "id") for name in ENTRY_EXPORT_FIELDS})
        return {
            "contract_version": 1,
            "period": period,
            "generated_at": _now(),
            "filters": data["filters"],
            "kpi": data["kpi"],
            "by_saleswoman": data["by_saleswoman"],
            "entries": entries,
            "policy_disclaimer": "El porcentaje de comisión es configuración sintética pendiente de aprobación.",
        }

    # ------------------------------------------------------------ integración
    def sync_review_sales(self, actor: Principal, review_service):
        """Ingesta desde la revisión de ventas. Gastos y entregas nunca ingresan."""
        registered = skipped = invalid_date = 0
        for row in review_service.list_sales(actor):
            payload = row["payload"]
            total = int(payload.get("total") or 0)
            saleswoman = str(payload.get("saleswoman") or "").strip()
            if total <= 0 or not saleswoman:
                skipped += 1
                continue
            try:
                # El período de liquidación depende de esta fecha: no se ingiere si es inválida.
                _month(payload.get("date", ""))
            except ValueError:
                invalid_date += 1
                continue
            agreement = int(payload.get("agreement") or 0)
            settled = int(payload.get("cash") or 0) + int(payload.get("card_transfer") or 0)
            kind = "CONVENIO" if agreement >= total else "COMUN"
            paid = total if kind == "CONVENIO" else min(settled, total)
            sale = CommissionSaleInput(
                branch=row["branch"], source_sale_id=row["identity"], saleswoman=saleswoman,
                sale_date=payload["date"], kind=kind, total_amount=total, initial_paid=paid,
                envelope=payload.get("envelope", ""),
            )
            registered += int(self.register_sale(actor, sale)[1])
        return {"registered": registered, "skipped": skipped, "invalid_date": invalid_date}
