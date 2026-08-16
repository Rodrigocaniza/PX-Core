"""BC-CAJA-RC20: alta de lote desde Pilar y ABM de laboratorios."""

from __future__ import annotations

import socket
import unittest
from datetime import date, timedelta

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import CashEntry, SaleItem
from modulos.caja_diaria.domain.tracking import TrackingStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()


class RC20Base(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = CashDayService(self.repository)
        self.tracking = TrackingService(self.repository)

    def tearDown(self):
        self.repository.close()

    def _consulta_pilar(self, cantidad=15, branch="Pilar"):
        dia = self.service.open_day(business_date=HOY, unit=branch, opening_cash=0)
        for numero in range(1, cantidad + 1):
            self.service.add_entry(dia.id, CashEntry(
                description=f"Cliente {numero:02d}", envelope=f"S-{numero:03d}",
                saleswoman="Nidia", delivery_date=HOY + timedelta(days=7),
                cash=150_000,
                items=(SaleItem(description="Armazon", frame_price=150_000),),
            ))
        return dia


class AltaDeLoteTests(RC20Base):
    def test_encuentra_los_trabajos_de_la_consulta_de_pilar(self):
        self._consulta_pilar(15)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        self.assertEqual(len(candidatos), 15)
        # CashDay normaliza la unidad a mayusculas y el pedido la hereda; por
        # eso la busqueda por sucursal es case-insensitive.
        self.assertTrue(all(pedido.branch == "PILAR" for pedido in candidatos))

    def test_seleccionar_todos_crea_el_lote_completo(self):
        self._consulta_pilar(15)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        resultado = self.tracking.create_pilar_shipment(
            [pedido.id for pedido in candidatos], operator="Nidia", consultation_date=HOY,
        )
        self.assertEqual(resultado["count"], 15)
        self.assertTrue(all(
            work.status is TrackingStatus.SENT_FROM_PILAR for work in resultado["works"]
        ))

    def test_seleccion_parcial_crea_solo_lo_elegido(self):
        self._consulta_pilar(15)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        elegidos = [candidatos[0].id, candidatos[3].id, candidatos[9].id]
        resultado = self.tracking.create_pilar_shipment(
            elegidos, operator="Nidia", consultation_date=HOY,
        )
        self.assertEqual(resultado["count"], 3)
        self.assertEqual(
            sorted(work.envelope for work in resultado["works"]),
            ["S-001", "S-004", "S-010"],
        )
        self.assertEqual(len(self.tracking.shipment_candidates(consultation_date=HOY)), 12)

    def test_el_lote_registra_origen_destino_operadora_y_cantidad(self):
        self._consulta_pilar(4)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        resultado = self.tracking.create_pilar_shipment(
            [pedido.id for pedido in candidatos], operator="Nidia",
            consultation_date=HOY, note="Consulta del viernes",
        )
        envio = resultado["shipment"]
        self.assertEqual(envio.origin_branch, "PILAR")
        self.assertEqual(envio.destination_branch, "ASUNCION")
        self.assertEqual(envio.operator, "Nidia")
        self.assertEqual(envio.note, "Consulta del viernes")
        detalle = self.tracking.shipment_detail(envio.id)
        self.assertEqual(detalle["enviados"], 4)
        self.assertEqual(detalle["estado"], "ENVIADO")

    def test_no_permite_enviar_dos_veces_el_mismo_trabajo(self):
        self._consulta_pilar(3)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        ids = [pedido.id for pedido in candidatos]
        self.tracking.create_pilar_shipment(ids[:2], operator="Nidia", consultation_date=HOY)
        with self.assertRaises(InvalidCashDayError) as error:
            self.tracking.create_pilar_shipment(ids, operator="Nidia", consultation_date=HOY)
        self.assertIn("ya salieron en un envío anterior", str(error.exception))
        # El intento fallido no debe dejar un lote a medias.
        self.assertEqual(len(self.tracking.list_shipments()), 1)

    def test_rechaza_un_envio_vacio(self):
        with self.assertRaises(InvalidCashDayError):
            self.tracking.create_pilar_shipment([], operator="Nidia")

    def test_conserva_la_relacion_con_orders_y_con_la_venta(self):
        self._consulta_pilar(1)
        pedido = self.tracking.shipment_candidates(consultation_date=HOY)[0]
        resultado = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia", consultation_date=HOY,
        )
        work = resultado["works"][0]
        self.assertEqual(work.order_id, pedido.id)
        self.assertEqual(work.cash_entry_id, pedido.cash_entry_id)
        self.assertEqual(work.envelope, pedido.envelope)
        self.assertEqual(work.customer_name, pedido.customer_name)

    def test_no_crea_otra_fuente_de_verdad_del_cliente(self):
        """El seguimiento no copia telefono ni documento: eso vive en orders."""
        self._consulta_pilar(1)
        pedido = self.tracking.shipment_candidates(consultation_date=HOY)[0]
        work = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia", consultation_date=HOY,
        )["works"][0]
        self.assertFalse(hasattr(work, "customer_phone"))
        self.assertFalse(hasattr(work, "customer_document"))


