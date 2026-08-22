from __future__ import annotations

import sqlite3
from argparse import Namespace

from modulos.seguridad.application.field_protection import PROTECTED_COLUMNS
from tools.bc_security import comando_verificar_bcx1, construir_parser


def _base(tmp_path, *, valor="bcx1:prueba"):
    ruta = tmp_path / "copia.sqlite3"
    with sqlite3.connect(ruta) as conexion:
        for tabla, columnas in PROTECTED_COLUMNS.items():
            definicion = ", ".join(f'"{columna}" TEXT' for columna in columnas)
            conexion.execute(f'CREATE TABLE "{tabla}" ({definicion})')
            nombres = ", ".join(f'"{columna}"' for columna in columnas)
            marcas = ", ".join("?" for _ in columnas)
            conexion.execute(
                f'INSERT INTO "{tabla}" ({nombres}) VALUES ({marcas})',
                [valor] * len(columnas),
            )
    return ruta


def test_checker_acepta_todos_los_campos_protegidos(tmp_path, capsys):
    base = _base(tmp_path)
    assert comando_verificar_bcx1(Namespace(base=str(base))) == 0
    salida = capsys.readouterr().out
    assert salida.startswith("BCX1_OK valores=19 en_claro=0 integrity_check=ok")


def test_checker_falla_si_un_solo_campo_esta_en_claro(tmp_path, capsys):
    base = _base(tmp_path)
    with sqlite3.connect(base) as conexion:
        conexion.execute("UPDATE orders SET customer_name = 'Paciente Visible'")
    assert comando_verificar_bcx1(Namespace(base=str(base))) == 4
    salida = capsys.readouterr().out
    assert "BCX1_FAIL" in salida
    assert "orders.customer_name:en_claro=1" in salida
    assert "Paciente Visible" not in salida


def test_checker_falla_si_no_hay_nada_comprobable(tmp_path, capsys):
    base = _base(tmp_path, valor="")
    assert comando_verificar_bcx1(Namespace(base=str(base))) == 4
    assert "valores_protegidos=0" in capsys.readouterr().out


def test_checker_parsea_base_antes_y_despues_del_subcomando():
    despues = construir_parser().parse_args(
        ["verificar-bcx1", "--base", "copia.sqlite3"]
    )
    antes = construir_parser().parse_args(
        ["--base", "copia.sqlite3", "verificar-bcx1"]
    )
    assert despues.base == antes.base == "copia.sqlite3"
