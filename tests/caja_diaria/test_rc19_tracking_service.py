"""BC-CAJA-RC19: caso operativo real de punta a punta, sin red.

Reproduce el viernes de Pilar, el sabado de Asuncion, los laboratorios, los
atrasos y el regreso de la encomienda.
"""

from __future__ import annotations

import socket
import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE
from modulos.caja_diaria.domain.tracking import ContactChannel, TrackingStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

VIERNES = date(2026, 8, 14)
SABADO = VIERNES + timedelta(days=1)
DOMINGO = VIERNES + timedelta(days=2)


def momento(dia: date, hora: str) -> datetime:
    horas, minutos = (int(parte) for parte in hora.split(":"))
    return datetime.combine(dia, time(horas, minutos), tzinfo=BUSINESS_TIMEZONE)


class TrackingServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = TrackingService(self.repository)
        self.lab_a = self.service.save_laboratory(
            name="LAB A", phone_line="021 111 222", whatsapp="0981 111 222",
        )
        self.lab_b = self.service.save_laboratory(
            name="LAB B", phone_line="021 333 444", whatsapp="0982 333 444",
        )

    def tearDown(self):
        self.repository.close()

    def _consulta_de_pilar(self, cantidad=15):
        return self.service.register_pilar_batch(
            [
                {"envelope": f"S-{numero:03d}", "customer_name": f"Cliente {numero:02d}"}
                for numero in range(1, cantidad + 1)
            ],
            consultation_date=VIERNES, created_by="Nidia",
        )


class CasoOperativoTests(TrackingServiceTests):
    def test_viernes_nidia_registra_quince_trabajos_enviados_desde_pilar(self):
        lote = self._consulta_de_pilar()
        self.assertEqual(len(lote), 15)
        self.assertTrue(all(work.status is TrackingStatus.SENT_FROM_PILAR for work in lote))
        self.assertTrue(all(work.created_by == "Nidia" for work in lote))

    def test_sabado_asuncion_recibe_catorce_y_la_pantalla_muestra_uno_faltante(self):
        lote = self._consulta_de_pilar()
        self.service.receive_batch_in_asuncion(
            [work.id for work in lote[:14]], responsible="Ana",
        )
        tablero = self.service.board(consultation_date=VIERNES, now=momento(SABADO, "10:00"))
        self.assertEqual(tablero["reception"], {
            "enviados": 15, "recibidos": 14, "falta_recibir": 1,
        })
        self.assertEqual(tablero["summary"]["por_recibir_en_asuncion"], 1)

    def test_el_lote_se_reparte_entre_varios_laboratorios(self):
        lote = self._consulta_de_pilar(5)
        self.service.receive_batch_in_asuncion([work.id for work in lote], responsible="Ana")
        for work, destino in zip(lote, (self.lab_a, self.lab_a, self.lab_b, self.lab_b, self.lab_a)):
            self.service.send_to_laboratory(
                work.id, destino.id, expected_date=SABADO, responsible="Ana",
            )
        en_a = self.service.list_works(laboratory_id=self.lab_a.id)
        en_b = self.service.list_works(laboratory_id=self.lab_b.id)
        self.assertEqual((len(en_a), len(en_b)), (3, 2))

    def test_circuito_completo_hasta_recepcion_final_en_pilar(self):
        work = self._consulta_de_pilar(1)[0]
        self.service.receive_in_asuncion(work.id, responsible="Ana")
        self.service.send_to_laboratory(
            work.id, self.lab_a.id, expected_date=SABADO, responsible="Ana",
        )
        self.service.receive_from_laboratory(work.id, responsible="Ana")
        self.service.send_batch_to_pilar([work.id], responsible="Ana", note="Encomienda 1")
        self.service.receive_in_pilar(work.id, responsible="Nidia")
        final = self.service.close_work(work.id, responsible="Nidia")

        self.assertIs(final.status, TrackingStatus.CLOSED)
        self.assertEqual(len(final.transitions), 6)
        self.assertEqual(final.transitions[3].note, "Encomienda 1")
        self.assertEqual(final.transitions[-1].responsible, "Nidia")

    def test_la_encomienda_viaja_como_lote_conservando_traza_individual(self):
        lote = self._consulta_de_pilar(3)
        for work in lote:
            self.service.receive_in_asuncion(work.id, responsible="Ana")
            self.service.send_to_laboratory(
                work.id, self.lab_a.id, expected_date=SABADO, responsible="Ana",
            )
            self.service.receive_from_laboratory(work.id, responsible="Ana")
        enviados = self.service.send_batch_to_pilar(
            [work.id for work in lote], responsible="Ana",
        )
        self.assertTrue(all(work.status is TrackingStatus.SENT_TO_PILAR for work in enviados))
        self.assertEqual({len(work.transitions) for work in enviados}, {4})

    def test_pilar_confirma_uno_por_uno_al_dia_siguiente(self):
        lote = self._consulta_de_pilar(2)
        for work in lote:
            self.service.receive_in_asuncion(work.id, responsible="Ana")
            self.service.send_to_laboratory(
                work.id, self.lab_a.id, expected_date=SABADO, responsible="Ana",
            )
            self.service.receive_from_laboratory(work.id, responsible="Ana")
        self.service.send_batch_to_pilar([work.id for work in lote], responsible="Ana")
        self.service.receive_in_pilar(lote[0].id, responsible="Nidia")

        tablero = self.service.board(consultation_date=VIERNES, now=momento(DOMINGO, "09:00"))
        self.assertEqual(tablero["summary"]["en_transito_a_pilar"], 1)

    def test_rechaza_una_transicion_fuera_de_orden(self):
        work = self._consulta_de_pilar(1)[0]
        with self.assertRaises(InvalidCashDayError):
            self.service.send_to_laboratory(
                work.id, self.lab_a.id, expected_date=SABADO, responsible="Ana",
            )

    def test_rechaza_un_laboratorio_inexistente(self):
        work = self._consulta_de_pilar(1)[0]
        self.service.receive_in_asuncion(work.id, responsible="Ana")
        with self.assertRaises(InvalidCashDayError):
            self.service.send_to_laboratory(
                work.id, "lab-fantasma", expected_date=SABADO, responsible="Ana",
            )

    def test_rechaza_un_trabajo_inexistente(self):
        with self.assertRaises(InvalidCashDayError):
            self.service.receive_in_asuncion("no-existe", responsible="Ana")


