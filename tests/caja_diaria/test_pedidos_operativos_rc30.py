"""BC-CAJA-PEDIDOS-OPERATIVOS-RC30-001.

Pedidos tiene que poder atenderse sin abrir otra ventana: qué pidió el cliente,
para cuándo, en qué laboratorio está y a quién llamar. Sobre el diseño del
tronco, sin resucitar la grilla de rc.15.
"""
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

import CajaDiaria
from modulos.caja_diaria.application.services import (
    GRUPO_ATRASADOS, GRUPO_PARA_HOY, GRUPO_PROXIMOS,
)
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import SaleItem

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")
HOY = date.today()


def _fecha(desplazamiento):
    return (HOY + timedelta(days=desplazamiento)).strftime("%d-%m-%Y")


class DatosOperativosTests(unittest.TestCase):
    def setUp(self):
        self.directorio = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(
            Path(self.directorio.name) / "caja.sqlite3")
        self.base = {
            "fecha": _fecha(0), "unidad": "PC", "caja_inicial": "500000",
            "cliente_documento": "4.123.456", "cliente_telefono": "0981 555 444",
            "sobre": "583", "vendedora": "Ana", "notas": "", "arm_org": "", "cod": "",
            "armazon": "100000", "cristal": "200000", "laboratorio": "LAB ALFA",
            "receta_dr": "DR", "total": "300000", "efectivo": "300000",
            "tarjeta_cheque": "", "ordenes": "", "cuotas": "", "saldo": "", "gastos": "",
        }

    def tearDown(self):
        self.controller.service.repository.close()
        self.directorio.cleanup()

    def _pedido(self, cliente, entrega, items=()):
        valores = {**self.base, "descripcion": cliente, "fecha_entrega": entrega}
        if items:
            valores["items"] = items
        _, _entry = self.controller.add_manual_entry(valores)
        return next(o for o in self.controller.list_orders("Todos")
                    if o.customer_name == cliente)

    def test_los_tres_grupos_salen_en_orden_de_urgencia(self):
        self._pedido("Atrasado", _fecha(-3))
        self._pedido("De hoy", _fecha(0))
        self._pedido("Futuro", _fecha(5))
        grupos = dict(self.controller.order_operational_groups())
        self.assertEqual(
            list(grupos), [GRUPO_ATRASADOS, GRUPO_PARA_HOY, GRUPO_PROXIMOS])
        self.assertEqual([o.customer_name for o in grupos[GRUPO_ATRASADOS]], ["Atrasado"])
        self.assertEqual([o.customer_name for o in grupos[GRUPO_PARA_HOY]], ["De hoy"])
        self.assertEqual([o.customer_name for o in grupos[GRUPO_PROXIMOS]], ["Futuro"])

    def test_lo_entregado_deja_de_ocupar_los_grupos(self):
        pedido = self._pedido("De hoy", _fecha(0))
        self.controller.update_order_status(
            pedido.id, "LISTO", reason="Listo", responsible="Ana")
        self.controller.update_order_status(
            pedido.id, "ENTREGADO", reason="Entregado", responsible="Ana")
        grupos = dict(self.controller.order_operational_groups())
        self.assertEqual(sum(len(v) for v in grupos.values()), 0)

    def test_la_grilla_sabe_que_pidio_el_cliente_y_a_que_laboratorio_fue(self):
        pedido = self._pedido(
            "Con artículos", _fecha(0),
            items=(SaleItem(description="Cristal orgánico", item_type="Cristal",
                            lens_price=200000, laboratory="LAB BETA"),),
        )
        detalle = self.controller.order_work_details([pedido.id])[pedido.id]
        self.assertIn("Cristal", detalle["trabajo"])
        self.assertEqual(detalle["laboratorio"], "LAB BETA")

    def test_sin_articulos_cae_en_el_laboratorio_de_la_venta(self):
        pedido = self._pedido("Sin artículos", _fecha(0))
        detalle = self.controller.order_work_details([pedido.id])[pedido.id]
        self.assertEqual(detalle["laboratorio"], "LAB ALFA")

    def test_el_contacto_del_laboratorio_sale_del_abm_por_nombre(self):
        self.controller.tracking.save_laboratory(
            name="LAB ALFA", phone_line="021 100 100", whatsapp="0981 100 100")
        contacto = self.controller.laboratory_contact("lab alfa")
        self.assertEqual(contacto["telefono"], "021 100 100")
        self.assertEqual(contacto["whatsapp"], "0981 100 100")
        self.assertEqual(self.controller.laboratory_contact("LAB QUE NO EXISTE"), {})

    def test_la_correccion_sigue_derivandose_del_dominio(self):
        self.assertEqual(
            self.controller.allowed_order_transitions("LISTO"), ("PENDIENTE", "ENTREGADO"))
        self.assertEqual(self.controller.allowed_order_transitions("PENDIENTE"), ("LISTO",))
        with self.assertRaises(ValueError):
            self.controller.allowed_order_transitions("EN CAMINO")


