from pathlib import Path

import pytest

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import Order

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def create_order(controller):
    return controller.service.repository.save_order(Order(
        delivery_date="20-08-2026", branch="PC", customer_name="Paciente",
        customer_phone="0981000000", customer_document="123", envelope="S-1",
        saleswoman="Ana",
    ))


def test_reversible_order_statuses_are_persistent_audited_and_duplicate_safe(tmp_path):
    controller = build_cash_day_controller(tmp_path / "rc10.sqlite3")
    order = create_order(controller)
    ready = controller.update_order_status(order.id, "LISTO", responsible="ana")
    assert ready.status.value == "LISTO"
    controller.update_order_status(order.id, "LISTO", responsible="ana")
    assert len(controller.service.repository.list_order_status_revisions(order.id)) == 1
    pending = controller.update_order_status(order.id, "PENDIENTE", responsible="ana")
    assert pending.status.value == "PENDIENTE"
    controller.update_order_status(order.id, "LISTO", responsible="ana")
    controller.update_order_status(order.id, "ENTREGADO", responsible="ana")
    with pytest.raises(InvalidCashDayError, match="motivo"):
        controller.update_order_status(order.id, "PENDIENTE", responsible="supervisora")
    corrected = controller.update_order_status(
        order.id, "PENDIENTE", reason="Entrega marcada por error", responsible="supervisora"
    )
    assert corrected.status.value == "PENDIENTE"
    audit = controller.service.repository.list_order_status_revisions(order.id)
    assert [(x["previous_status"], x["new_status"]) for x in audit] == [
        ("PENDIENTE", "LISTO"), ("LISTO", "PENDIENTE"),
        ("PENDIENTE", "LISTO"), ("LISTO", "ENTREGADO"),
        ("ENTREGADO", "PENDIENTE"),
    ]
    assert audit[-1]["responsible"] == "supervisora"
    assert audit[-1]["reason"] == "Entrega marcada por error"
    assert audit[-1]["recorded_at"]
    reopened = controller.list_orders("Todos", today="14-08-2026")[0]
    assert reopened.status.value == "PENDIENTE"
    controller.service.repository.close()


def test_history_contrast_and_order_alignment_chip_contract():
    for color in ("#F3F6FA", "#FFFFFF", "#EEF4FB", "#132238", "#DCEBFA", "#FDECEC", "#A32626"):
        assert color in SOURCE
    # El port de Pedidos movió la alineación a ORDER_COLUMN_SPECS; sólo "Última novedad" estira.
    assert 'for clave, titulo, ancho, anchor in ORDER_COLUMN_SPECS:' in SOURCE
    assert 'estirable = clave == "novedad"' in SOURCE
    assert 'grilla_pedidos.heading(clave, text=titulo, anchor=anchor)' in SOURCE
    assert 'grilla_pedidos.column(clave, width=ancho, minwidth=ancho, anchor=anchor, stretch=estirable)' in SOURCE
    for state in ("PENDIENTE", "LISTO", "ENTREGADO", "ANULADO"):
        assert f'"{state}": (' in SOURCE
    # La reversión auditada dejó de ser un caso especial: toda corrección pasa por
    # el diálogo de lista cerrada y exige observación.
    assert 'text="Observación / motivo (obligatorio)"' in SOURCE
    assert 'aviso_correccion.configure(text="La observación es obligatoria.")' in SOURCE
    assert 'orient="vertical"' in SOURCE


def test_migration_014_is_minimal_idempotent_audit_storage():
    migration = Path("modulos/caja_diaria/infrastructure/migrations/014_order_status_revisions.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS order_status_revisions" in migration
    assert "CREATE INDEX IF NOT EXISTS" in migration
    assert "previous_status TEXT NOT NULL" in migration
    assert "new_status TEXT NOT NULL" in migration
    assert "responsible TEXT NOT NULL" in migration
    assert "reason TEXT NOT NULL" in migration
    assert "VALUES ('014', CURRENT_TIMESTAMP)" in migration