class ControlHorarioTests(TrackingServiceTests):
    def _en_laboratorio(self, hora="15:00"):
        work = self._consulta_de_pilar(1)[0]
        self.service.receive_in_asuncion(work.id, responsible="Ana")
        return self.service.send_to_laboratory(
            work.id, self.lab_a.id, expected_date=SABADO, expected_time=hora, responsible="Ana",
        )

    def test_recibido_a_tiempo_no_aparece_atrasado(self):
        work = self._en_laboratorio()
        tablero = self.service.board(now=momento(SABADO, "14:00"))
        self.assertEqual(tablero["summary"]["atrasados"], 0)
        self.assertEqual(tablero["alert"], "")
        self.service.receive_from_laboratory(work.id, responsible="Ana")
        tarde = self.service.board(now=momento(SABADO, "18:00"))
        self.assertEqual(tarde["summary"]["atrasados"], 0)

    def test_al_vencer_la_hora_el_trabajo_queda_atrasado(self):
        self._en_laboratorio()
        tablero = self.service.board(now=momento(SABADO, "15:01"))
        self.assertEqual(tablero["summary"]["atrasados"], 1)
        self.assertEqual(tablero["rows"][0].status_label, "ATRASADO")
        self.assertEqual(tablero["alert"], "1 trabajo atrasado — contactar laboratorios")

    def test_la_hora_por_defecto_es_configurable_y_no_esta_cableada(self):
        self.assertEqual(self.service.default_expected_time(), time(15, 0))
        with self.repository._connection() as connection:
            connection.execute(
                "UPDATE app_settings SET value_json = ? WHERE key = 'tracking'",
                ('{"default_expected_time":"15:30"}',),
            )
            connection.commit()
        self.assertEqual(self.service.default_expected_time(), time(15, 30))
        work = self._consulta_de_pilar(1)[0]
        self.service.receive_in_asuncion(work.id, responsible="Ana")
        enviado = self.service.send_to_laboratory(
            work.id, self.lab_a.id, expected_date=SABADO, responsible="Ana",
        )
        self.assertEqual(enviado.expected_time, time(15, 30))


