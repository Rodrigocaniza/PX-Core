"""BC-CAJA-RC25: el circuito completo sobre los mismos 15 TEST.

Punta a punta, sin sembrar otro escenario: Pilar envia 15, Asuncion los recibe
con dos discrepancias y un fisico que no figuraba, los reparte entre tres
laboratorios, atiende un atraso, registra novedades, recibe la devolucion, los
manda de vuelta y Pilar cierra el circuito.

Cada paso verifica lo que la operadora veria en pantalla en ese momento: la
alerta de su sucursal, la conciliacion, el rotulo del boton principal y la
observacion de la fila. Lo que no se puede leer, no esta hecho.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin
from modulos.caja_diaria.domain.tracking import NextAction, ReceptionIssue, TrackingStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class CircuitoCompletoTests(unittest.TestCase):
    """Un solo test: es un recorrido, y partirlo perderia el hilo."""

    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.tracking = TrackingService(self.repository)
        self.labs = {
            nombre: self.tracking.save_laboratory(name=nombre, phone_line=f"021 {i}")
            for i, nombre in enumerate(("LAB ALFA", "LAB BETA", "LAB GAMMA"), start=1)
        }

    def tearDown(self):
        self.repository.close()

    def _pedidos(self, cantidad, prefijo="TEST"):
        creados = []
        for i in range(1, cantidad + 1):
            pedido = Order(
                delivery_date=HOY + timedelta(days=7), branch="PILAR",
                customer_name=f"Cliente TEST {i:02d}", saleswoman="Nidia (TEST)",
                envelope=f"{prefijo}-{i:03d}", origin=OrderOrigin.WORKSHOP,
                observations="Armazon + cristales",
                created_at=datetime.combine(AYER, time(14, 0), tzinfo=BUSINESS_TIMEZONE))
            self.repository.save_order(pedido)
            creados.append(pedido)
        return creados

    def _fila(self, work_id, **kw):
        kw.setdefault("scope", "TODOS")
        return next(
            f for f in self.tracking.board(**kw)["rows"] if f.work.id == work_id)

    def test_el_circuito_completo_con_los_mismos_quince(self):
        tracking = self.tracking

        # 1. Pilar envia 15.
        pedidos = self._pedidos(15)
        lote = tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia (TEST)")
        self.assertEqual(lote["count"], 15)
        works = lote["works"]

        # 2. La principal de Asuncion avisa que hay 15 por recibir.
        alerta = tracking.pending_actions_for_branch("ASUNCION")["principal"]
        self.assertEqual(alerta["texto"], "15 por recibir desde Pilar")
        self.assertEqual(alerta["cantidad"], 15)
        # Pilar no ve como propio lo que le toca a Asuncion.
        self.assertIsNone(tracking.pending_actions_for_branch("PILAR")["principal"])

        # 3. El clic abre exactamente esos 15 y ninguno mas.
        enfocados = tracking.board(
            responsible_branch="ASUNCION", group=alerta["grupo"])["rows"]
        self.assertEqual(len(enfocados), 15)
        self.assertEqual({f.work.id for f in enfocados}, {w.id for w in works})

        # 4. Se reciben 12, en una sola accion masiva.
        recibidos = [w.id for w in works[:12]]
        resumen = tracking.next_action_for(recibidos)
        self.assertEqual(resumen["action"], NextAction.RECEIVE_IN_ASUNCION)
        self.assertEqual(resumen["label"], "Recibir 12 en Asunción")
        tracking.apply_next_action(recibidos, responsible="Ana")

        # 5. Dos no llegaron: quedan ligados al lote y no avanzan.
        faltantes = [w.id for w in works[12:14]]
        tracking.mark_batch_not_arrived(faltantes, responsible="Ana")
        for work_id in faltantes:
            fila = self._fila(work_id)
            self.assertEqual(fila.status_display, "NO LLEGÓ · ENVIADO DESDE PILAR")
            self.assertEqual(fila.next_action, NextAction.RESOLVE_RECEPTION)
            with self.assertRaises(InvalidCashDayError):
                tracking.apply_next_action([work_id], responsible="Ana")
        self.assertEqual(
            self.repository.get_tracked_work(faltantes[0]).shipment_id,
            lote["shipment"].id)

        # 6. Aparece un fisico que no estaba en la lista: se reutiliza su pedido.
        extra_pedido = self._pedidos(1, prefijo="EXTRA")[0]
        candidatos = tracking.search_receivable_orders("EXTRA-001")
        self.assertEqual([p.id for p in candidatos], [extra_pedido.id])
        extra = tracking.add_unlisted_reception(
            candidatos[0].id, responsible="Ana", shipment_id=lote["shipment"].id)
        self.assertEqual(extra.customer_name, extra_pedido.customer_name)
        self.assertEqual(extra.observations, extra_pedido.observations)
        self.assertEqual(extra.created_by, "Ana")
        self.assertIs(extra.reception_issue, ReceptionIssue.NOT_IN_LIST)

        # La conciliacion cierra contra lo que Pilar declaro.
        self.assertEqual(
            tracking.reception_reconciliation(lote["shipment"].id),
            {"declarados": 15, "recibidos": 12, "no_llego": 2, "extra": 1})
        self.assertEqual(
            tracking.current_reception("ASUNCION")["line"],
            "Declarados 15 · Recibidos 12 · No llegó 2 · Extra 1")
        # 12 + 2 = 14: el decimoquinto sigue sin revisar, y la recepcion sigue
        # abierta justamente por eso. La linea no lo disimula.
        sin_revisar = works[14].id
        self.assertIs(
            self.repository.get_tracked_work(sin_revisar).status,
            TrackingStatus.SENT_FROM_PILAR)
        self.assertIsNotNone(tracking.current_reception("ASUNCION")["shipment"])

        # 7 y 8. Seleccion multiple: tres grupos a tres laboratorios.
        listos = recibidos + [extra.id]          # 13 en Asuncion
        self.assertEqual(
            tracking.next_action_for(listos)["action"], NextAction.SEND_TO_LABORATORY)
        reparto = {
            "LAB ALFA": listos[:5], "LAB BETA": listos[5:9], "LAB GAMMA": listos[9:],
        }
        for nombre, grupo in reparto.items():
            tracking.apply_next_action(
                grupo, responsible="Ana", laboratory_id=self.labs[nombre].id,
                # ALFA vence ayer a proposito: es el atraso del paso 9.
                expected_date=AYER if nombre == "LAB ALFA" else MANANA,
                expected_time="15:00")
        for nombre, grupo in reparto.items():
            for work_id in grupo:
                self.assertEqual(self._fila(work_id).laboratory_name, nombre)

        # 9. Atrasados: cinco, y el boton principal deja de ofrecer "recibir".
        ahora = momento(HOY, "10:00")
        tablero = tracking.board(responsible_branch="ASUNCION", now=ahora)
        atrasados = [f for f in tablero["rows"] if f.overdue]
        self.assertEqual(len(atrasados), 5)
        self.assertEqual(
            tracking.next_action_for(reparto["LAB ALFA"], now=ahora)["action"],
            NextAction.CONTACT_LABORATORY)
        principal = tracking.pending_actions_for_branch("ASUNCION", now=ahora)["principal"]
        self.assertEqual(principal["clave"], "atrasados")
        self.assertEqual(principal["cantidad"], 5)
        # La agrupacion por laboratorio evita llamar cinco veces.
        grupos_lab = tracking.board(
            responsible_branch="ASUNCION", now=ahora)["overdue_groups"]
        self.assertEqual([g["name"] for g in grupos_lab], ["LAB ALFA"])
        self.assertEqual(grupos_lab[0]["count"], 5)

        # 10 y 11. Novedades hoy y manana, legibles en la fila.
        hoy_mismo, manana_mismo = reparto["LAB ALFA"][0], reparto["LAB ALFA"][1]
        tracking.confirm_for_next_day(
            hoy_mismo, operator="Ana", next_expected_date=HOY,
            next_expected_time="17:30", result="Lab confirmó salida 14:30",
            recorded_at=momento(HOY, "09:30"))
        tracking.confirm_for_next_day(
            manana_mismo, operator="Ana", next_expected_date=MANANA,
            next_expected_time="15:00", result="", recorded_at=momento(HOY, "09:31"))
        observacion_hoy = self._fila(hoy_mismo, now=ahora).observation
        self.assertIn("Hoy 17:30", observacion_hoy)
        self.assertIn("Lab confirmó salida 14:30", observacion_hoy)
        self.assertTrue(observacion_hoy.startswith("☎"))
        self.assertIn("Mañana 15:00", self._fila(manana_mismo, now=ahora).observation)
        # Confirmar corre el plazo: deja de estar atrasado sin borrar la etapa.
        self.assertFalse(self._fila(manana_mismo, now=ahora).overdue)
        self.assertEqual(
            self._fila(manana_mismo, now=ahora).physical_status, "EN LABORATORIO")

        # 12. Los laboratorios devuelven los 13.
        #
        # Los tres de ALFA que siguen vencidos no ofrecen "recibir" sino
        # "contactar", y una seleccion que mezcla ambas cosas se rechaza: es la
        # misma regla que impide dar por recibido lo que todavia no llamaste.
        pendientes_de_llamada = [
            w for w in reparto["LAB ALFA"]
            if self._fila(w, now=ahora).next_action is NextAction.CONTACT_LABORATORY
        ]
        self.assertEqual(len(pendientes_de_llamada), 3)
        with self.assertRaises(InvalidCashDayError):
            tracking.apply_next_action(listos, responsible="Ana", now=ahora)
        for work_id in pendientes_de_llamada:
            tracking.confirm_for_next_day(
                work_id, operator="Ana", next_expected_date=MANANA,
                next_expected_time="15:00", result="Lab pide un día más",
                recorded_at=momento(HOY, "09:40"))
        tracking.apply_next_action(listos, responsible="Ana", now=ahora)
        self.assertTrue(all(
            self.repository.get_tracked_work(w).status
            is TrackingStatus.RECEIVED_FROM_LABORATORY for w in listos))

        # 13. Encomienda de vuelta a Pilar.
        self.assertEqual(
            tracking.next_action_for(listos)["action"], NextAction.SEND_TO_PILAR)
        tracking.apply_next_action(listos, responsible="Ana")

        # 14. Ahora la alerta es de Pilar, y Asuncion ya no la reclama.
        alerta_pilar = tracking.pending_actions_for_branch("PILAR")["principal"]
        self.assertEqual(alerta_pilar["cantidad"], 13)
        self.assertEqual(alerta_pilar["grupo"], "por_recibir_pilar")
        pendiente_asuncion = tracking.pending_actions_for_branch("ASUNCION")["principal"]
        # A Asuncion le quedan los dos NO LLEGÓ y el que nunca se reviso: tres
        # cabos sueltos que la alerta sigue reclamando aunque el lote grande ya
        # haya cerrado su vuelta.
        self.assertEqual(pendiente_asuncion["clave"], "por_recibir")
        self.assertEqual(pendiente_asuncion["cantidad"], 3)

        # 15. Recepcion final en Pilar.
        self.assertEqual(
            tracking.next_action_for(listos)["action"], NextAction.RECEIVE_IN_PILAR)
        tracking.apply_next_action(listos, responsible="Nidia (TEST)")

        # 16. Completados: salen de la vista activa y quedan consultables.
        activos = tracking.board(scope="ACTIVOS")["rows"]
        self.assertEqual({f.work.id for f in activos}, set(faltantes) | {sin_revisar})
        completados = tracking.board(scope="COMPLETADOS")["rows"]
        self.assertEqual(len(completados), 13)
        self.assertTrue(all(f.group == "completados" for f in completados))
        self.assertTrue(all(
            f.physical_status == "RECIBIDO EN PILAR" for f in completados))
        self.assertIsNone(tracking.pending_actions_for_branch("PILAR")["principal"])

        # El extra conserva su marca: documenta que entro fuera del envio.
        self.assertIs(
            self.repository.get_tracked_work(extra.id).reception_issue,
            ReceptionIssue.NOT_IN_LIST)

        # Cada trabajo conserva su identidad y su traza completa.
        self.assertEqual(len(tracking.list_works()), 16)
        recorrido = self.repository.get_tracked_work(listos[0])
        self.assertEqual(
            [t.to_status for t in recorrido.transitions],
            [TrackingStatus.RECEIVED_IN_ASUNCION, TrackingStatus.IN_LABORATORY,
             TrackingStatus.RECEIVED_FROM_LABORATORY, TrackingStatus.SENT_TO_PILAR,
             TrackingStatus.RECEIVED_IN_PILAR])


if __name__ == "__main__":
    unittest.main()
