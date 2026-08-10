"""Characterization tests for TXT serialization, closing and cash count."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import CajaDiaria


def record(**overrides):
    value = {field: "" for field in CajaDiaria.CAMPOS}
    value.update({"fecha": "02-08-2026", "unidad": "PC", "origen": "manual"})
    value.update(overrides)
    return value


class LegacyCalculationTests(unittest.TestCase):
    def test_pipe_is_replaced_during_txt_serialization(self):
        source = record(descripcion="CLIENTE | OBSERVACIÓN", total=100000)
        restored = CajaDiaria.linea_a_registro(CajaDiaria.registro_a_linea(source))
        self.assertEqual(restored["descripcion"], "CLIENTE / OBSERVACIÓN")
        self.assertEqual(restored["total"], "100000")

    def test_closing_formula_uses_opening_cash_cash_sales_and_expenses(self):
        rows = [
            record(descripcion="CAJA INICIAL", efectivo=500000),
            record(descripcion="VENTA 1", total=600000, efectivo=400000, tarjeta_cheque=200000),
            record(descripcion="VENTA 2", total=300000, efectivo=100000, tarjeta_cheque=200000),
            record(descripcion="GASTO", gastos=50000),
        ]
        with patch.object(CajaDiaria, "leer_datos", return_value=[CajaDiaria.registro_a_linea(r) for r in rows]):
            closing = CajaDiaria.calcular_cierre("02-08-2026", "PC")
        self.assertEqual(closing, {
            "caja_inicial": 500000,
            "total": 900000,
            "efectivo_ventas": 500000,
            "tarjeta_cheque": 400000,
            "gastos": 50000,
            "efectivo_esperado": 950000,
            "cantidad_registros": 3,
        })

    def test_cash_count_classifies_ok_surplus_and_shortage(self):
        expected = 150000
        with patch.object(CajaDiaria, "calcular_cierre", return_value={"efectivo_esperado": expected}), \
             patch.object(CajaDiaria, "leer_datos", return_value=[]), \
             patch.object(CajaDiaria, "guardar_datos"):
            ok = CajaDiaria.registrar_arqueo("02-08-2026", "PC", {100000: 1, 50000: 1})
            surplus = CajaDiaria.registrar_arqueo("02-08-2026", "PC", {100000: 2})
            shortage = CajaDiaria.registrar_arqueo("02-08-2026", "PC", {100000: 1})
        self.assertEqual(ok["estado"], "OK")
        self.assertEqual(surplus["estado"], "SOBRA")
        self.assertEqual(shortage["estado"], "FALTA")

    def test_deleting_a_day_is_the_only_legacy_edit_like_operation(self):
        rows = [record(descripcion="A"), record(fecha="03-08-2026", descripcion="B")]
        stored = [CajaDiaria.registro_a_linea(r) for r in rows]
        with patch.object(CajaDiaria, "leer_datos", return_value=stored), \
             patch.object(CajaDiaria, "guardar_datos") as save:
            removed = CajaDiaria.eliminar_dia("02-08-2026", "PC")
        self.assertEqual(removed, 1)
        self.assertEqual(len(save.call_args.args[1]), 1)


if __name__ == "__main__":
    unittest.main()
