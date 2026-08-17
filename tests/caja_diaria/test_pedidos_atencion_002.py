"""BC-CAJA-PEDIDOS-ATENCION-002 quedó superada por el tronco recuperado.

El slice de rc.15 reescribía la grilla de Pedidos con chips flotantes sobre el
frame contenedor. RC22/RC23 ya habían resuelto lo mismo mejor —el estado es un
tag de la propia fila— y RC28 hizo que la alerta transporte su filtro. Al
consolidar se eligió el diseño posterior, así que aquel contrato dejó de valer.

Este archivo conserva la decisión en forma verificable: comprueba que el diseño
vigente es el del tronco y que no volvieron los chips flotantes.
"""
from pathlib import Path
import unittest

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


class PedidosDisenoVigenteTests(unittest.TestCase):
    def test_la_consulta_canonica_sigue_siendo_requieren_atencion(self):
        from modulos.caja_diaria.application.services import FILTRO_REQUIEREN_ATENCION

        self.assertEqual(FILTRO_REQUIEREN_ATENCION, "Requieren atención")
        self.assertIn(
            "filtro_pedidos = ctk.StringVar(value=FILTRO_REQUIEREN_ATENCION)", SOURCE)

    def test_la_alerta_transporta_su_filtro(self):
        # RC28: el número de la alerta y lo que abre el clic no pueden discrepar.
        self.assertIn("def orders_alert(", Path(
            "modulos/caja_diaria/ui/controller.py").read_text(encoding="utf-8"))
        self.assertIn("abrir_pedidos_desde_alerta", SOURCE)

    def test_el_estado_va_anclado_a_la_fila_y_no_como_capa_flotante(self):
        # RC23 eliminó los chips flotantes como defecto: no deben volver.
        self.assertIn('grilla_pedidos.tag_configure(\n            f"estado_', SOURCE)
        self.assertNotIn("chips_pedidos", SOURCE)
        self.assertNotIn("posicionar_chips_pedidos", SOURCE)

    def test_lo_que_aportaba_rc15_ya_esta_sobre_el_diseno_del_tronco(self):
        # BC-CAJA-PEDIDOS-OPERATIVOS-RC30-001 cerró la deuda: agrupación,
        # "Última novedad" y corrección con lista cerrada viven ahora sobre el
        # diseño del tronco, sin resucitar la grilla de rc.15.
        self.assertIn("ORDER_ROW_PREFIX_GROUP", SOURCE)
        self.assertIn("encabezado_grupo(", SOURCE)
        self.assertIn("resumen_novedad(", SOURCE)
        self.assertIn("controller.allowed_order_transitions(actual)", SOURCE)


if __name__ == "__main__":
    unittest.main()
