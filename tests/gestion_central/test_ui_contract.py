from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_viewsonic_24_inch_and_smaller_resolution_contract():
    source = (ROOT / "modulos" / "gestion_central" / "ui.py").read_text(encoding="utf-8")
    assert 'self.root.geometry("1600x900")' in source
    assert 'self.root.minsize(1180, 680)' in source
    assert "columns = 4 if width >= 1500 else 2" in source


def test_pilot_warning_is_permanently_visible():
    source = (ROOT / "modulos" / "gestion_central" / "ui.py").read_text(encoding="utf-8")
    assert "DATOS SINTÉTICOS" in source
    assert "NO PRODUCCIÓN" in source
