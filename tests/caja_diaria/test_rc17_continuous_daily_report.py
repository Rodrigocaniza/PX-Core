from __future__ import annotations

import fitz

from modulos.caja_diaria.application.continuous_report import HEADERS, generate_continuous_daily_control
from tests.caja_diaria.test_rc16_daily_envelope_report import representative_close


def _text(path):
    with fitz.open(path) as document:
        return "\n".join(page.get_text() for page in document), document.page_count


def test_rc17_is_landscape_continuous_and_keeps_sales_together(tmp_path):
    day, count = representative_close(); before = repr(day)
    target = generate_continuous_daily_control(day, count, "closure-rc17", tmp_path / "rc17.pdf")
    assert repr(day) == before
    with fitz.open(target) as document:
        assert document.page_count >= 1
        assert all(page.rect.width > page.rect.height for page in document)
        assert all("BC Caja" in page.get_text() for page in document)
        assert all(f"Página {i} de {document.page_count}" in page.get_text() for i, page in enumerate(document, 1))
        first = document[0].get_text()
    assert "CAJA INICIAL" in first and "Cliente / Descripción" in first
    assert all(header.replace(" / ", "\n/ ") in first or header in first for header in HEADERS[:3])


def test_rc17_multi_item_does_not_duplicate_sale_totals_or_payments(tmp_path):
    day, count = representative_close()
    target = generate_continuous_daily_control(day, count, "closure-rc17", tmp_path / "rc17.pdf")
    content, _ = _text(target)
    assert content.count("Armazón azul") == 1
    assert content.count("Cristales orgánicos") == 1
    assert content.count("350.000") == 1
    assert "TOTALES" in content and "CIERRE" in content
    compact = " ".join(content.split())
    assert "G 50.000 / E 75.000" in compact


def test_rc17_excludes_clinical_notes_and_marks_operational_cases(tmp_path):
    day, count = representative_close()
    target = generate_continuous_daily_control(day, count, "closure-rc17", tmp_path / "rc17.pdf")
    content, _ = _text(target)
    assert "Detalle de recetas y observaciones" not in content
    assert "Línea clínica 001" not in content and "Línea clínica 090" not in content
    assert "OD:" not in content and "OI:" not in content
    assert "Observación y firma" not in content and "Control / firma" not in content
    assert content.index("Totales por vendedora") < content.index("CAJA INICIAL")
    assert "Cancelado" in content and "CONVENIO" not in content  # real convenio name is shown, not an invented label
    assert "ANULADA" in content and "GASTO" in content and "ENTREGA ADM." in content
    assert content.index("Cliente multi artículo") < content.index("Cliente con saldo") < content.index("Cliente receta extensa")
