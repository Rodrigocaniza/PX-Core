"""BC-CAJA-RC22: el trabajo enviado tiene que quedar visible.

Regresion del fallo real detectado en la prueba manual: el dialogo buscaba
candidatos por rango pero el envio los revalidaba por un unico dia, de modo
que "Crear envio" fallaba con "ya no estan disponibles" y la pestaña quedaba
vacia sin que se hubiera creado nada.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.application.tracking_service import (
    SCOPE_ACTIVOS,
    SCOPE_COMPLETADOS,
    SCOPE_TODOS,
    TrackingService,
)
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin
from modulos.caja_diaria.domain.tracking import TrackingStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
AYER = HOY - timedelta(days=1)
FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class Base(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = CashDayService(self.repository)
        self.tracking = TrackingService(self.repository)
        self.lab = self.tracking.save_laboratory(
            name="LAB PRUEBA", phone_line="021 555 101", whatsapp="0981 555 201")

    def tearDown(self):
        self.repository.close()

    def _pedidos_de_pilar(self, cantidad=15, creado: date = AYER):
        """Pedidos sin venta asociada, igual que el escenario TEST real."""
        creados = []
        for i in range(1, cantidad + 1):
            pedido = Order(
                delivery_date=creado + timedelta(days=7), branch="PILAR",
                customer_name=f"Cliente Prueba {i:02d}", saleswoman="Nidia (TEST)",
                envelope=f"TEST-P-{i:03d}", origin=OrderOrigin.WORKSHOP,
                observations="Cristal", cash_entry_id=None,
                created_at=datetime.combine(creado, time(14, 0), tzinfo=BUSINESS_TIMEZONE),
            )
            self.repository.save_order(pedido)
            creados.append(pedido)
        return creados


class EnvioDesdeRangoTests(Base):
    def test_el_envio_funciona_con_la_ventana_por_defecto_de_tres_dias(self):
        """El caso exacto que fallaba: buscar por rango y enviar."""
        pedidos = self._pedidos_de_pilar(15, creado=AYER)
        desde, _hasta = self.tracking.default_candidate_range()
        candidatos = self.tracking.shipment_candidates()
        self.assertEqual(len(candidatos), 15)

        resultado = self.tracking.create_pilar_shipment(
            [p.id for p in candidatos], operator="Nidia",
            consultation_date=desde.strftime("%d-%m-%Y"),
        )
        self.assertEqual(resultado["count"], 15)

    def test_el_envio_no_depende_de_la_fecha_que_se_le_pase(self):
        pedidos = self._pedidos_de_pilar(3, creado=AYER)
        resultado = self.tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia",
        )
        self.assertEqual(resultado["count"], 3)
        # Sin fecha explicita se deduce del propio lote.
        self.assertEqual(resultado["shipment"].consultation_date, AYER)

    def test_sigue_rechazando_un_pedido_inexistente(self):
        with self.assertRaises(InvalidCashDayError):
            self.tracking.create_pilar_shipment(["no-existe"], operator="Nidia")

    def test_sigue_rechazando_reenviar_lo_ya_enviado(self):
        pedidos = self._pedidos_de_pilar(2)
        ids = [p.id for p in pedidos]
        self.tracking.create_pilar_shipment(ids, operator="Nidia")
        with self.assertRaises(InvalidCashDayError) as error:
            self.tracking.create_pilar_shipment(ids, operator="Nidia")
        self.assertIn("ya salieron", str(error.exception))

    def test_rechaza_pedidos_de_otra_sucursal(self):
        ajeno = Order(delivery_date=HOY + timedelta(days=3), branch="PC",
                      customer_name="Cliente real", saleswoman="Ana", envelope="9999")
        self.repository.save_order(ajeno)
        with self.assertRaises(InvalidCashDayError) as error:
            self.tracking.create_pilar_shipment([ajeno.id], operator="Nidia")
        self.assertIn("no son de", str(error.exception))


class VisibilidadTests(Base):
    def _lote(self, cantidad=15):
        pedidos = self._pedidos_de_pilar(cantidad)
        return self.tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia")["works"]

    def test_apenas_creado_el_envio_los_trabajos_estan_a_la_vista(self):
        self._lote(15)
        tablero = self.tracking.board()
        self.assertEqual(len(tablero["rows"]), 15)
        self.assertTrue(all(
            f.physical_status == "ENVIADO DESDE PILAR" for f in tablero["rows"]))

    def test_el_trabajo_permanece_visible_en_todo_el_circuito(self):
        work = self._lote(1)[0]
        visibles = [len(self.tracking.board()["rows"])]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        visibles.append(len(self.tracking.board()["rows"]))
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY + timedelta(days=1), responsible="Ana")
        visibles.append(len(self.tracking.board()["rows"]))
        self.tracking.receive_from_laboratory(work.id, responsible="Ana")
        visibles.append(len(self.tracking.board()["rows"]))
        self.tracking.send_batch_to_pilar([work.id], responsible="Ana")
        visibles.append(len(self.tracking.board()["rows"]))
        self.assertEqual(visibles, [1, 1, 1, 1, 1])

    def test_conserva_la_misma_identidad_en_todo_el_circuito(self):
        work = self._lote(1)[0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY, responsible="Ana")
        fila = self.tracking.board()["rows"][0]
        self.assertEqual(fila.work.id, work.id)
        self.assertEqual(len(self.tracking.list_works()), 1)

    def test_recibido_en_pilar_sale_de_activos_y_entra_en_completados(self):
        work = self._lote(1)[0]
        for paso in ("asuncion", "lab", "del_lab", "a_pilar", "en_pilar"):
            if paso == "asuncion":
                self.tracking.receive_in_asuncion(work.id, responsible="Ana")
            elif paso == "lab":
                self.tracking.send_to_laboratory(
                    work.id, self.lab.id, expected_date=HOY + timedelta(days=1),
                    responsible="Ana")
            elif paso == "del_lab":
                self.tracking.receive_from_laboratory(work.id, responsible="Ana")
            elif paso == "a_pilar":
                self.tracking.send_batch_to_pilar([work.id], responsible="Ana")
            else:
                self.tracking.receive_in_pilar(work.id, responsible="Nidia")
        self.assertEqual(len(self.tracking.board(scope=SCOPE_ACTIVOS)["rows"]), 0)
        completados = self.tracking.board(scope=SCOPE_COMPLETADOS)["rows"]
        self.assertEqual(len(completados), 1)
        self.assertEqual(completados[0].physical_status, "RECIBIDO EN PILAR")
        self.assertEqual(len(self.tracking.board(scope=SCOPE_TODOS)["rows"]), 1)

    def test_un_trabajo_cerrado_tampoco_ensucia_la_vista_activa(self):
        work = self._lote(1)[0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY + timedelta(days=1), responsible="Ana")
        self.tracking.receive_from_laboratory(work.id, responsible="Ana")
        self.tracking.send_batch_to_pilar([work.id], responsible="Ana")
        self.tracking.receive_in_pilar(work.id, responsible="Nidia")
        self.tracking.close_work(work.id, responsible="Nidia")
        self.assertEqual(len(self.tracking.board(scope=SCOPE_ACTIVOS)["rows"]), 0)
        self.assertEqual(len(self.tracking.board(scope=SCOPE_COMPLETADOS)["rows"]), 1)

    def test_los_atrasados_se_filtran_dentro_de_los_activos(self):
        works = self._lote(3)
        for work in works[:2]:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
            self.tracking.send_to_laboratory(
                work.id, self.lab.id, expected_date=AYER, expected_time="15:00",
                responsible="Ana")
        ahora = momento(HOY, "10:00")
        self.assertEqual(len(self.tracking.board(now=ahora)["rows"]), 3)
        solo = self.tracking.board(only_overdue=True, now=ahora)["rows"]
        self.assertEqual(len(solo), 2)
        self.assertTrue(all(f.overdue for f in solo))


class DetalleTests(Base):
    def test_el_detalle_reune_todo_lo_necesario(self):
        pedidos = self._pedidos_de_pilar(1)
        work = self.tracking.create_pilar_shipment(
            [pedidos[0].id], operator="Nidia")["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY, expected_time="15:30",
            responsible="Ana")
        self.tracking.register_contact(
            work.id, operator="Ana", result="Lab confirmo salida 14:30",
            recorded_at=momento(HOY, "13:12"))

        d = self.tracking.work_detail(work.id, now=momento(HOY, "14:00"))
        self.assertEqual(d["envelope"], "TEST-P-001")
        self.assertEqual(d["customer_name"], "Cliente Prueba 01")
        self.assertEqual(d["work_type"], "Cristal")
        self.assertEqual(d["physical_status"], "EN LABORATORIO")
        self.assertEqual(d["laboratory"], "LAB PRUEBA")
        self.assertEqual(d["phone_line"], "021 555 101")
        self.assertEqual(d["whatsapp"], "0981 555 201")
        self.assertTrue(d["expected"])
        self.assertIn("Lab confirmo salida 14:30", d["last_news"])
        self.assertEqual(len(d["contacts"]), 1)
        self.assertEqual(len(d["transitions"]), 2)
        self.assertEqual(d["order_id"], pedidos[0].id)

    def test_el_detalle_de_un_trabajo_recien_enviado_no_rompe(self):
        pedidos = self._pedidos_de_pilar(1)
        work = self.tracking.create_pilar_shipment(
            [pedidos[0].id], operator="Nidia")["works"][0]
        d = self.tracking.work_detail(work.id)
        self.assertEqual(d["laboratory"], "SIN ASIGNAR")
        self.assertEqual(d["expected"], "")
        self.assertEqual(d["transitions"], ())


class InterfazTests(unittest.TestCase):
    def test_la_vista_abre_en_activos(self):
        self.assertIn('filtro_seguimiento = ctk.StringVar(value="Activos")', FUENTE)

    def test_existen_los_filtros_completados_y_todos(self):
        self.assertIn('("Completados", "COMPLETADOS")', FUENTE)
        self.assertIn('("Todos", "TODOS")', FUENTE)

    def test_la_alerta_lleva_a_los_atrasados(self):
        self.assertIn("def ir_a_atrasados", FUENTE)
        self.assertIn('alerta_seguimiento.bind("<Button-1>", ir_a_atrasados', FUENTE)

    def test_la_tabla_vacia_explica_por_que(self):
        self.assertIn("MENSAJES_VACIO", FUENTE)
        self.assertIn("No hay trabajos en circuito.", FUENTE)

    def test_el_detalle_es_alcanzable_por_boton_y_doble_clic(self):
        self.assertIn("def abrir_detalle_trabajo", FUENTE)
        self.assertIn('text="Ver detalle"', FUENTE)
        self.assertIn('grilla_seguimiento.bind("<Double-1>", abrir_detalle_trabajo', FUENTE)

    def test_los_comandos_de_funciones_tardias_se_resuelven_al_pulsar(self):
        """El boton se crea antes de que exista la funcion del detalle.

        Pasarla como referencia directa lanzaba UnboundLocalError al abrir la
        pestaña. Tiene que ir envuelta para resolverse recien al pulsar.
        """
        self.assertIn("command=lambda: abrir_detalle_trabajo()", FUENTE)
        boton = FUENTE[FUENTE.index('text="Ver detalle"'):]
        self.assertNotIn("command=abrir_detalle_trabajo,", boton[:400])

    def test_crear_envio_refresca_la_tabla(self):
        bloque = FUENTE[FUENTE.index("def crear_envio()"):]
        self.assertIn("refrescar_seguimiento()", bloque[:1600])


if __name__ == "__main__":
    unittest.main()
