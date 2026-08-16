"""BC-CAJA-RC19: persistencia local-first del seguimiento."""

from __future__ import annotations

import sqlite3
import unittest
from datetime import date, time, timedelta

from modulos.caja_diaria.domain.tracking import (
    ContactChannel,
    ContactRecord,
    Laboratory,
    TrackedWork,
    TrackingStatus,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

VIERNES = date(2026, 8, 14)


class TrackingRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.lab_a = self.repository.save_laboratory(
            Laboratory(name="LAB A", phone_line="021 111 222", whatsapp="0981 111 222")
        )
        self.lab_b = self.repository.save_laboratory(
            Laboratory(name="LAB B", phone_line="021 333 444", whatsapp="0982 333 444")
        )

    def tearDown(self):
        self.repository.close()

    def _trabajo(self, numero: int) -> TrackedWork:
        return TrackedWork(
            envelope=f"S-{numero:03d}", customer_name=f"Cliente {numero:02d}",
            consultation_date=VIERNES, created_by="Nidia",
        )

    def test_la_migracion_016_se_aplica(self):
        with self.repository._connection() as connection:
            aplicadas = {
                row[0] for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
        self.assertIn("016", aplicadas)

    def test_guarda_y_recupera_laboratorios_con_linea_y_whatsapp_distintos(self):
        recuperado = self.repository.get_laboratory(self.lab_a.id)
        self.assertEqual(recuperado.name, "LAB A")
        self.assertEqual(recuperado.phone_line, "021 111 222")
        self.assertEqual(recuperado.whatsapp, "0981 111 222")
        self.assertNotEqual(recuperado.phone_line, recuperado.whatsapp)

    def test_el_nombre_de_laboratorio_es_unico(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_laboratory(Laboratory(name="lab a"))

    def test_lista_solo_laboratorios_activos_cuando_se_pide(self):
        self.repository.save_laboratory(Laboratory(name="LAB VIEJO", active=False))
        todos = self.repository.list_laboratories()
        activos = self.repository.list_laboratories(only_active=True)
        self.assertEqual(len(todos), 3)
        self.assertEqual([lab.name for lab in activos], ["LAB A", "LAB B"])

    def test_persiste_el_trabajo_con_su_traza_completa(self):
        work = self._trabajo(1)
        work = work.transition_to(TrackingStatus.RECEIVED_IN_ASUNCION, responsible="Ana")
        work = work.send_to_laboratory(
            self.lab_a.id, expected_date=VIERNES, expected_time="15:30", responsible="Ana",
        )
        work = work.register_contact(ContactRecord(
            operator="Ana", channel=ContactChannel.CALL, result="Sale 14:30",
        ))
        self.repository.save_tracked_work(work)

        recuperado = self.repository.get_tracked_work(work.id)
        self.assertIs(recuperado.status, TrackingStatus.IN_LABORATORY)
        self.assertEqual(recuperado.laboratory_id, self.lab_a.id)
        self.assertEqual(recuperado.expected_date, VIERNES)
        self.assertEqual(recuperado.expected_time, time(15, 30))
        self.assertEqual(len(recuperado.transitions), 2)
        self.assertEqual(len(recuperado.contacts), 1)
        self.assertEqual(recuperado.contacts[0].result, "Sale 14:30")
        self.assertEqual(recuperado.consultation_date, VIERNES)

    def test_guardar_dos_veces_no_duplica_el_trabajo_ni_su_traza(self):
        work = self._trabajo(1).transition_to(
            TrackingStatus.RECEIVED_IN_ASUNCION, responsible="Ana",
        )
        self.repository.save_tracked_work(work)
        self.repository.save_tracked_work(work)
        avanzado = work.send_to_laboratory(self.lab_a.id, expected_date=VIERNES)
        self.repository.save_tracked_work(avanzado)

        self.assertEqual(len(self.repository.list_tracked_works()), 1)
        recuperado = self.repository.get_tracked_work(work.id)
        self.assertEqual(len(recuperado.transitions), 2)

    def test_persiste_la_confirmacion_para_manana(self):
        work = self._trabajo(1).transition_to(TrackingStatus.RECEIVED_IN_ASUNCION)
        work = work.send_to_laboratory(self.lab_a.id, expected_date=VIERNES)
        work = work.register_contact(ContactRecord(
            operator="Ana", result="Llega manana",
            next_expected_date=VIERNES + timedelta(days=1), next_expected_time="15:30",
        ))
        self.repository.save_tracked_work(work)

        recuperado = self.repository.get_tracked_work(work.id)
        self.assertTrue(recuperado.confirmed_for_next_day)
        self.assertEqual(recuperado.expected_date, VIERNES + timedelta(days=1))
        self.assertEqual(recuperado.contacts[0].next_expected_time, time(15, 30))

    def test_filtra_por_estado_laboratorio_y_fecha_de_consulta(self):
        pendiente = self._trabajo(1)
        enviado = self._trabajo(2).transition_to(
            TrackingStatus.RECEIVED_IN_ASUNCION
        ).send_to_laboratory(self.lab_b.id, expected_date=VIERNES)
        for work in (pendiente, enviado):
            self.repository.save_tracked_work(work)

        self.assertEqual(
            len(self.repository.list_tracked_works(status="ENVIADO_DESDE_PILAR")), 1,
        )
        self.assertEqual(
            len(self.repository.list_tracked_works(laboratory_id=self.lab_b.id)), 1,
        )
        self.assertEqual(
            len(self.repository.list_tracked_works(consultation_date=VIERNES)), 2,
        )
        self.assertEqual(
            len(self.repository.list_tracked_works(consultation_date=VIERNES + timedelta(days=5))),
            0,
        )

    def test_un_trabajo_enlaza_como_maximo_un_pedido(self):
        primero = TrackedWork(envelope="S-1", customer_name="A", order_id="order-1")
        segundo = TrackedWork(envelope="S-2", customer_name="B", order_id="order-1")
        with self.repository._connection() as connection:
            connection.execute(
                """INSERT INTO orders(
                    id,origin,source_reference,delivery_date,branch,customer_name,
                    customer_document,customer_phone,envelope,saleswoman,status,
                    observations,cash_entry_id,created_at,updated_at
                ) VALUES ('order-1','CAJA','','2026-08-14','PC','A','','','S-1','Ana',
                          'PENDIENTE','',NULL,'2026-08-14T10:00:00','2026-08-14T10:00:00')"""
            )
            connection.commit()
        self.repository.save_tracked_work(primero)
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_tracked_work(segundo)

    def test_el_trabajo_sin_sobre_ni_cliente_es_rechazado_por_la_base(self):
        with self.repository._connection() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """INSERT INTO tracked_works(
                        id,envelope,customer_name,status,origin_branch,
                        confirmed_for_next_day,observations,created_by,created_at,updated_at
                    ) VALUES ('x','','','ENVIADO_DESDE_PILAR','PILAR',0,'','',
                              '2026-08-14T10:00:00','2026-08-14T10:00:00')"""
                )

    def test_la_base_rechaza_un_estado_fuera_del_circuito(self):
        with self.repository._connection() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """INSERT INTO tracked_works(
                        id,envelope,customer_name,status,origin_branch,
                        confirmed_for_next_day,observations,created_by,created_at,updated_at
                    ) VALUES ('x','S-1','A','ENTREGADO_AL_CLIENTE','PILAR',0,'','',
                              '2026-08-14T10:00:00','2026-08-14T10:00:00')"""
                )

    def test_el_default_operativo_de_hora_queda_configurable(self):
        with self.repository._connection() as connection:
            fila = connection.execute(
                "SELECT value_json FROM app_settings WHERE key = 'tracking'"
            ).fetchone()
        self.assertIn("default_expected_time", fila[0])
        self.assertIn("15:00", fila[0])

    def test_la_base_sobrevive_al_chequeo_de_integridad(self):
        self.repository.save_tracked_work(self._trabajo(1))
        self.repository.integrity_check()


if __name__ == "__main__":
    unittest.main()
