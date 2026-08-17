"""BC-CAJA-RC26: ninguna condicion derivada puede trabar el circuito fisico.

Regresion del bloqueo detectado en la prueba manual de rc.24: un trabajo
`EN LABORATORIO` que quedaba `ATRASADO` dejaba de ofrecer "recibir" y solo
ofrecia "contactar". Como contactar no transiciona, la operadora podia
registrar llamadas indefinidamente sin poder avanzar nunca el trabajo, y la
unica salida era comprometer un plazo futuro que el laboratorio no habia dado.

La regla: `ATRASADO` y `CONTACTAR` son condicion y accion complementarias, no
estados terminales. El trabajo conserva siempre su etapa fisica y siempre
puede seguir avanzando.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import (
    BUSINESS_TIMEZONE,
    Order,
    OrderOrigin,
    OrderStatus,
)
from modulos.caja_diaria.domain.tracking import (
    NextAction,
    ReceptionIssue,
    TrackingStatus,
    complementary_action,
    next_action,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)
FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class Base(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.tracking = TrackingService(self.repository)
        self.service = CashDayService(self.repository)
        self.lab = self.tracking.save_laboratory(name="LAB ALFA", phone_line="021 111")
        self.ahora = momento(HOY, "10:00")

    def tearDown(self):
        self.repository.close()

    def _pedido(self, envelope="TEST-001", telefono="0981 555 111"):
        pedido = Order(
            delivery_date=HOY + timedelta(days=7), branch="PILAR",
            customer_name="Cliente TEST 01", saleswoman="Nidia (TEST)",
            envelope=envelope, origin=OrderOrigin.WORKSHOP,
            customer_phone=telefono, observations="Armazon + cristales",
            created_at=momento(AYER, "14:00"))
        self.repository.save_order(pedido)
        return pedido

    def _atrasado_en_laboratorio(self):
        """Un trabajo EN LABORATORIO con el plazo vencido ayer."""
        pedido = self._pedido()
        work = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia")["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=AYER, expected_time="15:00",
            responsible="Ana")
        return work, pedido

    def _fila(self, work_id, **kw):
        kw.setdefault("scope", "TODOS")
        kw.setdefault("now", self.ahora)
        return next(f for f in self.tracking.board(**kw)["rows"] if f.work.id == work_id)


class ContactarNoMueveLaEtapaTests(Base):
    def test_contactar_no_modifica_la_etapa_fisica(self):
        work, _ = self._atrasado_en_laboratorio()
        antes = self._fila(work.id).physical_status
        self.tracking.register_contact(
            work.id, operator="Ana", channel="LLAMADA",
            result="Llamé, no atienden", recorded_at=momento(HOY, "09:00"))
        despues = self._fila(work.id)
        self.assertEqual(antes, "EN LABORATORIO")
        self.assertEqual(despues.physical_status, "EN LABORATORIO")
        self.assertIs(
            self.repository.get_tracked_work(work.id).status,
            TrackingStatus.IN_LABORATORY)

    def test_contactar_no_es_una_transicion(self):
        from modulos.caja_diaria.domain.tracking import TRANSICION_DE_ACCION
        self.assertIsNone(TRANSICION_DE_ACCION[NextAction.CONTACT_LABORATORY])

    def test_despues_de_contactar_sigue_disponible_la_transicion_siguiente(self):
        """El caso exacto que se trababa."""
        work, _ = self._atrasado_en_laboratorio()
        for intento, resultado in enumerate(
                ("Llamé, no atienden", "Sigo sin respuesta", "Insisto mañana"), start=1):
            self.tracking.register_contact(
                work.id, operator="Ana", channel="LLAMADA", result=resultado,
                recorded_at=momento(HOY, f"09:0{intento}"))
            resumen = self.tracking.next_action_for([work.id], now=self.ahora)
            self.assertEqual(
                resumen["action"], NextAction.RECEIVE_FROM_LABORATORY,
                f"tras contactar {intento} vez/veces la transicion desaparecio")
        # Y se ejecuta de verdad, sin haber movido ningun plazo.
        self.tracking.apply_next_action([work.id], responsible="Ana", now=self.ahora)
        self.assertIs(
            self.repository.get_tracked_work(work.id).status,
            TrackingStatus.RECEIVED_FROM_LABORATORY)

    def test_no_hace_falta_inventar_un_plazo_para_destrabar(self):
        """La vieja unica salida era comprometer una fecha que nadie dio."""
        work, _ = self._atrasado_en_laboratorio()
        guardado = self.repository.get_tracked_work(work.id)
        self.tracking.apply_next_action([work.id], responsible="Ana", now=self.ahora)
        despues = self.repository.get_tracked_work(work.id)
        # El plazo original nunca se toco para poder avanzar.
        self.assertEqual(guardado.expected_date, AYER)
        self.assertFalse(guardado.confirmed_for_next_day)
        self.assertFalse(despues.confirmed_for_next_day)


class AtrasadoNoEsTerminalTests(Base):
    def test_un_trabajo_atrasado_puede_seguir_avanzando(self):
        work, _ = self._atrasado_en_laboratorio()
        self.assertTrue(self._fila(work.id).overdue)
        self.tracking.apply_next_action([work.id], responsible="Ana", now=self.ahora)
        self.assertIs(
            self.repository.get_tracked_work(work.id).status,
            TrackingStatus.RECEIVED_FROM_LABORATORY)

    def test_atrasado_coexiste_con_la_etapa_fisica(self):
        work, _ = self._atrasado_en_laboratorio()
        fila = self._fila(work.id)
        self.assertTrue(fila.overdue)
        self.assertEqual(fila.alert, "ATRASADO")
        self.assertEqual(fila.physical_status, "EN LABORATORIO")
        self.assertEqual(fila.status_display, "ATRASADO · EN LABORATORIO")

    def test_el_atraso_solo_agrega_una_sugerencia(self):
        work, _ = self._atrasado_en_laboratorio()
        fila = self._fila(work.id)
        self.assertEqual(fila.next_action, NextAction.RECEIVE_FROM_LABORATORY)
        self.assertEqual(fila.complementary_action, NextAction.CONTACT_LABORATORY)
        self.assertEqual(fila.complementary_action_label, "Contactar laboratorio")

    def test_sin_atraso_no_hay_sugerencia_de_contacto(self):
        pedido = self._pedido(envelope="TEST-002")
        work = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia")["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=MANANA, expected_time="15:00",
            responsible="Ana")
        fila = self._fila(work.id)
        self.assertFalse(fila.overdue)
        self.assertIsNone(fila.complementary_action)
        self.assertEqual(fila.complementary_action_label, "")

    def test_ninguna_etapa_del_circuito_se_queda_sin_transicion(self):
        """Barrido: solo el final del circuito puede no tener accion."""
        for etapa in TrackingStatus:
            for vencido in (False, True):
                accion = next_action(etapa, overdue=vencido)
                if etapa in (TrackingStatus.RECEIVED_IN_PILAR, TrackingStatus.CLOSED):
                    self.assertIs(accion, NextAction.NONE, etapa)
                else:
                    self.assertIsNot(accion, NextAction.NONE, etapa)
                    self.assertIsNot(
                        accion, NextAction.CONTACT_LABORATORY,
                        f"{etapa} con vencido={vencido} devuelve una accion que no "
                        "transiciona: el trabajo quedaria trabado")

    def test_la_sugerencia_nunca_ocupa_el_lugar_de_la_transicion(self):
        from modulos.caja_diaria.domain.tracking import TRANSICION_DE_ACCION
        for etapa in TrackingStatus:
            for vencido in (False, True):
                sugerida = complementary_action(etapa, overdue=vencido)
                if sugerida is not None:
                    self.assertIsNone(
                        TRANSICION_DE_ACCION[sugerida],
                        "una accion complementaria no puede transicionar")


class CircuitoCompletoDesdeAtrasoTests(Base):
    def test_entregado_sigue_siendo_alcanzable(self):
        """Del atraso al final del circuito, sin mover plazos."""
        work, pedido = self._atrasado_en_laboratorio()
        self.tracking.register_contact(
            work.id, operator="Ana", channel="LLAMADA", result="No atienden",
            recorded_at=momento(HOY, "09:00"))
        recorrido = [self.repository.get_tracked_work(work.id).status]
        for _ in range(3):
            self.tracking.apply_next_action(
                [work.id], responsible="Ana", now=self.ahora)
            recorrido.append(self.repository.get_tracked_work(work.id).status)
        self.assertEqual(recorrido, [
            TrackingStatus.IN_LABORATORY,
            TrackingStatus.RECEIVED_FROM_LABORATORY,
            TrackingStatus.SENT_TO_PILAR,
            TrackingStatus.RECEIVED_IN_PILAR,
        ])
        self.tracking.close_work(work.id, responsible="Nidia")
        self.assertIs(self.repository.get_tracked_work(work.id).status,
                      TrackingStatus.CLOSED)

        # Y el pedido de origen llega a ENTREGADO.
        self.service.update_order_status(pedido.id, OrderStatus.READY, responsible="Ana")
        entregado = self.service.update_order_status(
            pedido.id, OrderStatus.DELIVERED, responsible="Ana")
        self.assertIs(entregado.status, OrderStatus.DELIVERED)

    def test_un_atrasado_no_sale_de_la_vista_ni_del_conteo(self):
        work, _ = self._atrasado_en_laboratorio()
        tablero = self.tracking.board(now=self.ahora)
        self.assertIn(work.id, {f.work.id for f in tablero["rows"]})
        self.assertEqual(tablero["summary"]["atrasados"], 1)
        self.assertEqual(tablero["summary"]["en_laboratorio"], 1)
        self.assertEqual(
            self._fila(work.id, scope="ACTIVOS").group, "en_laboratorio")


class ResolverRecepcionEsEjecutableTests(Base):
    def _no_llego(self):
        pedido = self._pedido(envelope="TEST-003")
        work = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia")["works"][0]
        self.tracking.mark_not_arrived(work.id, responsible="Ana")
        return work

    def test_no_llego_ofrece_una_accion_que_de_verdad_resuelve(self):
        """Mismo patron que el atraso: anunciaba una salida que no existia."""
        work = self._no_llego()
        self.assertEqual(
            self.tracking.next_action_for([work.id])["action"],
            NextAction.RESOLVE_RECEPTION)
        self.tracking.apply_next_action([work.id], responsible="Ana")
        recuperado = self.repository.get_tracked_work(work.id)
        self.assertIs(recuperado.status, TrackingStatus.RECEIVED_IN_ASUNCION)
        self.assertIsNone(recuperado.reception_issue)

    def test_sigue_sin_poder_saltarse_la_recepcion(self):
        work = self._no_llego()
        with self.assertRaises(InvalidCashDayError):
            self.tracking.send_to_laboratory(
                work.id, self.lab.id, expected_date=MANANA, responsible="Ana")

    def test_no_llego_coexiste_con_su_etapa(self):
        work = self._no_llego()
        fila = self._fila(work.id)
        self.assertEqual(fila.status_display, "NO LLEGÓ · ENVIADO DESDE PILAR")


class TelefonoEnSeguimientoTests(Base):
    def test_el_telefono_se_lee_en_la_fila(self):
        work, pedido = self._atrasado_en_laboratorio()
        self.assertEqual(self._fila(work.id).customer_phone, pedido.customer_phone)

    def test_sale_del_pedido_y_no_se_duplica_en_seguimiento(self):
        columnas = [c[1] for c in self.repository._connection().__enter__().execute(
            "PRAGMA table_info(tracked_works)")]
        self.assertNotIn("customer_phone", columnas)

    def test_sin_telefono_cargado_no_rompe(self):
        pedido = self._pedido(envelope="TEST-004", telefono="")
        work = self.tracking.create_pilar_shipment(
            [pedido.id], operator="Nidia")["works"][0]
        self.assertEqual(self._fila(work.id).customer_phone, "")

    def test_un_trabajo_sin_pedido_de_origen_tampoco_rompe(self):
        work = self.tracking.register_pilar_batch(
            [{"envelope": "S-001", "customer_name": "Cliente sin pedido"}],
            consultation_date=HOY, created_by="Nidia")[0]
        self.assertEqual(self._fila(work.id).customer_phone, "")

    def test_el_detalle_tambien_lo_muestra(self):
        work, pedido = self._atrasado_en_laboratorio()
        detalle = self.tracking.work_detail(work.id, now=self.ahora)
        self.assertEqual(detalle["customer_phone"], pedido.customer_phone)

    def test_se_resuelve_en_una_consulta_por_lote(self):
        """Una consulta para toda la tabla, no una por fila."""
        pedidos = [self._pedido(envelope=f"TEST-1{i:02d}") for i in range(5)]
        self.tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia")
        filas = self.tracking.board()["rows"]
        self.assertEqual(len(filas), 5)
        self.assertTrue(all(f.customer_phone == "0981 555 111" for f in filas))


class InterfazTests(unittest.TestCase):
    def test_la_barra_ya_no_desvia_contactar_ni_bloquea_resolver(self):
        bloque = FUENTE[
            FUENTE.index("def ejecutar_accion_siguiente"):
            FUENTE.index("def pedir_destino_laboratorio")
        ]
        # El desvio a "solo registrar informacion" era el bloqueo.
        self.assertNotIn("if accion is NextAction.CONTACT_LABORATORY:", bloque)
        self.assertNotIn("Recibilos cuando aparezcan", bloque)
        self.assertIn("controller.tracking.apply_next_action(", bloque)

    def test_la_sugerencia_de_contacto_se_ve_sin_sumar_un_cuarto_boton(self):
        bloque = FUENTE[FUENTE.index("def actualizar_acciones_seguimiento"):]
        self.assertIn('info.get("complementary")', bloque[:1200])
        self.assertIn("Contactar laboratorio", bloque[:1400])
        # Sigue siendo el boton Novedad, que es el que ya registra el contacto.
        barra = FUENTE[
            FUENTE.index("boton_accion_siguiente = ctk.CTkButton"):
            FUENTE.index("etiqueta_seleccion = ctk.CTkLabel")
        ]
        self.assertEqual(barra.count("ctk.CTkButton("), 3)

    def test_el_boton_principal_no_se_deshabilita_por_atraso(self):
        bloque = FUENTE[FUENTE.index("def actualizar_acciones_seguimiento"):]
        # La condicion es la misma; ahora la aplica `aplicar_disponibilidad`,
        # que ademas apaga el boton de verdad y explica por que.
        self.assertIn("aplicar_disponibilidad(", bloque[:1200])
        self.assertIn(
            'info["action"] not in (None, NextAction.NONE)', bloque[:1200])
        self.assertNotIn("atrasado", bloque[:1200])

    def test_la_columna_telefono_se_dibuja_en_la_fila(self):
        self.assertIn('("telefono", "Teléfono"', FUENTE)
        self.assertIn("fila.customer_phone", FUENTE)

    def test_todavia_no_se_implementa_whatsapp_ni_llamar(self):
        """El slice siguiente. Mezclarlo con el fix seria ampliar alcance."""
        tabla = FUENTE[
            FUENTE.index("COLUMNAS_SEGUIMIENTO = ("):
            FUENTE.index("lista_seguimiento = ctk.CTkScrollableFrame")
        ]
        for pendiente in ("wa.me", "whatsapp://", 'text="Llamar"', "webbrowser"):
            self.assertNotIn(pendiente, tabla)


if __name__ == "__main__":
    unittest.main()
