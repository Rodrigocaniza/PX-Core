from pathlib import Path

from modulos.caja_diaria.bootstrap import build_cash_day_controller


SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_arqueo_is_available_from_cash_day_and_not_operator_navigation():
    assert 'text="Arqueo"' in SOURCE
    assert "def abrir_modal_arqueo" in SOURCE
    assert 'if nombre == "Arqueo":' in SOURCE
    assert 'modal.grab_set()' in SOURCE
    assert 'campos_manual["fecha"]' in SOURCE
    assert 'campos_manual["unidad"]' in SOURCE


def test_outflow_has_no_visible_responsible_or_windows_profile_fallback():
    outflow_start = SOURCE.index('text="SALIDA DE CAJA"')
    outflow_end = SOURCE.index('# El draft es una zona propia', outflow_start)
    outflow_ui = SOURCE[outflow_start:outflow_end]
    assert "salida_usuario" not in SOURCE
    assert "Responsable" not in outflow_ui
    assert 'os.environ.get("USERNAME")' not in outflow_ui


def test_cash_count_reopens_without_duplicates_and_outflow_uses_cash_identity(tmp_path):
    controller = build_cash_day_controller(tmp_path / "cash.sqlite3")
    day = controller.service.open_day(
        business_date="14-08-2026", unit="PC", opening_cash=100_000,
        opened_by="Operadora Central",
    )
    first = controller.record_cash_count("14-08-2026", "PC", {100_000: 1})
    reopened = controller.record_cash_count("14-08-2026", "PC", {50_000: 1})
    assert reopened.id == first.id
    assert controller.latest_cash_count(day.id).quantities == {100_000: 1}

    _, outflow = controller.add_outflow(
        "14-08-2026", "PC", "GASTO", "Insumos", 10_000,
        performed_by="Striker",
    )
    assert outflow.performed_by == "Operadora Central"
    controller.service.repository.close()