class DerivadosTests(unittest.TestCase):
    def test_el_atraso_es_derivado_de_la_fecha(self):
        hoy = date(2026, 8, 17)
        self.assertEqual(CajaDiaria.texto_atraso(date(2026, 8, 16), hoy, False), "1 día")
        self.assertEqual(CajaDiaria.texto_atraso(date(2026, 8, 14), hoy, False), "3 días")
        self.assertEqual(CajaDiaria.texto_atraso(hoy, hoy, False), "hoy")
        self.assertEqual(CajaDiaria.texto_atraso(date(2026, 8, 20), hoy, False), "")
        # Un pedido entregado no arrastra atraso.
        self.assertEqual(CajaDiaria.texto_atraso(date(2026, 8, 14), hoy, True), "")

    def test_la_novedad_es_compacta(self):
        texto = CajaDiaria.resumen_novedad({
            "new_status": "LISTO", "reason": "Llegó del laboratorio",
            "recorded_at": "2026-08-17T10:30:00+00:00",
        })
        self.assertEqual(texto, "17-08 LISTO · Llegó del laboratorio")
        self.assertEqual(CajaDiaria.resumen_novedad(None), "")
        largo = CajaDiaria.resumen_novedad({
            "new_status": "PENDIENTE", "reason": "x" * 80,
            "recorded_at": "2026-08-17T10:30:00+00:00",
        })
        self.assertLessEqual(len(largo), 60)
        self.assertTrue(largo.endswith("…"))


class GrillaOperativaTests(unittest.TestCase):
    def test_las_columnas_dicen_el_trabajo_y_no_solo_identificadores(self):
        claves = [clave for clave, _t, _a, _an in CajaDiaria.ORDER_COLUMN_SPECS]
        self.assertEqual(
            claves,
            ["entrega", "cliente", "sobre", "trabajo", "laboratorio",
             "estado", "atraso", "novedad"])
        self.assertNotIn("documento", claves)
        self.assertNotIn("origen", claves)

    def test_la_entrada_normal_nunca_es_una_hoja_vacia(self):
        bloque = SOURCE[SOURCE.index("def refrescar_pedidos"):]
        self.assertIn("if (atrasados or para_hoy) else ((GRUPO_PROXIMOS, proximos),)", bloque[:2600])

    def test_los_encabezados_de_grupo_no_son_filas_accionables(self):
        self.assertIn("seleccion[0].startswith(ORDER_ROW_PREFIX_GROUP)", SOURCE)
        self.assertIn('grilla_pedidos.tag_configure(\n        "grupo"', SOURCE)

    def test_tres_acciones_y_el_resto_en_el_menu(self):
        barra = SOURCE[SOURCE.index("boton_avance_pedido = ctk.CTkButton"):
                       SOURCE.index("def actualizar_botones_pedido")]
        self.assertEqual(barra.count("ctk.CTkButton("), 3)
        self.assertIn('label="Corregir estado"', SOURCE)

    def test_el_contacto_prioriza_al_laboratorio_y_cae_en_el_cliente(self):
        bloque = SOURCE[SOURCE.index("def contactar_pedido"):
                        SOURCE.index("def corregir_estado_pedido")]
        self.assertIn('contacto.get("whatsapp") or contacto.get("telefono")', bloque)
        self.assertIn("pedido.customer_phone if pedido else", bloque)
        self.assertIn("enlace_whatsapp(numero)", bloque)


if __name__ == "__main__":
    unittest.main()
