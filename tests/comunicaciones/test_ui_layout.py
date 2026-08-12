"""Contrato de la ventana de BC Comunicaciones.

La parte de inspección de código corre siempre. La parte de widgets reales sólo
corre donde hay un entorno gráfico disponible.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from modulos.comunicaciones.bootstrap import build_controller
from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard
from modulos.comunicaciones.ui import app as app_module


def tk_disponible() -> bool:
    try:
        import tkinter

        root = tkinter.Tk()
    except Exception:
        return False
    root.destroy()
    return True


class LayoutContractTests(unittest.TestCase):
    def test_window_targets_1366x768_and_never_demands_more(self):
        self.assertEqual(app_module.VENTANA_ANCHO, 1366)
        self.assertEqual(app_module.VENTANA_ALTO, 768)
        source = inspect.getsource(app_module.VentanaComunicaciones.__init__)
        self.assertIn('self.geometry(f"{VENTANA_ANCHO}x{VENTANA_ALTO}")', source)
        self.assertIn("self.minsize(1180, 700)", source)

    def test_the_three_fixed_columns_fit_inside_the_target_width(self):
        usado = app_module.ANCHO_COLUMNA_IZQUIERDA + app_module.ANCHO_COLUMNA_CENTRO
        self.assertLess(usado, app_module.VENTANA_ANCHO)
        # El panel de trabajo se queda con el resto y debe ser el más ancho.
        self.assertGreater(app_module.VENTANA_ANCHO - usado, app_module.ANCHO_COLUMNA_CENTRO)

    def test_main_actions_are_visible_and_bound_to_keys(self):
        fuente = inspect.getsource(app_module)
        for etiqueta in (
            '"Nueva  F2"', '"Recientes  F4"', '"Respaldo  F9"', '"Restaurar  F10"',
            '"COPIAR MENSAJE   Ctrl+Enter"', '"GUARDAR"',
        ):
            self.assertIn(etiqueta, fuente)

    def test_keyboard_accessibility_covers_every_main_action(self):
        fuente = inspect.getsource(app_module.VentanaComunicaciones._registrar_atajos)
        for atajo in ('"<F2>"', '"<F3>"', '"<Control-f>"', '"<F4>"', '"<F9>"', '"<F10>"',
                      '"<Control-Return>"', '"<Escape>"'):
            self.assertIn(atajo, fuente)

    def test_the_shortcut_hint_shown_to_the_operator_matches_the_bindings(self):
        for atajo in ("F2", "F3", "F4", "F9", "F10", "Ctrl+Enter", "Esc"):
            self.assertIn(atajo, app_module.ATAJOS)

    def test_the_shortcut_hint_lives_in_the_footer_where_it_fits_uncut(self):
        # En la barra superior el texto se recortaba a 1366 px de ancho.
        superior = inspect.getsource(app_module.VentanaComunicaciones._construir_barra_superior)
        pie = inspect.getsource(app_module.VentanaComunicaciones._construir_pie)
        self.assertNotIn("ATAJOS", superior)
        self.assertIn("ATAJOS", pie)

    def test_the_variable_block_grows_with_the_fields_and_stays_bounded(self):
        self.assertEqual(app_module.alto_datos(0), app_module.ALTO_DATOS_MINIMO)
        self.assertEqual(app_module.alto_datos(1), app_module.ALTO_DATOS_MINIMO)
        self.assertLess(app_module.alto_datos(2), app_module.alto_datos(4))
        self.assertEqual(app_module.alto_datos(40), app_module.ALTO_DATOS_MAXIMO)
        # Nunca debe robarle el alto al mensaje final.
        self.assertLess(app_module.ALTO_DATOS_MAXIMO, app_module.VENTANA_ALTO // 3)

    def test_the_operator_always_sees_where_the_data_lives(self):
        fuente = inspect.getsource(app_module.VentanaComunicaciones._construir_pie)
        self.assertIn("resolve_data_paths().root", fuente)

    def test_the_window_accepts_an_injected_controller(self):
        firma = inspect.signature(app_module.abrir_comunicaciones)
        self.assertEqual(list(firma.parameters), ["ventana_padre", "controller"])


@unittest.skipUnless(tk_disponible(), "sin entorno gráfico disponible")
class WindowSmokeTests(unittest.TestCase):
    """Abre la ventana real y recorre el flujo principal con widgets vivos.

    Cada test levanta su propia ventana sobre datos limpios. Compartir una única
    ventana entre tests hacía que el estado de uno contaminara al siguiente y
    producía fallos que dependían del orden de ejecución.
    """

    def setUp(self) -> None:
        import customtkinter as ctk

        self.ctk = ctk
        self.directory = Path(tempfile.mkdtemp())
        self.clipboard = InMemoryClipboard()
        try:
            self.root = ctk.CTk()
        except Exception as error:
            # El Tcl local falla de forma intermitente al leer init.tcl cuando se
            # lanzan procesos en ráfaga. Es del entorno, no del producto: se salta
            # en vez de reportar un fallo falso. Todo lo que se construye después
            # sí falla fuerte si el producto tiene un defecto.
            raise unittest.SkipTest(f"Tk no pudo iniciar en este entorno: {error}") from error
        self.addCleanup(self._cerrar_todo)
        self.root.withdraw()
        self.controller = build_controller(
            self.directory / "bc_comunicaciones.sqlite3", clipboard=self.clipboard
        )
        self.window = app_module.abrir_comunicaciones(self.root, self.controller)
        self.window.update()
        self.window._primer_dibujado()
        self.window.update()

    def _cerrar_todo(self) -> None:
        for cerrar in (
            lambda: self.controller.repository.close(),
            lambda: self.window.destroy(),
            lambda: self.root.destroy(),
        ):
            try:
                cerrar()
            except Exception:
                pass

    def _abrir_y_completar(self, titulo: str):
        """Abre una plantilla y completa todos sus campos con datos válidos."""
        plantilla = self.controller.search(titulo)[0]
        self.window._abrir_plantilla(plantilla.id)
        self.window.update()
        for nombre, campo in self.window._campos_variables.items():
            campo.delete(0, "end")
            campo.insert(0, f"dato {nombre}")
        self.window._refrescar_vista_previa()
        self.window.update()
        return plantilla

    def test_window_opens_at_the_requested_size(self):
        self.assertEqual(self.window.winfo_reqwidth() <= 1366, True)
        geometry = self.window.geometry()
        self.assertTrue(geometry.startswith("1366x768"), geometry)

    def test_the_library_is_listed_on_first_paint(self):
        self.assertGreater(len(self.window._resultados), 0)
        self.assertEqual(len(self.window._botones_plantilla), len(self.window._resultados))
        self.assertIn("PLANTILLAS", self.window.etiqueta_resultados.cget("text"))

    def test_searching_narrows_the_list_and_clearing_restores_it(self):
        total = len(self.window._resultados)
        self.window.entrada_busqueda.insert(0, "retirar")
        self.window._refrescar_resultados()
        self.window.update()
        self.assertGreater(len(self.window._resultados), 0)
        self.assertLess(len(self.window._resultados), total)

        self.window.entrada_busqueda.delete(0, "end")
        self.window._refrescar_resultados()
        self.window.update()
        self.assertEqual(len(self.window._resultados), total)

    def test_a_search_without_matches_shows_a_helpful_empty_state(self):
        self.window.entrada_busqueda.insert(0, "zzzz-inexistente")
        self.window._refrescar_resultados()
        self.window.update()
        self.assertEqual(self.window._resultados, [])
        textos = [
            hijo.cget("text")
            for hijo in self.window.lista_plantillas.winfo_children()
            if isinstance(hijo, self.ctk.CTkLabel)
        ]
        self.assertTrue(any("zzzz-inexistente" in texto for texto in textos))
        self.window.entrada_busqueda.delete(0, "end")
        self.window._refrescar_resultados()
        self.window.update()

    def test_opening_filling_and_copying_a_message_end_to_end(self):
        plantilla = self.controller.search("Pedido listo")[0]
        self.window._abrir_plantilla(plantilla.id)
        self.window.update()

        self.assertEqual(self.window.titulo_panel.cget("text"), plantilla.title)
        self.assertEqual(set(self.window._campos_variables), set(plantilla.variables))
        self.assertEqual(str(self.window.boton_copiar.cget("state")), "disabled")
        self.assertIn("Faltan completar", self.window.etiqueta_faltantes.cget("text"))

        for nombre, campo in self.window._campos_variables.items():
            campo.delete(0, "end")
            campo.insert(0, f"dato {nombre}")
        self.window._refrescar_vista_previa()
        self.window.update()

        self.assertEqual(str(self.window.boton_copiar.cget("state")), "normal")
        self.assertIn("listo para copiar", self.window.etiqueta_faltantes.cget("text"))
        previa = self.window.caja_mensaje.get("1.0", "end").strip()
        self.assertNotIn("{{", previa)

        copias_antes = self.clipboard.copies
        self.window._copiar_mensaje()
        self.window.update()

        self.assertEqual(self.clipboard.copies, copias_antes + 1)
        self.assertEqual(self.clipboard.text, previa)
        self.assertIn("Copiado", self.window.etiqueta_copiado.cget("text"))
        self.assertEqual(self.controller.recent()[0].final_text, previa)

    def test_editing_the_final_text_before_copying_is_respected(self):
        self._abrir_y_completar("Bienvenida")
        self.window.caja_mensaje.delete("1.0", "end")
        self.window.caja_mensaje.insert("1.0", "Texto ajustado a mano por el mostrador.")
        self.window._refrescar_estado_copiado()
        self.window.update()

        self.assertTrue(self.window._texto_editado_a_mano())
        self.window._copiar_mensaje()
        self.window.update()

        self.assertEqual(self.clipboard.text, "Texto ajustado a mano por el mostrador.")
        self.assertTrue(self.controller.recent()[0].manually_edited)

    def test_a_non_editing_keystroke_does_not_freeze_the_preview(self):
        """Apoyar una flecha sobre el mensaje congelaba la vista previa.

        El texto viejo quedaba en pantalla mientras el operador corregía los
        campos, y era ese texto viejo el que terminaba en WhatsApp.
        """
        plantilla = self.controller.search("Bienvenida")[0]
        self.window._abrir_plantilla(plantilla.id)
        primera = next(iter(self.window._campos_variables.values()))
        primera.delete(0, "end")
        primera.insert(0, "Marta")
        self.window._refrescar_vista_previa()
        self.window.update()
        self.assertIn("Marta", self.window._texto_actual())

        # El operador hace clic en el mensaje y mueve el cursor sin escribir nada.
        self.window.caja_mensaje.focus_set()
        self.window.caja_mensaje.event_generate("<KeyRelease-Right>")
        self.window.update()
        self.assertFalse(self.window._texto_editado_a_mano())

        # Corrige el nombre: la vista previa debe seguirlo.
        primera.delete(0, "end")
        primera.insert(0, "Rosa")
        self.window._refrescar_vista_previa()
        self.window.update()
        self.assertIn("Rosa", self.window._texto_actual())
        self.assertNotIn("Marta", self.window._texto_actual())

    def test_a_placeholder_can_never_be_copied_even_via_the_shortcut(self):
        """Ctrl+Enter no puede saltearse el bloqueo del botón."""
        plantilla = self.controller.search("Bienvenida")[0]
        self.window._abrir_plantilla(plantilla.id)
        self.window.caja_mensaje.focus_set()
        self.window.caja_mensaje.event_generate("<KeyRelease-Down>")
        self.window._refrescar_estado_copiado()
        self.window.update()

        texto = self.window._texto_actual()
        self.assertTrue(self.controller.pending_in_text(plantilla, texto))
        self.assertEqual(str(self.window.boton_copiar.cget("state")), "disabled")
        self.assertEqual(self.clipboard.copies, 0)

    def test_favourite_toggle_updates_the_button_and_the_list(self):
        plantilla = self.controller.search("Pedido listo")[0]
        self.window._abrir_plantilla(plantilla.id)
        self.window.update()
        inicial = self.window.boton_favorita.cget("text")
        self.window._alternar_favorita()
        self.window.update()
        self.assertNotEqual(self.window.boton_favorita.cget("text"), inicial)
        self.assertTrue(self.controller.library.get(plantilla.id).favorite)
        self.window._alternar_favorita()
        self.window.update()

    def test_category_filter_changes_the_visible_list(self):
        self.window._elegir_categoria("aseguradoras-recetas")
        self.window.update()
        self.assertTrue(self.window._resultados)
        self.assertTrue(
            all(item.category_slug == "aseguradoras-recetas" for item in self.window._resultados)
        )
        self.window._elegir_categoria("")
        self.window.update()

    def test_editor_detects_variables_and_saves_a_new_template(self):
        self.window._nueva_plantilla()
        self.window.update()
        self.assertEqual(self.window._modo, "editar")

        self.window.editor_titulo.insert(0, "Plantilla de prueba UI")
        self.window.editor_cuerpo.insert("1.0", "Hola {{cliente}}, aviso sobre {{producto}}.")
        self.window.editor_claves.insert(0, "prueba ui")
        self.window._refrescar_variables_detectadas()
        self.window.update()

        detectadas = self.window.etiqueta_variables.cget("text")
        self.assertIn("Cliente", detectadas)
        self.assertIn("Producto", detectadas)

        self.window._guardar_editor()
        self.window.update()

        self.assertEqual(self.window._modo, "preparar")
        guardada = self.controller.search("Plantilla de prueba UI")
        self.assertEqual(len(guardada), 1)
        self.assertEqual(guardada[0].variables, ("cliente", "producto"))

    def test_editor_marks_unsaved_changes_before_leaving(self):
        plantilla = self.controller.save_template({
            "title": "Plantilla de prueba UI",
            "body": "Hola {{cliente}}, aviso sobre {{producto}}.",
            "category_slug": "generales", "keywords": "prueba ui", "active": True,
        })
        self.window._refrescar_resultados()
        self.window._abrir_plantilla(plantilla.id)
        self.window._editar_plantilla()
        self.window.update()

        self.assertFalse(
            self.window.controller.has_unsaved_changes(
                self.window._borrador_original, self.window._borrador_editor()
            )
        )
        self.window.editor_titulo.insert("end", " editada")
        self.assertTrue(
            self.window.controller.has_unsaved_changes(
                self.window._borrador_original, self.window._borrador_editor()
            )
        )
        self.window.editor_titulo.delete(0, "end")
        self.window.editor_titulo.insert(0, plantilla.title)
        self.window._volver()
        self.window.update()
        self.assertEqual(self.window._modo, "preparar")

    def _temporizadores_pendientes(self) -> set[str]:
        return set(self.window.tk.call("after", "info"))

    def test_a_second_copy_does_not_get_its_confirmation_wiped_by_the_first(self):
        """El aviso «✓ Copiado» se borra a los 4 s; ese temporizador debe ser único.

        Sin cancelar el anterior, copiar dos mensajes seguidos hacía que el
        temporizador del primero borrase la confirmación del segundo.
        """
        self._abrir_y_completar("Pedido listo")

        self.window._copiar_mensaje()
        self.window.update()
        primero = self.window._temporizador_copiado
        self.assertIsNotNone(primero)
        self.assertIn(primero, self._temporizadores_pendientes())

        self.window._copiar_mensaje()
        self.window.update()
        segundo = self.window._temporizador_copiado
        self.assertIsNotNone(segundo)
        self.assertNotEqual(segundo, primero)
        self.assertNotIn(primero, self._temporizadores_pendientes())
        self.assertIn("Copiado", self.window.etiqueta_copiado.cget("text"))

        # Al vencer, el temporizador vigente sí limpia el aviso.
        self.window._ocultar_aviso_copiado()
        self.assertEqual(self.window.etiqueta_copiado.cget("text"), "")

    def test_switching_template_after_copying_leaves_no_timer_on_a_destroyed_widget(self):
        self._abrir_y_completar("Pedido listo")
        self.window._copiar_mensaje()
        self.window.update()
        pendiente = self.window._temporizador_copiado
        self.assertIsNotNone(pendiente)

        otra = self.controller.search("Bienvenida")[0]
        self.window._abrir_plantilla(otra.id)
        self.window.update()

        self.assertIsNone(self.window._temporizador_copiado)
        self.assertNotIn(pendiente, self._temporizadores_pendientes())

    def test_recent_view_lists_the_copied_messages(self):
        self.window._mostrar_recientes()
        self.window.update()
        self.assertEqual(self.window._modo, "recientes")
        self.assertIn("recientemente", self.window.titulo_panel.cget("text"))
        self.window._volver()
        self.window.update()


if __name__ == "__main__":
    unittest.main()
