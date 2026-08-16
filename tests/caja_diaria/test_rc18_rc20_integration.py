"""BC-CAJA-RC18–RC20 INTEGRATION: ventana por defecto de candidatos.

La consulta puede terminar un dia y el lote armarse al siguiente. El default
cubre hoy y los dos dias previos sin cambiar el criterio canonico: sigue
siendo la fecha de creacion del pedido, no la de entrega.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.models import CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()


class VentanaPorDefectoTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = CashDayService(self.repository)
        self.tracking = TrackingService(self.repository)

    def tearDown(self):
        self.repository.close()

    def _pedido(self, envelope: str, creado_hace_dias: int, branch="Pilar"):
        """Crea un pedido y retrasa su created_at los dias indicados."""
        dia = self.repository.get_by_date_and_unit(HOY, branch)
        if dia is None:
            dia = self.service.open_day(business_date=HOY, unit=branch, opening_cash=0)
        self.service.add_entry(dia.id, CashEntry(
            description=f"Cliente {envelope}", envelope=envelope, saleswoman="Nidia",
            delivery_date=HOY + timedelta(days=7), cash=100_000,
            items=(SaleItem(description="Armazon", frame_price=100_000),),
        ))
        creado = datetime.combine(
            HOY - timedelta(days=creado_hace_dias), datetime.min.time(),
        ).replace(hour=11)
        with self.repository._connection() as connection:
            connection.execute(
                "UPDATE orders SET created_at = ? WHERE envelope = ?",
                (creado.isoformat(), envelope),
            )
            connection.commit()

    def test_el_rango_por_defecto_cubre_hoy_y_los_dos_dias_previos(self):
        desde, hasta = self.tracking.default_candidate_range()
        self.assertEqual(hasta, HOY)
        self.assertEqual(desde, HOY - timedelta(days=2))
        self.assertEqual((hasta - desde).days + 1, 3)

    def test_la_consulta_del_viernes_aparece_el_sabado_sin_tocar_el_selector(self):
        self._pedido("P-VIERNES", creado_hace_dias=1)
        candidatos = self.tracking.shipment_candidates()
        self.assertEqual([pedido.envelope for pedido in candidatos], ["P-VIERNES"])

    def test_incluye_hoy_y_el_limite_de_tres_dias(self):
        self._pedido("P-HOY", creado_hace_dias=0)
        self._pedido("P-AYER", creado_hace_dias=1)
        self._pedido("P-ANTEAYER", creado_hace_dias=2)
        candidatos = self.tracking.shipment_candidates()
        self.assertEqual(
            sorted(pedido.envelope for pedido in candidatos),
            ["P-ANTEAYER", "P-AYER", "P-HOY"],
        )

    def test_deja_fuera_lo_anterior_a_la_ventana(self):
        self._pedido("P-VIEJO", creado_hace_dias=3)
        self.assertEqual(self.tracking.shipment_candidates(), [])

    def test_un_rango_explicito_manda_sobre_el_default(self):
        self._pedido("P-VIEJO", creado_hace_dias=10)
        self.assertEqual(self.tracking.shipment_candidates(), [])
        elegido = self.tracking.shipment_candidates(
            consultation_date=HOY - timedelta(days=10),
            end_date=HOY - timedelta(days=10),
        )
        self.assertEqual([pedido.envelope for pedido in elegido], ["P-VIEJO"])

    def test_una_sola_fecha_explicita_sigue_siendo_un_unico_dia(self):
        self._pedido("P-HOY", creado_hace_dias=0)
        self._pedido("P-AYER", creado_hace_dias=1)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        self.assertEqual([pedido.envelope for pedido in candidatos], ["P-HOY"])

    def test_el_criterio_sigue_siendo_la_fecha_de_creacion_no_la_de_entrega(self):
        # La entrega cae fuera de la ventana por defecto y aun asi el pedido
        # aparece, porque lo que decide es cuando se cargo.
        self._pedido("P-HOY", creado_hace_dias=0)
        candidatos = self.tracking.shipment_candidates()
        self.assertEqual(len(candidatos), 1)
        self.assertGreater(candidatos[0].delivery_date, HOY + timedelta(days=2))

    def test_el_default_no_mezcla_otras_sucursales(self):
        self._pedido("P-PILAR", creado_hace_dias=1, branch="Pilar")
        self._pedido("P-PC", creado_hace_dias=1, branch="PC")
        candidatos = self.tracking.shipment_candidates()
        self.assertEqual([pedido.envelope for pedido in candidatos], ["P-PILAR"])

    def test_el_dialogo_precarga_la_ventana_por_defecto(self):
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn("default_candidate_range()", fuente)
        self.assertIn("desde_defecto.strftime", fuente)
        self.assertIn("hasta_defecto.strftime", fuente)


class VersionDelPaqueteTests(unittest.TestCase):
    """El pie mostraba una version cableada y quedaba desfasado tras instalar."""

    def _version_empaquetada(self) -> str:
        from pathlib import Path
        primera = Path("pilot/package_docs/VERSION.txt").read_text(
            encoding="utf-8"
        ).splitlines()[0].strip()
        return primera[len("BC Caja "):].strip()

    def test_el_pie_no_cablea_ninguna_version(self):
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn("BC Caja {version_aplicacion()}", fuente)
        pie = fuente[fuente.index("etiqueta_pie = ctk.CTkLabel"):]
        self.assertNotIn("1.0.0-rc.", pie[:400])

    def test_la_version_mostrada_coincide_con_la_del_paquete(self):
        from CajaDiaria import version_aplicacion
        self.assertEqual(version_aplicacion(), self._version_empaquetada())

    def test_el_valor_de_respaldo_sigue_al_paquete(self):
        from CajaDiaria import VERSION_APLICACION
        self.assertEqual(VERSION_APLICACION, self._version_empaquetada())


if __name__ == "__main__":
    unittest.main()
