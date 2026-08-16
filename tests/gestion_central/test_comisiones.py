from pathlib import Path

import pytest

from modulos.gestion_central.comisiones import (
    AGREEMENT_DISCOUNT_BP, COMMISSION_STATES, POLICY_ABSENT, POLICY_PENDING,
    CommissionSaleInput, CommissionService, agreement_discount, commissionable_base,
)
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied, CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)
AUDITOR = Principal("audit", Role.AUDITOR)
LOCAL = Principal("local", Role.OPERADOR_LOCAL)


@pytest.fixture
def service(tmp_path):
    return CommissionService(CentralManagementService(CentralRepository(tmp_path / "central.sqlite3")))


def common(**changes):
    values = dict(branch="Óptica Asunción", source_sale_id="venta-001", saleswoman="Vendedora Uno",
                  sale_date="2099-04-10", kind="COMUN", total_amount=400_000, initial_paid=200_000,
                  envelope="S-001")
    values.update(changes)
    return CommissionSaleInput(**values)


def agreement(**changes):
    values = dict(branch="Óptica Pilar", source_sale_id="convenio-001", saleswoman="Vendedora Dos",
                  sale_date="2099-04-12", kind="CONVENIO", total_amount=500_000, envelope="S-900")
    values.update(changes)
    return CommissionSaleInput(**values)


def active(service, sale_id, actor=SOL):
    return next(row for row in service.list_entries(actor) if row["sale_id"] == sale_id
                and row["status"] != "REVERTIDA")


# ------------------------------------------------------------------ reglas económicas
def test_common_sale_with_balance_is_not_commissionable_yet(service):
    sale_id, created = service.register_sale(SOL, common())
    assert created
    entry = active(service, sale_id)
    assert entry["status"] == "PENDIENTE_SALDO"
    assert entry["period"] is None and entry["commissionable_base"] == 0
    assert entry["balance_amount"] == 200_000
    assert "saldo pendiente" in service.breakdown(SOL, entry["id"])["reason"]
    report = service.report(SOL, "2099-04")
    assert report["kpi"]["pending_balance_sales"] == 1
    assert report["kpi"]["commissionable_base"] == 0
    assert report["kpi"]["gross_informative"] == 400_000


def test_partial_payment_stays_informative_and_never_pays(service):
    sale_id, _ = service.register_sale(SOL, common())
    payment_id, applied = service.register_payment(SOL, sale_id, 100_000, "2099-04-20", "recibo-1")
    assert applied and payment_id
    entry = active(service, sale_id)
    assert entry["status"] == "PENDIENTE_SALDO" and entry["balance_amount"] == 100_000
    report = service.report(SOL, "2099-04")
    assert report["kpi"]["partial_payments_count"] == 2  # alta + cobro parcial
    assert report["kpi"]["partial_payments_amount"] == 300_000
    assert report["kpi"]["commission_amount"] == 0
    actions = [event["action"] for event in service.sale_history(SOL, sale_id)]
    assert "PARTIAL_PAYMENT_INFORMATIVE" in actions


def test_cancellation_enters_the_period_of_its_settlement(service):
    sale_id, _ = service.register_sale(SOL, common())
    service.register_payment(SOL, sale_id, 200_000, "2099-05-03", "recibo-final")
    entry = active(service, sale_id)
    assert entry["status"] == "ELEGIBLE" and entry["period"] == "2099-05"
    assert entry["commissionable_base"] == 400_000 and entry["agreement_discount"] == 0
    assert service.report(SOL, "2099-04")["kpi"]["commissionable_base"] == 0
    mayo = service.report(SOL, "2099-05")
    assert mayo["kpi"]["cancelled_sales"] == 1 and mayo["kpi"]["commissionable_base"] == 400_000


