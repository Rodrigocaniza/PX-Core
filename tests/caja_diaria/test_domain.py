from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from modulos.caja_diaria.domain.errors import CashDayClosedError, InvalidCashCountError, InvalidMoneyError
from modulos.caja_diaria.domain.models import CashCountStatus, CashDay, CashEntry


class CashDayDomainTests(unittest.TestCase):
    def test_confirmed_legacy_totals_are_preserved(self):
        day = CashDay.open(date="02-08-2026", unit="pc", opening_cash=500000)
        day.add_entry(CashEntry(description="EFECTIVO", total=500000, cash=500000))
        day.add_entry(CashEntry(description="TARJETA", total=600000, card_check=600000, balance="cancelado"))
        day.add_entry(CashEntry(
            description="MIXTO", total=400000, cash=150000, card_check=150000,
            orders="ORD-10", installments="2x50000", balance="50000",
        ))
        day.add_entry(CashEntry(description="GASTO", expenses=30000))

        totals = day.totals()
        self.assertEqual(day.business_date, date(2026, 8, 2))
        self.assertEqual(day.unit, "PC")
        self.assertEqual(totals.total, 1500000)
        self.assertEqual(totals.cash, 650000)
        self.assertEqual(totals.card_check, 750000)
        self.assertEqual(totals.expenses, 30000)
        self.assertEqual(totals.expected_cash, 1120000)
        self.assertEqual(totals.entry_count, 4)

    def test_optional_money_is_distinct_from_zero_and_text_is_preserved(self):
        entry = CashEntry(description="CLIENTE", balance="cancelado", orders="ORD-1", installments="3 cuotas")
        self.assertIsNone(entry.total)
        self.assertIsNone(entry.cash)
        self.assertEqual(entry.balance, "cancelado")
        self.assertEqual(entry.orders, "ORD-1")
        self.assertEqual(entry.installments, "3 cuotas")

    def test_negative_and_float_money_are_rejected(self):
        for value in (-1, 10.5, True, "abc"):
            with self.subTest(value=value), self.assertRaises(InvalidMoneyError):
                CashEntry(description="INVÁLIDA", total=value)

    def test_update_and_logical_void_are_allowed_only_while_open(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=0)
        original = day.add_entry(CashEntry(description="ORIGINAL", total=100))
        updated = replace(original, description="ACTUALIZADA", updated_at=original.updated_at)
        day.update_entry(updated)
        self.assertEqual(day.entries[0].description, "ACTUALIZADA")
        day.void_entry(original.id, "Carga duplicada")
        self.assertEqual(len(day.entries), 1)
        self.assertEqual(day.entries[0].status.value, "VOIDED")
        self.assertEqual(day.totals().entry_count, 0)
        day.close()
        with self.assertRaises(CashDayClosedError):
            day.add_entry(CashEntry(description="TARDE"))

    def test_close_freezes_a_snapshot(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=200000)
        day.add_entry(CashEntry(description="VENTA", total=100000, cash=100000))
        day.close()
        self.assertEqual(day.closing_totals, day.totals())
        self.assertEqual(day.closing_totals.expected_cash, 300000)

    def test_expenses_reduce_only_expected_cash_and_survive_close(self):
        day = CashDay.open(date="2026-08-03", unit="PC", opening_cash=500000)
        day.add_entry(CashEntry(
            description="VENTA MIXTA", total=700000, cash=300000, card_check=400000
        ))
        day.add_entry(CashEntry(description="GASTO", expenses=50000))

        totals = day.totals()
        self.assertEqual(totals.expected_cash, 500000 + 300000 - 50000)
        self.assertEqual(totals.card_check, 400000)
        day.close()
        self.assertEqual(day.closing_totals.expected_cash, 750000)
        self.assertEqual(day.closing_totals.card_check, 400000)

    def test_cash_count_reports_shortage_and_surplus_without_rejecting_them(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=1500000)
        conforming = day.count_cash({100000: 15})
        shortage = day.count_cash({100000: 14, 50000: 1})
        surplus = day.count_cash({100000: 15, 50000: 1})
        self.assertEqual((conforming.counted_total, conforming.difference), (1500000, 0))
        self.assertEqual((shortage.counted_total, shortage.difference), (1450000, -50000))
        self.assertEqual((surplus.counted_total, surplus.difference), (1550000, 50000))
        self.assertEqual(shortage.status, CashCountStatus.SHORTAGE)
        self.assertEqual(surplus.status, CashCountStatus.SURPLUS)
    def test_cash_count_rejects_negative_or_unknown_denominations(self):
        day = CashDay.open(date="2026-08-02", unit="PC", opening_cash=100000)
        with self.assertRaises(InvalidCashCountError):
            day.count_cash({100000: -1})
        with self.assertRaises(InvalidCashCountError):
            day.count_cash({25000: 1})
        count = day.count_cash({100000: 1})
        self.assertEqual(count.status, CashCountStatus.OK)


if __name__ == "__main__":
    unittest.main()
