"""BC-CAJA-RC27: pulido posterior a la prueba manual del circuito.

Solo los hallazgos reales del usuario. No rediseña Seguimiento: la vista, los
tres botones, la agrupación y el reuso de filas quedan como estaban.

Cubre los doce puntos de validación de la misión.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.tracking_service import (
    ESTADOS_COMPLETADOS,
    ETIQUETAS_ESTADO,
    TrackingService,
)
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin
from modulos.caja_diaria.domain.tracking import (
    ETIQUETA_A_CONFIRMAR,
    TRANSICIONES_REVERSIBLES,
    NextAction,
    TrackingStatus,
    next_action,
    puede_corregirse_a,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

HOY = date.today()
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)
FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def momento(dia: date, hora: str) -> datetime:
    h, m = (int(x) for x in hora.split(":"))
    return datetime.combine(dia, time(h, m), tzinfo=BUSINESS_TIMEZONE)


class Base(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.tracking = TrackingService(self.repository)
        self.lab = self.tracking.save_laboratory(name="LAB ALFA", phone_line="021 1")

    def tearDown(self):
        self.repository.close()

    def _pedido(self, envelope="TEST-001", branch="PILAR"):
        pedido = Order(
            delivery_date=HOY + timedelta(days=7), branch=branch,
            customer_name="Cliente TEST", saleswoman="Nidia (TEST)",
            envelope=envelope, origin=OrderOrigin.WORKSHOP,
            customer_phone="0981 555 111", observations="Armazon + cristales",
            created_at=momento(AYER, "14:00"))
        self.repository.save_order(pedido)
        return pedido

    def _en_optica(self, envelope="TEST-001"):
        """Un trabajo recibido en Asuncion, listo para ir al laboratorio."""
        work = self.tracking.create_pilar_shipment(
            [self._pedido(envelope).id], operator="Nidia")["works"][0]
        return self.tracking.receive_in_asuncion(work.id, responsible="Ana")

    def _fila(self, work_id, **kw):
        kw.setdefault("scope", "TODOS")
        return next(f for f in self.tracking.board(**kw)["rows"] if f.work.id == work_id)


# ------------------------------------------------- 1 y 2: sucursal automatica

class SucursalAutomaticaTests(Base):
    def test_el_tablero_filtra_por_la_sucursal_de_la_caja(self):
        self._en_optica()
        self.assertEqual(
            len(self.tracking.board(responsible_branch="ASUNCION")["rows"]), 1)
        self.assertEqual(
            len(self.tracking.board(responsible_branch="PILAR")["rows"]), 0)

    def test_los_bindings_canonicos_resuelven_la_sucursal(self):
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")
        self.assertEqual(self.tracking.branch_of_register("P2"), "PILAR")
        self.assertEqual(self.tracking.branch_of_register("PILAR"), "PILAR")

    def test_seguimiento_abre_en_mi_sucursal_sin_pedir_nada(self):
        """`todas` arranca en False: la vista ya viene acotada a la caja."""
        self.assertIn('"todas": False', FUENTE)
        self.assertIn(
            'local = None if (contexto_sucursal["todas"] or not sucursal) else sucursal',
            FUENTE)

    def test_ver_todas_las_sucursales_ya_no_ocupa_la_barra(self):
        barra = FUENTE[
            FUENTE.index("botones_seguimiento = {}"):
            FUENTE.index("barra_recepcion = ctk.CTkFrame")
        ]
        self.assertNotIn("boton_alcance_sucursal", barra)
        self.assertNotIn("boton_alcance_sucursal", FUENTE)
        menu = FUENTE[FUENTE.index("def abrir_menu_mas"):]
        self.assertIn("Ver todas las sucursales", menu[:1400])
        self.assertIn("command=alternar_alcance_sucursal", menu[:1400])

    def test_la_tabla_vacia_dice_de_que_sucursal_habla(self):
        self.assertIn('f"No hay trabajos pendientes en {sucursal.title()}."', FUENTE)

    def test_la_alerta_abre_exactamente_sus_trabajos(self):
        for _ in range(3):
            pass
        works = [self._en_optica(f"T-{i}") for i in range(3)]
        pendientes = self.tracking.pending_actions_for_branch("ASUNCION")
        principal = pendientes["principal"]
        self.assertEqual(principal["cantidad"], 3)
        filas = self.tracking.board(
            responsible_branch="ASUNCION", group=principal["grupo"])["rows"]
        self.assertEqual({f.work.id for f in filas}, {w.id for w in works})


# ------------------------------------------------------- 4: seleccionar todo

class SeleccionarTodoTests(unittest.TestCase):
    def test_el_rotulo_es_seleccionar_todo(self):
        menu = FUENTE[FUENTE.index("def abrir_menu_mas"):]
        self.assertIn('label="Seleccionar todo"', menu[:1400])
        self.assertNotIn("Seleccionar visibles", FUENTE)

    def test_selecciona_lo_que_la_vista_esta_mostrando(self):
        bloque = FUENTE[
            FUENTE.index("    def seleccionar_todo():"):
            FUENTE.index("    def trabajo_seleccionado():")
        ]
        self.assertIn('set(estado_seguimiento["filas"])', bloque)
        # Sigue sin reconstruir la tabla (RC26).
        self.assertIn("aplicar_marcas_visibles()", bloque)


# ------------------------------------------------------------ 5: cierre normal

class CierreNormalTests(Base):
    def _hasta_pilar(self):
        work = self._en_optica()
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=MANANA, responsible="Ana")
        self.tracking.receive_from_laboratory(work.id, responsible="Ana")
        self.tracking.send_batch_to_pilar([work.id], responsible="Ana")
        return self.tracking.receive_in_pilar(work.id, responsible="Nidia")

    def test_recibido_en_pilar_cierra_solo(self):
        work = self._hasta_pilar()
        self.assertIn(TrackingStatus.RECEIVED_IN_PILAR, ESTADOS_COMPLETADOS)
        self.assertEqual(len(self.tracking.board(scope="ACTIVOS")["rows"]), 0)
        completados = self.tracking.board(scope="COMPLETADOS")["rows"]
        self.assertEqual(len(completados), 1)
        self.assertEqual(completados[0].group, "completados")

    def test_no_exige_ninguna_accion_adicional(self):
        work = self._hasta_pilar()
        self.assertEqual(
            self.tracking.next_action_for([work.id])["action"], NextAction.NONE)

    def test_conserva_su_historial(self):
        work = self._hasta_pilar()
        guardado = self.repository.get_tracked_work(work.id)
        # recibir + laboratorio + del laboratorio + a Pilar + en Pilar
        self.assertEqual(len(guardado.transitions), 5)
        self.assertEqual(guardado.transitions[-1].to_status,
                         TrackingStatus.RECEIVED_IN_PILAR)

    def test_deja_de_generar_alertas_logisticas(self):
        self._hasta_pilar()
        for sucursal in ("ASUNCION", "PILAR"):
            self.assertIsNone(
                self.tracking.pending_actions_for_branch(sucursal)["principal"],
                sucursal)


# ------------------------------------------------------ 6: cerrar por excepcion

class CierrePorExcepcionTests(Base):
    def test_exige_motivo(self):
        work = self._en_optica()
        for vacio in ("", "   "):
            with self.assertRaises(InvalidCashDayError):
                self.tracking.close_by_exception(
                    work.id, responsible="Ana", reason=vacio)

    def test_exige_responsable(self):
        work = self._en_optica()
        with self.assertRaises(InvalidCashDayError):
            self.tracking.close_by_exception(
                work.id, responsible="  ", reason="Cancelación")

    def test_cierra_y_deja_traza_auditada(self):
        work = self._en_optica()
        cerrado = self.tracking.close_by_exception(
            work.id, responsible="Ana", reason="Cliente devolvió a exhibición")
        self.assertIs(cerrado.status, TrackingStatus.CLOSED)
        ultima = cerrado.transitions[-1]
        self.assertEqual(ultima.responsible, "Ana")
        self.assertIn("Cliente devolvió a exhibición", ultima.note)
        self.assertIn("Cierre por excepción", ultima.note)
        self.assertIsNotNone(ultima.recorded_at)
        self.assertIs(ultima.from_status, TrackingStatus.RECEIVED_IN_ASUNCION)

    def test_no_se_cierra_dos_veces(self):
        work = self._en_optica()
        self.tracking.close_by_exception(work.id, responsible="Ana", reason="X")
        with self.assertRaises(InvalidCashDayError):
            self.tracking.close_by_exception(work.id, responsible="Ana", reason="X")

    def test_se_puede_cerrar_desde_cualquier_etapa_sin_completar(self):
        for i, etapa in enumerate(("optica", "lab")):
            work = self._en_optica(f"E-{i}")
            if etapa == "lab":
                self.tracking.send_to_laboratory(
                    work.id, self.lab.id, expected_date=MANANA, responsible="Ana")
            cerrado = self.tracking.close_by_exception(
                work.id, responsible="Ana", reason="Trabajo sin efecto")
            self.assertIs(cerrado.status, TrackingStatus.CLOSED)


# --------------------------------------------- 7, 8 y 9: queda a confirmar

class QuedaAConfirmarTests(Base):
    def test_se_marca_sobre_un_trabajo_que_esta_en_la_optica(self):
        work = self._en_optica()
        marcados = self.tracking.mark_awaiting_confirmation(
            [work.id], responsible="Ana", note="Cliente confirma mañana")
        self.assertTrue(marcados[0].awaiting_confirmation)
        self.assertEqual(marcados[0].confirmation_note, "Cliente confirma mañana")

    def test_no_es_una_etapa_nueva_sino_una_condicion(self):
        """Fisicamente el trabajo sigue recibido en la óptica."""
        work = self._en_optica()
        self.tracking.mark_awaiting_confirmation(
            [work.id], responsible="Ana", note="Esperando llamada")
        guardado = self.repository.get_tracked_work(work.id)
        self.assertIs(guardado.status, TrackingStatus.RECEIVED_IN_ASUNCION)
        fila = self._fila(work.id)
        self.assertEqual(fila.alert, ETIQUETA_A_CONFIRMAR)
        self.assertEqual(fila.physical_status, "RECIBIDO EN ASUNCIÓN")
        self.assertEqual(fila.status_display,
                         "QUEDA A CONFIRMAR · RECIBIDO EN ASUNCIÓN")

    def test_la_observacion_breve_se_lee_en_la_fila(self):
        for nota in ("Cliente confirma mañana", "Esperando llamada",
                     "Falta confirmar cristal", "Esperando autorización"):
            work = self._en_optica(f"N-{nota[:6]}")
            self.tracking.mark_awaiting_confirmation(
                [work.id], responsible="Ana", note=nota)
            self.assertEqual(self._fila(work.id).observation, nota)

    def test_sin_nota_igual_dice_que_se_espera(self):
        work = self._en_optica()
        self.tracking.mark_awaiting_confirmation([work.id], responsible="Ana")
        self.assertEqual(self._fila(work.id).observation,
                         "Falta que el cliente confirme")

    def test_la_accion_principal_pasa_a_resolver_la_confirmacion(self):
        work = self._en_optica()
        self.tracking.mark_awaiting_confirmation(
            [work.id], responsible="Ana", note="Esperando llamada")
        resumen = self.tracking.next_action_for([work.id])
        self.assertEqual(resumen["action"], NextAction.RESOLVE_CONFIRMATION)
        self.assertEqual(resumen["label"], "Resolver confirmación")

    def test_solo_puede_quedar_a_confirmar_lo_que_esta_en_la_optica(self):
        work = self._en_optica()
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=MANANA, responsible="Ana")
        with self.assertRaises(InvalidCashDayError):
            self.tracking.mark_awaiting_confirmation([work.id], responsible="Ana")

    def test_confirmo_continua_hacia_el_laboratorio(self):
        work = self._en_optica()
        self.tracking.mark_awaiting_confirmation(
            [work.id], responsible="Ana", note="Cliente confirma mañana")
        self.tracking.resolve_confirmation_confirmed(
            [work.id], responsible="Ana", laboratory_id=self.lab.id,
            expected_date=MANANA, expected_time="15:00")
        guardado = self.repository.get_tracked_work(work.id)
        self.assertIs(guardado.status, TrackingStatus.IN_LABORATORY)
        self.assertFalse(guardado.awaiting_confirmation)
        self.assertEqual(guardado.confirmation_note, "")

    def test_cancelo_cierra_por_excepcion_con_trazabilidad(self):
        work = self._en_optica()
        self.tracking.mark_awaiting_confirmation(
            [work.id], responsible="Ana", note="Esperando autorización")
        self.tracking.resolve_confirmation_cancelled(
            [work.id], responsible="Ana", reason="Devuelto a exhibición")
        guardado = self.repository.get_tracked_work(work.id)
        self.assertIs(guardado.status, TrackingStatus.CLOSED)
        self.assertFalse(guardado.awaiting_confirmation)
        self.assertIn("Devuelto a exhibición", guardado.transitions[-1].note)
        self.assertEqual(guardado.transitions[-1].responsible, "Ana")

    def test_cancelar_sin_motivo_no_pasa(self):
        work = self._en_optica()
        self.tracking.mark_awaiting_confirmation([work.id], responsible="Ana")
        with self.assertRaises(InvalidCashDayError):
            self.tracking.resolve_confirmation_cancelled(
                [work.id], responsible="Ana", reason="")

    def test_la_condicion_no_traba_el_circuito(self):
        """RC26 sigue valiendo: siempre hay una transicion posible."""
        self.assertEqual(
            next_action(TrackingStatus.RECEIVED_IN_ASUNCION,
                        awaiting_confirmation=True),
            NextAction.RESOLVE_CONFIRMATION)
        from modulos.caja_diaria.domain.tracking import TRANSICION_DE_ACCION
        self.assertIs(TRANSICION_DE_ACCION[NextAction.RESOLVE_CONFIRMATION],
                      TrackingStatus.IN_LABORATORY)


# ------------------------------------------------------ 10: corregir estado

class CorregirEstadoTests(Base):
    def test_solo_admite_retrocesos_declarados(self):
        self.assertTrue(puede_corregirse_a(
            TrackingStatus.IN_LABORATORY, TrackingStatus.RECEIVED_IN_ASUNCION))
        self.assertFalse(puede_corregirse_a(
            TrackingStatus.IN_LABORATORY, TrackingStatus.SENT_FROM_PILAR))
        self.assertFalse(puede_corregirse_a(
            TrackingStatus.SENT_FROM_PILAR, TrackingStatus.RECEIVED_IN_PILAR))

    def test_ningun_retroceso_salta_mas_de_un_paso(self):
        orden = [e for e in TrackingStatus]
        for actual, destinos in TRANSICIONES_REVERSIBLES.items():
            for destino in destinos:
                self.assertEqual(
                    orden.index(actual) - orden.index(destino), 1,
                    f"{actual} -> {destino} no es un retroceso de un paso")

    def test_corrige_con_motivo_y_responsable_auditados(self):
        work = self._en_optica()
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=MANANA, responsible="Ana")
        corregido = self.tracking.correct_status(
            work.id, TrackingStatus.RECEIVED_IN_ASUNCION,
            responsible="Rodrigo", reason="Se envió por error")
        self.assertIs(corregido.status, TrackingStatus.RECEIVED_IN_ASUNCION)
        ultima = corregido.transitions[-1]
        self.assertEqual(ultima.responsible, "Rodrigo")
        self.assertIn("Corrección de estado", ultima.note)
        self.assertIn("Se envió por error", ultima.note)
        self.assertIs(ultima.from_status, TrackingStatus.IN_LABORATORY)
        self.assertIsNotNone(ultima.recorded_at)
        # El plazo del laboratorio se suelta al salir de esa etapa.
        self.assertIsNone(corregido.expected_date)

    def test_exige_motivo_y_responsable(self):
        work = self._en_optica()
        for motivo, responsable in (("", "Ana"), ("   ", "Ana"), ("Motivo", "  ")):
            with self.assertRaises(InvalidCashDayError):
                self.tracking.correct_status(
                    work.id, TrackingStatus.SENT_FROM_PILAR,
                    responsible=responsable, reason=motivo)

    def test_un_salto_arbitrario_se_rechaza_y_lo_explica(self):
        work = self._en_optica()
        with self.assertRaises(InvalidCashDayError) as error:
            self.tracking.correct_status(
                work.id, TrackingStatus.RECEIVED_IN_PILAR,
                responsible="Ana", reason="Ajuste")
        self.assertIn("no se puede corregir", str(error.exception))

    def test_los_destinos_validos_se_pueden_consultar(self):
        work = self._en_optica()
        self.assertEqual(self.tracking.correctable_targets(work.id),
                         (TrackingStatus.SENT_FROM_PILAR,))

    def test_una_etapa_sin_retroceso_lo_dice(self):
        work = self._en_optica()
        cerrado = self.tracking.close_by_exception(
            work.id, responsible="Ana", reason="X")
        self.assertEqual(self.tracking.correctable_targets(cerrado.id), ())


# ------------------------------------------------------------- 11 y 12: UX

class UxSinRegresionTests(unittest.TestCase):
    def test_siguen_siendo_tres_botones_principales(self):
        barra = FUENTE[
            FUENTE.index("boton_accion_siguiente = ctk.CTkButton"):
            FUENTE.index("etiqueta_seleccion = ctk.CTkLabel")
        ]
        self.assertEqual(barra.count("ctk.CTkButton("), 3)

    def test_no_reaparecieron_botones_de_transicion_individuales(self):
        barra = FUENTE[
            FUENTE.index("boton_accion_siguiente = ctk.CTkButton"):
            FUENTE.index("etiqueta_seleccion = ctk.CTkLabel")
        ]
        for residuo in ('text="Recibir en Asunción"', 'text="Enviar a laboratorio"',
                        'text="Enviar a Pilar"', 'text="Recibir en Pilar"'):
            self.assertNotIn(residuo, barra)

    def test_las_excepciones_son_entradas_de_menu_y_no_botones(self):
        menu = FUENTE[FUENTE.index("def abrir_menu_mas"):]
        for etiqueta in ("Cerrar por excepción", "Corregir estado",
                         "Queda a confirmar"):
            self.assertIn(f'menu.add_command(label="{etiqueta}"', menu[:1400])
            # Ninguna de las tres se dibuja como boton de la barra principal.
            self.assertNotIn(f'acciones_seguimiento, text="{etiqueta}"', FUENTE)

    def test_resolver_confirmacion_ofrece_solo_los_dos_caminos(self):
        bloque = FUENTE[
            FUENTE.index("    def resolver_confirmacion(ids):"):
            FUENTE.index("    def cerrar_por_excepcion():")
        ]
        self.assertIn("Confirmó  —  enviar a laboratorio", bloque)
        self.assertIn("Canceló  —  cerrar por excepción", bloque)
        # No se despliega la lista completa de estados.
        self.assertNotIn("ESTADOS_VISIBLES", bloque)

    def test_el_reuso_de_filas_sigue_vivo(self):
        self.assertIn("def crear_fila(identificador):", FUENTE)
        self.assertIn("def pintar_fila(fila, indice, posicion):", FUENTE)


if __name__ == "__main__":
    unittest.main()
