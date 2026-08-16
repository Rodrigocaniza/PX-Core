"""BC-CAJA-RC22: la caja pertenece a una sucursal; la cajera no la define.

Modelo canonico: Sucursal -> Caja -> sesion/cajera. La responsabilidad de la
proxima accion se deriva de la etapa del trabajo, nunca de quien lo cargo.
"""

from __future__ import annotations

import sqlite3
import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, CashEntry, Order, OrderOrigin
from modulos.caja_diaria.domain.tracking import (
    RESPONSABLE_POR_ETAPA,
    TrackingStatus,
    sucursal_responsable,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
AYER = HOY - timedelta(days=1)


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class ResponsabilidadTests(unittest.TestCase):
    def test_cada_etapa_tiene_su_local_responsable(self):
        esperado = {
            TrackingStatus.SENT_FROM_PILAR: "ASUNCION",
            TrackingStatus.RECEIVED_IN_ASUNCION: "ASUNCION",
            TrackingStatus.IN_LABORATORY: "ASUNCION",
            TrackingStatus.RECEIVED_FROM_LABORATORY: "ASUNCION",
            TrackingStatus.SENT_TO_PILAR: "PILAR",
            TrackingStatus.RECEIVED_IN_PILAR: None,
            TrackingStatus.CLOSED: None,
        }
        for estado, local in esperado.items():
            self.assertEqual(
                sucursal_responsable(estado, origin_branch="PILAR",
                                     processing_branch="ASUNCION"),
                local, estado.value)

    def test_la_tabla_de_responsabilidad_cubre_todas_las_etapas(self):
        self.assertEqual(set(RESPONSABLE_POR_ETAPA), set(TrackingStatus))

    def test_la_responsabilidad_sigue_a_las_sucursales_reales_no_a_nombres_fijos(self):
        self.assertEqual(
            sucursal_responsable(TrackingStatus.SENT_TO_PILAR,
                                 origin_branch="encarnacion", processing_branch="ASUNCION"),
            "ENCARNACION")
        self.assertEqual(
            sucursal_responsable(TrackingStatus.IN_LABORATORY,
                                 origin_branch="ENCARNACION", processing_branch="ciudad del este"),
            "CIUDAD DEL ESTE")


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.tracking = TrackingService(self.repository)

    def tearDown(self):
        self.repository.close()

    def test_la_migracion_018_se_aplica(self):
        with self.repository._connection() as c:
            versiones = {r[0] for r in c.execute("SELECT version FROM schema_migrations")}
        self.assertIn("018", versiones)

    def test_una_caja_sin_asignar_no_inventa_sucursal(self):
        """El principio sigue siendo no adivinar.

        La 020 siembra PC, P2 y PILAR porque la operacion las declaro
        inequivocas, no porque se hayan deducido. Cualquier otra caja sigue sin
        sucursal hasta que alguien la asigne: inventarsela enrutaria trabajos
        al local errado.
        """
        self.assertIsNone(self.tracking.branch_of_register("CAJA-NUEVA"))

    def test_los_tres_vinculos_canonicos_vienen_sembrados(self):
        """RC25: la alerta principal necesita saber en que local esta la caja."""
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")
        self.assertEqual(self.tracking.branch_of_register("P2"), "PILAR")
        self.assertEqual(self.tracking.branch_of_register("PILAR"), "PILAR")

    def test_el_binding_persiste_y_es_unico_por_caja(self):
        self.tracking.bind_register_to_branch("PC", "ASUNCION", assigned_by="Admin")
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")
        # Reasignar no duplica: la caja tiene una sola sucursal.
        self.tracking.bind_register_to_branch(
            "PC", "PILAR", assigned_by="Admin", reason="mudanza")
        self.assertEqual(self.tracking.branch_of_register("PC"), "PILAR")
        self.assertEqual(
            len([b for b in self.tracking.list_register_branches()
                 if b["cash_register"] == "PC"]), 1)

    def test_el_binding_sobrevive_a_reabrir_la_aplicacion(self):
        import tempfile
        from pathlib import Path
        base = Path(tempfile.mkdtemp()) / "bc.sqlite3"
        r1 = SQLiteCashDayRepository(base)
        TrackingService(r1).bind_register_to_branch("PC", "ASUNCION", assigned_by="Admin")
        r1.close()
        r2 = SQLiteCashDayRepository(base)          # "reinicio" de la aplicacion
        self.assertEqual(TrackingService(r2).branch_of_register("PC"), "ASUNCION")
        r2.close()

    def test_el_cambio_de_sucursal_queda_auditado(self):
        self.tracking.bind_register_to_branch(
            "PC", "ASUNCION", assigned_by="Rodrigo", reason="alta inicial")
        with self.repository._connection() as c:
            filas = c.execute(
                "SELECT actor, action, target_id, details_json FROM admin_audit_log"
                " WHERE action='CASH_REGISTER_BRANCH_BIND'").fetchall()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["actor"], "Rodrigo")
        self.assertIn("ASUNCION", filas[0]["details_json"])

    def test_la_asignacion_exige_responsable(self):
        with self.assertRaises(InvalidCashDayError):
            self.tracking.bind_register_to_branch("PC", "ASUNCION", assigned_by="  ")

    def test_cambiar_de_cajera_no_cambia_la_sucursal(self):
        self.tracking.bind_register_to_branch("PC", "ASUNCION", assigned_by="Admin")
        servicio = CashDayService(self.repository)
        servicio.open_day(business_date=HOY, unit="PC", opening_cash=0, opened_by="Ana")
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")
        servicio.open_day(business_date=HOY + timedelta(days=1), unit="PC",
                          opening_cash=0, opened_by="Carla")
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")
        self.assertEqual(
            len([b for b in self.tracking.list_register_branches()
                 if b["cash_register"] == "PC"]), 1)


