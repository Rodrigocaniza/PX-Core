"""BC-CAJA-RC19: circuito Pilar -> Asuncion -> laboratorio -> Pilar.

Dominio puro: sin SQLite, sin UI, sin red.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE
from modulos.caja_diaria.domain.tracking import (
    ContactChannel,
    ContactRecord,
    Laboratory,
    TrackedWork,
    TrackingStatus,
    group_overdue_by_laboratory,
    operational_summary,
    overdue_alert,
    parse_expected_time,
    reception_progress,
)

VIERNES = date(2026, 8, 14)


def momento(dia: date, hora: str) -> datetime:
    horas, minutos = (int(parte) for parte in hora.split(":"))
    return datetime.combine(dia, time(horas, minutos), tzinfo=BUSINESS_TIMEZONE)


def trabajo(numero: int, **extra) -> TrackedWork:
    base = dict(
        envelope=f"S-{numero:03d}", customer_name=f"Cliente {numero:02d}",
        consultation_date=VIERNES, created_by="Nidia",
    )
    base.update(extra)
    return TrackedWork(**base)


def recibir_en_asuncion(work: TrackedWork) -> TrackedWork:
    return work.transition_to(TrackingStatus.RECEIVED_IN_ASUNCION, responsible="Ana")


class LoteDesdePilarTests(unittest.TestCase):
    def test_quince_enviados_y_catorce_recibidos_dejan_uno_pendiente(self):
        lote = [trabajo(numero) for numero in range(1, 16)]
        recibidos = [recibir_en_asuncion(work) for work in lote[:14]] + lote[14:]
        progreso = reception_progress(recibidos)
        self.assertEqual(progreso["enviados"], 15)
        self.assertEqual(progreso["recibidos"], 14)
        self.assertEqual(progreso["falta_recibir"], 1)

    def test_un_trabajo_ya_enviado_al_laboratorio_sigue_contando_recibido(self):
        lote = [recibir_en_asuncion(trabajo(1)), trabajo(2)]
        lote[0] = lote[0].send_to_laboratory("lab-a", expected_date=VIERNES)
        progreso = reception_progress(lote)
        self.assertEqual((progreso["recibidos"], progreso["falta_recibir"]), (1, 1))

    def test_el_trabajo_nace_enviado_desde_pilar_y_conserva_un_unico_registro(self):
        work = trabajo(1)
        self.assertIs(work.status, TrackingStatus.SENT_FROM_PILAR)
        recibido = recibir_en_asuncion(work)
        self.assertEqual(recibido.id, work.id)
        self.assertEqual(len(recibido.transitions), 1)


class CircuitoCompletoTests(unittest.TestCase):
    def test_recorre_el_circuito_canonico_completo_sin_duplicar(self):
        work = trabajo(1)
        work = recibir_en_asuncion(work)
        work = work.send_to_laboratory("lab-a", expected_date=VIERNES, responsible="Ana")
        for estado in (
            TrackingStatus.RECEIVED_FROM_LABORATORY,
            TrackingStatus.SENT_TO_PILAR,
            TrackingStatus.RECEIVED_IN_PILAR,
            TrackingStatus.CLOSED,
        ):
            work = work.transition_to(estado, responsible="Ana")
        self.assertIs(work.status, TrackingStatus.CLOSED)
        self.assertEqual(len(work.transitions), 6)
        self.assertEqual(
            [transicion.to_status for transicion in work.transitions],
            [
                TrackingStatus.RECEIVED_IN_ASUNCION,
                TrackingStatus.IN_LABORATORY,
                TrackingStatus.RECEIVED_FROM_LABORATORY,
                TrackingStatus.SENT_TO_PILAR,
                TrackingStatus.RECEIVED_IN_PILAR,
                TrackingStatus.CLOSED,
            ],
        )

    def test_rechaza_transiciones_invalidas(self):
        work = trabajo(1)
        for destino in (
            TrackingStatus.IN_LABORATORY,
            TrackingStatus.SENT_TO_PILAR,
            TrackingStatus.RECEIVED_IN_PILAR,
            TrackingStatus.CLOSED,
        ):
            with self.assertRaises(InvalidCashDayError):
                work.transition_to(destino)

    def test_un_trabajo_cerrado_no_admite_mas_transiciones(self):
        work = trabajo(1)
        for estado in (
            TrackingStatus.RECEIVED_IN_ASUNCION, TrackingStatus.IN_LABORATORY,
            TrackingStatus.RECEIVED_FROM_LABORATORY, TrackingStatus.SENT_TO_PILAR,
            TrackingStatus.RECEIVED_IN_PILAR, TrackingStatus.CLOSED,
        ):
            work = work.transition_to(estado)
        with self.assertRaises(InvalidCashDayError):
            work.transition_to(TrackingStatus.RECEIVED_IN_PILAR)

    def test_un_trabajo_mal_hecho_puede_volver_al_laboratorio(self):
        work = recibir_en_asuncion(trabajo(1))
        work = work.send_to_laboratory("lab-a", expected_date=VIERNES)
        work = work.transition_to(TrackingStatus.RECEIVED_FROM_LABORATORY)
        reenviado = work.send_to_laboratory("lab-a", expected_date=VIERNES + timedelta(days=1))
        self.assertIs(reenviado.status, TrackingStatus.IN_LABORATORY)

    def test_el_envio_a_laboratorio_exige_laboratorio(self):
        work = recibir_en_asuncion(trabajo(1))
        with self.assertRaises(InvalidCashDayError):
            work.send_to_laboratory("", expected_date=VIERNES)


class VariosLaboratoriosTests(unittest.TestCase):
    def test_un_mismo_lote_se_reparte_entre_varios_laboratorios(self):
        lote = [recibir_en_asuncion(trabajo(numero)) for numero in range(1, 6)]
        destinos = ("lab-a", "lab-a", "lab-b", "lab-b", "lab-c")
        enviados = [
            work.send_to_laboratory(destino, expected_date=VIERNES)
            for work, destino in zip(lote, destinos)
        ]
        por_laboratorio: dict[str, int] = {}
        for work in enviados:
            por_laboratorio[work.laboratory_id] = por_laboratorio.get(work.laboratory_id, 0) + 1
        self.assertEqual(por_laboratorio, {"lab-a": 2, "lab-b": 2, "lab-c": 1})


class AtrasoTests(unittest.TestCase):
    def _en_laboratorio(self, hora="15:00", dia=VIERNES):
        work = recibir_en_asuncion(trabajo(1))
        return work.send_to_laboratory("lab-a", expected_date=dia, expected_time=hora)

    def test_recibido_a_tiempo_no_queda_atrasado(self):
        work = self._en_laboratorio()
        self.assertFalse(work.is_overdue(momento(VIERNES, "14:30")))
        recibido = work.transition_to(TrackingStatus.RECEIVED_FROM_LABORATORY)
        self.assertFalse(recibido.is_overdue(momento(VIERNES, "18:00")))

    def test_el_vencimiento_marca_atraso_automaticamente(self):
        work = self._en_laboratorio()
        self.assertTrue(work.is_overdue(momento(VIERNES, "15:00")))
        self.assertTrue(work.is_overdue(momento(VIERNES, "16:20")))

    def test_el_atraso_solo_aplica_mientras_esta_en_laboratorio(self):
        work = trabajo(1)
        self.assertFalse(work.is_overdue(momento(VIERNES, "23:00")))

    def test_recibir_del_laboratorio_libera_el_plazo(self):
        work = self._en_laboratorio()
        recibido = work.transition_to(TrackingStatus.RECEIVED_FROM_LABORATORY)
        self.assertIsNone(recibido.expected_date)
        self.assertFalse(recibido.confirmed_for_next_day)

    def test_sin_hora_explicita_usa_el_default_operativo(self):
        work = recibir_en_asuncion(trabajo(1)).send_to_laboratory(
            "lab-a", expected_date=VIERNES,
        )
        self.assertEqual(work.expected_time, time(15, 0))

    def test_la_hora_esperada_admite_formatos_operativos(self):
        self.assertEqual(parse_expected_time("15:30"), time(15, 30))
        self.assertEqual(parse_expected_time("15.30"), time(15, 30))
        self.assertEqual(parse_expected_time("1530"), time(15, 30))
        self.assertIsNone(parse_expected_time(""))
        with self.assertRaises(InvalidCashDayError):
            parse_expected_time("tarde")


class ConfirmadoParaMananaTests(unittest.TestCase):
    def _atrasado(self):
        work = recibir_en_asuncion(trabajo(1))
        return work.send_to_laboratory("lab-a", expected_date=VIERNES, expected_time="15:00")

    def test_la_confirmacion_quita_el_atraso_actual(self):
        work = self._atrasado()
        ahora = momento(VIERNES, "16:00")
        self.assertTrue(work.is_overdue(ahora))
        confirmado = work.register_contact(ContactRecord(
            operator="Ana", channel=ContactChannel.CALL,
            result="Lab confirma envio manana", next_expected_date=VIERNES + timedelta(days=1),
            next_expected_time="15:30", recorded_at=ahora,
        ))
        self.assertTrue(confirmado.confirmed_for_next_day)
        self.assertFalse(confirmado.is_overdue(ahora))
        self.assertEqual(confirmado.expected_date, VIERNES + timedelta(days=1))
        self.assertEqual(confirmado.expected_time, time(15, 30))

    def test_si_el_nuevo_plazo_vence_vuelve_a_estar_atrasado(self):
        confirmado = self._atrasado().register_contact(ContactRecord(
            operator="Ana", result="Llega manana",
            next_expected_date=VIERNES + timedelta(days=1), next_expected_time="15:30",
            recorded_at=momento(VIERNES, "16:00"),
        ))
        sabado = VIERNES + timedelta(days=1)
        self.assertFalse(confirmado.is_overdue(momento(sabado, "15:29")))
        self.assertTrue(confirmado.is_overdue(momento(sabado, "15:30")))

    def test_una_novedad_sin_nuevo_plazo_no_mueve_el_vencimiento(self):
        work = self._atrasado()
        registrado = work.register_contact(ContactRecord(
            operator="Ana", result="No atienden", recorded_at=momento(VIERNES, "16:00"),
        ))
        self.assertFalse(registrado.confirmed_for_next_day)
        self.assertEqual(registrado.expected_date, VIERNES)
        self.assertTrue(registrado.is_overdue(momento(VIERNES, "16:00")))


class HistorialDeContactoTests(unittest.TestCase):
    def test_acumula_las_novedades_en_orden(self):
        work = recibir_en_asuncion(trabajo(1)).send_to_laboratory(
            "lab-a", expected_date=VIERNES,
        )
        work = work.register_contact(ContactRecord(
            operator="Ana", channel=ContactChannel.CALL,
            result="Lab confirmo salida 14:30", recorded_at=momento(VIERNES, "13:12"),
        ))
        work = work.register_contact(ContactRecord(
            operator="Carla", channel=ContactChannel.WHATSAPP,
            result="Sin respuesta", recorded_at=momento(VIERNES, "14:40"),
        ))
        self.assertEqual(len(work.contacts), 2)
        self.assertEqual(work.contacts[0].operator, "Ana")
        self.assertEqual(work.last_contact.operator, "Carla")

    def test_la_ultima_novedad_se_resume_para_la_grilla(self):
        work = recibir_en_asuncion(trabajo(1)).send_to_laboratory(
            "lab-a", expected_date=VIERNES,
        ).register_contact(ContactRecord(
            operator="Ana", channel=ContactChannel.CALL,
            result="Lab confirmo salida 14:30", recorded_at=momento(VIERNES, "13:12"),
        ))
        self.assertEqual(work.last_news(), "13:12 — Ana — llamada — Lab confirmo salida 14:30")

    def test_sin_novedades_la_grilla_muestra_la_ultima_transicion(self):
        work = recibir_en_asuncion(trabajo(1))
        self.assertIn(TrackingStatus.RECEIVED_IN_ASUNCION.value, work.last_news())

    def test_la_novedad_exige_operadora(self):
        with self.assertRaises(InvalidCashDayError):
            ContactRecord(operator="  ")


class LaboratorioTests(unittest.TestCase):
    def test_linea_y_whatsapp_son_independientes(self):
        lab = Laboratory(name="Lab A", phone_line="021 123 456", whatsapp="0981 555 111")
        self.assertNotEqual(lab.phone_line, lab.whatsapp)
        self.assertTrue(lab.has_contact_details)

    def test_el_laboratorio_puede_desactivarse(self):
        self.assertFalse(Laboratory(name="Lab viejo", active=False).active)

    def test_el_laboratorio_exige_nombre(self):
        with self.assertRaises(InvalidCashDayError):
            Laboratory(name="   ")


class AgrupacionYResumenTests(unittest.TestCase):
    def _lote_atrasado(self):
        works = []
        for numero, destino in enumerate(("lab-a", "lab-a", "lab-a", "lab-b"), start=1):
            work = recibir_en_asuncion(trabajo(numero)).send_to_laboratory(
                destino, expected_date=VIERNES, expected_time="15:00",
            )
            works.append(work)
        works.append(recibir_en_asuncion(trabajo(9)))
        return works

    def test_agrupa_los_atrasados_por_laboratorio_con_sus_telefonos(self):
        catalogo = {
            "lab-a": Laboratory(name="LAB A", phone_line="021 111", whatsapp="0981 111", id="lab-a"),
            "lab-b": Laboratory(name="LAB B", phone_line="021 222", whatsapp="0982 222", id="lab-b"),
        }
        grupos = group_overdue_by_laboratory(
            self._lote_atrasado(), catalogo, momento(VIERNES, "16:00"),
        )
        self.assertEqual([(grupo["name"], grupo["count"]) for grupo in grupos],
                         [("LAB A", 3), ("LAB B", 1)])
        self.assertEqual(grupos[0]["phone_line"], "021 111")
        self.assertEqual(grupos[0]["whatsapp"], "0981 111")

    def test_el_resumen_operativo_cuenta_cada_etapa(self):
        resumen = operational_summary(self._lote_atrasado(), momento(VIERNES, "16:00"))
        self.assertEqual(resumen["atrasados"], 4)
        self.assertEqual(resumen["en_laboratorio"], 4)
        self.assertEqual(resumen["por_recibir_en_asuncion"], 0)

    def test_los_confirmados_no_se_cuentan_como_atrasados(self):
        works = self._lote_atrasado()
        works[0] = works[0].register_contact(ContactRecord(
            operator="Ana", result="Manana", next_expected_date=VIERNES + timedelta(days=1),
            recorded_at=momento(VIERNES, "16:00"),
        ))
        resumen = operational_summary(works, momento(VIERNES, "16:00"))
        self.assertEqual(resumen["atrasados"], 3)
        self.assertEqual(resumen["confirmados_para_manana"], 1)

    def test_la_alerta_nombra_la_cantidad_y_desaparece_sin_atrasos(self):
        works = self._lote_atrasado()
        self.assertEqual(
            overdue_alert(works, momento(VIERNES, "16:00")),
            "4 trabajos atrasados — contactar laboratorios",
        )
        self.assertEqual(overdue_alert(works, momento(VIERNES, "10:00")), "")

    def test_los_atrasados_sin_laboratorio_no_rompen_la_agrupacion(self):
        huerfano = recibir_en_asuncion(trabajo(7)).send_to_laboratory(
            "lab-desconocido", expected_date=VIERNES,
        )
        grupos = group_overdue_by_laboratory([huerfano], {}, momento(VIERNES, "16:00"))
        self.assertEqual(grupos[0]["name"], "Sin laboratorio")


class IdentidadTests(unittest.TestCase):
    def test_reutiliza_la_identidad_del_trabajo_existente(self):
        work = trabajo(1, order_id="order-1", cash_entry_id="entry-1")
        self.assertEqual(work.order_id, "order-1")
        self.assertEqual(work.cash_entry_id, "entry-1")

    def test_admite_registro_de_pilar_sin_venta_previa(self):
        work = trabajo(1)
        self.assertIsNone(work.order_id)
        self.assertIsNone(work.cash_entry_id)

    def test_exige_al_menos_sobre_o_cliente(self):
        with self.assertRaises(InvalidCashDayError):
            TrackedWork(envelope="", customer_name="")


if __name__ == "__main__":
    unittest.main()