def test_agreement_deducts_exactly_five_percent_and_creates_no_client_balance(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    entry = active(service, sale_id)
    assert entry["status"] == "ELEGIBLE" and entry["period"] == "2099-04"
    assert entry["balance_amount"] == 0
    assert agreement_discount(500_000) == 25_000 and commissionable_base("CONVENIO", 500_000) == 475_000
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["agreement_discount"] == 25_000 and entry["commissionable_base"] == 475_000
    assert "convenio" in service.breakdown(SOL, entry["id"])["reason"].lower()
    with pytest.raises(ValueError, match="no registra saldo"):
        service.register_payment(SOL, sale_id, 100_000, "2099-04-20")
    with pytest.raises(ValueError, match="saldo cliente parcial"):
        agreement(initial_paid=100_000)


def test_agreement_discount_applies_exactly_once_even_after_repeated_recalculation(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    for _ in range(3):
        service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["agreement_discount"] == 25_000 and entry["commissionable_base"] == 475_000
    assert sum(1 for row in service.list_entries(SOL) if row["sale_id"] == sale_id) == 1


def test_voided_sale_never_generates_commission(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    assert service.void_sale(SOL, sale_id, "anulada por error de carga")
    assert not service.void_sale(SOL, sale_id, "repetida")
    rows = [row for row in service.list_entries(SOL) if row["sale_id"] == sale_id]
    assert [row["status"] for row in rows] == ["REVERTIDA"]
    assert service.report(SOL, "2099-04")["kpi"]["commissionable_base"] == 0


def test_reverting_a_cancellation_reverts_the_commission_effect_and_keeps_history(service):
    sale_id, _ = service.register_sale(SOL, common())
    payment_id, _ = service.register_payment(SOL, sale_id, 200_000, "2099-05-03", "recibo-final")
    eligible = active(service, sale_id)
    service.revert_payment(SOL, payment_id, "cheque rechazado")
    rows = sorted((row for row in service.list_entries(SOL) if row["sale_id"] == sale_id),
                  key=lambda row: row["sequence"])
    assert [row["status"] for row in rows] == ["REVERTIDA", "PENDIENTE_SALDO"]
    assert rows[0]["id"] == eligible["id"] and rows[0]["period"] == "2099-05"
    assert service.report(SOL, "2099-05")["kpi"]["commissionable_base"] == 0
    assert [event["to_state"] for event in service.history(SOL, eligible["id"])] == \
        ["PENDIENTE_SALDO", "ELEGIBLE", "REVERTIDA"]


def test_expenses_and_administration_deliveries_never_enter_the_ledger(service):
    with pytest.raises(ValueError, match="total positivo"):
        common(total_amount=0)
    with pytest.raises(ValueError, match="entero no negativo"):
        common(total_amount=-50_000)


# --------------------------------------------------------------------- integridad
def test_duplicate_registration_is_rejected_and_identity_is_stable(service):
    sale_id, created = service.register_sale(SOL, common())
    assert created
    assert service.register_sale(SOL, common()) == (sale_id, False)
    assert len(service.list_entries(SOL)) == 1
    other, _ = service.register_sale(SOL, common(branch="Óptica Pilar", source_sale_id="venta-002"))
    assert other != sale_id and len(service.list_entries(SOL)) == 2


def test_duplicate_payment_key_is_idempotent(service):
    sale_id, _ = service.register_sale(SOL, common())
    first = service.register_payment(SOL, sale_id, 50_000, "2099-04-15", "recibo-x")
    second = service.register_payment(SOL, sale_id, 50_000, "2099-04-15", "recibo-x")
    assert first[1] and second == (None, False)
    assert active(service, sale_id)["balance_amount"] == 150_000
    with pytest.raises(ValueError, match="supera el saldo"):
        service.register_payment(SOL, sale_id, 999_000, "2099-04-16", "recibo-y")


def test_recalculation_is_idempotent(service):
    service.register_sale(SOL, common(initial_paid=400_000))
    service.register_sale(SOL, agreement())
    first = service.recalculate(SOL)
    second = service.recalculate(SOL)
    assert first == {"evaluated": 2, "changed": 2}
    assert second == {"evaluated": 2, "changed": 0}
    assert len(service.list_entries(SOL)) == 2


def test_amounts_stay_integers_end_to_end(service):
    service.register_sale(SOL, agreement(total_amount=333_333))
    service.set_policy(SOL, "GENERAL", 250)
    service.recalculate(SOL)
    entry = service.list_entries(SOL)[0]
    for name in ("gross_amount", "agreement_discount", "commissionable_base", "rate_bp", "commission_amount"):
        assert isinstance(entry[name], int) and not isinstance(entry[name], bool)
    assert entry["agreement_discount"] == 16_667 and entry["commissionable_base"] == 316_666
    assert entry["commission_amount"] == 7_917


# ------------------------------------------------------------------------ estados
def test_payment_without_review_and_approval_is_blocked(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry = active(service, sale_id)
    with pytest.raises(ValueError, match="transición inválida"):
        service.mark_paid(SOL, entry["id"], "2099-05-05", "TRANSF-1")
    service.review(SOL, entry["id"], "cálculo verificado")
    with pytest.raises(ValueError, match="transición inválida"):
        service.mark_paid(SOL, entry["id"], "2099-05-05", "TRANSF-1")
    service.approve(SOL, entry["id"], "Sol")
    assert service.mark_paid(SOL, entry["id"], "2099-05-05", "TRANSF-1")
    assert active(service, sale_id)["status"] == "PAGADA"


def test_approval_requires_responsible_and_payment_requires_reference(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    with pytest.raises(ValueError, match="responsable obligatorio"):
        service.approve(SOL, entry_id, "  ")
    service.approve(SOL, entry_id, "Sol")
    with pytest.raises(ValueError, match="referencia de pago"):
        service.mark_paid(SOL, entry_id, "2099-05-05", " ")


def test_observation_and_motivated_reversal_require_reason(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    with pytest.raises(ValueError, match="motivo obligatorio"):
        service.observe(SOL, entry_id, " ")
    service.observe(SOL, entry_id, "diferencia con la planilla del local")
    assert active(service, sale_id)["observation"] == "diferencia con la planilla del local"
    with pytest.raises(ValueError, match="motivo obligatorio"):
        service.revert(SOL, entry_id, "")
    service.revert(SOL, entry_id, "liquidación anulada por corrección")
    assert [row["status"] for row in service.list_entries(SOL)] == ["REVERTIDA"]


def test_paid_settlement_is_never_modified_silently(service):
    sale_id, _ = service.register_sale(SOL, common(initial_paid=0))
    payment_id, _ = service.register_payment(SOL, sale_id, 400_000, "2099-04-30", "recibo-total")
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-02", "TRANSF-9")
    service.revert_payment(SOL, payment_id, "transferencia rechazada")
    entry = active(service, sale_id)
    assert entry["id"] == entry_id and entry["status"] == "OBSERVADA"
    assert "Reversión posterior al pago" in entry["observation"]
    assert [row["status"] for row in service.list_entries(SOL)] == ["OBSERVADA"]


def test_paid_settlement_can_never_reach_reverted_even_through_observed(service):
    """Bloqueante A1/A2 (Auditor independiente, generación 1)."""
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    service.observe(SOL, entry_id, "diferencia detectada tras el pago")
    with pytest.raises(ValueError, match="ya pagada.*no admite reversión"):
        service.revert(SOL, entry_id, "intento de revertir una liquidación pagada")
    entry = active(service, sale_id)
    assert entry["status"] == "OBSERVADA" and entry["paid_at"] == "2099-05-05"
    # El índice de unicidad sigue bloqueando: no puede nacer una segunda liquidación pagable.
    service.register_sale(SOL, agreement(total_amount=600_000))
    assert [row["status"] for row in service.list_entries(SOL)] == ["OBSERVADA"]


def test_voiding_a_paid_sale_observes_instead_of_reverting(service):
    """Bloqueante A1: la anulación posterior al pago tampoco puede revertir."""
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-2")
    service.observe(SOL, entry_id, "planilla en revisión")
    service.void_sale(SOL, sale_id, "venta anulada por el local")
    assert [row["status"] for row in service.list_entries(SOL)] == ["OBSERVADA"]


def test_invalid_dates_are_rejected_and_never_produce_a_period(service):
    """Bloqueante Q1 (QA independiente, generación 1)."""
    for bad in ("2099-4-10", "2099-13-45", "9999-99-99", "abcd-ef-gh", "2099-04"):
        with pytest.raises(ValueError, match="fecha inválida"):
            common(sale_date=bad)
    with pytest.raises(ValueError, match="sale_date obligatorio"):
        common(sale_date="")
    sale_id, _ = service.register_sale(SOL, common())
    for bad in ("2099-5-03", "2099-99-99", "no-es-fecha"):
        with pytest.raises(ValueError, match="fecha inválida"):
            service.register_payment(SOL, sale_id, 200_000, bad, "recibo")
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    assert active(service, sale_id)["status"] == "PENDIENTE_SALDO"
    # Ningún período con formato inválido pudo persistirse.
    periods = {row["period"] for row in service.list_entries(SOL)} - {None}
    assert all(len(period) == 7 and period[4] == "-" for period in periods)
    service.register_payment(SOL, sale_id, 200_000, "2099-05-03", "recibo-final")
    assert active(service, sale_id)["period"] == "2099-05"
    assert service.report(SOL, "2099-05")["kpi"]["commissionable_base"] == 400_000


def test_review_sync_reports_invalid_dates_instead_of_losing_them(service):
    """Bloqueante Q1: una fecha corrupta del snapshot externo no se ingiere en silencio."""
    class FakeReview:
        @staticmethod
        def list_sales(_actor):
            return [
                {"branch": "Óptica Asunción", "identity": "ok",
                 "payload": {"date": "2099-04-08", "saleswoman": "Vendedora Uno", "total": 400_000,
                             "cash": 400_000, "card_transfer": 0, "agreement": 0, "envelope": "S-11"}},
                {"branch": "Óptica Pilar", "identity": "fecha-rota",
                 "payload": {"date": "2099-4-9", "saleswoman": "Vendedora Dos", "total": 900_000,
                             "cash": 900_000, "card_transfer": 0, "agreement": 0, "envelope": "S-12"}},
            ]

    result = service.sync_review_sales(SOL, FakeReview())
    assert result == {"registered": 1, "skipped": 0, "invalid_date": 1}
    assert result["invalid_date"] == 1, "la fila con fecha corrupta debe contarse, no perderse"
    assert len(service.list_entries(SOL)) == 1


def test_state_contract_and_append_only_history(service):
    assert COMMISSION_STATES == ("PENDIENTE_SALDO", "ELEGIBLE", "CALCULADA", "REVISADA",
                                 "APROBADA", "PAGADA", "OBSERVADA", "REVERTIDA")
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-2")
    service.observe(SOL, entry_id, "revisión posterior de la planilla")
    history = service.history(SOL, entry_id)
    assert [event["to_state"] for event in history] == [
        "ELEGIBLE", "CALCULADA", "REVISADA", "APROBADA", "PAGADA", "OBSERVADA"]
    assert [event["id"] for event in history] == sorted(event["id"] for event in history)
    with service.repository.connection() as con:
        con.execute("DELETE FROM commission_entry_history WHERE id=?", (history[0]["id"],))
        con.rollback()
    assert len(service.history(SOL, entry_id)) == len(history)


def test_source_correction_after_review_never_pays_a_stale_base(service):
    """Bloqueante QA generación 2: REVISADA caía al UPDATE sin recalcular la base."""
    sale_id, _ = service.register_sale(SOL, agreement())
    service.set_policy(SOL, "GENERAL", 300)
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.register_sale(SOL, agreement(total_amount=900_000))
    entry = active(service, sale_id)
    # No puede quedar aprobable ni pagable con una base que ya no corresponde al total.
    assert entry["status"] == "OBSERVADA"
    with pytest.raises(ValueError, match="transición inválida"):
        service.approve(SOL, entry_id, "Sol")
    with pytest.raises(ValueError, match="transición inválida"):
        service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-X")


def test_source_correction_before_review_recomputes_the_whole_base(service):
    """La corrección previa a la revisión recalcula base y descuento, no sólo el total."""
    sale_id, _ = service.register_sale(SOL, agreement())
    service.set_policy(SOL, "GENERAL", 300)
    service.recalculate(SOL)
    assert active(service, sale_id)["commissionable_base"] == 475_000
    service.register_sale(SOL, agreement(total_amount=900_000))
    entry = active(service, sale_id)
    assert entry["status"] == "ELEGIBLE"
    assert entry["gross_amount"] == 900_000
    assert entry["agreement_discount"] == 45_000 and entry["commissionable_base"] == 855_000
    assert entry["rate_bp"] is None and entry["commission_amount"] is None
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["commission_amount"] == 25_650
    # Cambio de tipo: el 5% del convenio debe aplicarse, nunca quedar en cero.
    other, _ = service.register_sale(SOL, common(source_sale_id="mixta", initial_paid=400_000))
    service.recalculate(SOL)
    assert active(service, other)["agreement_discount"] == 0
    service.register_sale(SOL, common(source_sale_id="mixta", kind="CONVENIO", initial_paid=400_000))
    service.recalculate(SOL)
    changed = active(service, other)
    assert changed["sale_kind"] == "CONVENIO" and changed["agreement_discount"] == 20_000
    assert changed["commissionable_base"] == 380_000


def test_source_correction_cannot_reattribute_already_paid_commission(service):
    """Observación O1 del Auditor generación 2, cerrada por la misma guarda."""
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-Y")
    service.observe(SOL, entry_id, "revisión posterior")
    service.register_sale(SOL, agreement(saleswoman="Otra Vendedora", total_amount=900_000))
    entry = active(service, sale_id)
    assert entry["saleswoman"] == "Vendedora Dos" and entry["gross_amount"] == 500_000
    assert entry["status"] == "OBSERVADA" and entry["paid_at"] == "2099-05-05"


def test_source_correction_after_approval_becomes_observed(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    changed_id, changed = service.register_sale(SOL, agreement(total_amount=600_000))
    assert changed_id == sale_id and changed
    entry = active(service, sale_id)
    assert entry["status"] == "OBSERVADA" and "corregido" in entry["observation"]


# ------------------------------------------------------------------ multi entidad
def test_multiple_saleswomen_locals_and_monthly_filters(service):
    service.register_sale(SOL, common(source_sale_id="a1", initial_paid=400_000))
    service.register_sale(SOL, common(branch="Óptica Pilar", source_sale_id="b1",
                                      saleswoman="Vendedora Dos", initial_paid=400_000))
    service.register_sale(SOL, agreement(source_sale_id="c1", sale_date="2099-05-02"))
    service.register_sale(SOL, common(source_sale_id="d1", saleswoman="Vendedora Tres"))
    service.recalculate(SOL)
    abril = service.report(SOL, "2099-04")
    assert abril["kpi"]["cancelled_sales"] == 2 and abril["kpi"]["agreements"] == 0
    assert abril["kpi"]["pending_balance_sales"] == 1
    assert {row["saleswoman"] for row in abril["by_saleswoman"]} == {
        "Vendedora Uno", "Vendedora Dos", "Vendedora Tres"}
    mayo = service.report(SOL, "2099-05")
    assert mayo["kpi"]["agreements"] == 1 and mayo["kpi"]["commissionable_base"] == 475_000
    solo_pilar = service.report(SOL, "2099-04", branch="Óptica Pilar")
    assert solo_pilar["kpi"]["cancelled_sales"] == 1
    assert len(service.list_entries(SOL, period="2099-04", saleswoman="Vendedora Uno")) == 1
    assert len(service.list_entries(SOL, period="2099-04", status="PENDIENTE_SALDO")) == 1
    assert len(service.list_entries(SOL, period="2099-04", kind="CONVENIO")) == 0


def test_persistence_survives_reopening(service):
    sale_id, _ = service.register_sale(SOL, common(initial_paid=400_000))
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    reopened = CommissionService(CentralManagementService(CentralRepository(service.repository.database_path)))
    entry = active(reopened, sale_id)
    assert entry["status"] == "REVISADA" and entry["commissionable_base"] == 400_000
    assert len(reopened.history(SOL, entry_id)) == 3


# ---------------------------------------------------------------------- política
def test_policy_is_synthetic_pending_approval_and_optional(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["rate_bp"] is None and entry["commission_amount"] is None
    assert entry["policy_status"] == POLICY_ABSENT
    assert "sólo la base" in service.breakdown(SOL, entry["id"])["policy_note"]
    service.set_policy(SOL, "GENERAL", 300)
    service.set_policy(SOL, "VENDEDORA", 500, "Vendedora Dos")
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["rate_bp"] == 500 and entry["commission_amount"] == 23_750
    assert entry["policy_status"] == POLICY_PENDING
    assert all(row["approval_status"] == POLICY_PENDING for row in service.policies(SOL))
    with pytest.raises(ValueError, match="porcentaje inválido"):
        service.set_policy(SOL, "GENERAL", 20_000)


# ------------------------------------------------------------- permisos y export
def test_permissions(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    assert service.get_entry(AUDITOR, entry_id)
    with pytest.raises(AccessDenied):
        service.review(AUDITOR, entry_id)
    with pytest.raises(AccessDenied):
        service.list_entries(LOCAL)


def test_structured_export_has_stable_contract_and_no_customer_data(service):
    service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    export = service.export_summary(SOL, "2099-04")
    assert export["contract_version"] == 1 and export["period"] == "2099-04"
    assert "pendiente de aprobación" in export["policy_disclaimer"]
    entry = export["entries"][0]
    assert entry["commissionable_base"] == 475_000 and entry["agreement_discount"] == 25_000
    assert set(entry) == {
        "entry_id", "period", "branch", "saleswoman", "sale_kind", "status", "sale_date",
        "cancelled_date", "gross_amount", "agreement_discount", "commissionable_base",
        "rate_bp", "commission_amount", "policy_status", "balance_amount", "observation"}


def test_review_sales_integration_skips_non_sale_rows(service, tmp_path):
    class FakeReview:
        @staticmethod
        def list_sales(_actor):
            return [
                {"branch": "Óptica Asunción", "identity": "r1",
                 "payload": {"date": "2099-04-08", "saleswoman": "Vendedora Uno", "total": 400_000,
                             "cash": 200_000, "card_transfer": 0, "agreement": 0, "envelope": "S-11"}},
                {"branch": "Óptica Pilar", "identity": "r2",
                 "payload": {"date": "2099-04-09", "saleswoman": "Vendedora Dos", "total": 500_000,
                             "cash": 0, "card_transfer": 0, "agreement": 500_000, "envelope": "S-12"}},
                {"branch": "Óptica Pilar", "identity": "gasto",
                 "payload": {"date": "2099-04-09", "saleswoman": "", "total": 0,
                             "cash": 0, "card_transfer": 0, "agreement": 0, "envelope": ""}},
            ]

    assert service.sync_review_sales(SOL, FakeReview()) == {"registered": 2, "skipped": 1, "invalid_date": 0}
    assert service.sync_review_sales(SOL, FakeReview()) == {"registered": 0, "skipped": 1, "invalid_date": 0}
    service.recalculate(SOL)
    report = service.report(SOL, "2099-04")
    assert report["kpi"]["agreements"] == 1 and report["kpi"]["pending_balance_sales"] == 1
    assert report["kpi"]["commissionable_base"] == 475_000


def test_no_external_provider_or_secrets_in_module():
    source = Path("modulos/gestion_central/comisiones.py").read_text(encoding="utf-8").lower()
    for forbidden in ("requests", "selenium", "playwright", "http://", "https://", "password", "token"):
        assert forbidden not in source
    assert "float(" not in source and AGREEMENT_DISCOUNT_BP == 500
