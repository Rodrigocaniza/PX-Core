from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / "pilot" / "package_docs" / "PREPARAR-PRUEBA-PC-B.ps1"
RUN = ROOT / "pilot" / "package_docs" / "EJECUTAR-PRUEBA-PC-B.ps1"


def test_preparador_es_fail_closed_y_no_fabrica_identidad():
    text = PREPARE.read_text(encoding="utf-8")
    for required in (
        "ALLOW / OK",
        "BCX1_OK",
        "installation.json",
        "installation.secret",
        "license.bclic",
        "ABORT:",
        "MANIFEST-PC-B.json",
        "-journal",
        "copiedCheck",
    ):
        assert required in text
    for forbidden in (" enroller ", " enrolar ", "instalar-licencia", "proteger-datos"):
        assert forbidden not in f" {text.lower()} "


def test_ejecutor_exige_el_resultado_fisico_exacto():
    text = RUN.read_text(encoding="utf-8")
    assert "DENY / MAQUINA_DISTINTA" in text
    assert "denyCode -ne 2" in text
    assert "BCX1_OK" in text
    assert "Get-FileHash" in text


def test_build_incluye_los_dos_scripts():
    build = (ROOT / "pilot" / "build_pilot.ps1").read_text(encoding="utf-8")
    assert "PREPARAR-PRUEBA-PC-B.ps1" in build
    assert "EJECUTAR-PRUEBA-PC-B.ps1" in build
