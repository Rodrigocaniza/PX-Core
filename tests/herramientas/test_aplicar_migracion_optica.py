"""Aplicar una migración es aplicar una, no la cola entera.

Las herramientas de la 029 y la 030 se escribieron cuando su migración era la
punta de la cola y aplicaban construyendo `SQLiteCashDayRepository`, que corre
todas las pendientes. Corridas más tarde, sobre una base en 028, llevaban el
archivo hasta el final sin decirlo: eso es el F2 de
`BC-OPTICA-DESPLIEGUE-PRODUCTIVO-029-032`. Estas pruebas fijan lo contrario.
"""

from pathlib import Path

import pytest

from tests.migration_chain import MIGRATIONS_DIR, versiones_esperadas
from tools.aplicar_migracion_optica import aplicar_una


def base_en(tmp_path: Path, hasta: str) -> Path:
    """Una base construida hasta `hasta` inclusive, y ni una migración más."""
    import sqlite3
    ruta = tmp_path / "bc_caja.sqlite3"
    con = sqlite3.connect(ruta)
    for archivo in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = archivo.name.split("_", 1)[0]
        if version > hasta:
            break
        con.executescript(archivo.read_text(encoding="utf-8"))
        # Las primeras migraciones son anteriores a la convencion de
        # registrarse a si mismas: quien las corre las anota. El repositorio
        # hace exactamente esto, y por eso la base productiva en 028 tiene sus
        # 28 filas. Si el fixture no lo hiciera, estaria probando contra una
        # base que no existe en ningun lado.
        con.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at)"
            " VALUES (?, datetime('now'))", (version,))
    con.commit()
    con.close()
    return ruta


def aplicadas(ruta: Path) -> list[str]:
    import sqlite3
    con = sqlite3.connect(ruta)
    try:
        return [f[0] for f in con.execute(
            "SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        con.close()


def tablas(ruta: Path) -> set[str]:
    import sqlite3
    con = sqlite3.connect(ruta)
    try:
        return {f[0] for f in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_aplica_exactamente_la_pedida_y_no_la_que_sigue(tmp_path):
    base = base_en(tmp_path, "028")
    assert aplicadas(base)[-1] == "028"

    aplicar_una(base, "029")

    assert aplicadas(base)[-1] == "029"
    assert "factufacil_loads" in tablas(base)
    # La 031 crea service_jobs. Si apareció, la herramienta siguió sola.
    assert "service_jobs" not in tablas(base)


def test_repetirla_no_reaplica_ni_sigue_con_la_cola(tmp_path):
    base = base_en(tmp_path, "029")
    with pytest.raises(RuntimeError, match="ya esta aplicada"):
        aplicar_una(base, "029")
    assert aplicadas(base)[-1] == "029"


def test_saltearse_una_previa_no_pasa_en_silencio(tmp_path):
    base = base_en(tmp_path, "029")
    with pytest.raises(RuntimeError, match="faltan migraciones previas"):
        aplicar_una(base, "032")
    assert aplicadas(base)[-1] == "029"
    assert "service_commission_policy_versions" not in tablas(base)


def test_la_cadena_completa_se_puede_aplicar_de_a_una(tmp_path):
    base = base_en(tmp_path, "028")
    for version in [v for v in versiones_esperadas() if v > "028"]:
        aplicar_una(base, version)
    assert aplicadas(base) == versiones_esperadas()