class DosLocalesTests(unittest.TestCase):
    """El mismo circuito visto desde Pilar y desde Asuncion."""

    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.tracking = TrackingService(self.repository)
        self.tracking.bind_register_to_branch("PC", "ASUNCION", assigned_by="Admin")
        self.tracking.bind_register_to_branch("PILAR", "PILAR", assigned_by="Admin")
        self.lab = self.tracking.save_laboratory(
            name="LAB PRUEBA", phone_line="021 555 101", whatsapp="0981 555 201")
        pedidos = []
        for i in range(1, 16):
            pedido = Order(
                delivery_date=HOY + timedelta(days=7), branch="PILAR",
                customer_name=f"Cliente Prueba {i:02d}", saleswoman="Nidia (TEST)",
                envelope=f"TEST-P-{i:03d}", origin=OrderOrigin.WORKSHOP,
                observations="Cristal", cash_entry_id=None,
                created_at=datetime.combine(AYER, time(14, 0), tzinfo=BUSINESS_TIMEZONE))
            self.repository.save_order(pedido)
            pedidos.append(pedido)
        self.works = self.tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia (TEST)")["works"]

    def tearDown(self):
        self.repository.close()

    def _ver(self, sucursal, **kw):
        return self.tracking.board(responsible_branch=sucursal, **kw)["rows"]

    def _alertas(self, sucursal, **kw):
        return self.tracking.pending_actions_for_branch(sucursal, **kw)

    def test_1y2_pilar_creo_el_envio_y_ve_los_quince_enviados(self):
        todos = self.tracking.board()["rows"]
        self.assertEqual(len(todos), 15)
        self.assertTrue(all(f.physical_status == "ENVIADO DESDE PILAR" for f in todos))

    def test_3_asuncion_recibe_los_pendientes_de_recepcion(self):
        alertas = self._alertas("ASUNCION")
        claves = {a["clave"] for a in alertas["alertas"]}
        self.assertIn("por_recibir", claves)
        self.assertEqual(alertas["total"], 15)
        self.assertEqual(len(self._ver("ASUNCION")), 15)

    def test_4_pilar_no_muestra_la_alerta_operativa_de_asuncion(self):
        alertas = self._alertas("PILAR")
        self.assertEqual(alertas["alertas"], [])
        self.assertEqual(alertas["total"], 0)
        self.assertEqual(len(self._ver("PILAR")), 0)

    def test_5y6_asuncion_recibe_y_reparte_a_laboratorios(self):
        for work in self.works:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.assertIn("por_enviar_lab",
                      {a["clave"] for a in self._alertas("ASUNCION")["alertas"]})
        for work in self.works[:3]:
            self.tracking.send_to_laboratory(
                work.id, self.lab.id, expected_date=AYER, expected_time="15:00",
                responsible="Ana")
        self.assertEqual(len(self._ver("ASUNCION")), 15)
        self.assertEqual(len(self._ver("PILAR")), 0)

    def test_7_los_atrasados_son_de_asuncion_no_de_pilar(self):
        for work in self.works[:3]:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
            self.tracking.send_to_laboratory(
                work.id, self.lab.id, expected_date=AYER, expected_time="15:00",
                responsible="Ana")
        ahora = momento(HOY, "10:00")
        self.assertEqual(self._alertas("ASUNCION", now=ahora)["atrasados"], 3)
        self.assertEqual(self._alertas("PILAR", now=ahora)["atrasados"], 0)
        self.assertEqual(
            len(self._ver("ASUNCION", only_overdue=True, now=ahora)), 3)
        self.assertEqual(len(self._ver("PILAR", only_overdue=True, now=ahora)), 0)

    def _hasta_encomienda(self, work):
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY + timedelta(days=1), responsible="Ana")
        self.tracking.receive_from_laboratory(work.id, responsible="Ana")
        self.tracking.send_batch_to_pilar([work.id], responsible="Ana")

    def test_8y9_al_salir_la_encomienda_la_responsabilidad_pasa_a_pilar(self):
        work = self.works[0]
        self._hasta_encomienda(work)
        pilar = self._alertas("PILAR")
        self.assertIn("por_recibir_encomienda", {a["clave"] for a in pilar["alertas"]})
        self.assertEqual(len(self._ver("PILAR")), 1)
        # Asuncion ya no tiene ese trabajo entre sus pendientes.
        self.assertTrue(all(f.work.id != work.id for f in self._ver("ASUNCION")))

    def test_10_recibido_en_pilar_cierra_y_nadie_queda_responsable(self):
        work = self.works[0]
        self._hasta_encomienda(work)
        self.tracking.receive_in_pilar(work.id, responsible="Nidia")
        self.assertIsNone(
            self.repository.get_tracked_work(work.id).responsible_branch)
        self.assertEqual(len(self._ver("PILAR")), 0)
        self.assertEqual(len(self._ver("ASUNCION")), 14)
        self.assertEqual(self._alertas("PILAR")["total"], 0)

    def test_11_cambiar_cajera_no_altera_a_quien_le_toca(self):
        antes = [f.responsible_branch for f in self._ver("ASUNCION")]
        CashDayService(self.repository).open_day(
            business_date=HOY, unit="PC", opening_cash=0, opened_by="Otra Cajera")
        self.assertEqual([f.responsible_branch for f in self._ver("ASUNCION")], antes)
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")

    def test_el_trabajo_conserva_origen_y_local_responsable(self):
        work = self.repository.get_tracked_work(self.works[0].id)
        self.assertEqual(work.origin_branch, "PILAR")
        self.assertEqual(work.processing_branch, "ASUNCION")
        self.assertEqual(work.responsible_branch, "ASUNCION")

    def test_la_sucursal_no_se_infiere_de_la_vendedora(self):
        fuente = open("modulos/caja_diaria/application/tracking_service.py",
                      encoding="utf-8").read()
        bloque = fuente[fuente.index("def pending_actions_for_branch"):
                        fuente.index("# -- alta de lote desde Pilar")]
        for prohibido in ("saleswoman", "vendedora", "cajera", "opened_by"):
            self.assertNotIn(prohibido, bloque)


if __name__ == "__main__":
    unittest.main()
