"""Comisiones por vendedora y local: reglas económicas aprobadas, cálculo local-first.

La lógica vive separada de la interfaz. Los importes son enteros de guaraníes y el
cálculo es `Decimal` con redondeo HALF_UP: no se usan floats en ningún punto.

El porcentaje ya no es configuración sintética. La regla productiva aprobada —1% general,
igual para toda vendedora y todo local— vive en `comision_policy.py`; aquí se aplica y se
deja grabada en cada liquidación junto con su versión y su vigencia.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from typing import Protocol

from .comision_policy import (
    AGREEMENT_DISCOUNT_BP, BASIS_POINTS, BOUNDARY_SQL_IN, CANONICAL_CODE,
    CANONICAL_EFFECTIVE_FROM, CANONICAL_POLICY_ID, CANONICAL_RATE_BP, CANONICAL_SCOPE,
    CANONICAL_VERSION, CURRENCY, POLICY_ABSENT, POLICY_CANONICAL, POLICY_LEGACY,
    POLICY_OUT_OF_EFFECT, POLICY_STATUSES, RATING_BOUNDARY_STATES, ROUNDING_MODE, PolicyDecision,
    agreement_discount, apply_basis_points, commission_for, commissionable_base, is_in_effect,
    normalize_effective_from, rate_decimal_text, rate_percent_text,
)
from .models import Principal, Role, utc_now
from .service import AccessDenied, CentralManagementService


COMMISSION_STATES = (
    "PENDIENTE_SALDO", "ELEGIBLE", "CALCULADA", "REVISADA",
    "APROBADA", "PAGADA", "OBSERVADA", "REVERTIDA",
)
SALE_KINDS = ("COMUN", "CONVENIO")

# Estados que no pueden recalcularse ni revertirse en silencio.
FROZEN_STATES = frozenset({"PAGADA"})
RECALCULABLE_STATES = frozenset({"ELEGIBLE", "CALCULADA"})
OPEN_STATES = frozenset({"ELEGIBLE", "CALCULADA", "REVISADA", "APROBADA"})
# Ya pasaron por revisión humana: una corrección de origen no puede recalcularlos en silencio.
REVIEWED_STATES = frozenset({"REVISADA", "APROBADA", "PAGADA"})
# Estados en los que una liquidación ya recibió un porcentaje. Se conservan porque describen el
# ciclo, pero **no** son la protección de un período: la fijación de la tasa vive en el libro
# `commission_period_rate_events` y depende de si hay algún hecho oficial **vivo**, no del estado
# de una liquidación concreta.
SETTLED_STATES = ("CALCULADA", "REVISADA", "APROBADA", "PAGADA")

# `RATING_BOUNDARY_STATES` —el boundary económico— vive en `comision_policy` porque la migración
# del repositorio necesita exactamente el mismo predicado que el cálculo. Se reexporta aquí para
# que quien lea este módulo lo encuentre donde lo espera.
#
# El período NO queda fijado en el primer cálculo: se fija cuando una liquidación alcanza
# `APROBADA` o `PAGADA`, y permanece fijado **mientras alguno de esos hechos siga vivo**. Un
# cálculo provisional puede estar mal —una fecha mal tipeada, una venta que después se anula— y
# fijar el mes con él lo volvía incorregible; sostenerlo con un hecho que después se anuló lo
# volvía incorregible igual, un estado más adelante.
#
# Estados provisionales: siguen siendo corregibles y no fijan nada.
PROVISIONAL_STATES = frozenset({"ELEGIBLE", "CALCULADA", "REVISADA"})

# La trazabilidad de la política viaja con la liquidación, no se reconstruye después.
POLICY_TRACE_FIELDS = ("policy_status", "policy_code", "policy_version",
                       "policy_effective_from", "policy_scope")

ENTRY_EXPORT_FIELDS = (
    "entry_id", "period", "branch", "saleswoman", "sale_kind", "status",
    "sale_date", "cancelled_date", "gross_amount", "agreement_discount",
    "commissionable_base", "rate_bp", "commission_amount", "policy_status",
    "policy_code", "policy_version", "policy_effective_from", "policy_scope",
    "balance_amount", "observation",
)


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


POLICY_STALE_MESSAGE = "recalcule antes de continuar"

# Eventos del libro de tasas por período. Sólo estos dos, y siempre en pares alternos por período.
PERIOD_RATE_PINNED = "PINNED"
PERIOD_RATE_UNPINNED = "UNPINNED"


def _last_period_rate_event(con, period):
    """Último evento del período: es lo que define si hoy está fijado y a qué tasa."""
    return con.execute(
        "SELECT * FROM commission_period_rate_events WHERE period=? ORDER BY id DESC LIMIT 1",
        (str(period)[:7],),
    ).fetchone()


def _pinned_periods_from(con, effective_from):
    """Períodos hoy fijados cuyo mes no es anterior a esa vigencia.

    Sirve para dejar constancia de qué queda fuera del alcance real de una publicación. Un período
    desfijado **no** aparece aquí: la versión nueva sí lo gobierna, que es justamente el efecto de
    haber retirado su justificación.
    """
    return [row[0] for row in con.execute(
        "SELECT e.period FROM commission_period_rate_events e"
        " JOIN (SELECT period, MAX(id) AS newest FROM commission_period_rate_events GROUP BY period) last"
        "   ON last.period=e.period AND last.newest=e.id"
        " WHERE e.event=? AND substr(e.period,1,7)>=substr(?,1,7) ORDER BY e.period",
        (PERIOD_RATE_PINNED, effective_from))]


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
    """Puerto de resolución de la política oficial de comisión."""

    def decide(self, *, branch: str, saleswoman: str, period: str) -> PolicyDecision: ...


class CanonicalCommissionPolicy:
    """Regla productiva aprobada: un único porcentaje general, versionado y con vigencia.

    `branch` y `saleswoman` se reciben para dejar explícito en la firma que **no** alteran
    el porcentaje: la decisión aprobada es el mismo 1% para toda vendedora y todo local.
    No existe alcance por vendedora ni por local, y la migración retiró los que había.
    """

    def __init__(self, repository):
        self.repository = repository

    def current(self) -> dict:
        """Última versión publicada; si faltara la fila, la constante aprobada del módulo."""
        with self.repository.connection() as con:
            row = con.execute(
                "SELECT * FROM commission_policies WHERE scope=? AND scope_value=''",
                (CANONICAL_SCOPE,),
            ).fetchone()
        if row is None:
            return {"id": CANONICAL_POLICY_ID, "scope": CANONICAL_SCOPE, "scope_value": "",
                    "rate_bp": CANONICAL_RATE_BP, "approval_status": POLICY_CANONICAL,
                    "code": CANONICAL_CODE, "version": CANONICAL_VERSION,
                    "effective_from": CANONICAL_EFFECTIVE_FROM}
        return dict(row)

    def catalogue(self) -> list[dict]:
        """Versiones publicadas, ordenadas por vigencia. El historial no es decorativo."""
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT version,rate_bp,effective_from,code FROM commission_policy_versions"
                " WHERE policy_id=? ORDER BY effective_from,version", (CANONICAL_POLICY_ID,))]

    def in_force_for(self, period: str) -> dict | None:
        """Versión que gobierna ese período: la de vigencia más reciente que no lo supera.

        Resolver por período —y no por «la última publicada»— es lo que impide que
        programar el porcentaje del mes que viene reescriba el mes en curso.
        """
        applicable = [row for row in self.catalogue() if is_in_effect(period, row["effective_from"])]
        return applicable[-1] if applicable else None

    def pinned_for(self, period: str) -> dict | None:
        """Tasa con la que ese período está fijado **ahora**, si un hecho económico vivo la sostiene.

        Se resuelve por el **último evento** del libro `commission_period_rate_events`: si es
        `PINNED`, ésa es la tasa del período; si es `UNPINNED` —o si no hay ningún evento— el
        período no está fijado y vuelve a resolverse por catálogo.

        La tasa de un período **no es inmutable por haber existido alguna vez un hecho que la
        justificó**. Se fija en el boundary `APROBADA`/`PAGADA` y se sostiene mientras quede al
        menos un hecho oficial vivo. Cuando el último se retira —una aprobación revertida, una venta
        anulada, un cobro que se cae— la justificación desaparece y el período vuelve a ser
        resoluble; el rastro de que estuvo fijado no desaparece nunca, porque el libro es
        append-only.

        Un período que sólo tiene cálculos provisionales nunca tuvo evento, y por eso sigue siendo
        corregible: es la diferencia entre un número todavía en revisión y dinero avalado.
        """
        if not period:
            return None
        with self.repository.connection() as con:
            row = _last_period_rate_event(con, str(period)[:7])
        if row is None or row["event"] != "PINNED":
            return None
        return dict(row)

    def decide(self, *, branch: str, saleswoman: str, period: str) -> PolicyDecision:
        # Un período ya **fijado** conserva su tasa. Publicar una versión nueva no lo reescribe,
        # y por eso publicar nunca hace falta bloquearlo: la protección no está en negar la
        # operación sino en que el período ya comprometido deje de depender de lo que se publique.
        # Un período con sólo cálculos provisionales no está fijado y sí se resuelve por catálogo:
        # eso es lo que lo mantiene corregible.
        pinned = self.pinned_for(period)
        if pinned is not None:
            return PolicyDecision(int(pinned["rate_bp"]), POLICY_CANONICAL,
                                  int(pinned["policy_version"]), pinned["policy_effective_from"],
                                  pinned["policy_scope"] or CANONICAL_SCOPE,
                                  pinned["policy_code"] or CANONICAL_CODE)
        catalogue = self.catalogue()
        if not catalogue:
            # Base sin historial de versiones: se resuelve con la fila vigente.
            policy = self.current()
            effective_from = policy["effective_from"] or CANONICAL_EFFECTIVE_FROM
            version, code = int(policy["version"]), policy["code"] or CANONICAL_CODE
            if not is_in_effect(period, effective_from):
                return PolicyDecision(None, POLICY_OUT_OF_EFFECT, version, effective_from,
                                      CANONICAL_SCOPE, code)
            return PolicyDecision(int(policy["rate_bp"]), POLICY_CANONICAL, version,
                                  effective_from, CANONICAL_SCOPE, code)
        version = self.in_force_for(period)
        if version is None:
            # Un período anterior a toda vigencia no comisiona: se informa la base y se deja
            # dicho por qué, en vez de aplicar un porcentaje hacia atrás.
            oldest = catalogue[0]
            return PolicyDecision(None, POLICY_OUT_OF_EFFECT, int(oldest["version"]),
                                  oldest["effective_from"], CANONICAL_SCOPE,
                                  oldest["code"] or CANONICAL_CODE)
        return PolicyDecision(int(version["rate_bp"]), POLICY_CANONICAL, int(version["version"]),
                              version["effective_from"], CANONICAL_SCOPE,
                              version["code"] or CANONICAL_CODE)


class CommissionService:
    """Bandeja y reporte mensual de comisiones. No altera las reglas de BC Caja."""

    def __init__(self, core: CentralManagementService, policy: CommissionPolicyPort | None = None):
        self.core = core
        self.repository = core.repository
        self.policy = policy or CanonicalCommissionPolicy(core.repository)

    # ---------------------------------------------------------------- acceso
    def _read(self, actor: Principal):
        if actor.role == Role.OPERADOR_LOCAL:
            raise AccessDenied("operador local sin acceso a comisiones")
        self.core._require(actor, "dashboard.read")

    def _write(self, actor: Principal):
        self.core._require(actor, "reviews.manage")

    # -------------------------------------------------------------- guardas
    def _reject_voided_sale(self, entry) -> None:
        """Regla aprobada 8, defendida también donde sale el dinero.

        `void_sale` mueve la liquidación a `REVERTIDA` u `OBSERVADA`, así que por ruta pública no
        se llega aquí con una venta anulada. Una base legada de procedencia externa sí puede traer
        esa fila, y hasta la generación 7 el sistema la revisaba, la aprobaba y la pagaba. Una venta
        anulada no genera comisión: tampoco cuando la incoherencia llega de fuera.
        """
        with self.repository.connection() as con:
            voided = con.execute("SELECT voided FROM commission_sales WHERE id=?",
                                 (entry["sale_id"],)).fetchone()
        if voided is not None and voided[0]:
            raise ValueError("la venta de origen está anulada: no genera comisión")

    def _require_official_and_live(self, entry) -> None:
        """Guarda de la cadena de pago: la venta existe de verdad y el importe es el oficial."""
        self._reject_voided_sale(entry)
        self._require_current_policy(entry)

    def _require_current_policy(self, entry) -> None:
        """Nadie revisa, aprueba ni paga un importe que no sea el oficial vigente hoy.

        No alcanza con que haya un importe, ni con que lleve el sello `CANONICA_APROBADA`:
        el sello se grabó en el momento del cálculo y puede haber quedado atrás. Se compara
        contra la política que rige **hoy el período de esa liquidación**, así que una
        publicación posterior no puede colar al pago un porcentaje que ya no es el oficial.
        """
        if entry["rate_bp"] is None or entry["commission_amount"] is None:
            raise ValueError(
                f"la liquidación no tiene la política oficial aplicada: {POLICY_STALE_MESSAGE}")
        if entry["policy_status"] != POLICY_CANONICAL:
            raise ValueError(
                f"la liquidación no lleva la política oficial vigente ({entry['policy_status']}): "
                f"{POLICY_STALE_MESSAGE}")
        decision = self.policy.decide(branch=entry["branch"], saleswoman=entry["saleswoman"],
                                      period=entry["period"] or "")
        if (decision.rate_bp, decision.version) != (int(entry["rate_bp"]), entry["policy_version"]):
            raise ValueError(
                f"la política del período cambió desde el cálculo "
                f"(v{entry['policy_version']} → v{decision.version}): {POLICY_STALE_MESSAGE}")

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
        if row["sale_kind"] == "CONVENIO":
            # Toda corrección sobre un convenio re-expresa su liquidación: se revierte la anterior
            # y, si sigue siendo convenio, se asienta la nueva por el total corregido. Así el
            # convenio puede corregirse a la baja, cosa que su propia liquidación previa impedía.
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
            # La corrección invalida el cálculo anterior: cae también la traza de política,
            # porque la que había ya no describe el importe que se va a recalcular.
            "UPDATE commission_entries SET saleswoman=?,sale_kind=?,gross_amount=?,agreement_discount=?,"
            "commissionable_base=?,rate_bp=NULL,commission_amount=NULL,policy_status=?,policy_code=NULL,"
            "policy_version=NULL,policy_effective_from=NULL,policy_scope=NULL,status=?,updated_at=?"
            " WHERE id=?",
            (sale.saleswoman, sale.kind, sale.total_amount, discount, base, POLICY_ABSENT, target,
             _now(), entry["id"]),
        )
        source_details = {**details, "commissionable_base": base, "agreement_discount": discount}
        # La corrección retira la tasa y el importe anteriores. Si los había, se asientan: es la
        # única ruta pública por la que un importe heredado —que no tiene asiento previo porque
        # llegó migrado— podría desaparecer sin dejar rastro. Mismo bloque y mismo nombre que
        # escribe `recalculate`, para que auditar no dependa de por dónde se anuló.
        if entry["commission_amount"] is not None or entry["rate_bp"] is not None:
            source_details["replaced"] = {"rate_bp": entry["rate_bp"],
                                          "commission_amount": entry["commission_amount"],
                                          "policy_status": entry["policy_status"]}
        self._history(con, entry["id"], row["id"], entry["status"], target, actor.username,
                      "SOURCE_UPDATED", source_details)
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
        # Toda transición de estado pasa por aquí, así que aquí es donde se comprueba si el período
        # se quedó sin hechos económicos vivos. Ponerlo en el choke point y no en cada operación es
        # lo que hace que las cuatro rutas de `AB1-g6` —y cualquiera futura— queden cubiertas por
        # construcción en vez de una por una.
        self._reconcile_period_pin(con, entry["period"], actor, action)

    # ------------------------------------------------- fijación de la tasa del período
    #
    # Todo lo que fija o desfija un período pasa por aquí. Es deliberado que ningún otro sitio del
    # módulo escriba `commission_period_rate_events`: la regla económica es una sola y no puede
    # divergir entre quien aprueba, quien revierte y quien migra.

    @staticmethod
    def _live_official_facts(con, period):
        """Hechos económicos oficiales **vivos** del período, en orden.

        Un hecho está vivo si hoy sostiene dinero: la liquidación está `APROBADA` o `PAGADA` sobre
        una venta que no fue anulada, **o** conserva `paid_at`, que significa que el dinero salió de
        verdad. Lo pagado cuenta aunque después se observe o se anule la venta: observar no devuelve
        una transferencia.

        `ELEGIBLE`, `CALCULADA`, `REVISADA`, `OBSERVADA` sin pago y `REVERTIDA` no son hechos vivos.
        Una aprobación revertida deja de sostener nada, y ése es exactamente el punto: era el
        bloqueante `AB1-g6`.

        La migración usa esta misma definición, en SQL equivalente, para que migrar una base y
        reconstruirla operando den el mismo resultado.
        """
        return con.execute(
            "SELECT e.id,e.status,e.rate_bp,e.paid_at FROM commission_entries e"
            " JOIN commission_sales s ON s.id=e.sale_id"
            " WHERE e.period=? AND (e.paid_at IS NOT NULL"
            f"        OR (e.status IN {BOUNDARY_SQL_IN} AND COALESCE(s.voided,0)=0))"
            " ORDER BY e.id",
            (str(period)[:7],),
        ).fetchall()

    def _record_period_rate_event(self, con, period, event, *, rate_bp, policy_code, policy_version,
                                  policy_effective_from, policy_scope, origin, actor, reason,
                                  entry_id=None, sale_id=None):
        """Único escritor del libro de tasas. Append-only: nunca actualiza ni borra.

        Escribe el evento y su asiento en `central_audit` en la misma transacción, de modo que no
        existe un estado en el que uno esté sin el otro. Que sea el único escritor es lo que permite
        afirmar que la secuencia `PINNED` → `UNPINNED` → `PINNED` de un período está completa.
        """
        action = ("COMMISSION_PERIOD_RATE_PINNED" if event == PERIOD_RATE_PINNED
                  else "COMMISSION_PERIOD_RATE_UNPINNED")
        con.execute(
            "INSERT INTO commission_period_rate_events(period,event,rate_bp,policy_code,policy_version,"
            "policy_effective_from,policy_scope,origin,entry_id,sale_id,reason,actor,recorded_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (period, event, int(rate_bp), policy_code or CANONICAL_CODE, policy_version,
             policy_effective_from or CANONICAL_EFFECTIVE_FROM, policy_scope or CANONICAL_SCOPE,
             origin, entry_id, sale_id, reason, actor, _now()),
        )
        self.repository.audit(con, actor, action, period, details={
            "rate_bp": int(rate_bp), "origin": origin, "reason": reason, "entry_id": entry_id,
            "sale_id": sale_id, "policy_code": policy_code, "policy_version": policy_version,
            "policy_effective_from": policy_effective_from})

    def _pin_rated_period(self, con, entry, actor, boundary):
        """Fija la tasa del período al alcanzarse un hecho económico oficial.

        Se llama sólo desde `approve` y `mark_paid` —el boundary `RATING_BOUNDARY_STATES`—. El
        primer cálculo no fija nada: mientras la liquidación es provisional el mes sigue siendo
        corregible, que es lo que permite deshacer una fecha mal tipeada o una venta que después se
        anula.

        La tasa que se graba es la de **esta** liquidación, que la guarda de transición ya verificó
        idéntica a la oficial del período. Es idempotente por el estado del libro: si el período ya
        está fijado no se escribe nada, así que aprobar una segunda liquidación del mismo mes, o
        reintentar la misma aprobación, no duplica ni el evento ni el asiento.

        Después de un `UNPINNED` esta misma función vuelve a fijar: refijar no es un caso especial,
        es el contrato normal aplicado al siguiente hecho oficial.
        """
        if boundary not in RATING_BOUNDARY_STATES:
            # Nadie debería llamar aquí desde otro estado, y si alguien lo intenta el sistema
            # tiene que decirlo, no fijar un mes en silencio desde un hecho que no lo justifica.
            raise ValueError(f"solo un hecho economico oficial fija un periodo: {boundary}")
        period = str(entry["period"] or "")[:7]
        if not period or entry["rate_bp"] is None or entry["policy_status"] != POLICY_CANONICAL:
            return False
        last = _last_period_rate_event(con, period)
        if last is not None and last["event"] == PERIOD_RATE_PINNED:
            return False
        self._record_period_rate_event(
            con, period, PERIOD_RATE_PINNED, rate_bp=int(entry["rate_bp"]),
            policy_code=entry["policy_code"], policy_version=entry["policy_version"],
            policy_effective_from=entry["policy_effective_from"], policy_scope=entry["policy_scope"],
            origin=boundary, actor=actor, entry_id=entry["id"], sale_id=entry["sale_id"],
            reason=f"hecho economico oficial: la liquidacion alcanzo {boundary}")
        return True

    def _reconcile_period_pin(self, con, period, actor, action, reason=""):
        """Retira la fijación cuando desaparece el último hecho oficial vivo que la sostenía.

        Es el **boundary de salida**, y el único sitio del sistema que desfija. Se invoca desde
        `_set_status`, que es por donde pasa toda transición de estado, de modo que las cuatro rutas
        que retiran un hecho —revertir la aprobación, `void_sale`, la reversa de un cobro que
        arrastra la liquidación, y `observe` seguido de `revert`— quedan cubiertas por construcción
        y no una por una. Cualquier ruta futura que mueva un estado queda cubierta también.

        **Una `PAGADA` viva nunca desfija**: `_live_official_facts` cuenta `paid_at`, así que el
        dinero consolidado sostiene el período aunque la liquidación se observe después o la venta
        se anule. Un pago sólo deja de sostener si su reversión se completa de verdad.

        No borra ni reescribe el `PINNED` anterior: escribe un `UNPINNED` detrás, con la tasa que se
        retira, la causa y el actor. Es idempotente: si el período no está fijado, no hace nada.
        """
        period = str(period or "")[:7]
        if not period:
            return False
        last = _last_period_rate_event(con, period)
        if last is None or last["event"] != PERIOD_RATE_PINNED:
            return False
        if self._live_official_facts(con, period):
            return False
        self._record_period_rate_event(
            con, period, PERIOD_RATE_UNPINNED, rate_bp=int(last["rate_bp"]),
            policy_code=last["policy_code"], policy_version=last["policy_version"],
            policy_effective_from=last["policy_effective_from"], policy_scope=last["policy_scope"],
            origin=action, actor=actor,
            reason=reason or "sin hechos economicos oficiales vivos que sostengan la tasa del periodo")
        return True

    def _transition(self, actor, entry_id, allowed, target, action, details=None, guard=None,
                    pin_period=False, **columns):
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
            if pin_period:
                # Sólo aquí se fija un período, y sólo dentro de la misma transacción que
                # registra el hecho económico: no hay ventana en la que uno exista sin el otro.
                self._pin_rated_period(con, entry, actor.username, target)
            con.commit()
        return True

    def review(self, actor: Principal, entry_id: str, note: str = ""):
        """Revisar el cálculo antes de cualquier aprobación.

        Es el primer punto donde una persona avala un importe, así que exige que la
        política oficial ya esté aplicada: nada sin porcentaje entra a la cadena de pago.
        """
        return self._transition(actor, entry_id, {"CALCULADA"}, "REVISADA", "CALCULATION_REVIEWED",
                                {"note": note}, guard=self._require_official_and_live,
                                reviewed_by=actor.username, reviewed_at=_now())

    def approve(self, actor: Principal, entry_id: str, responsible: str):
        responsible = responsible.strip()
        if not responsible:
            raise ValueError("responsable obligatorio")
        # Aprobar es el primer hecho económico oficial: aquí queda fijada la tasa del período.
        return self._transition(actor, entry_id, {"REVISADA"}, "APROBADA", "COMMISSION_APPROVED",
                                {"responsible": responsible}, guard=self._require_official_and_live,
                                pin_period=True, approved_by=responsible, approved_at=_now())

    def mark_paid(self, actor: Principal, entry_id: str, payment_date: str, reference: str):
        """Sólo se paga lo revisado y aprobado; nunca se salta la aprobación."""
        reference = reference.strip()
        if not reference:
            raise ValueError("referencia de pago obligatoria")
        _month(payment_date)
        # Pagar también fija: una base que llegue migrada sin su aprobación registrada no
        # puede quedar sin fijar sólo porque el asiento de aprobación no exista.
        return self._transition(actor, entry_id, {"APROBADA"}, "PAGADA", "COMMISSION_PAID",
                                {"payment_date": payment_date, "reference": reference},
                                guard=self._require_official_and_live, pin_period=True,
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
    def policy_for_period(self, actor: Principal, period: str) -> dict:
        """Política que gobierna ese período concreto, no la última publicada.

        Un período ya fijado conserva su tasa, así que la vigente puede ser otra. Rotular un
        período con la tasa global sería declarar oficial un porcentaje que ahí no rige: es el
        mismo error que la generación 2 cometió al llamar «oficial» a un importe heredado.

        Cuando el período no tiene tasa en vigor la respuesta lleva `rate_bp=None` y quien rotula
        debe decirlo así. Caer a la política global y llamarla «oficial de este mes» es inventar
        una tasa que ahí no existe.
        """
        self._read(actor)
        decision = self.policy.decide(branch="", saleswoman="", period=period)
        fallback = self.policy.current()
        rate = decision.rate_bp
        return {
            "code": decision.code or fallback["code"] or CANONICAL_CODE,
            "scope": decision.scope,
            "status": decision.status,
            "version": decision.version,
            "effective_from": decision.effective_from,
            "rate_bp": None if rate is None else int(rate),
            "rate_percent": None if rate is None else rate_decimal_text(int(rate)),
            "rounding": ROUNDING_MODE,
            "currency": CURRENCY,
            "pinned": self.policy.pinned_for(period) is not None,
        }

    def current_policy(self, actor: Principal) -> dict:
        """Política oficial vigente, con porcentaje, versión, vigencia y redondeo."""
        self._read(actor)
        policy = self.policy.current()
        return {
            "code": policy["code"] or CANONICAL_CODE,
            "scope": policy["scope"],
            "status": policy["approval_status"],
            "version": int(policy["version"]),
            "effective_from": policy["effective_from"] or CANONICAL_EFFECTIVE_FROM,
            "rate_bp": int(policy["rate_bp"]),
            "rate_percent": rate_decimal_text(int(policy["rate_bp"])),
            "rounding": ROUNDING_MODE,
            "currency": CURRENCY,
        }

    def set_general_rate(self, actor: Principal, rate_bp: int, effective_from: str, note: str = ""):
        """Publica una nueva versión de la política general. No admite alcances parciales.

        Cambiar el porcentaje es un hecho versionado: la versión anterior queda íntegra en
        `commission_policy_versions` y ninguna liquidación ya calculada se toca aquí. Repetir
        el mismo porcentaje y la misma vigencia no crea versión: la operación es idempotente.

        Una tasa publicada gobierna hacia adelante, y esto **no se sostiene bloqueando la
        publicación**. La única guarda que queda aquí es que la vigencia no puede retroceder
        respecto de la última publicada, que ordena el historial.

        La protección de lo ya comprometido vive en otro sitio y es de otra naturaleza: cada
        período en el que una liquidación alcanzó `APROBADA` o `PAGADA` queda fijado en el libro
        `commission_period_rate_events`, y `decide()` resuelve ese período contra ese libro y no
        contra el catálogo. Una versión nueva no lo reescribe aunque su vigencia lo abarque.

        La protección dura **mientras haya un hecho oficial vivo que la sostenga**. No depende del
        estado de ninguna liquidación en particular —dos aprobaciones sostienen el mes y revertir
        una no lo suelta— pero tampoco sobrevive a que no quede ninguna: revertir la última
        aprobación, anular la venta o que se caiga el cobro escriben un `UNPINNED` y el período
        vuelve a resolverse por catálogo. Un pago consolidado nunca se suelta.

        Lo que **sí** alcanza una versión nueva son los períodos que aún no fueron aprobados ni
        pagados, y los que dejaron de estarlo: ahí no hay dinero avalado y el recálculo debe poder
        corregirlos. Fijar en el primer cálculo era el defecto de la generación 5; fijar para
        siempre por un hecho que después se anuló era el de la 6.

        Bloquear la publicación era la defensa anterior y fallaba por los dos lados. Por
        abajo, porque cualquier transición que sacara la liquidación de los estados liquidados
        borraba la marca y devolvía la fuga. Por arriba, porque una venta con fecha errónea
        —un `2036` en lugar de un `2026`— congelaba la publicación de todos los meses
        anteriores a ella. Con la evidencia por período no ocurre ninguna de las dos cosas:
        publicar siempre es posible, y lo tarifado nunca se re-tarifa.

        Corregir la tasa de un período ya tarifado sigue exigiendo un flujo separado de
        corrección explícita y auditada, que hoy no existe: no es un cambio de política, es
        otra decisión. Cada publicación deja asentado en `central_audit` qué períodos quedan
        fuera de su alcance, para que eso sea visible y no una sorpresa.
        """
        self._write(actor)
        if isinstance(rate_bp, bool) or not isinstance(rate_bp, int) or not 0 <= rate_bp <= BASIS_POINTS:
            raise ValueError("porcentaje inválido: use puntos básicos enteros de 0 a 10000")
        effective_from = normalize_effective_from(effective_from)
        with self.repository.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            latest = con.execute(
                "SELECT MAX(effective_from) FROM commission_policy_versions WHERE policy_id=?",
                (CANONICAL_POLICY_ID,),
            ).fetchone()[0]
            if latest and effective_from < latest:
                raise ValueError(
                    f"la vigencia no puede retroceder: la última publicada rige desde {latest}")
            current = con.execute(
                "SELECT * FROM commission_policies WHERE scope=? AND scope_value=''", (CANONICAL_SCOPE,)
            ).fetchone()
            if (current is not None and int(current["rate_bp"]) == rate_bp
                    and current["effective_from"] == effective_from
                    and current["approval_status"] == POLICY_CANONICAL):
                con.rollback()
                return int(current["version"]), False
            # Publicar no se bloquea. Los períodos ya fijados —los que tienen una liquidación
            # aprobada o pagada— están protegidos por su propia evidencia durable, de modo que la
            # versión nueva no puede reescribirlos por mucho que su vigencia los abarque. Bloquear
            # la publicación era la defensa anterior y tenía dos defectos: se apoyaba en el estado
            # actual, que cualquier transición posterior borraba, y un período con fecha errónea
            # congelaba la publicación de todos los meses anteriores a él. Se deja constancia de
            # qué períodos quedan fuera del alcance real de esta versión, para que publicar no sea
            # silencioso.
            protected = _pinned_periods_from(con, effective_from)
            version = int(con.execute(
                "SELECT COALESCE(MAX(version),0) FROM commission_policy_versions WHERE policy_id=?",
                (CANONICAL_POLICY_ID,),
            ).fetchone()[0]) + 1
            now = _now()
            con.execute(
                "INSERT INTO commission_policies(id,scope,scope_value,rate_bp,approval_status,code,version,"
                "effective_from,created_by,created_at) VALUES(?,?,'',?,?,?,?,?,?,?)"
                " ON CONFLICT(scope,scope_value) DO UPDATE SET rate_bp=excluded.rate_bp,"
                "approval_status=excluded.approval_status,code=excluded.code,version=excluded.version,"
                "effective_from=excluded.effective_from,created_by=excluded.created_by,created_at=excluded.created_at",
                (CANONICAL_POLICY_ID, CANONICAL_SCOPE, rate_bp, POLICY_CANONICAL, CANONICAL_CODE,
                 version, effective_from, actor.username, now),
            )
            con.execute(
                "INSERT INTO commission_policy_versions(policy_id,code,scope,scope_value,version,rate_bp,"
                "approval_status,effective_from,note,actor,recorded_at) VALUES(?,?,?,'',?,?,?,?,?,?,?)",
                (CANONICAL_POLICY_ID, CANONICAL_CODE, CANONICAL_SCOPE, version, rate_bp,
                 POLICY_CANONICAL, effective_from, note, actor.username, now),
            )
            self.repository.audit(con, actor.username, "COMMISSION_POLICY_VERSION_PUBLISHED",
                                  f"{CANONICAL_CODE}:v{version}",
                                  details={"rate_bp": rate_bp, "effective_from": effective_from,
                                           "approval_status": POLICY_CANONICAL, "note": note,
                                           "protected_periods": protected,
                                           "protected_periods_count": len(protected)})
            con.commit()
        return version, True

    def policies(self, actor: Principal):
        self._read(actor)
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM commission_policies ORDER BY scope,scope_value")]

    def policy_versions(self, actor: Principal):
        """Historial append-only de versiones de la política oficial."""
        self._read(actor)
        with self.repository.connection() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM commission_policy_versions ORDER BY version,id")]

    # ------------------------------------------------------------- recálculo
    def recalculate(self, actor: Principal, *, period: str | None = None, branch: str | None = None):
        """Recalcula base y comisión oficial de forma segura e idempotente.

        Alcanza `ELEGIBLE` y `CALCULADA`, y también `REVISADA` y `APROBADA`, pero a estas
        dos **sólo cuando su importe ya no es el oficial** del período: una política retirada,
        una ausente, o una versión que quedó atrás. Esas no pueden quedarse como están
        —serían pagables a un porcentaje que no rige— ni pueden conservar su aval: vuelven a
        `CALCULADA` con la regla vigente y pierden la revisión y la aprobación, que deben
        rehacerse sobre el importe correcto. Si su importe ya es el oficial, no se tocan.

        Nunca alcanza nada que haya movido dinero: `paid_at IS NULL` cuelga del `WHERE`
        entero, no de una rama, así que `PAGADA` queda fuera aunque su estado se hubiera
        alterado por otra vía. `OBSERVADA` y `REVERTIDA` también quedan fuera. Repetirlo no
        duplica ni reaplica nada, porque la comparación incluye la traza de política completa.

        Reparar no siempre significa recuperar un importe. Si el período es **anterior a la
        vigencia**, la decisión es `FUERA_DE_VIGENCIA` y la liquidación queda sin porcentaje:
        eso retira un importe heredado sin sustituirlo. No es un caso con salida —ninguna
        ruta pública devuelve ese importe— y por eso todo valor retirado se asienta en
        `replaced`, en esta rama y en la de reparación, para que quede auditable.
        """
        self._write(actor)
        query = ("SELECT * FROM commission_entries"
                 " WHERE status IN ('ELEGIBLE','CALCULADA','REVISADA','APROBADA')"
                 " AND paid_at IS NULL")
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
                decision = self.policy.decide(
                    branch=sale["branch"], saleswoman=sale["saleswoman"], period=entry["period"] or "")
                commission = None if decision.rate_bp is None else commission_for(base, decision.rate_bp)
                current = (int(entry["gross_amount"]), int(entry["agreement_discount"]),
                           int(entry["commissionable_base"]), entry["rate_bp"], entry["commission_amount"],
                           entry["policy_status"], entry["policy_code"], entry["policy_version"],
                           entry["policy_effective_from"], entry["policy_scope"])
                target = (total, discount, base, decision.rate_bp, commission,
                          decision.status, decision.code, decision.version, decision.effective_from,
                          decision.scope)
                # `ELEGIBLE` avanza a `CALCULADA` aunque los números coincidan; el resto sólo
                # se toca si algo cambió. Una `REVISADA` o `APROBADA` ya correcta conserva su aval.
                if current == target and entry["status"] != "ELEGIBLE":
                    continue
                changed += 1
                # Reparar una REVISADA o APROBADA retira también su aval: el importe cambió,
                # así que la revisión y la aprobación anteriores ya no lo respaldan.
                repairing = entry["status"] in {"REVISADA", "APROBADA"}
                con.execute(
                    "UPDATE commission_entries SET status='CALCULADA',gross_amount=?,agreement_discount=?,"
                    "commissionable_base=?,rate_bp=?,commission_amount=?,policy_status=?,policy_code=?,"
                    "policy_version=?,policy_effective_from=?,policy_scope=?,updated_at=?"
                    + (",reviewed_by=NULL,reviewed_at=NULL,approved_by=NULL,approved_at=NULL" if repairing else "")
                    + " WHERE id=?",
                    (total, discount, base, decision.rate_bp, commission, decision.status, decision.code,
                     decision.version, decision.effective_from, decision.scope, _now(), entry["id"]),
                )
                # Calcular **no** fija el período. El cálculo es provisional: puede venir de una
                # fecha mal tipeada o de una venta que después se anula, y fijar el mes con él lo
                # volvía incorregible. El período se fija en `approve`/`mark_paid`, donde existe
                # un hecho económico oficial. Recalcular un período ya fijado sigue devolviendo su
                # tasa, porque `decide()` resuelve contra la evidencia y no contra el catálogo.
                details = {"commissionable_base": base, "agreement_discount": discount,
                           "commission_amount": commission, "policy": decision.as_dict()}
                # Todo importe anterior que se anula o se reemplaza queda asentado, esté la
                # liquidación revisada o no. Una legada en `ELEGIBLE` o `CALCULADA` cuyo período
                # es anterior a la vigencia pierde su importe igual que una `REVISADA`, y sin
                # este asiento el valor retirado no sobrevive en ninguna ruta pública.
                replaces_amount = (
                    (entry["commission_amount"] is not None and entry["commission_amount"] != commission)
                    or (entry["rate_bp"] is not None and entry["rate_bp"] != decision.rate_bp)
                )
                if repairing or replaces_amount:
                    details["replaced"] = {"rate_bp": entry["rate_bp"],
                                           "commission_amount": entry["commission_amount"],
                                           "policy_status": entry["policy_status"]}
                self._history(con, entry["id"], entry["sale_id"], entry["status"], "CALCULADA", actor.username,
                              "COMMISSION_POLICY_REPAIRED" if repairing else "COMMISSION_RECALCULATED",
                              details)
                if repairing:
                    # Reparar una APROBADA la devuelve a CALCULADA: retira un hecho oficial. Sólo
                    # ocurre sobre un período sin fijar —si estuviera fijado la liquidación ya sería
                    # la oficial y no se tocaría—, pero la reconciliación se hace igual, porque la
                    # regla no puede depender de qué rama nos trajo hasta aquí.
                    self._reconcile_period_pin(con, entry["period"], actor.username,
                                               "COMMISSION_POLICY_REPAIRED")
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
            # El signo acompaña al resultado, no al factor: la línea ya es la comisión.
            # Sólo se llama «oficial» a la que efectivamente lleva la política vigente.
            official = entry["policy_status"] == POLICY_CANONICAL
            name = "Comisión oficial" if official else "Comisión con política anterior (no pagable)"
            lines.append({"label": f"{name} ({rate_percent_text(int(entry['rate_bp']))} de la base)",
                          "amount": int(entry["commission_amount"] or 0), "sign": "="})
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
            "policy": self._entry_policy(entry),
            "policy_note": self._policy_note(entry),
        }

    @staticmethod
    def _entry_policy(entry) -> dict:
        """Política con la que se calculó esta liquidación, tal como quedó grabada."""
        rate = entry["rate_bp"]
        return {
            "code": entry["policy_code"], "scope": entry["policy_scope"],
            "status": entry["policy_status"], "version": entry["policy_version"],
            "effective_from": entry["policy_effective_from"],
            "rate_bp": None if rate is None else int(rate),
            "rate_percent": None if rate is None else rate_decimal_text(int(rate)),
            "rounding": ROUNDING_MODE, "currency": CURRENCY,
        }

    @staticmethod
    def _policy_note(entry) -> str:
        status, rate = entry["policy_status"], entry["rate_bp"]
        if status == POLICY_CANONICAL:
            return (f"Política oficial {entry['policy_code']} v{entry['policy_version']}: "
                    f"{rate_percent_text(int(rate))} de la base comisionable, igual para toda vendedora y "
                    f"local, vigente desde {entry['policy_effective_from']}. "
                    f"Redondeo {ROUNDING_MODE} a guaraní entero.")
        if status == POLICY_OUT_OF_EFFECT:
            return (f"El período es anterior a la vigencia de la política oficial "
                    f"({entry['policy_effective_from']}): se informa sólo la base comisionable.")
        if status == POLICY_LEGACY:
            note = (f"Importe calculado con una política anterior a la regla aprobada "
                    f"({rate_percent_text(int(rate))}). No es pagable con este importe.")
            if entry["paid_at"]:
                return note + " Ya fue pagado: se conserva tal cual por auditoría."
            return note + " Recalcule para llevarlo a la comisión oficial vigente."
        return "Todavía sin política aplicada: recalcule para obtener la comisión oficial."

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
        # «Comisión oficial» sólo suma lo calculado con la política aprobada. Un importe
        # heredado de una política retirada existe y se informa, pero aparte: llamarlo
        # oficial sería declarar como 1% una cifra que no lo es.
        official = [row for row in eligible if row["policy_status"] == POLICY_CANONICAL]
        unofficial = [row for row in eligible
                      if row["policy_status"] != POLICY_CANONICAL and row["commission_amount"]]
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
            "commission_amount": sum(int(row["commission_amount"] or 0) for row in official),
            "non_official_amount": sum(int(row["commission_amount"] or 0) for row in unofficial),
            "non_official_entries": len(unofficial),
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
                "commissionable_base": 0, "commission_amount": 0, "non_official_amount": 0,
                "paid_amount": 0,
            })
            bucket["sales"] += 1
            bucket["gross_informative"] += int(row["gross_amount"])
            if row["status"] == "PENDIENTE_SALDO":
                bucket["pending_balance"] += 1
                continue
            bucket["cancelled" if row["sale_kind"] == "COMUN" else "agreements"] += 1
            bucket["agreement_discount"] += int(row["agreement_discount"])
            bucket["commissionable_base"] += int(row["commissionable_base"])
            official_row = row["policy_status"] == POLICY_CANONICAL
            bucket["commission_amount" if official_row else "non_official_amount"] += \
                int(row["commission_amount"] or 0)
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
        # Política **de este período**, no la última publicada: si el período ya quedó fijado,
        # su tasa es la que se fijó y ninguna versión posterior la reemplaza.
        policy = self.policy_for_period(actor, period)
        return {
            "contract_version": 3,
            "period": period,
            "generated_at": _now(),
            "filters": data["filters"],
            "policy": policy,
            "current_policy": self.current_policy(actor),
            "kpi": data["kpi"],
            "by_saleswoman": data["by_saleswoman"],
            "entries": entries,
            "policy_disclaimer": self._policy_disclaimer(period, policy),
        }

    @staticmethod
    def _policy_disclaimer(period: str, policy: dict) -> str:
        """Texto del export. Un período sin tasa en vigor se dice, no se inventa.

        La versión anterior interpolaba `rate_percent` sin mirar si existía y publicaba
        «Comisión oficial None%»: un contrato exportable no puede emitir el nombre de un valor
        ausente donde va un porcentaje de dinero.
        """
        common = (f"Convenio: {AGREEMENT_DISCOUNT_BP // 100}% de descuento antes de la base. "
                  f"Redondeo {ROUNDING_MODE} a guaraní entero.")
        if policy["rate_bp"] is None:
            return (
                f"Sin tasa de comisión en vigor para {period}: la tasa del período se fija cuando "
                f"una liquidación alcanza APROBADA o PAGADA, y hasta entonces el cálculo es "
                f"provisional y corregible. Se informa sólo la base comisionable. " + common
            )
        # Se describe la **ausencia de fijación**, no la ausencia de aprobaciones. Afirmar que
        # nadie aprobó ni pagó es falso en una base legada con evidencia discrepante, que no fija
        # el período justamente porque contiene dos hechos oficiales que no coinciden.
        fixed = (" · tasa ya fijada por un hecho económico oficial (aprobación o pago)"
                 if policy.get("pinned") else
                 " · el período todavía no tiene una tasa fijada y sigue siendo corregible")
        return (
            f"Comisión oficial {policy['rate_percent']}% de la base comisionable "
            f"({policy['code']} v{policy['version']}, vigente desde {policy['effective_from']})"
            f"{fixed}, igual para toda vendedora y local. " + common
        )

    # ------------------------------------------------------------ integración
    def sync_review_sales(self, actor: Principal, review_service):
        """Ingesta desde la revisión de ventas. Gastos y entregas nunca ingresan."""
        registered = skipped = invalid_date = rejected = 0
        for row in review_service.list_sales(actor):
            # La guarda cubre el parseo, la construcción y el alta, no sólo el alta: una fila con
            # datos mal formados se cuenta en `rejected` y no trunca el lote. No pretende atrapar
            # cualquier fallo: `AccessDenied` es `PermissionError` y sigue propagando, porque un
            # fallo de permisos debe cortar la sincronización, no degradarse a una fila rechazada.
            try:
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
            except (ValueError, TypeError, KeyError):
                rejected += 1
        return {"registered": registered, "skipped": skipped,
                "invalid_date": invalid_date, "rejected": rejected}
