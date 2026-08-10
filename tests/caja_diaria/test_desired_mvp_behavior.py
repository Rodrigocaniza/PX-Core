"""Executable MVP contract implemented by BC-CAJA-CORE-001."""

from __future__ import annotations

import importlib
import unittest


def load_future_domain():
    return importlib.import_module("modulos.caja_diaria.domain.models")


class DesiredMvpBehaviorTests(unittest.TestCase):
    def test_cash_day_has_open_and_closed_states(self):
        domain = load_future_domain()
        day = domain.CashDay.open(date="2026-08-02", unit="PC", opening_cash=500000)
        self.assertEqual(day.status.value, "OPEN")
        self.assertEqual(day.close().status.value, "CLOSED")

    def test_closed_day_rejects_new_entries(self):
        domain = load_future_domain()
        day = domain.CashDay.open(date="2026-08-02", unit="PC", opening_cash=0).close()
        with self.assertRaises(domain.CashDayClosedError):
            day.add_entry(domain.CashEntry(description="VENTA", total=100000, cash=100000))

    def test_invalid_money_is_rejected_instead_of_silently_becoming_zero(self):
        domain = load_future_domain()
        with self.assertRaises(domain.InvalidMoneyError):
            domain.CashEntry(description="VENTA", total="NO-ES-MONTO")

    def test_history_query_is_a_repository_contract(self):
        ports = importlib.import_module("modulos.caja_diaria.application.ports")
        self.assertTrue(hasattr(ports.CashDayRepository, "get_by_date_and_unit"))
        self.assertTrue(hasattr(ports.CashDayRepository, "list_between"))

    def test_carry_forward_requires_an_explicit_approved_policy(self):
        services = importlib.import_module("modulos.caja_diaria.application.services")
        self.assertTrue(hasattr(services, "CarryForwardPolicy"))


if __name__ == "__main__":
    unittest.main()
