from pathlib import Path

import pytest

from modulos.gestion_central.comision_policy import (
    CANONICAL_CODE, CANONICAL_EFFECTIVE_FROM, CANONICAL_RATE_BP, RETIRED_POLICY_STATUSES,
)
from modulos.gestion_central.comisiones import (
    AGREEMENT_DISCOUNT_BP, COMMISSION_STATES, POLICY_ABSENT, POLICY_CANONICAL, POLICY_LEGACY,
    POLICY_OUT_OF_EFFECT, CommissionSaleInput, CommissionService, agreement_discount,
    apply_basis_points, commissionable_base,
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


def test_explicit_idempotency_key_protects_integration_retries(service):
    sale_id, _ = service.register_sale(SOL, common())
    first = service.register_payment(SOL, sale_id, 50_000, "2099-04-15", "recibo-x", idempotency_key="sync-1")
    second = service.register_payment(SOL, sale_id, 50_000, "2099-04-15", "recibo-x", idempotency_key="sync-1")
    assert first[1] and second == (None, False)
    assert active(service, sale_id)["balance_amount"] == 150_000
    with pytest.raises(ValueError, match="supera el saldo"):
        service.register_payment(SOL, sale_id, 999_000, "2099-04-16", "recibo-y")


def test_two_identical_genuine_payments_are_both_registered(service):
    """Bloqueante QA generación 3: dos cobros reales iguales no son un duplicado."""
    sale_id, _ = service.register_sale(SOL, common(initial_paid=0))
    first, applied_first = service.register_payment(SOL, sale_id, 200_000, "2099-04-20")
    second, applied_second = service.register_payment(SOL, sale_id, 200_000, "2099-04-20")
    assert applied_first and applied_second and first != second
    entry = active(service, sale_id)
    assert entry["balance_amount"] == 0 and entry["status"] == "ELEGIBLE"
    assert entry["period"] == "2099-04"
    assert len(service.payments(SOL, sale_id)) == 2


def test_a_reverted_payment_can_be_registered_again(service):
    """Bloqueante QA generación 3: una reversa deshace el hecho, no bloquea el recobro."""
    sale_id, _ = service.register_sale(SOL, common(initial_paid=0))
    payment_id, _ = service.register_payment(SOL, sale_id, 400_000, "2099-04-28", "RECIBO-77",
                                             idempotency_key="recibo-77")
    assert active(service, sale_id)["period"] == "2099-04"
    service.revert_payment(SOL, payment_id, "cheque rechazado por el banco")
    assert active(service, sale_id)["status"] == "PENDIENTE_SALDO"
    # El mismo recibo real vuelve a cargarse con su fecha real y su misma clave.
    again, applied = service.register_payment(SOL, sale_id, 400_000, "2099-04-28", "RECIBO-77",
                                              idempotency_key="recibo-77")
    assert applied and again is not None
    entry = active(service, sale_id)
    assert entry["status"] == "ELEGIBLE" and entry["period"] == "2099-04"
    assert entry["balance_amount"] == 0
    assert service.report(SOL, "2099-04")["kpi"]["commissionable_base"] == 400_000


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
    service.recalculate(SOL)
    entry = service.list_entries(SOL)[0]
    for name in ("gross_amount", "agreement_discount", "commissionable_base", "rate_bp", "commission_amount"):
        assert isinstance(entry[name], int) and not isinstance(entry[name], bool)
    assert entry["agreement_discount"] == 16_667 and entry["commissionable_base"] == 316_666
    # 1% de 316.666 son 3.166,66 guaraníes: HALF_UP redondea a 3.167.
    assert entry["commission_amount"] == 3_167


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
    assert result == {"registered": 1, "skipped": 0, "invalid_date": 1, "rejected": 0}
    assert result["invalid_date"] == 1, "la fila con fecha corrupta debe contarse, no perderse"
    assert len(service.list_entries(SOL)) == 1


def settled(service, sale_id):
    """Liquidado neto según el libro append-only."""
    return sum(int(p["amount"]) * (-1 if p["kind"] == "REVERSA" else 1)
               for p in service.payments(SOL, sale_id))


def test_resync_with_a_later_payment_settles_the_sale(service):
    """Bloqueante QA generación 4: la corrección de origen ignoraba el cobro declarado."""
    class FakeReview:
        cash = 100_000

        @classmethod
        def list_sales(cls, _actor):
            return [{"branch": "Óptica Asunción", "identity": "r1",
                     "payload": {"date": "2099-04-08", "saleswoman": "Vendedora Uno", "total": 400_000,
                                 "cash": cls.cash, "card_transfer": 0, "agreement": 0, "envelope": "S-11"}}]

    assert service.sync_review_sales(SOL, FakeReview())["registered"] == 1
    sale_id = service.list_entries(SOL)[0]["sale_id"]
    assert active(service, sale_id)["status"] == "PENDIENTE_SALDO"
    FakeReview.cash = 400_000
    assert service.sync_review_sales(SOL, FakeReview())["registered"] == 1
    entry = active(service, sale_id)
    assert entry["status"] == "ELEGIBLE" and entry["period"] == "2099-04"
    assert entry["balance_amount"] == 0 and entry["paid_amount"] == 400_000
    assert settled(service, sale_id) == 400_000, "lo cobrado debe estar respaldado por el libro"


def test_paid_amount_is_always_backed_by_the_ledger(service):
    """Bloqueante Auditor generación 4: `paid_amount` no puede quedar negativo ni sin respaldo."""
    sale_id, _ = service.register_sale(SOL, common(initial_paid=400_000))
    assert settled(service, sale_id) == 400_000
    # Corrección a convenio con total menor: el libro manda y no admite cobrar más que el total.
    with pytest.raises(ValueError, match="menor a lo ya cobrado"):
        service.register_sale(SOL, common(kind="CONVENIO", total_amount=100_000, initial_paid=0))
    service.register_sale(SOL, common(kind="CONVENIO", total_amount=400_000, initial_paid=0))
    row = active(service, sale_id)
    assert row["paid_amount"] == settled(service, sale_id) == 400_000
    assert row["balance_amount"] == 0
    with pytest.raises(ValueError, match="convenio"):
        service.revert_payment(SOL, service.payments(SOL, sale_id)[0]["id"], "intento")
    assert active(service, sale_id)["paid_amount"] >= 0


def test_convenio_settlement_is_recorded_in_the_ledger(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    ledger = service.payments(SOL, sale_id)
    assert [p["kind"] for p in ledger] == ["CONVENIO"]
    assert ledger[0]["amount"] == 500_000
    assert active(service, sale_id)["paid_amount"] == settled(service, sale_id) == 500_000


def test_retrying_the_cancelling_payment_is_discarded_not_rejected(service):
    """Bloqueante Auditor generación 4: el reintento explotaba por saldo en vez de descartarse."""
    sale_id, _ = service.register_sale(SOL, common(initial_paid=0))
    first = service.register_payment(SOL, sale_id, 400_000, "2099-04-28", "R-1", idempotency_key="sync-final")
    assert first[1] and active(service, sale_id)["status"] == "ELEGIBLE"
    retry = service.register_payment(SOL, sale_id, 400_000, "2099-04-28", "R-1", idempotency_key="sync-final")
    assert retry == (None, False), "el reintento debe descartarse limpiamente, no lanzar por saldo"
    assert active(service, sale_id)["balance_amount"] == 0
    assert settled(service, sale_id) == 400_000


def test_reverting_a_payment_on_a_voided_sale_is_rejected(service):
    sale_id, _ = service.register_sale(SOL, common(initial_paid=0))
    payment_id, _ = service.register_payment(SOL, sale_id, 400_000, "2099-04-28", "R-2")
    service.void_sale(SOL, sale_id, "anulada por el local")
    with pytest.raises(ValueError, match="venta anulada"):
        service.revert_payment(SOL, payment_id, "intento")


def test_downgrading_an_agreement_to_a_common_sale_reopens_the_balance(service):
    """Bloqueante QA y Auditor generación 5: la fila CONVENIO sobrevivía a la conversión."""
    sale_id, _ = service.register_sale(SOL, agreement())
    assert active(service, sale_id)["balance_amount"] == 0
    service.register_sale(SOL, agreement(kind="COMUN", initial_paid=0))
    entry = active(service, sale_id)
    assert entry["status"] == "PENDIENTE_SALDO", "sin convenio la venta no está liquidada"
    assert entry["balance_amount"] == 500_000 and entry["paid_amount"] == 0
    assert settled(service, sale_id) == 0, "el libro no puede sostener dinero nunca cobrado"
    assert service.report(SOL, "2099-04")["kpi"]["commissionable_base"] == 0
    # El cobro real posterior vuelve a ser posible y liquida la venta de verdad.
    service.register_payment(SOL, sale_id, 500_000, "2099-05-04", "recibo-real")
    entry = active(service, sale_id)
    assert entry["status"] == "ELEGIBLE" and entry["period"] == "2099-05"
    assert entry["commissionable_base"] == 0 or entry["balance_amount"] == 0


def test_a_downgraded_agreement_keeps_only_real_payments(service):
    """Tras revertir el convenio, sólo los cobros reales sostienen el saldo."""
    sale_id, _ = service.register_sale(SOL, common(initial_paid=600_000, total_amount=1_000_000))
    service.register_sale(SOL, common(kind="CONVENIO", total_amount=1_000_000, initial_paid=0))
    assert active(service, sale_id)["balance_amount"] == 0
    service.register_sale(SOL, common(total_amount=1_000_000, initial_paid=600_000))
    entry = active(service, sale_id)
    assert entry["paid_amount"] == 600_000 and entry["balance_amount"] == 400_000
    assert settled(service, sale_id) == 600_000


def test_reverted_payments_are_never_reported_as_collected(service):
    """Bloqueante QA generación 5: el KPI de cobros informaba dinero ya revertido."""
    sale_id, _ = service.register_sale(SOL, common(initial_paid=0))
    payment_id, _ = service.register_payment(SOL, sale_id, 300_000, "2099-04-20", "seña")
    assert service.report(SOL, "2099-04")["kpi"]["partial_payments_amount"] == 300_000
    service.revert_payment(SOL, payment_id, "cheque rechazado")
    kpi = service.report(SOL, "2099-04")["kpi"]
    assert kpi["partial_payments_amount"] == 0 and kpi["partial_payments_count"] == 0


def test_an_agreement_total_can_be_corrected_downwards(service):
    """Bloqueante QA generación 6: su propia liquidación impedía corregir el convenio a la baja."""
    sale_id, _ = service.register_sale(SOL, agreement(total_amount=1_000_000))
    service.recalculate(SOL)
    assert active(service, sale_id)["commissionable_base"] == 950_000
    service.register_sale(SOL, agreement(total_amount=900_000))
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["gross_amount"] == 900_000 and entry["agreement_discount"] == 45_000
    assert entry["commissionable_base"] == 855_000 and entry["balance_amount"] == 0
    assert settled(service, sale_id) == 900_000
    assert service.report(SOL, "2099-04")["kpi"]["commissionable_base"] == 855_000


def test_correcting_an_agreement_keeps_the_real_payments(service):
    """Corregir un convenio no puede destruir los cobros reales que ya tenía la venta."""
    sale_id, _ = service.register_sale(SOL, common(total_amount=1_000_000, initial_paid=600_000))
    service.register_sale(SOL, common(kind="CONVENIO", total_amount=1_000_000, initial_paid=0))
    service.register_sale(SOL, common(kind="CONVENIO", total_amount=900_000, initial_paid=0))
    entry = active(service, sale_id)
    assert entry["balance_amount"] == 0 and settled(service, sale_id) == 900_000
    service.register_sale(SOL, common(total_amount=900_000, initial_paid=600_000))
    entry = active(service, sale_id)
    assert entry["paid_amount"] == 600_000 and entry["balance_amount"] == 300_000


def test_a_rejected_row_never_truncates_the_sync_batch(service):
    """Bloqueante QA generación 6: la excepción abortaba el lote y salteaba las filas siguientes."""
    def row(identity, day, total, cash):
        return {"branch": "L", "identity": identity,
                "payload": {"date": f"2099-04-{day}", "saleswoman": "Ana", "total": total,
                            "cash": cash, "card_transfer": 0, "agreement": 0, "envelope": identity}}

    class FakeReview:
        rows = [row("antes", "01", 100_000, 100_000), row("malo", "02", 1_000_000, 600_000)]

        @classmethod
        def list_sales(cls, _actor):
            return cls.rows

    assert service.sync_review_sales(SOL, FakeReview())["registered"] == 2
    # El origen corrige el total por debajo de lo realmente cobrado: esa fila no puede aplicarse.
    FakeReview.rows = [row("antes", "01", 100_000, 100_000), row("malo", "02", 500_000, 600_000),
                       row("despues", "03", 300_000, 300_000)]
    result = service.sync_review_sales(SOL, FakeReview())
    assert result["rejected"] == 1, "la fila rechazada debe contarse, no abortar el lote"
    assert "despues" in {r["envelope"] for r in service.list_entries(SOL)}, \
        "las filas posteriores a una rechazada deben ingerirse igual"


def test_a_malformed_row_never_truncates_the_sync_batch(service):
    """Bloqueante QA generación 7: el parseo y la construcción quedaban fuera de la guarda."""
    def good(identity, day, total):
        return {"branch": "L", "identity": identity,
                "payload": {"date": f"2099-04-{day}", "saleswoman": "Ana", "total": total,
                            "cash": total, "card_transfer": 0, "agreement": 0, "envelope": identity}}

    malformed = [
        {"branch": "", "identity": "sin-local",  # local vacío: lo rechaza el dominio
         "payload": {"date": "2099-04-05", "saleswoman": "Ana", "total": 100_000,
                     "cash": 100_000, "card_transfer": 0, "agreement": 0, "envelope": "X"}},
        {"branch": "L", "identity": "total-texto",  # total con separador de miles del origen legacy
         "payload": {"date": "2099-04-06", "saleswoman": "Ana", "total": "1.000.000",
                     "cash": 0, "card_transfer": 0, "agreement": 0, "envelope": "Y"}},
        {"branch": "L", "identity": "sin-payload"},  # fila incompleta del origen
    ]

    class FakeReview:
        @staticmethod
        def list_sales(_actor):
            return [good("antes", "01", 100_000), *malformed, good("despues", "09", 300_000)]

    result = service.sync_review_sales(SOL, FakeReview())
    assert result["rejected"] == 3, "cada fila mal formada se cuenta, no aborta el lote"
    assert result["registered"] == 2
    assert "despues" in {r["envelope"] for r in service.list_entries(SOL)}


def test_a_permission_failure_still_stops_the_sync(service):
    """Un fallo de permisos no puede degradarse a fila rechazada."""
    class FakeReview:
        @staticmethod
        def list_sales(_actor):
            return [{"branch": "L", "identity": "x",
                     "payload": {"date": "2099-04-01", "saleswoman": "Ana", "total": 100_000,
                                 "cash": 100_000, "card_transfer": 0, "agreement": 0, "envelope": "X"}}]

    with pytest.raises(AccessDenied):
        service.sync_review_sales(AUDITOR, FakeReview())


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
    assert entry["commission_amount"] == 8_550
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


# ------------------------------------------------------- política canónica del 1%
def test_the_official_policy_is_the_approved_general_one_percent(service):
    policy = service.current_policy(SOL)
    assert policy["rate_bp"] == CANONICAL_RATE_BP == 100
    assert policy["rate_percent"] == "1.00" and policy["scope"] == "GENERAL"
    assert policy["status"] == POLICY_CANONICAL and policy["code"] == CANONICAL_CODE
    assert policy["version"] == 1 and policy["effective_from"] == CANONICAL_EFFECTIVE_FROM
    assert policy["rounding"] == "HALF_UP" and policy["currency"] == "GS"
    # La etiqueta sintética del piloto ya no existe en ninguna política almacenada.
    stored = service.policies(SOL)
    assert [row["scope"] for row in stored] == ["GENERAL"]
    assert all(row["approval_status"] not in RETIRED_POLICY_STATUSES for row in stored)
    assert [row["version"] for row in service.policy_versions(SOL)] == [1]


def test_a_cancelled_common_sale_of_400000_commissions_exactly_4000(service):
    sale_id, _ = service.register_sale(SOL, common(initial_paid=400_000))
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["gross_amount"] == 400_000 and entry["agreement_discount"] == 0
    assert entry["commissionable_base"] == 400_000
    assert entry["rate_bp"] == 100 and entry["commission_amount"] == 4_000
    assert entry["policy_status"] == POLICY_CANONICAL


def test_a_common_sale_with_balance_has_zero_payable_commission(service):
    sale_id, _ = service.register_sale(SOL, common(initial_paid=200_000))
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["status"] == "PENDIENTE_SALDO" and entry["balance_amount"] == 200_000
    # No hay comisión pagable: ni base, ni porcentaje aplicado, ni importe.
    assert entry["commissionable_base"] == 0
    assert entry["rate_bp"] is None and entry["commission_amount"] is None
    assert service.report(SOL, "2099-04")["kpi"]["commission_amount"] == 0
    # Un cobro parcial sigue siendo informativo y no crea comisión.
    service.register_payment(SOL, sale_id, 100_000, "2099-04-25", "seña")
    service.recalculate(SOL)
    assert active(service, sale_id)["commission_amount"] is None


def test_an_agreement_of_500000_discounts_25000_and_commissions_4750(service):
    sale_id, _ = service.register_sale(SOL, agreement(total_amount=500_000))
    service.recalculate(SOL)
    entry = active(service, sale_id)
    # Primero el 5% del total, después el 1% sobre la base resultante.
    assert entry["gross_amount"] == 500_000 and entry["agreement_discount"] == 25_000
    assert entry["commissionable_base"] == 475_000
    assert entry["rate_bp"] == 100 and entry["commission_amount"] == 4_750
    assert entry["policy_status"] == POLICY_CANONICAL


def test_the_same_one_percent_applies_to_every_saleswoman_and_branch(service):
    sales = [
        service.register_sale(SOL, common(branch="Óptica Asunción", source_sale_id="p1",
                                          saleswoman="Vendedora Uno", initial_paid=400_000))[0],
        service.register_sale(SOL, common(branch="Óptica Pilar", source_sale_id="p2",
                                          saleswoman="Vendedora Dos", initial_paid=400_000))[0],
        service.register_sale(SOL, common(branch="Óptica Encarnación", source_sale_id="p3",
                                          saleswoman="Vendedora Tres", initial_paid=400_000))[0],
    ]
    service.recalculate(SOL)
    entries = [active(service, sale_id) for sale_id in sales]
    assert {entry["rate_bp"] for entry in entries} == {100}
    assert {entry["commission_amount"] for entry in entries} == {4_000}
    assert {entry["policy_scope"] for entry in entries} == {"GENERAL"}


def test_the_policy_used_is_traceable_on_every_settlement(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["policy_code"] == CANONICAL_CODE and entry["policy_version"] == 1
    assert entry["policy_effective_from"] == CANONICAL_EFFECTIVE_FROM
    assert entry["policy_scope"] == "GENERAL"
    detail = service.breakdown(SOL, entry["id"])
    assert detail["policy"]["rate_percent"] == "1.00" and detail["policy"]["rounding"] == "HALF_UP"
    assert "1,00%" in detail["policy_note"] and CANONICAL_EFFECTIVE_FROM in detail["policy_note"]
    assert [line["label"] for line in detail["lines"]][-1].startswith("Comisión oficial (1,00%")
    assert detail["lines"][-1]["amount"] == 4_750
    history = [event for event in service.history(SOL, entry["id"])
               if event["action"] == "COMMISSION_RECALCULATED"]
    assert "COMISION_GENERAL_1PCT" in history[-1]["details_json"]


def test_a_period_before_the_effective_date_never_applies_the_rate(service):
    """La vigencia no se aplica hacia atrás: se informa la base y se dice por qué."""
    sale_id, _ = service.register_sale(SOL, common(sale_date="2026-07-10", initial_paid=400_000))
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["period"] == "2026-07" and entry["commissionable_base"] == 400_000
    assert entry["rate_bp"] is None and entry["commission_amount"] is None
    assert entry["policy_status"] == POLICY_OUT_OF_EFFECT
    assert "anterior a la vigencia" in service.breakdown(SOL, entry["id"])["policy_note"]
    # Sin comisión oficial aplicada no hay revisión ni pago posible.
    with pytest.raises(ValueError, match="política oficial"):
        service.review(SOL, entry["id"])


def test_half_up_rounding_to_whole_guarani_is_explicit(service):
    # Medio guaraní exacto: HALF_UP sube, no trunca ni redondea al par.
    assert apply_basis_points(50, 100) == 1          # 0,50 → 1
    assert apply_basis_points(150, 100) == 2         # 1,50 → 2
    assert apply_basis_points(49, 100) == 0          # 0,49 → 0
    assert apply_basis_points(1_234_567, 100) == 12_346  # 12.345,67 → 12.346
    sale_id, _ = service.register_sale(SOL, common(total_amount=1_234_567, initial_paid=1_234_567))
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["commission_amount"] == 12_346 and isinstance(entry["commission_amount"], int)


def test_recalculating_never_duplicates_and_never_reapplies(service):
    service.register_sale(SOL, common(initial_paid=400_000))
    service.register_sale(SOL, agreement())
    assert service.recalculate(SOL) == {"evaluated": 2, "changed": 2}
    for _ in range(3):
        assert service.recalculate(SOL) == {"evaluated": 2, "changed": 0}
    entries = service.list_entries(SOL)
    assert len(entries) == 2
    assert sorted(entry["commission_amount"] for entry in entries) == [4_000, 4_750]
    recalculations = sum(1 for entry in entries
                         for event in service.history(SOL, entry["id"])
                         if event["action"] == "COMMISSION_RECALCULATED")
    assert recalculations == 2


def test_a_paid_settlement_is_never_touched_by_a_policy_change(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    paid = service.get_entry(SOL, entry_id)
    version, published = service.set_general_rate(SOL, 200, "2099-06-01", "prueba de cambio")
    assert (version, published) == (2, True)
    assert service.recalculate(SOL) == {"evaluated": 0, "changed": 0}
    after = service.get_entry(SOL, entry_id)
    assert after["commission_amount"] == paid["commission_amount"] == 4_750
    assert after["rate_bp"] == 100 and after["policy_version"] == 1
    assert after["status"] == "PAGADA" and after["updated_at"] == paid["updated_at"]


def test_publishing_a_policy_version_is_audited_and_idempotent(service):
    assert service.set_general_rate(SOL, 100, CANONICAL_EFFECTIVE_FROM) == (1, False)
    assert service.set_general_rate(SOL, 150, "2099-01-01", "suba pactada") == (2, True)
    assert service.set_general_rate(SOL, 150, "2099-01-01") == (2, False)
    versions = service.policy_versions(SOL)
    assert [(row["version"], row["rate_bp"]) for row in versions] == [(1, 100), (2, 150)]
    assert service.current_policy(SOL)["rate_bp"] == 150
    with pytest.raises(ValueError, match="porcentaje inválido"):
        service.set_general_rate(SOL, 20_000, "2099-01-01")
    with pytest.raises(ValueError, match="vigencia inválida"):
        service.set_general_rate(SOL, 100, "2099-13-40")
    audit = [row for row in service.repository.audit_log()
             if row["action"] == "COMMISSION_POLICY_VERSION_PUBLISHED"]
    assert len(audit) == 1 and "150" in audit[0]["details_json"]


def test_voiding_and_reverting_keep_the_audit_trail_of_the_policy(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["commission_amount"] == 4_750 and entry["policy_version"] == 1
    assert service.void_sale(SOL, sale_id, "anulada por error de carga")
    reverted = next(row for row in service.list_entries(SOL) if row["id"] == entry["id"])
    assert reverted["status"] == "REVERTIDA"
    # La liquidación revertida conserva intacta la traza de la política que usó.
    assert reverted["rate_bp"] == 100 and reverted["policy_code"] == CANONICAL_CODE
    assert reverted["policy_version"] == 1 and reverted["policy_effective_from"] == CANONICAL_EFFECTIVE_FROM
    assert [event["to_state"] for event in service.history(SOL, entry["id"])] == \
        ["ELEGIBLE", "CALCULADA", "REVERTIDA"]
    assert service.report(SOL, "2099-04")["kpi"]["commission_amount"] == 0


def test_the_official_commission_survives_reopening_the_database(service):
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    reopened = CommissionService(CentralManagementService(CentralRepository(service.repository.database_path)))
    entry = reopened.get_entry(SOL, entry_id)
    assert entry["commission_amount"] == 4_750 and entry["rate_bp"] == 100
    assert entry["policy_code"] == CANONICAL_CODE and entry["policy_version"] == 1
    assert reopened.current_policy(SOL)["rate_bp"] == 100
    # Reabrir vuelve a migrar y la migración no puede duplicar versiones ni políticas.
    assert len(reopened.policies(SOL)) == 1 and len(reopened.policy_versions(SOL)) == 1
    assert reopened.recalculate(SOL) == {"evaluated": 1, "changed": 0}


def test_migration_retires_the_synthetic_label_without_touching_money(tmp_path):
    """Una base del piloto anterior se abre con la política canónica y sin perder importes."""
    import sqlite3

    database = tmp_path / "legado.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(database)))
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    legacy_status = RETIRED_POLICY_STATUSES[0]
    with sqlite3.connect(database) as con:
        # Se reconstruye el estado que dejaba el piloto: 3% sintético por vendedora.
        con.execute("UPDATE commission_entries SET rate_bp=300,commission_amount=14250,policy_status=?,"
                    "policy_code=NULL,policy_version=NULL,policy_effective_from=NULL,policy_scope=NULL"
                    " WHERE id=?", (legacy_status, entry_id))
        con.execute("UPDATE commission_policies SET approval_status=?,rate_bp=300", (legacy_status,))
        con.execute("INSERT INTO commission_policies(id,scope,scope_value,rate_bp,approval_status,code,"
                    "version,effective_from,created_by,created_at)"
                    " VALUES('legacy-v','VENDEDORA','Vendedora Dos',500,?,'',1,'','sol','2026-01-01')",
                    (legacy_status,))
        con.commit()

    migrated = CommissionService(CentralManagementService(CentralRepository(database)))
    policy = migrated.current_policy(SOL)
    assert policy["rate_bp"] == 100 and policy["status"] == POLICY_CANONICAL
    assert [row["scope"] for row in migrated.policies(SOL)] == ["GENERAL"]
    entry = migrated.get_entry(SOL, entry_id)
    # El importe histórico no se toca; sólo cae la etiqueta retirada.
    assert entry["rate_bp"] == 300 and entry["commission_amount"] == 14_250
    assert entry["policy_status"] == POLICY_LEGACY
    assert "política anterior" in migrated.breakdown(SOL, entry_id)["policy_note"]
    retired = [row for row in migrated.repository.audit_log()
               if row["action"] == "COMMISSION_POLICY_RETIRED"]
    assert {"VENDEDORA:Vendedora Dos", "GENERAL:"} <= {row["target"] for row in retired}
    # El recálculo posterior sí la trae a la regla aprobada, porque no está pagada.
    assert migrated.recalculate(SOL)["changed"] == 1
    recalculated = migrated.get_entry(SOL, entry_id)
    assert recalculated["rate_bp"] == 100 and recalculated["commission_amount"] == 4_750
    assert recalculated["policy_status"] == POLICY_CANONICAL


def legacy_database(tmp_path, status, rate_bp=700, commission=33_250):
    """Base del piloto anterior: una liquidación con porcentaje ya retirado."""
    import sqlite3

    database = tmp_path / "legado.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(database)))
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    with sqlite3.connect(database) as con:
        con.execute("UPDATE commission_entries SET status=?,rate_bp=?,commission_amount=?,policy_status=?,"
                    "policy_code=NULL,policy_version=NULL,policy_effective_from=NULL,policy_scope=NULL,"
                    "reviewed_by='Sol',reviewed_at='2026-07-01',"
                    "approved_by=CASE WHEN ?='APROBADA' THEN 'Sol' ELSE NULL END,"
                    "approved_at=CASE WHEN ?='APROBADA' THEN '2026-07-02' ELSE NULL END WHERE id=?",
                    (status, rate_bp, commission, RETIRED_POLICY_STATUSES[0], status, status, entry_id))
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(database))), entry_id


@pytest.mark.parametrize("status", ["REVISADA", "APROBADA"])
def test_a_retired_rate_can_never_be_paid_through_the_normal_flow(tmp_path, status):
    """Bloqueante A2: una liquidación legada era pagable al porcentaje ya retirado."""
    service, entry_id = legacy_database(tmp_path, status)
    entry = service.get_entry(SOL, entry_id)
    assert entry["status"] == status and entry["policy_status"] == POLICY_LEGACY
    assert entry["commission_amount"] == 33_250  # 7% de 475.000, siete veces lo oficial
    # El paso siguiente de la cadena de pago se corta en cada punto de entrada posible.
    if status == "REVISADA":
        with pytest.raises(ValueError, match="política oficial vigente"):
            service.approve(SOL, entry_id, "Sol")
    else:
        with pytest.raises(ValueError, match="política oficial vigente"):
            service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-X")
    assert service.get_entry(SOL, entry_id)["status"] == status
    # La pantalla no lo llama «oficial» ni lo presenta como pagable.
    detail = service.breakdown(SOL, entry_id)
    assert detail["lines"][-1]["label"].startswith("Comisión con política anterior (no pagable)")
    assert "No es pagable con este importe" in detail["policy_note"]
    assert "Recalcule" in detail["policy_note"]


@pytest.mark.parametrize("status", ["REVISADA", "APROBADA"])
def test_recalculating_repairs_a_retired_rate_and_withdraws_its_approval(tmp_path, status):
    """La salida sí existe y no destruye la comisión: vuelve a CALCULADA con el 1%."""
    service, entry_id = legacy_database(tmp_path, status)
    assert service.recalculate(SOL) == {"evaluated": 1, "changed": 1}
    repaired = service.get_entry(SOL, entry_id)
    assert repaired["status"] == "CALCULADA" and repaired["commission_amount"] == 4_750
    assert repaired["rate_bp"] == 100 and repaired["policy_status"] == POLICY_CANONICAL
    assert repaired["policy_code"] == CANONICAL_CODE and repaired["policy_version"] == 1
    # El aval anterior cae con el importe que respaldaba: hay que rehacerlo.
    assert repaired["reviewed_by"] is None and repaired["reviewed_at"] is None
    assert repaired["approved_by"] is None and repaired["approved_at"] is None
    event = service.history(SOL, entry_id)[-1]
    assert event["action"] == "COMMISSION_POLICY_REPAIRED" and event["from_state"] == status
    assert "33250" in event["details_json"].replace(" ", "")
    # Idempotente: reparar no se repite.
    assert service.recalculate(SOL) == {"evaluated": 1, "changed": 0}
    # Y ahora sí se puede rehacer la cadena, sobre el importe correcto.
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-OK")
    assert service.get_entry(SOL, entry_id)["commission_amount"] == 4_750


def test_a_paid_legacy_settlement_keeps_its_amount_and_is_never_repaired(tmp_path):
    """Lo que ya movió dinero no se repara: se conserva con su traza vacía por auditoría."""
    service, entry_id = legacy_database(tmp_path, "APROBADA")
    import sqlite3
    with sqlite3.connect(service.repository.database_path) as con:
        con.execute("UPDATE commission_entries SET status='PAGADA',paid_at='2026-07-10',"
                    "payment_reference='TRANSF-LEGADA' WHERE id=?", (entry_id,))
        con.commit()
    assert service.recalculate(SOL) == {"evaluated": 0, "changed": 0}
    paid = service.get_entry(SOL, entry_id)
    assert paid["status"] == "PAGADA" and paid["commission_amount"] == 33_250
    assert paid["policy_status"] == POLICY_LEGACY and paid["policy_code"] is None
    assert "Ya fue pagado" in service.breakdown(SOL, entry_id)["policy_note"]


def test_a_complete_trace_means_a_policy_evaluated_it_and_an_empty_one_means_none_did(tmp_path):
    """Invariante de traza en su forma verificable, con los cuatro estados en una misma base."""
    import sqlite3

    service, legacy_id = legacy_database(tmp_path, "APROBADA")
    with sqlite3.connect(service.repository.database_path) as con:
        # Pagada: es el único caso que conserva POLITICA_HISTORICA_PREVIA tras recalcular.
        con.execute("UPDATE commission_entries SET status='PAGADA',paid_at='2099-05-01',"
                    "payment_reference='TRANSF-LEGADA' WHERE id=?", (legacy_id,))
        con.commit()
    service.register_sale(SOL, common(source_sale_id="nueva", initial_paid=400_000))
    service.register_sale(SOL, common(source_sale_id="vieja", sale_date="2026-07-10",
                                      initial_paid=400_000))
    pending, _ = service.register_sale(SOL, common(source_sale_id="con-saldo", initial_paid=100_000))
    service.recalculate(SOL)

    trace = ("policy_code", "policy_version", "policy_effective_from", "policy_scope")
    seen = set()
    for entry in service.list_entries(SOL):
        seen.add(entry["policy_status"])
        complete = all(entry[name] is not None for name in trace)
        empty = not any(entry[name] is not None for name in trace)
        assert complete or empty, "la traza nunca queda a medias"
        if entry["policy_status"] == POLICY_CANONICAL:
            assert complete and entry["rate_bp"] == 100 and entry["commission_amount"] is not None
        elif entry["policy_status"] == POLICY_OUT_OF_EFFECT:
            # Se evaluó una política y no rige: hay traza, pero ningún importe que respaldar.
            assert complete and entry["rate_bp"] is None and entry["commission_amount"] is None
        else:
            # Ninguna política aprobada produjo este importe, y la traza vacía lo dice.
            assert empty
    assert seen == {POLICY_CANONICAL, POLICY_OUT_OF_EFFECT, POLICY_LEGACY, POLICY_ABSENT}
    # El caso que da sentido al invariante: importe presente y traza vacía, ya pagado.
    paid = service.get_entry(SOL, legacy_id)
    assert paid["commission_amount"] == 33_250 and paid["policy_code"] is None
    assert active(service, pending)["policy_status"] == POLICY_ABSENT


def test_the_retired_label_survives_only_as_the_thing_the_migration_removes():
    """`SINTETICA_PENDIENTE_APROBACION` no se produce en ningún lado; sólo se retira."""
    modules = Path(__file__).resolve().parents[2] / "modulos" / "gestion_central"
    for name in ("comisiones.py", "comisiones_ui.py", "repository.py"):
        assert "SINTETICA_PENDIENTE_APROBACION" not in (modules / name).read_text("utf-8"), name
    policy_source = (modules / "comision_policy.py").read_text("utf-8")
    retired = policy_source.split("RETIRED_POLICY_STATUSES", 1)[1]
    assert "SINTETICA_PENDIENTE_APROBACION" in retired.split("\n\n", 1)[0]
    assert policy_source.count("SINTETICA_PENDIENTE_APROBACION") == 1


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
    assert export["contract_version"] == 2 and export["period"] == "2099-04"
    assert export["policy"] == {
        "code": CANONICAL_CODE, "scope": "GENERAL", "status": POLICY_CANONICAL, "version": 1,
        "effective_from": CANONICAL_EFFECTIVE_FROM, "rate_bp": 100, "rate_percent": "1.00",
        "rounding": "HALF_UP", "currency": "GS"}
    assert "1.00%" in export["policy_disclaimer"] and "5%" in export["policy_disclaimer"]
    assert "HALF_UP" in export["policy_disclaimer"]
    entry = export["entries"][0]
    assert entry["commissionable_base"] == 475_000 and entry["agreement_discount"] == 25_000
    assert entry["commission_amount"] == 4_750 and entry["rate_bp"] == 100
    assert entry["policy_code"] == CANONICAL_CODE and entry["policy_version"] == 1
    assert entry["policy_effective_from"] == CANONICAL_EFFECTIVE_FROM
    assert set(entry) == {
        "entry_id", "period", "branch", "saleswoman", "sale_kind", "status", "sale_date",
        "cancelled_date", "gross_amount", "agreement_discount", "commissionable_base",
        "rate_bp", "commission_amount", "policy_status", "policy_code", "policy_version",
        "policy_effective_from", "policy_scope", "balance_amount", "observation"}


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

    assert service.sync_review_sales(SOL, FakeReview()) == {"registered": 2, "skipped": 1, "invalid_date": 0, "rejected": 0}
    assert service.sync_review_sales(SOL, FakeReview()) == {"registered": 0, "skipped": 1, "invalid_date": 0, "rejected": 0}
    service.recalculate(SOL)
    report = service.report(SOL, "2099-04")
    assert report["kpi"]["agreements"] == 1 and report["kpi"]["pending_balance_sales"] == 1
    assert report["kpi"]["commissionable_base"] == 475_000


def test_no_external_provider_or_secrets_in_module():
    source = Path("modulos/gestion_central/comisiones.py").read_text(encoding="utf-8").lower()
    for forbidden in ("requests", "selenium", "playwright", "http://", "https://", "password", "token"):
        assert forbidden not in source
    assert "float(" not in source and AGREEMENT_DISCOUNT_BP == 500


# ------------------------------------- bloqueantes de la generación 2 (deriva y varados)
def test_scheduling_the_next_rate_never_touches_the_current_period(service):
    """Bloqueante QA generación 2: publicar la vigencia siguiente borraba el mes en curso."""
    for index in range(3):
        service.register_sale(SOL, common(source_sale_id=f"v{index}", initial_paid=400_000))
    service.recalculate(SOL)
    assert service.report(SOL, "2099-04")["kpi"]["commission_amount"] == 12_000
    # La política del año que viene se publica hoy y no puede tocar lo de este período.
    assert service.set_general_rate(SOL, 150, "2100-01-01", "suba pactada") == (2, True)
    assert service.recalculate(SOL) == {"evaluated": 3, "changed": 0}
    assert service.report(SOL, "2099-04")["kpi"]["commission_amount"] == 12_000
    for entry in service.list_entries(SOL):
        assert entry["rate_bp"] == 100 and entry["policy_version"] == 1
    # Y una venta del período ya cubierto por la versión nueva sí toma el 1,5%.
    later, _ = service.register_sale(SOL, common(source_sale_id="futura", sale_date="2100-02-10",
                                                 initial_paid=400_000))
    service.recalculate(SOL)
    entry = active(service, later)
    assert entry["rate_bp"] == 150 and entry["commission_amount"] == 6_000
    assert entry["policy_version"] == 2


def test_a_policy_version_can_never_re_rate_a_closed_period(service):
    """La vigencia no retrocede: se programa el futuro, no se reescribe el pasado."""
    service.set_general_rate(SOL, 150, "2100-01-01")
    with pytest.raises(ValueError, match="la vigencia no puede retroceder"):
        service.set_general_rate(SOL, 400, CANONICAL_EFFECTIVE_FROM)
    assert [row["version"] for row in service.policy_versions(SOL)] == [1, 2]
    assert service.current_policy(SOL)["rate_bp"] == 150


def test_a_settlement_calculated_under_an_older_version_is_never_paid(service):
    """Bloqueante Auditor generación 2: el sello CANONICA_APROBADA quedaba desactualizado."""
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    # La política del propio período de la liquidación cambia: su importe deja de ser oficial.
    service.set_general_rate(SOL, 50, "2099-01-01", "baja pactada")
    assert service.get_entry(SOL, entry_id)["commission_amount"] == 4_750
    with pytest.raises(ValueError, match="la política del período cambió"):
        service.approve(SOL, entry_id, "Sol")
    # El recálculo la repara y retira el aval, igual que con una política retirada.
    assert service.recalculate(SOL) == {"evaluated": 1, "changed": 1}
    repaired = service.get_entry(SOL, entry_id)
    assert repaired["status"] == "CALCULADA" and repaired["commission_amount"] == 2_375
    assert repaired["rate_bp"] == 50 and repaired["policy_version"] == 2
    assert repaired["reviewed_by"] is None
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-OK")
    assert service.get_entry(SOL, entry_id)["commission_amount"] == 2_375


@pytest.mark.parametrize("status", ["REVISADA", "APROBADA"])
def test_a_legacy_settlement_without_any_rate_is_repaired_too(tmp_path, status):
    """Bloqueante QA/Auditor generación 2: el piloto no sembraba política alguna.

    La reparación cubría sólo `POLITICA_HISTORICA_PREVIA` y dejaba varada para siempre a la
    liquidación sin porcentaje, que era el estado por defecto del piloto anterior.
    """
    import sqlite3

    database = tmp_path / "sin-politica.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(database)))
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    with sqlite3.connect(database) as con:
        con.execute("UPDATE commission_entries SET status=?,rate_bp=NULL,commission_amount=NULL,"
                    "policy_status=?,policy_code=NULL,policy_version=NULL,policy_effective_from=NULL,"
                    "policy_scope=NULL,reviewed_by='Sol',reviewed_at='2026-07-01' WHERE id=?",
                    (status, POLICY_ABSENT, entry_id))
        con.commit()
    service = CommissionService(CentralManagementService(CentralRepository(database)))
    assert service.get_entry(SOL, entry_id)["policy_status"] == POLICY_ABSENT
    with pytest.raises(ValueError, match="política oficial"):
        service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-X") if status == "APROBADA" \
            else service.approve(SOL, entry_id, "Sol")
    # No queda varada: el recálculo la trae a la comisión oficial sin destruirla.
    assert service.recalculate(SOL) == {"evaluated": 1, "changed": 1}
    repaired = service.get_entry(SOL, entry_id)
    assert repaired["status"] == "CALCULADA" and repaired["commission_amount"] == 4_750
    assert repaired["policy_status"] == POLICY_CANONICAL and repaired["reviewed_by"] is None
    assert service.recalculate(SOL) == {"evaluated": 1, "changed": 0}


def test_recalculate_never_reaches_anything_that_moved_money(tmp_path):
    """Bloqueante Auditor generación 2: `paid_at IS NULL` colgaba de una rama, no del WHERE."""
    import sqlite3

    database = tmp_path / "pagada.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(database)))
    sale_id, _ = service.register_sale(SOL, agreement())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    with sqlite3.connect(database) as con:
        # Estado imposible por la API pública, pero es justo lo que el invariante afirma cubrir.
        con.execute("UPDATE commission_entries SET status='CALCULADA',paid_at='2099-05-01',"
                    "payment_reference='TRANSF-VIEJA',rate_bp=700,commission_amount=33250,"
                    "policy_status=? WHERE id=?", (POLICY_LEGACY, entry_id))
        con.commit()
    service = CommissionService(CentralManagementService(CentralRepository(database)))
    assert service.recalculate(SOL) == {"evaluated": 0, "changed": 0}
    untouched = service.get_entry(SOL, entry_id)
    assert untouched["commission_amount"] == 33_250 and untouched["rate_bp"] == 700
    assert untouched["paid_at"] == "2099-05-01"


def test_the_official_kpi_never_counts_an_amount_from_a_retired_policy(tmp_path):
    """Bloqueante QA generación 2: el KPI «oficial 1,00%» sumaba importes al 7%."""
    import sqlite3

    service, entry_id = legacy_database(tmp_path, "APROBADA")
    with sqlite3.connect(service.repository.database_path) as con:
        con.execute("UPDATE commission_entries SET status='PAGADA',paid_at='2099-05-01',"
                    "payment_reference='TRANSF-LEGADA' WHERE id=?", (entry_id,))
        con.commit()
    service.register_sale(SOL, common(source_sale_id="oficial", initial_paid=400_000))
    service.recalculate(SOL)
    kpi = service.report(SOL, "2099-04")["kpi"]
    assert kpi["commission_amount"] == 4_000
    assert kpi["non_official_amount"] == 33_250 and kpi["non_official_entries"] == 1
    # Lo pagado sí incluye el importe histórico: ese dinero efectivamente salió.
    assert kpi["paid_amount"] == 33_250
    export = service.export_summary(SOL, "2099-04")
    assert export["kpi"]["commission_amount"] == 4_000
    assert export["kpi"]["non_official_amount"] == 33_250
