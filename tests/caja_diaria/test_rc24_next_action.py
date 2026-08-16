"""BC-CAJA-RC24: una sola autoridad decide que hacer, y discrepancias reales.

La barra de acciones, las alertas y las operaciones masivas preguntan todas a
`next_action`, de modo que no puedan discrepar entre si.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin
from modulos.caja_diaria.domain.tracking import (
    ETIQUETA_ACCION,
    NextAction,
    ReceptionIssue,
    TrackingStatus,
    next_action,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
AYER = HOY - timedelta(days=1)


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class AutoridadNextActionTests(unittest.TestCase):
    def test_cada_etapa_determina_su_accion(self):
        self.assertEqual(next_action(TrackingStatus.SENT_FROM_PILAR),
                         NextAction.RECEIVE_IN_ASUNCION)
        self.assertEqual(next_action(TrackingStatus.RECEIVED_IN_ASUNCION),
                         NextAction.SEND_TO_LABORATORY)
        self.assertEqual(next_action(TrackingStatus.IN_LABORATORY),
                         NextAction.RECEIVE_FROM_LABORATORY)
        self.assertEqual(next_action(TrackingStatus.RECEIVED_FROM_LABORATORY),
                         NextAction.SEND_TO_PILAR)
        self.assertEqual(next_action(TrackingStatus.SENT_TO_PILAR),
                         NextAction.RECEIVE_IN_PILAR)
        self.assertEqual(next_action(TrackingStatus.RECEIVED_IN_PILAR), NextAction.NONE)

    def test_el_atraso_cambia_la_accion_a_contactar(self):
        self.assertEqual(
            next_action(TrackingStatus.IN_LABORATORY, overdue=True),
            NextAction.CONTACT_LABORATORY)

    def test_no_llego_bloquea_el_avance_hasta_resolver(self):
        self.assertEqual(
            next_action(TrackingStatus.SENT_FROM_PILAR,
                        reception_issue=ReceptionIssue.NOT_ARRIVED),
            NextAction.RESOLVE_RECEPTION)

    def test_toda_accion_tiene_etiqueta_para_el_boton(self):
        for accion in NextAction:
            self.assertTrue(ETIQUETA_ACCION[accion])


class Base(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.tracking = TrackingService(self.repository)
        self.lab_a = self.tracking.save_laboratory(name="LAB ALFA", phone_line="021 1")
        self.lab_b = self.tracking.save_laboratory(name="LAB BETA", phone_line="021 2")

    def tearDown(self):
        self.repository.close()

    def _pedidos(self, cantidad):
        creados = []
        for i in range(1, cantidad + 1):
            pedido = Order(
                delivery_date=HOY + timedelta(days=7), branch="PILAR",
                customer_name=f"Cliente Prueba {i:02d}", saleswoman="Nidia (TEST)",
                envelope=f"TEST-P-{i:03d}", origin=OrderOrigin.WORKSHOP,
                observations="Cristal", cash_entry_id=None,
                created_at=datetime.combine(AYER, time(14, 0), tzinfo=BUSINESS_TIMEZONE))
            self.repository.save_order(pedido)
            creados.append(pedido)
        return creados

    def _lote(self, cantidad=15):
        pedidos = self._pedidos(cantidad)
        return self.tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia (TEST)")


class SeleccionYAccionTests(Base):
    def test_una_seleccion_homogenea_ofrece_una_sola_accion(self):
        works = self._lote(5)["works"]
        resumen = self.tracking.next_action_for([w.id for w in works])
        self.assertEqual(resumen["action"], NextAction.RECEIVE_IN_ASUNCION)
        self.assertEqual(resumen["label"], "Recibir 5 en Asunción")
        self.assertEqual(resumen["reason"], "")

    def test_un_solo_trabajo_usa_la_etiqueta_simple(self):
        works = self._lote(1)["works"]
        self.assertEqual(
            self.tracking.next_action_for([works[0].id])["label"], "Recibir en Asunción")

    def test_etapas_distintas_no_ofrecen_accion_masiva(self):
        works = self._lote(2)["works"]
        self.tracking.receive_in_asuncion(works[0].id, responsible="Ana")
        resumen = self.tracking.next_action_for([w.id for w in works])
        self.assertIsNone(resumen["action"])
        self.assertIn("etapas diferentes", resumen["reason"])

    def test_sin_seleccion_lo_dice(self):
        self.assertIn("al menos un trabajo", self.tracking.next_action_for([])["reason"])

    def test_la_accion_masiva_recibe_todos(self):
        works = self._lote(12)["works"]
        self.tracking.apply_next_action([w.id for w in works], responsible="Ana")
        self.assertTrue(all(
            w.status is TrackingStatus.RECEIVED_IN_ASUNCION
            for w in self.tracking.list_works()))

    def test_envio_masivo_al_mismo_laboratorio(self):
        works = self._lote(5)["works"]
        self.tracking.apply_next_action([w.id for w in works], responsible="Ana")
        enviados = self.tracking.apply_next_action(
            [w.id for w in works], responsible="Ana", laboratory_id=self.lab_a.id,
            expected_date=HOY, expected_time="15:00")
        self.assertEqual(len(enviados), 5)
        for work in self.tracking.list_works():
            self.assertIs(work.status, TrackingStatus.IN_LABORATORY)
            self.assertEqual(work.laboratory_id, self.lab_a.id)
            self.assertEqual(work.expected_date, HOY)
            # Cada trabajo conserva su transicion propia.
            self.assertEqual(len(work.transitions), 2)

    def test_el_envio_masivo_exige_laboratorio(self):
        works = self._lote(3)["works"]
        self.tracking.apply_next_action([w.id for w in works], responsible="Ana")
        with self.assertRaises(InvalidCashDayError):
            self.tracking.apply_next_action([w.id for w in works], responsible="Ana")

    def test_contactar_no_es_una_transicion(self):
        works = self._lote(1)["works"]
        self.tracking.apply_next_action([works[0].id], responsible="Ana")
        self.tracking.send_to_laboratory(
            works[0].id, self.lab_a.id, expected_date=AYER, expected_time="15:00",
            responsible="Ana")
        ahora = momento(HOY, "10:00")
        resumen = self.tracking.next_action_for([works[0].id], now=ahora)
        self.assertEqual(resumen["action"], NextAction.CONTACT_LABORATORY)
        with self.assertRaises(InvalidCashDayError):
            self.tracking.apply_next_action([works[0].id], responsible="Ana", now=ahora)


class DiscrepanciasTests(Base):
    def test_no_llego_queda_ligado_al_lote_y_no_avanza(self):
        lote = self._lote(3)
        work = lote["works"][0]
        marcado = self.tracking.mark_not_arrived(work.id, responsible="Ana")
        self.assertIs(marcado.reception_issue, ReceptionIssue.NOT_ARRIVED)
        self.assertEqual(marcado.shipment_id, lote["shipment"].id)
        self.assertEqual(
            self.tracking.next_action_for([work.id])["action"],
            NextAction.RESOLVE_RECEPTION)
        with self.assertRaises(InvalidCashDayError):
            self.tracking.apply_next_action([work.id], responsible="Ana")

    def test_recibirlo_despues_limpia_la_discrepancia(self):
        work = self._lote(1)["works"][0]
        self.tracking.mark_not_arrived(work.id, responsible="Ana")
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        recuperado = self.repository.get_tracked_work(work.id)
        self.assertIsNone(recuperado.reception_issue)
        self.assertIs(recuperado.status, TrackingStatus.RECEIVED_IN_ASUNCION)

    def test_no_llego_solo_aplica_antes_de_recibir(self):
        work = self._lote(1)["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        with self.assertRaises(InvalidCashDayError):
            self.tracking.mark_not_arrived(work.id, responsible="Ana")

    def test_un_trabajo_no_listado_reutiliza_el_pedido_existente(self):
        lote = self._lote(2)
        extra = self._pedidos(3)[2]        # pedido real que no entro al lote
        agregado = self.tracking.add_unlisted_reception(
            extra.id, responsible="Ana", shipment_id=lote["shipment"].id)
        self.assertEqual(agregado.order_id, extra.id)
        self.assertEqual(agregado.envelope, extra.envelope)
        self.assertEqual(agregado.customer_name, extra.customer_name)
        self.assertIs(agregado.reception_issue, ReceptionIssue.NOT_IN_LIST)
        self.assertIs(agregado.status, TrackingStatus.RECEIVED_IN_ASUNCION)
        self.assertEqual(agregado.created_by, "Ana")

    def test_no_se_puede_agregar_dos_veces(self):
        lote = self._lote(1)
        with self.assertRaises(InvalidCashDayError):
            self.tracking.add_unlisted_reception(
                lote["works"][0].order_id, responsible="Ana")

    def test_conciliacion_del_lote(self):
        lote = self._lote(15)
        works = lote["works"]
        for work in works[:12]:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        for work in works[13:]:
            self.tracking.mark_not_arrived(work.id, responsible="Ana")
        extra = self._pedidos(16)[15]
        self.tracking.add_unlisted_reception(
            extra.id, responsible="Ana", shipment_id=lote["shipment"].id)
        conciliacion = self.tracking.reception_reconciliation(lote["shipment"].id)
        self.assertEqual(conciliacion,
                         {"declarados": 15, "recibidos": 12, "no_llego": 2, "extra": 1})


class ObservacionTests(Base):
    def _fila(self, **kw):
        return self.tracking.board(**kw)["rows"][0]

    def test_la_novedad_con_plazo_se_lee_en_una_linea(self):
        work = self._lote(1)["works"][0]
        self.tracking.apply_next_action([work.id], responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab_a.id, expected_date=AYER, expected_time="15:00",
            responsible="Ana")
        self.tracking.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=HOY, next_expected_time="15:00",
            result="Lab confirmó para mañana", recorded_at=momento(AYER, "16:00"))
        observacion = self._fila(now=momento(AYER, "17:00")).observation
        self.assertIn(HOY.strftime("%d-%m"), observacion)
        self.assertIn("Lab confirmó para mañana", observacion)

    def test_la_discrepancia_se_lee_en_la_lista(self):
        work = self._lote(1)["works"][0]
        self.tracking.mark_not_arrived(work.id, responsible="Ana")
        self.assertEqual(self._fila().observation, "No llegó en el envío")

    def test_sin_novedad_muestra_el_plazo_comprometido(self):
        work = self._lote(1)["works"][0]
        self.tracking.apply_next_action([work.id], responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab_a.id, expected_date=HOY, expected_time="15:30",
            responsible="Ana")
        self.assertIn("Debía", self._fila(now=momento(HOY, "09:00")).observation)

    def test_un_trabajo_recien_enviado_no_tiene_observacion(self):
        self._lote(1)
        self.assertEqual(self._fila().observation, "")


if __name__ == "__main__":
    unittest.main()


class BarraDeAccionesTests(unittest.TestCase):
    """Tres acciones conceptuales, no seis transiciones."""

    FUENTE = open("CajaDiaria.py", encoding="utf-8").read()

    def test_solo_hay_tres_botones_principales(self):
        barra = self.FUENTE[
            self.FUENTE.index("boton_accion_siguiente = ctk.CTkButton"):
            self.FUENTE.index("etiqueta_seleccion = ctk.CTkLabel")
        ]
        self.assertEqual(barra.count("ctk.CTkButton("), 3)
        for texto in ('text="Acción siguiente"', 'text="Novedad"', 'text="Más  ▾"'):
            self.assertIn(texto, barra)

    def test_ya_no_existen_los_seis_botones_de_transicion(self):
        for residuo in ("ACCIONES_SEGUIMIENTO", "botones_accion_seguimiento"):
            self.assertNotIn(residuo, self.FUENTE)

    def test_el_boton_principal_toma_su_texto_de_next_action_for(self):
        self.assertIn("info = controller.tracking.next_action_for(ids)", self.FUENTE)
        self.assertIn('text=info["label"] or "Acción siguiente"', self.FUENTE)

    def test_hay_seleccion_multiple_con_contador(self):
        for pieza in ("def alternar_marca", "def seleccionar_visibles",
                      "def limpiar_seleccion", "ctk.CTkCheckBox(",
                      "seleccionado{'' if len(ids) == 1 else 's'}"):
            self.assertIn(pieza, self.FUENTE)

    def test_las_acciones_secundarias_viven_en_el_menu_mas(self):
        menu = self.FUENTE[self.FUENTE.index("def abrir_menu_mas"):]
        for etiqueta in ("Ver detalle", "Seleccionar visibles", "Limpiar selección",
                         "Cerrar trabajo"):
            self.assertIn(etiqueta, menu[:1200])

    def test_la_novedad_aplica_a_varios_trabajos(self):
        self.assertIn("def abrir_novedad(work_ids):", self.FUENTE)
        for atajo in ("Más tarde hoy", "Mañana", "Elegir fecha/hora", "Solo observación"):
            self.assertIn(atajo, self.FUENTE)
