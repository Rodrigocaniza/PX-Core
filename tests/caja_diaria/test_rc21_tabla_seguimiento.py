"""BC-CAJA-RC21: la tabla de Seguimiento orientada al circuito logistico.

Cinco columnas, sin Vendedora, con el estado fisico siempre visible y las
condiciones derivadas anteponiendose sin reemplazarlo.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.application.tracking_service import (
    ALERTA_ATRASADO,
    SCOPE_TODOS,
    ALERTA_CONFIRMADO,
    ESTADOS_VISIBLES,
    ETIQUETAS_ESTADO,
    SIN_LABORATORIO,
    TrackingService,
)
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, CashEntry, SaleItem
from modulos.caja_diaria.domain.tracking import TrackingStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
FUENTE = open("CajaDiaria.py", encoding="utf-8").read()
TABLA = FUENTE[
    FUENTE.index("COLUMNAS_SEGUIMIENTO = ("):FUENTE.index("lista_seguimiento = ctk.CTkScrollableFrame")
]


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class ColumnasTests(unittest.TestCase):
    def test_las_columnas_estan_en_el_orden_pedido(self):
        """RC24 agrega el selector al inicio y Observación al final."""
        claves = [
            linea.split('("')[1].split('"')[0]
            for linea in TABLA.splitlines() if linea.strip().startswith('("')
        ]
        self.assertEqual(claves, ["sel", "sobre", "cliente", "tipo",
                                  "laboratorio", "estado", "observacion"])

    def test_vendedora_ya_no_se_muestra_en_seguimiento(self):
        self.assertNotIn("vendedora", TABLA.lower())
        self.assertNotIn("Vendedora", TABLA)

    def test_el_dato_de_vendedora_sigue_existiendo_en_el_dominio(self):
        # Solo deja de mostrarse aca: ventas y comisiones no se tocan.
        from modulos.caja_diaria.domain.models import CashEntry as Entry
        self.assertIn("saleswoman", Entry.__dataclass_fields__)
        self.assertIn('("vendedora", "Vendedora"', FUENTE)

    def test_laboratorio_va_inmediatamente_despues_de_tipo_de_trabajo(self):
        claves = [
            linea.split('("')[1].split('"')[0]
            for linea in TABLA.splitlines() if linea.strip().startswith('("')
        ]
        self.assertEqual(claves[claves.index("tipo") + 1], "laboratorio")

    def test_observacion_es_la_columna_que_se_expande(self):
        ultima = [l for l in TABLA.splitlines()
                  if l.strip().startswith('("observacion"')][0]
        self.assertTrue(ultima.rstrip().endswith("True),"))


class EstadosTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = CashDayService(self.repository)
        self.tracking = TrackingService(self.repository)
        self.lab = self.tracking.save_laboratory(
            name="LAB CENTRAL", phone_line="021 111 222", whatsapp="0981 111 222",
        )

    def tearDown(self):
        self.repository.close()

    def _trabajo(self, envelope="P-001", observacion="Armazon + cristales"):
        return self.tracking.register_pilar_batch(
            [{"envelope": envelope, "customer_name": "Cliente Pilar 01",
              "observations": observacion}],
            consultation_date=HOY, created_by="Nidia",
        )[0]

    def _fila(self, **kwargs):
        # Alcance completo: estos casos verifican el rotulo de cada etapa,
        # incluida RECIBIDO EN PILAR, que ya no esta en la vista activa.
        kwargs.setdefault("scope", SCOPE_TODOS)
        return self.tracking.board(**kwargs)["rows"][0]

    def test_los_seis_estados_canonicos_tienen_rotulo_legible(self):
        self.assertEqual([ETIQUETAS_ESTADO[e] for e in ESTADOS_VISIBLES], [
            "ENVIADO DESDE PILAR", "RECIBIDO EN ASUNCIÓN", "EN LABORATORIO",
            "RECIBIDO DEL LABORATORIO", "ENVIADO A PILAR", "RECIBIDO EN PILAR",
        ])

    def test_cerrado_no_es_un_estado_visible_del_circuito(self):
        self.assertNotIn(TrackingStatus.CLOSED, ESTADOS_VISIBLES)
        self.assertEqual(len(ESTADOS_VISIBLES), 6)

    def test_recorre_los_seis_estados_mostrando_la_etapa_real(self):
        work = self._trabajo()
        vistos = [self._fila().physical_status]

        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        vistos.append(self._fila().physical_status)

        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY + timedelta(days=1), responsible="Ana")
        vistos.append(self._fila().physical_status)

        self.tracking.receive_from_laboratory(work.id, responsible="Ana")
        vistos.append(self._fila().physical_status)

        self.tracking.send_batch_to_pilar([work.id], responsible="Ana")
        vistos.append(self._fila().physical_status)

        self.tracking.receive_in_pilar(work.id, responsible="Nidia")
        vistos.append(self._fila().physical_status)

        self.assertEqual(vistos, [ETIQUETAS_ESTADO[e] for e in ESTADOS_VISIBLES])

    def test_recibido_en_pilar_cierra_el_circuito_sin_mostrarse_cerrado(self):
        work = self._trabajo()
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY + timedelta(days=1), responsible="Ana")
        self.tracking.receive_from_laboratory(work.id, responsible="Ana")
        self.tracking.send_batch_to_pilar([work.id], responsible="Ana")
        self.tracking.receive_in_pilar(work.id, responsible="Nidia")
        fila = self._fila()
        self.assertEqual(fila.physical_status, "RECIBIDO EN PILAR")
        self.assertEqual(fila.status_display, "RECIBIDO EN PILAR")
        self.assertEqual(fila.alert, "")

    def test_atrasado_antepone_pero_conserva_la_etapa_fisica(self):
        work = self._trabajo()
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY, expected_time="15:00", responsible="Ana")
        fila = self._fila(now=momento(HOY, "16:00"))
        self.assertTrue(fila.overdue)
        self.assertEqual(fila.alert, ALERTA_ATRASADO)
        self.assertEqual(fila.physical_status, "EN LABORATORIO")
        self.assertEqual(fila.status_display, "ATRASADO · EN LABORATORIO")

    def test_confirmado_antepone_pero_conserva_la_etapa_fisica(self):
        work = self._trabajo()
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY, expected_time="15:00", responsible="Ana")
        self.tracking.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=HOY + timedelta(days=1),
            next_expected_time="15:30", recorded_at=momento(HOY, "16:00"))
        fila = self._fila(now=momento(HOY, "16:00"))
        self.assertFalse(fila.overdue)
        self.assertEqual(fila.alert, ALERTA_CONFIRMADO)
        self.assertEqual(fila.physical_status, "EN LABORATORIO")
        self.assertEqual(fila.status_display, "CONFIRMADO PARA MAÑANA · EN LABORATORIO")

    def test_ninguna_condicion_derivada_se_persiste(self):
        work = self._trabajo()
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY, expected_time="15:00", responsible="Ana")
        guardado = self.repository.get_tracked_work(work.id)
        self.assertIs(guardado.status, TrackingStatus.IN_LABORATORY)
        estados = {r[0] for r in self.repository._connection().__enter__().execute(
            "SELECT DISTINCT status FROM tracked_works")}
        self.assertTrue(estados <= {e.value for e in TrackingStatus})
        self.assertNotIn("ATRASADO", estados)
        self.assertNotIn("CONFIRMADO_PARA_MAÑANA", estados)


class LaboratorioYTipoTests(EstadosTests):
    def test_sin_laboratorio_asignado_muestra_sin_asignar(self):
        self._trabajo()
        self.assertEqual(self._fila().laboratory_name, SIN_LABORATORIO)

    def test_una_vez_asignado_muestra_el_nombre(self):
        work = self._trabajo()
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY + timedelta(days=1), responsible="Ana")
        self.assertEqual(self._fila().laboratory_name, "LAB CENTRAL")

    def test_el_contacto_del_laboratorio_sigue_accesible(self):
        work = self._trabajo()
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=HOY, expected_time="15:00", responsible="Ana")
        fila = self._fila(now=momento(HOY, "16:00"))
        self.assertEqual(fila.phone_line, "021 111 222")
        self.assertEqual(fila.whatsapp, "0981 111 222")
        self.assertNotEqual(fila.phone_line, fila.whatsapp)
        grupo = self.tracking.board(now=momento(HOY, "16:00"))["overdue_groups"][0]
        self.assertEqual(grupo["phone_line"], "021 111 222")
        self.assertEqual(grupo["whatsapp"], "0981 111 222")

    def test_el_tipo_de_trabajo_sale_de_la_observacion_del_pedido(self):
        self._trabajo(observacion="Armazon + cristales\nsegunda linea ignorada")
        self.assertEqual(self._fila().work_type, "Armazon + cristales")

    def test_sin_observacion_el_tipo_queda_vacio_sin_romper(self):
        self._trabajo(observacion="")
        self.assertEqual(self._fila().work_type, "")


class PresentacionTests(unittest.TestCase):
    def test_el_estado_se_dibuja_como_chip_dentro_de_la_fila(self):
        self.assertIn("COLORES_ESTADO_SEGUIMIENTO", FUENTE)
        # El chip es hijo de la celda de la fila, no una capa flotante.
        self.assertIn("celda_estado = ctk.CTkFrame(marco_fila", FUENTE)
        self.assertNotIn("posicionar_chips_seguimiento", FUENTE)

    def test_hay_un_color_por_cada_estado_visible(self):
        bloque = FUENTE[
            FUENTE.index("COLORES_ESTADO_SEGUIMIENTO = {"):FUENTE.index("COLOR_CHIP_ATRASADO")
        ]
        for estado in ESTADOS_VISIBLES:
            self.assertIn(ETIQUETAS_ESTADO[estado], bloque)

    def test_el_atraso_tiene_prioridad_visual_roja(self):
        self.assertIn('COLOR_CHIP_ATRASADO = ("#FDECEC", "#E5A3A3", "#A32626")', FUENTE)

    def test_no_queda_ninguna_capa_flotante_de_estado(self):
        """El chip ya no se posiciona a mano: se desplaza con su fila."""
        for residuo in ("posicionar_chips_seguimiento", "posicionar_chips_pedidos",
                        "chips_pedidos", 'estado_seguimiento["chips"]'):
            self.assertNotIn(residuo, FUENTE)
        self.assertIn("lista_seguimiento = ctk.CTkScrollableFrame", FUENTE)


class AnchosResponsiveTests(unittest.TestCase):
    def _anchos(self):
        anchos = []
        for linea in TABLA.splitlines():
            if linea.strip().startswith('("'):
                anchos.append(int(linea.split(",")[2].strip()))
        return anchos

    def test_las_cinco_columnas_entran_sin_scroll_horizontal_en_1920(self):
        # contenido_ancho full-hd = 1890, menos scrollbar y margenes.
        self.assertLessEqual(sum(self._anchos()) + 40, 1890)

    def test_tambien_entran_en_el_ancho_compacto_de_1366(self):
        # contenido_ancho compacto = 1330.
        self.assertLessEqual(sum(self._anchos()) + 40, 1330)

    def test_la_prioridad_de_ancho_respeta_el_orden_pedido(self):
        sel, sobre, cliente, tipo, laboratorio, estado, observacion = self._anchos()
        self.assertLess(sel, sobre)
        self.assertLess(sobre, cliente)
        self.assertGreaterEqual(cliente, laboratorio)
        self.assertGreaterEqual(tipo, laboratorio)
        # Estado es la mas ancha: aloja "CONFIRMADO PARA MAÑANA · <etapa>".
        self.assertGreater(estado, cliente)
        self.assertGreater(observacion, laboratorio)


if __name__ == "__main__":
    unittest.main()
