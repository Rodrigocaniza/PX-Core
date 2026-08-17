"""BC-CAJA-RC26: la tabla de Seguimiento no se reconstruye para repintarse.

El parpadeo medido: un refresco destruia y volvia a crear los ~440 widgets de
la tabla —unos 29 por fila— y tardaba cerca de 0,9 s con la tabla vacia a la
vista. Ocurria en cada refresco, incluso cuando la lista era exactamente la
misma, y tambien al marcar o limpiar la seleccion, que no cambia ninguna fila.

Estas pruebas fijan el contrato del codigo. La medicion real sobre la ventana
la hace `tools/probe_caja_reuso_filas.py`, que imprime cuantos widgets se
destruyen y se crean en un refresco: con reuso tiene que ser cero.
"""

from __future__ import annotations

import unittest

FUENTE = open("CajaDiaria.py", encoding="utf-8").read()
REFRESCO = FUENTE[
    FUENTE.index("    def refrescar_seguimiento("):
    FUENTE.index("    def marcar_no_llego(")
]


class ReusoDeFilasTests(unittest.TestCase):
    def test_la_fila_se_crea_una_vez_y_despues_se_repinta(self):
        self.assertIn("def crear_fila(identificador):", REFRESCO)
        self.assertIn("def pintar_fila(fila, indice, posicion):", REFRESCO)
        self.assertIn(
            'widgets = estado_seguimiento["widgets"].get(identificador)', REFRESCO)

    def test_solo_se_destruye_lo_que_dejo_de_estar(self):
        self.assertIn(
            'for identificador in set(estado_seguimiento["widgets"]) - set(',
            REFRESCO)

    def test_ya_no_se_destruye_la_tabla_entera_en_cada_refresco(self):
        """El patron exacto que producia el parpadeo."""
        self.assertNotIn('for widgets in estado_seguimiento["widgets"].values():\n'
                         '            widgets["fila"].destroy()', REFRESCO)
        self.assertNotIn('estado_seguimiento["widgets"].clear()', REFRESCO)

    def test_el_encabezado_de_grupo_tambien_se_reutiliza(self):
        self.assertIn("def pintar_grupo(", REFRESCO)
        self.assertIn('estado_seguimiento["secciones"].get(clave_grupo)', REFRESCO)
        # Un grupo que se queda sin filas se oculta, no se destruye.
        self.assertIn("cabecera.grid_remove()", REFRESCO)

    def test_las_secciones_se_indexan_por_grupo(self):
        self.assertIn('"secciones": {}', FUENTE)


class SinReconstruirPorSeleccionTests(unittest.TestCase):
    def test_marcar_todo_o_limpiar_no_refresca_la_tabla(self):
        bloque = FUENTE[
            FUENTE.index("    def aplicar_marcas_visibles():"):
            FUENTE.index("    def trabajo_seleccionado():")
        ]
        self.assertIn("def seleccionar_todo():", bloque)
        self.assertIn("def limpiar_seleccion():", bloque)
        # Antes ambas llamaban a refrescar_seguimiento() y reconstruian todo.
        self.assertNotIn("refrescar_seguimiento()", bloque)
        llamadas = [linea.strip() for linea in bloque.splitlines()
                    if linea.strip() == "aplicar_marcas_visibles()"]
        self.assertEqual(len(llamadas), 2)

    def test_las_marcas_se_sincronizan_sobre_los_widgets_existentes(self):
        bloque = FUENTE[FUENTE.index("    def aplicar_marcas_visibles():"):]
        self.assertIn('marca = widgets.get("marca")', bloque[:900])
        self.assertIn("marca.select()", bloque[:900])
        self.assertIn("marca.deselect()", bloque[:900])

    def test_la_fila_conserva_su_checkbox_para_poder_sincronizarlo(self):
        self.assertIn('"marca": marca', REFRESCO)


class UnSoloRepintadoTests(unittest.TestCase):
    def test_la_lista_se_descuelga_mientras_se_rehace(self):
        """Sin esto, Tk repinta a medida que se reposiciona cada fila."""
        self.assertIn("lista_seguimiento.grid_remove()", REFRESCO)
        self.assertIn("lista_seguimiento.grid()", REFRESCO)

    def test_la_lista_vuelve_aunque_el_repintado_falle(self):
        bloque = REFRESCO[REFRESCO.index("lista_seguimiento.grid_remove()"):]
        self.assertIn("try:", bloque[:120])
        self.assertIn("finally:", bloque)
        self.assertLess(bloque.index("finally:"),
                        bloque.index("lista_seguimiento.grid()"))


class SinRelayoutEnReposoTests(unittest.TestCase):
    """El otro sospechoso habitual, descartado por medicion.

    `aplicar_macro_layout` llama a `update_idletasks()` dentro del manejador de
    `<Configure>`, que es la receta clasica de un ciclo de relayout. La sonda
    midio la ventana en reposo en ambas pestañas: 0 `place()`, 0 `<Configure>`
    y 0 widgets creados o destruidos. No es la causa, y el debounce que lo
    evita tiene que seguir estando.
    """

    def test_el_relayout_sigue_debounceado(self):
        self.assertIn("def programar_macro_layout(_event=None):", FUENTE)
        self.assertIn('if estado_layout["after"] is not None:', FUENTE)
        self.assertIn("ventana.after_cancel(estado_layout[\"after\"])", FUENTE)
        self.assertIn('estado_layout["after"] = ventana.after_idle(aplicar_macro_layout)',
                      FUENTE)

    def test_el_reloj_no_toca_la_tabla(self):
        bloque = FUENTE[FUENTE.index("def actualizar_reloj():"):]
        self.assertNotIn("refrescar_seguimiento", bloque[:400])

    def test_no_hay_refresco_periodico_de_seguimiento(self):
        """Ningun timer puede estar repintando la tabla sola."""
        for patron in ("after(1000, refrescar_seguimiento",
                       "after_idle(refrescar_seguimiento",
                       "after(500, refrescar_seguimiento"):
            self.assertNotIn(patron, FUENTE)


if __name__ == "__main__":
    unittest.main()
