from pathlib import Path

import pytest

import CajaDiaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import SaleItem

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def visible(**overrides):
    values = {
        "arm_org": "Lente cortesía", "cod": "SC-01", "armazon": "",
        "cristal": "", "descuento_armazon": "", "descuento_cristal": "",
        "sin_costo": "1", "laboratorio": "LAB", "receta_dr": "Dra. Vera",
    }
    values.update(overrides)
    return CajaDiaria.construir_item_producto_visible(values)


def test_no_cost_accepts_empty_or_zero_prices_and_keeps_reference_price():
    empty = visible()
    zero = visible(armazon="0", cristal="0")
    priced = visible(armazon="300000", descuento_armazon="15")
    assert (empty.reference_subtotal, empty.subtotal, empty.no_cost) == (0, 0, True)
    assert (zero.reference_subtotal, zero.subtotal, zero.no_cost) == (0, 0, True)
    assert priced.reference_subtotal == 300_000
    assert priced.frame_discount_percent == 15
    assert priced.subtotal == 0


def test_unchecked_no_cost_restores_normal_price_validation():
    with pytest.raises(ValueError, match="debe tener un precio"):
        visible(sin_costo="0")


def test_empty_no_cost_item_in_multiproduct_sale_persists_reopens_and_audits(tmp_path):
    database = tmp_path / "rc8.sqlite3"
    controller = build_cash_day_controller(database)
    controller.open_or_load_day("14-08-2026", "PC", "100000")
    free = visible()
    paid = SaleItem(description="Anteojos", code="P-01", item_type="Recetado", frame_price=300_000, lens_price=200_000)
    values = {
        "fecha": "14-08-2026", "unidad": "PC", "caja_inicial": "100000",
        "descripcion": "Cliente RC8", "vendedora": "Ana", "total": "500000",
        "efectivo": "200000", "tarjeta_cheque": "100000", "transferencia": "0",
        "ordenes": "Convenio interno", "monto_convenio": "100000", "cuotas": "2", "saldo": "100000",
        "items": (free, paid),
    }
    _, saved = controller.add_manual_entry(values)
    reopened = controller.load_day("14-08-2026", "PC").entries[0]
    assert reopened.total == 500_000
    assert [item.subtotal for item in reopened.items] == [0, 500_000]
    assert reopened.items[0].no_cost is True
    assert reopened.items[0].frame_price is None and reopened.items[0].lens_price is None
    assert reopened.cash == 200_000
    assert reopened.balance == "100000"
    create = controller.service.repository.list_entry_revisions(saved.id)[0]
    assert create["action"] == "CREATE"
    assert create["snapshot"]["items"][0]["no_cost"] is True
    assert create["snapshot"]["items"][0]["frame_original_price"] is None
    controller.update_manual_entry(saved.id, values, reason="Confirma cortesía", user="auditora")
    update = controller.service.repository.list_entry_revisions(saved.id)[-1]
    assert update["action"] == "UPDATE"
    assert update["snapshot"]["items"][0]["no_cost"] is True
    controller.service.repository.close()


def test_rc8_draft_columns_and_observations_use_available_space():
    assert 'alto_observaciones = y_toolbar_actual - y_draft_actual - sep' in SOURCE
    assert 'width=ancho_derecho_actual, height=alto_observaciones' in SOURCE
    for marker in ('("producto", 0.45)', '("codigo", 0.11)', '("tipo", 0.12)',
                   '("armazon", 0.11)', '("cristal", 0.11)', '("subtotal", 0.10)'):
        assert marker in SOURCE
    assert 'stretch=False' in SOURCE
    assert 'orient="vertical", command=grilla_items.yview' in SOURCE