class ConfirmacionYContactoTests(TrackingServiceTests):
    def _atrasado(self):
        work = self._consulta_de_pilar(1)[0]
        self.service.receive_in_asuncion(work.id, responsible="Ana")
        return self.service.send_to_laboratory(
            work.id, self.lab_a.id, expected_date=SABADO, expected_time="15:00",
            responsible="Ana",
        )

    def test_confirmar_para_manana_saca_el_trabajo_de_atrasados(self):
        work = self._atrasado()
        ahora = momento(SABADO, "16:00")
        self.assertEqual(self.service.board(now=ahora)["summary"]["atrasados"], 1)

        self.service.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=DOMINGO,
            next_expected_time="15:30", result="Lab confirma envio manana",
            recorded_at=ahora,
        )
        tablero = self.service.board(now=ahora)
        self.assertEqual(tablero["summary"]["atrasados"], 0)
        self.assertEqual(tablero["summary"]["confirmados_para_manana"], 1)
        self.assertEqual(tablero["rows"][0].status_label, "CONFIRMADO_PARA_MAÑANA")

    def test_si_el_nuevo_plazo_vence_vuelve_a_atrasados(self):
        work = self._atrasado()
        self.service.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=DOMINGO, next_expected_time="15:30",
            recorded_at=momento(SABADO, "16:00"),
        )
        self.assertEqual(
            self.service.board(now=momento(DOMINGO, "15:29"))["summary"]["atrasados"], 0,
        )
        self.assertEqual(
            self.service.board(now=momento(DOMINGO, "15:31"))["summary"]["atrasados"], 1,
        )

    def test_el_historial_de_contacto_evita_la_llamada_duplicada(self):
        work = self._atrasado()
        self.service.register_contact(
            work.id, operator="Ana", channel=ContactChannel.CALL,
            result="Lab confirmo salida 14:30", recorded_at=momento(SABADO, "13:12"),
        )
        self.service.register_contact(
            work.id, operator="Carla", channel=ContactChannel.WHATSAPP,
            result="Sin respuesta", recorded_at=momento(SABADO, "14:40"),
        )
        historial = self.service.contact_history(work.id)
        self.assertEqual(len(historial), 2)
        self.assertEqual([contacto.operator for contacto in historial], ["Ana", "Carla"])
        fila = self.service.board(now=momento(SABADO, "15:01"))["rows"][0]
        self.assertEqual(fila.last_news, "14:40 — Carla — whatsapp — Sin respuesta")

    def test_la_confirmacion_queda_registrada_como_novedad_con_autoria(self):
        work = self._atrasado()
        ahora = momento(SABADO, "16:00")
        self.service.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=DOMINGO, recorded_at=ahora,
        )
        contacto = self.service.contact_history(work.id)[-1]
        self.assertEqual(contacto.operator, "Ana")
        self.assertEqual(contacto.recorded_at, ahora)
        self.assertEqual(contacto.next_expected_date, DOMINGO)


