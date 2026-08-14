from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "CajaDiaria.py"


def test_movements_grid_has_no_visible_pagination_controls():
    source = SOURCE.read_text(encoding="utf-8")
    assert "Mostrando 0 de 0 movimientos" not in source
    assert "pie_movimientos" not in source
    assert 'for pagina in (' not in source
    assert "scroll_vertical.grid" in source
    assert "scroll_horizontal.grid" in source


def test_all_daily_movements_are_ordered_and_rendered_in_safe_batches():
    source = SOURCE.read_text(encoding="utf-8")
    assert "sorted(cash_day.entries, key=lambda item: (item.created_at, item.id))" in source
    assert "TAMANO_LOTE_GRILLA = 250" in source
    assert "ventana.after_idle(lambda: insertar_lote(fin))" in source
