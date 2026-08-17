"""BC-CAJA-RECOVERED-TRUNK-CONSOLIDATION-001: disponible vs no disponible.

Una acción disponible se ve sólida; una no disponible se ve apagada de verdad y
dice por qué. Aplica tanto a las tres acciones de Seguimiento como a las de
Pedidos, sin tocar el diseño posterior de la línea recuperada.
"""
from pathlib import Path
import unittest

import CajaDiaria

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def _luminancia(color):
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class ContrasteAccionesTests(unittest.TestCase):
    def test_la_paleta_apagada_no_es_una_variante_del_blanco(self):
        for color in (CajaDiaria.COLOR_ACCION_INACTIVA,
                      CajaDiaria.COLOR_ACCION_INACTIVA_TEXTO,
                      CajaDiaria.COLOR_ACCION_INACTIVA_BORDE):
            self.assertRegex(color, r"^#[0-9A-Fa-f]{6}$")
        canales = [int(CajaDiaria.COLOR_ACCION_INACTIVA[i:i + 2], 16) for i in (1, 3, 5)]
        self.assertLess(max(canales), 240, CajaDiaria.COLOR_ACCION_INACTIVA)
        texto = [int(CajaDiaria.COLOR_ACCION_INACTIVA_TEXTO[i:i + 2], 16) for i in (1, 3, 5)]
        self.assertLess(max(texto), 170, CajaDiaria.COLOR_ACCION_INACTIVA_TEXTO)

    def test_el_salto_entre_disponible_y_no_disponible_es_medible(self):
        apagado = _luminancia(CajaDiaria.COLOR_ACCION_INACTIVA)
        for activo in ("#12855A", "#B42318", "#B45309"):
            self.assertIn(activo, SOURCE, activo)
            self.assertGreater(apagado - _luminancia(activo), 0.30, activo)

    def test_disponibilidad_cambia_fondo_texto_y_borde_juntos(self):
        self.assertIn(
            'def aplicar_disponibilidad(boton, habilitado, color_activo, motivo=""):', SOURCE)
        activo = SOURCE[SOURCE.index("    if habilitado:\n        boton.configure("):]
        activo = activo[:activo.index("    else:")]
        self.assertIn("fg_color=color_activo", activo)
        self.assertIn('text_color="#FFFFFF"', activo)
        self.assertIn("border_width=0", activo)
        apagado = SOURCE[SOURCE.index('state="disabled", fg_color=COLOR_ACCION_INACTIVA'):][:400]
        self.assertIn("COLOR_ACCION_INACTIVA_TEXTO", apagado)
        self.assertIn("COLOR_ACCION_INACTIVA_BORDE", apagado)

    def test_las_tres_acciones_de_seguimiento_pasan_por_el_ayudante(self):
        # RC24 dejó tres acciones: Acción siguiente, Novedad y Más. "Más" abre
        # un menú y siempre está disponible; las otras dos dependen del estado.
        self.assertIn("aplicar_disponibilidad(\n            boton_accion_siguiente,", SOURCE)
        self.assertIn("aplicar_disponibilidad(\n            boton_novedad, hay,", SOURCE)
        self.assertNotIn(
            'boton_accion_siguiente.configure(\n            text=info["label"] or "Acción siguiente",\n'
            '            state=', SOURCE)

    def test_las_acciones_de_pedidos_pasan_por_el_ayudante(self):
        # Pedidos pasó a las mismas tres acciones que Seguimiento.
        self.assertIn("aplicar_disponibilidad(\n            boton_avance_pedido,", SOURCE)
        self.assertIn("aplicar_disponibilidad(\n            boton_contactar_pedido,", SOURCE)
        self.assertNotIn(
            'botones_estado_pedido["LISTO"].configure(state="normal"', SOURCE)

    def test_cada_accion_apagada_explica_por_que(self):
        self.assertIn("class AvisoDeshabilitado:", SOURCE)
        self.assertIn('AvisoDeshabilitado.asignar(boton, "" if habilitado else motivo)', SOURCE)
        self.assertIn("Marcá uno o varios trabajos para registrar una novedad.", SOURCE)
        self.assertIn("Marcá un pedido para ver su próxima acción.", SOURCE)
        self.assertIn("Marcá un pedido para contactar a su laboratorio o al cliente.", SOURCE)
        # La razón que ya calcula el dominio se reusa en vez de inventar otra.
        self.assertIn('info.get("reason")', SOURCE)

    def test_el_aviso_no_abre_una_ventana_flotante(self):
        # RC4 exige marco nativo; el aviso se dibuja dentro de la ventana.
        self.assertNotIn("overrideredirect(True)", SOURCE)
        self.assertIn("raiz = self.widget.winfo_toplevel()", SOURCE)


if __name__ == "__main__":
    unittest.main()
