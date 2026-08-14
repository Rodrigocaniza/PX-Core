import sqlite3
import tempfile
from pathlib import Path

import pytest

from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import SaleItem


def item(**overrides):
    return SaleItem(
        description="Lente completo", frame_price=300_000, lens_price=200_000,
        **overrides,
    )


def test_independent_discount_boundaries_and_empty_values():
    assert item(frame_discount_percent=10, lens_discount_percent=5).frame_final_price == 270_000
    assert item(frame_discount_percent=10, lens_discount_percent=5).lens_final_price == 190_000
    assert item(frame_discount_percent=10, lens_discount_percent=5).subtotal == 460_000
    assert item(frame_discount_percent="", lens_discount_percent=0).subtotal == 500_000
    assert item(frame_discount_percent=100).subtotal == 200_000
    assert item(lens_discount_percent=100).subtotal == 300_000
    for invalid in (-1, 101, "x", "5.5"):
        with pytest.raises(InvalidCashDayError):
            item(frame_discount_percent=invalid)


def test_no_cost_is_per_item_and_distinct_from_full_discount():
    free = item(frame_discount_percent=10, lens_discount_percent=5, no_cost=True)
    discounted = item(frame_discount_percent=100, lens_discount_percent=100)
    regular = item()
    assert free.reference_subtotal == 500_000
    assert (free.frame_final_price, free.lens_final_price, free.subtotal) == (270_000, 190_000, 0)
    assert discounted.subtotal == 0 and not discounted.no_cost
    assert regular.subtotal == 500_000
    assert sum(x.subtotal for x in (free, regular)) == 500_000


def test_no_cost_only_sale_persists_with_zero_total(tmp_path):
    controller = build_cash_day_controller(tmp_path / "free-only.sqlite3")
    controller.open_or_load_day("15-08-2026", "PC", "0")
    values = {
        "fecha": "15-08-2026", "unidad": "PC", "caja_inicial": "0",
        "descripcion": "Cliente cortesía", "vendedora": "Ana",
        "total": "0", "efectivo": "0", "tarjeta_cheque": "0",
        "transferencia": "0", "monto_convenio": "0",
        "items": (item(no_cost=True),),
    }
    _, saved = controller.add_manual_entry(values)
    reopened = controller.load_day("15-08-2026", "PC").entries[0]
    assert saved.total == reopened.total == 0
    assert reopened.items[0].no_cost is True
    assert reopened.items[0].reference_subtotal == 500_000
    controller.service.repository.close()

def test_persistence_reopen_edit_audit_and_reporting(tmp_path):
    directory = tmp_path
    controller = build_cash_day_controller(Path(directory) / "rc6.sqlite3")
    controller.open_or_load_day("14-08-2026", "PC", "0")
    values = {
        "fecha": "14-08-2026", "unidad": "PC", "caja_inicial": "0",
        "descripcion": "Cliente RC6", "vendedora": "Ana", "total": "0", "efectivo": "0",
        "tarjeta_cheque": "0", "transferencia": "0", "monto_convenio": "0",
        "items": (
            item(frame_discount_percent=10, lens_discount_percent=5),
            item(no_cost=True),
        ),
    }
    _, saved = controller.add_manual_entry(values)
    reopened = controller.load_day("14-08-2026", "PC").entries[0]
    assert reopened.total == 460_000
    assert reopened.items[0].frame_discount_percent == 10
    assert reopened.items[0].lens_discount_percent == 5
    assert reopened.items[1].no_cost is True
    assert reopened.items[1].reference_subtotal == 500_000
    edited_items = (reopened.items[0], SaleItem(
        description="Lente completo", frame_price=300_000, lens_price=200_000,
        frame_discount_percent=5, lens_discount_percent=10, no_cost=False,
        id=reopened.items[1].id,
    ))
    values["items"] = edited_items
    values["total"] = "0"
    controller.update_manual_entry(saved.id, values, reason="Activa cobro", user="auditora")
    final = controller.load_day("14-08-2026", "PC").entries[0]
    assert final.total == 925_000
    revisions = controller.service.repository.list_entry_revisions(saved.id)
    create_items = revisions[0]["snapshot"]["items"]
    update_items = revisions[-1]["snapshot"]["items"]
    assert create_items[0]["frame_original_price"] == 300_000
    assert create_items[0]["frame_final_price"] == 270_000
    assert create_items[1]["no_cost"] is True
    assert update_items[1]["no_cost"] is False
    assert revisions[-1]["snapshot"]["item_changes"]["modified"]
    with sqlite3.connect(Path(directory) / "rc6.sqlite3") as connection:
        assert connection.execute("select count(*) from sale_items where no_cost=1").fetchone()[0] == 0
        assert connection.execute("select count(*) from schema_migrations where version='013'").fetchone()[0] == 1
    controller.service.repository.close()


def test_rc6_layout_and_clear_contract():
    source = Path("CajaDiaria.py").read_text(encoding="utf-8")
    assert '("descuento_armazon", 2), ("descuento_cristal", 5)' in source
    assert 'width=42' in source
    assert 'text="Artículo sin costo"' in source
    assert '"SIN COSTO" if item.no_cost' in source
    assert 'campos_manual["sin_costo"].deselect()' in source
    assert 'width=ancho_derecho_actual, height=alto_observaciones' in source
    assert 'zona_secundaria.configure(width=ancho_izquierdo_actual' in source
    assert 'filas_minimas = 5' in source
    assert 'anchor = "w" if clave == "producto" else "center"' in source