class RecepcionTests(RC20Base):
    def _lote(self, cantidad=15):
        self._consulta_pilar(cantidad)
        candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
        return self.tracking.create_pilar_shipment(
            [pedido.id for pedido in candidatos], operator="Nidia", consultation_date=HOY,
        )

    def test_la_recepcion_uno_por_uno_de_rc19_sigue_funcionando(self):
        lote = self._lote(15)
        for work in lote["works"][:14]:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        detalle = self.tracking.shipment_detail(lote["shipment"].id)
        self.assertEqual(detalle["enviados"], 15)
        self.assertEqual(detalle["recibidos"], 14)
        self.assertEqual(detalle["falta_recibir"], 1)
        self.assertEqual(detalle["estado"], "RECEPCION_PARCIAL")

    def test_al_recibir_todo_el_lote_queda_completo(self):
        lote = self._lote(3)
        for work in lote["works"]:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.assertEqual(
            self.tracking.shipment_detail(lote["shipment"].id)["estado"],
            "RECIBIDO_COMPLETO",
        )

    def test_cada_trabajo_sigue_siendo_trazable_individualmente(self):
        lote = self._lote(3)
        work = lote["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        individual = self.tracking.list_works()
        recibido = next(item for item in individual if item.id == work.id)
        self.assertEqual(len(recibido.transitions), 1)
        self.assertEqual(recibido.transitions[0].responsible, "Ana")
        self.assertEqual(recibido.shipment_id, lote["shipment"].id)

    def test_el_tablero_de_rc19_muestra_los_trabajos_del_lote(self):
        self._lote(5)
        tablero = self.tracking.board()
        self.assertEqual(len(tablero["rows"]), 5)
        self.assertEqual(tablero["reception"]["falta_recibir"], 5)


class AbmLaboratoriosTests(RC20Base):
    def test_alta_de_laboratorio(self):
        lab = self.tracking.save_laboratory(
            name="LAB NUEVO", phone_line="021 111", whatsapp="0981 111",
        )
        self.assertEqual(lab.name, "LAB NUEVO")
        self.assertTrue(lab.active)
        self.assertEqual(len(self.tracking.list_laboratories()), 1)

    def test_edicion_de_nombre(self):
        lab = self.tracking.save_laboratory(name="LAB VIEJO NOMBRE")
        editado = self.tracking.update_laboratory(lab.id, name="LAB NOMBRE CORREGIDO")
        self.assertEqual(editado.name, "LAB NOMBRE CORREGIDO")
        self.assertEqual(self.tracking.list_laboratories()[0].name, "LAB NOMBRE CORREGIDO")

    def test_edicion_de_linea_no_toca_el_whatsapp(self):
        lab = self.tracking.save_laboratory(
            name="LAB A", phone_line="021 111", whatsapp="0981 111",
        )
        editado = self.tracking.update_laboratory(lab.id, phone_line="021 999")
        self.assertEqual(editado.phone_line, "021 999")
        self.assertEqual(editado.whatsapp, "0981 111")

    def test_edicion_de_whatsapp_no_toca_la_linea(self):
        lab = self.tracking.save_laboratory(
            name="LAB A", phone_line="021 111", whatsapp="0981 111",
        )
        editado = self.tracking.update_laboratory(lab.id, whatsapp="0982 777")
        self.assertEqual(editado.whatsapp, "0982 777")
        self.assertEqual(editado.phone_line, "021 111")

    def test_linea_y_whatsapp_pueden_ser_numeros_distintos(self):
        lab = self.tracking.save_laboratory(
            name="LAB A", phone_line="021 111 222", whatsapp="0981 333 444",
        )
        self.assertNotEqual(lab.phone_line, lab.whatsapp)

    def test_desactivar_un_laboratorio(self):
        lab = self.tracking.save_laboratory(name="LAB A")
        desactivado = self.tracking.set_laboratory_active(lab.id, False)
        self.assertFalse(desactivado.active)
        self.assertEqual(len(self.tracking.list_laboratories()), 1)

    def test_el_historico_conserva_el_laboratorio_inactivo(self):
        lab = self.tracking.save_laboratory(name="LAB A", phone_line="021 111")
        self._consulta_pilar(1)
        pedido = self.tracking.shipment_candidates(consultation_date=HOY)[0]
        work = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia", consultation_date=HOY,
        )["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, lab.id, expected_date=HOY, responsible="Ana",
        )
        self.tracking.set_laboratory_active(lab.id, False)

        fila = self.tracking.board()["rows"][0]
        self.assertEqual(fila.laboratory_name, "LAB A")
        self.assertEqual(fila.phone_line, "021 111")
        self.assertTrue(self.tracking.laboratory_has_history(lab.id))

    def test_un_laboratorio_inactivo_no_es_elegible_para_un_envio_nuevo(self):
        activo = self.tracking.save_laboratory(name="LAB ACTIVO")
        inactivo = self.tracking.save_laboratory(name="LAB INACTIVO", active=False)
        elegibles = [lab.id for lab in self.tracking.selectable_laboratories()]
        self.assertIn(activo.id, elegibles)
        self.assertNotIn(inactivo.id, elegibles)

    def test_reactivar_devuelve_el_laboratorio_a_las_opciones(self):
        lab = self.tracking.save_laboratory(name="LAB A", active=False)
        self.tracking.set_laboratory_active(lab.id, True)
        self.assertIn(
            lab.id, [item.id for item in self.tracking.selectable_laboratories()],
        )

    def test_editar_un_laboratorio_inexistente_falla(self):
        with self.assertRaises(InvalidCashDayError):
            self.tracking.update_laboratory("no-existe", name="X")


class LocalFirstTests(RC20Base):
    def test_alta_de_lote_y_abm_no_requieren_red(self):
        original = socket.socket

        def prohibido(*args, **kwargs):
            raise AssertionError("RC20 no debe requerir red")

        self._consulta_pilar(5)
        socket.socket = prohibido
        try:
            lab = self.tracking.save_laboratory(name="LAB SIN RED", phone_line="021 1")
            self.tracking.update_laboratory(lab.id, whatsapp="0981 1")
            self.tracking.set_laboratory_active(lab.id, False)
            candidatos = self.tracking.shipment_candidates(consultation_date=HOY)
            lote = self.tracking.create_pilar_shipment(
                [pedido.id for pedido in candidatos], operator="Nidia",
                consultation_date=HOY,
            )
            self.tracking.receive_in_asuncion(lote["works"][0].id, responsible="Ana")
            self.assertEqual(
                self.tracking.shipment_detail(lote["shipment"].id)["falta_recibir"], 4,
            )
        finally:
            socket.socket = original


if __name__ == "__main__":
    unittest.main()
