"""BC-CAJA-RC20: persistencia del lote y elegibilidad de candidatos."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, CashDay, CashEntry, SaleItem
from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.domain.tracking import (
    Laboratory,
    PilarShipment,
    TrackedWork,
    TrackingStatus,
    shipment_progress,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = datetime.now(BUSINESS_TIMEZONE).date()


class ShipmentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = CashDayService(self.repository)

    def tearDown(self):
        self.repository.close()

    def _consulta_pilar(self, cantidad=15, branch="Pilar"):
        """Carga ventas reales en Caja: los pedidos nacen de `_ensure_order`."""
        dia = self.service.open_day(business_date=HOY, unit=branch, opening_cash=0)
        for numero in range(1, cantidad + 1):
            self.service.add_entry(dia.id, CashEntry(
                description=f"Cliente {numero:02d}", envelope=f"S-{numero:03d}",
                saleswoman="Nidia", delivery_date=HOY + timedelta(days=7),
                cash=150_000,
                items=(SaleItem(description="Armazon", frame_price=150_000),),
            ))
        return dia

    def test_la_migracion_017_se_aplica(self):
        with self.repository._connection() as connection:
            versiones = {
                fila[0] for fila in connection.execute(
                    "SELECT version FROM schema_migrations"
                )
            }
        self.assertIn("017", versiones)

    def test_encuentra_los_trabajos_de_pilar_por_fecha(self):
        self._consulta_pilar(15)
        candidatos = self.repository.list_shipment_candidates(
            branch="Pilar", start_date=HOY, end_date=HOY,
        )
        self.assertEqual(len(candidatos), 15)
        self.assertEqual(candidatos[0].envelope, "S-001")

    def test_no_mezcla_otras_sucursales(self):
        self._consulta_pilar(3, branch="Pilar")
        self._consulta_pilar(4, branch="PC")
        self.assertEqual(
            len(self.repository.list_shipment_candidates(
                branch="Pilar", start_date=HOY, end_date=HOY,
            )), 3,
        )

    def test_la_sucursal_no_distingue_mayusculas(self):
        self._consulta_pilar(2, branch="Pilar")
        self.assertEqual(
            len(self.repository.list_shipment_candidates(
                branch="PILAR", start_date=HOY, end_date=HOY,
            )), 2,
        )

    def test_fuera_del_rango_no_hay_candidatos(self):
        self._consulta_pilar(3)
        self.assertEqual(
            len(self.repository.list_shipment_candidates(
                branch="Pilar",
                start_date=HOY - timedelta(days=10), end_date=HOY - timedelta(days=5),
            )), 0,
        )

    def test_un_trabajo_ya_enviado_deja_de_ser_candidato(self):
        self._consulta_pilar(5)
        candidatos = self.repository.list_shipment_candidates(
            branch="Pilar", start_date=HOY, end_date=HOY,
        )
        envio = self.repository.save_pilar_shipment(
            PilarShipment(shipped_on=HOY, operator="Nidia"),
        )
        for pedido in candidatos[:2]:
            self.repository.save_tracked_work(TrackedWork(
                envelope=pedido.envelope, customer_name=pedido.customer_name,
                order_id=pedido.id, shipment_id=envio.id, consultation_date=HOY,
                created_by="Nidia",
            ))
        restantes = self.repository.list_shipment_candidates(
            branch="Pilar", start_date=HOY, end_date=HOY,
        )
        self.assertEqual(len(restantes), 3)
        self.assertNotIn(
            candidatos[0].id, [pedido.id for pedido in restantes],
        )

    def test_persiste_el_envio_con_sus_datos_minimos(self):
        envio = self.repository.save_pilar_shipment(PilarShipment(
            shipped_on=HOY, operator="Nidia", consultation_date=HOY, note="Consulta viernes",
        ))
        recuperado = self.repository.get_pilar_shipment(envio.id)
        self.assertEqual(recuperado.operator, "Nidia")
        self.assertEqual(recuperado.origin_branch, "PILAR")
        self.assertEqual(recuperado.destination_branch, "ASUNCION")
        self.assertEqual(recuperado.shipped_on, HOY)
        self.assertEqual(recuperado.note, "Consulta viernes")

    def test_el_trabajo_conserva_su_enlace_al_lote_y_al_pedido(self):
        self._consulta_pilar(1)
        pedido = self.repository.list_shipment_candidates(
            branch="Pilar", start_date=HOY, end_date=HOY,
        )[0]
        envio = self.repository.save_pilar_shipment(
            PilarShipment(shipped_on=HOY, operator="Nidia"),
        )
        work = self.repository.save_tracked_work(TrackedWork(
            envelope=pedido.envelope, customer_name=pedido.customer_name,
            order_id=pedido.id, cash_entry_id=pedido.cash_entry_id,
            shipment_id=envio.id, consultation_date=HOY, created_by="Nidia",
        ))
        recuperado = self.repository.get_tracked_work(work.id)
        self.assertEqual(recuperado.shipment_id, envio.id)
        self.assertEqual(recuperado.order_id, pedido.id)
        self.assertEqual(recuperado.cash_entry_id, pedido.cash_entry_id)

    def test_la_condicion_del_lote_se_deriva_de_sus_trabajos(self):
        works = [
            TrackedWork(envelope=f"S-{numero}", customer_name=f"C{numero}")
            for numero in range(1, 4)
        ]
        self.assertEqual(shipment_progress(works)["estado"], "ENVIADO")
        works[0] = works[0].transition_to(TrackingStatus.RECEIVED_IN_ASUNCION)
        parcial = shipment_progress(works)
        self.assertEqual(parcial["estado"], "RECEPCION_PARCIAL")
        self.assertEqual(parcial["falta_recibir"], 2)
        works[1] = works[1].transition_to(TrackingStatus.RECEIVED_IN_ASUNCION)
        works[2] = works[2].transition_to(TrackingStatus.RECEIVED_IN_ASUNCION)
        self.assertEqual(shipment_progress(works)["estado"], "RECIBIDO_COMPLETO")
        self.assertEqual(shipment_progress([])["estado"], "VACIO")

    def test_el_envio_exige_operadora(self):
        from modulos.caja_diaria.domain.errors import InvalidCashDayError
        with self.assertRaises(InvalidCashDayError):
            PilarShipment(shipped_on=HOY, operator="  ")

    def test_detecta_si_un_laboratorio_ya_tiene_historial(self):
        lab = self.repository.save_laboratory(Laboratory(name="LAB A"))
        self.assertFalse(self.repository.laboratory_has_history(lab.id))
        work = TrackedWork(envelope="S-1", customer_name="C1")
        work = work.transition_to(TrackingStatus.RECEIVED_IN_ASUNCION)
        work = work.send_to_laboratory(lab.id, expected_date=HOY)
        self.repository.save_tracked_work(work)
        self.assertTrue(self.repository.laboratory_has_history(lab.id))


if __name__ == "__main__":
    unittest.main()