class TableroTests(TrackingServiceTests):
    def _escenario_atrasos(self):
        lote = self._consulta_de_pilar(5)
        destinos = (self.lab_a, self.lab_a, self.lab_a, self.lab_b, None)
        for work, destino in zip(lote, destinos):
            self.service.receive_in_asuncion(work.id, responsible="Ana")
            if destino is not None:
                self.service.send_to_laboratory(
                    work.id, destino.id, expected_date=SABADO, expected_time="15:00",
                    responsible="Ana",
                )
        return lote

    def test_agrupa_los_atrasados_por_laboratorio_con_linea_y_whatsapp(self):
        self._escenario_atrasos()
        grupos = self.service.board(now=momento(SABADO, "16:00"))["overdue_groups"]
        self.assertEqual([(grupo["name"], grupo["count"]) for grupo in grupos],
                         [("LAB A", 3), ("LAB B", 1)])
        self.assertEqual(grupos[0]["phone_line"], "021 111 222")
        self.assertEqual(grupos[0]["whatsapp"], "0981 111 222")
        self.assertNotEqual(grupos[0]["phone_line"], grupos[0]["whatsapp"])

    def test_cada_fila_trae_el_contacto_del_laboratorio_resuelto(self):
        self._escenario_atrasos()
        fila = self.service.board(now=momento(SABADO, "16:00"))["rows"][0]
        self.assertTrue(fila.laboratory_name)
        self.assertTrue(fila.phone_line)
        self.assertTrue(fila.whatsapp)
        self.assertEqual(fila.expected_label, "15-08 15:00")

    def test_las_excepciones_se_ordenan_primero(self):
        self._escenario_atrasos()
        filas = self.service.board(now=momento(SABADO, "16:00"))["rows"]
        self.assertTrue(filas[0].overdue)
        self.assertFalse(filas[-1].overdue)

    def test_el_filtro_de_atrasados_deja_solo_excepciones(self):
        self._escenario_atrasos()
        tablero = self.service.board(only_overdue=True, now=momento(SABADO, "16:00"))
        self.assertEqual(len(tablero["rows"]), 4)
        self.assertTrue(all(fila.overdue for fila in tablero["rows"]))

    def test_filtra_por_laboratorio_y_por_estado(self):
        self._escenario_atrasos()
        por_lab = self.service.board(
            laboratory_id=self.lab_b.id, now=momento(SABADO, "16:00"),
        )
        self.assertEqual(len(por_lab["rows"]), 1)
        por_estado = self.service.board(
            status="RECIBIDO_EN_ASUNCION", now=momento(SABADO, "16:00"),
        )
        self.assertEqual(len(por_estado["rows"]), 1)

    def test_el_resumen_muestra_solo_indicadores_operativos(self):
        self._escenario_atrasos()
        resumen = self.service.board(now=momento(SABADO, "16:00"))["summary"]
        self.assertEqual(sorted(resumen), [
            "atrasados", "confirmados_para_manana", "en_laboratorio",
            "en_transito_a_pilar", "listos_para_enviar_a_pilar",
            "por_recibir_en_asuncion",
        ])


class IdentidadYLocalFirstTests(TrackingServiceTests):
    def test_reutiliza_el_pedido_existente_sin_duplicar_al_cliente(self):
        with self.repository._connection() as connection:
            connection.execute(
                """INSERT INTO orders(
                    id,origin,source_reference,delivery_date,branch,customer_name,
                    customer_document,customer_phone,envelope,saleswoman,status,
                    observations,cash_entry_id,created_at,updated_at
                ) VALUES ('order-9','CAJA','','2026-08-14','PC','Cliente 09','','',
                          'S-009','Ana','PENDIENTE','',NULL,
                          '2026-08-14T10:00:00','2026-08-14T10:00:00')"""
            )
            connection.commit()
        lote = self.service.register_pilar_batch(
            [{"envelope": "S-009", "customer_name": "Cliente 09", "order_id": "order-9"}],
            consultation_date=VIERNES, created_by="Nidia",
        )
        self.assertEqual(lote[0].order_id, "order-9")

    def test_pilar_puede_registrar_sin_venta_previa(self):
        lote = self.service.register_pilar_batch(
            [{"envelope": "S-100", "customer_name": "Cliente nuevo"}],
            consultation_date=VIERNES, created_by="Nidia",
        )
        self.assertIsNone(lote[0].order_id)
        self.assertIsNone(lote[0].cash_entry_id)

    def test_la_operacion_completa_no_abre_ninguna_conexion_de_red(self):
        original = socket.socket

        def prohibido(*args, **kwargs):
            raise AssertionError("el seguimiento no debe requerir red")

        socket.socket = prohibido
        try:
            work = self._consulta_de_pilar(1)[0]
            self.service.receive_in_asuncion(work.id, responsible="Ana")
            self.service.send_to_laboratory(
                work.id, self.lab_a.id, expected_date=SABADO, responsible="Ana",
            )
            self.service.register_contact(work.id, operator="Ana", result="Sin novedad")
            self.service.receive_from_laboratory(work.id, responsible="Ana")
            self.service.send_batch_to_pilar([work.id], responsible="Ana")
            self.service.receive_in_pilar(work.id, responsible="Nidia")
            final = self.service.close_work(work.id, responsible="Nidia")
            self.assertIs(final.status, TrackingStatus.CLOSED)
            # El trabajo quedo cerrado: se consulta el alcance completo.
            self.assertTrue(self.service.board(
                scope="TODOS", now=momento(SABADO, "16:00"))["rows"])
        finally:
            socket.socket = original


if __name__ == "__main__":
    unittest.main()
