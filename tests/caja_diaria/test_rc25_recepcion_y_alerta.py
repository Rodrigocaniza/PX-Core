"""BC-CAJA-RC25: la recepcion se ve en pantalla y la alerta llega a Caja.

Mision 2 — las discrepancias reales de una recepcion (NO LLEGO, NO ESTABA EN
LISTA) dejan de vivir solo en el dominio y se leen en la propia fila, con una
linea de conciliacion que cierra contra lo que Pilar declaro.

Mision 3 — la alerta de la sucursal se muestra en la pantalla en la que la
operadora ya esta, y el clic abre exactamente los trabajos que la originaron.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta

from modulos.caja_diaria.application.tracking_service import (
    GRUPOS_SEGUIMIENTO,
    TrackingService,
)
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin
from modulos.caja_diaria.domain.tracking import (
    NextAction,
    ReceptionIssue,
    TrackingStatus,
    etiqueta_dia,
    reception_reconciliation,
    reconciliation_line,
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

    def _pedidos(self, cantidad, branch="PILAR", prefijo="TEST-P"):
        creados = []
        for i in range(1, cantidad + 1):
            pedido = Order(
                delivery_date=HOY + timedelta(days=7), branch=branch,
                customer_name=f"Cliente Prueba {i:02d}", saleswoman="Nidia (TEST)",
                envelope=f"{prefijo}-{i:03d}", origin=OrderOrigin.WORKSHOP,
                observations="Cristal", cash_entry_id=None,
                created_at=datetime.combine(AYER, time(14, 0), tzinfo=BUSINESS_TIMEZONE))
            self.repository.save_order(pedido)
            creados.append(pedido)
        return creados

    def _lote(self, cantidad=15):
        pedidos = self._pedidos(cantidad)
        return self.tracking.create_pilar_shipment(
            [p.id for p in pedidos], operator="Nidia (TEST)")


# ---------------------------------------------------------------- Mision 2

class ConciliacionTests(Base):
    def test_la_linea_es_exactamente_la_que_lee_la_operadora(self):
        datos = {"declarados": 15, "recibidos": 14, "no_llego": 1, "extra": 1}
        self.assertEqual(
            reconciliation_line(datos),
            "Declarados 15 · Recibidos 14 · No llegó 1 · Extra 1")

    def test_los_ceros_no_se_ocultan(self):
        """Una recepcion que cerro tiene que poder confirmarse de un vistazo."""
        self.assertEqual(
            reconciliation_line(reception_reconciliation(self._lote(3)["works"])),
            "Declarados 3 · Recibidos 0 · No llegó 0 · Extra 0")

    def test_el_extra_no_infla_los_declarados_ni_los_recibidos(self):
        lote = self._lote(15)
        works = lote["works"]
        for work in works[:12]:
            self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.mark_batch_not_arrived(
            [w.id for w in works[12:14]], responsible="Ana")
        extra = self._pedidos(1, prefijo="EXTRA")[0]
        self.tracking.add_unlisted_reception(
            extra.id, responsible="Ana", shipment_id=lote["shipment"].id)
        self.assertEqual(
            self.tracking.reception_reconciliation(lote["shipment"].id),
            {"declarados": 15, "recibidos": 12, "no_llego": 2, "extra": 1})

    def test_la_recepcion_en_curso_es_el_lote_que_falta_terminar(self):
        lote = self._lote(15)
        actual = self.tracking.current_reception("ASUNCION")
        self.assertEqual(actual["shipment"].id, lote["shipment"].id)
        self.assertEqual(actual["pendientes"], 15)
        self.assertIn("Declarados 15", actual["line"])

    def test_cuando_la_recepcion_cierra_deja_de_haber_recepcion_en_curso(self):
        lote = self._lote(3)
        self.tracking.apply_next_action(
            [w.id for w in lote["works"]], responsible="Ana")
        actual = self.tracking.current_reception("ASUNCION")
        self.assertIsNone(actual["shipment"])
        self.assertEqual(actual["line"], "")

    def test_un_no_llego_mantiene_la_recepcion_abierta(self):
        """No se puede dar por cerrado un lote con algo sin resolver."""
        lote = self._lote(3)
        works = lote["works"]
        self.tracking.apply_next_action([w.id for w in works[:2]], responsible="Ana")
        self.tracking.mark_not_arrived(works[2].id, responsible="Ana")
        self.assertIsNotNone(self.tracking.current_reception("ASUNCION")["shipment"])


class DiscrepanciaEnPantallaTests(Base):
    def _fila(self, work_id, **kw):
        return next(f for f in self.tracking.board(**kw)["rows"] if f.work.id == work_id)

    def test_no_llego_se_lee_junto_a_su_origen(self):
        """`NO LLEGÓ · ENVIADO DESDE PILAR`: falta, y se sabe de donde venia."""
        work = self._lote(1)["works"][0]
        self.tracking.mark_not_arrived(work.id, responsible="Ana")
        fila = self._fila(work.id)
        self.assertEqual(fila.alert, "NO LLEGÓ")
        self.assertEqual(fila.physical_status, "ENVIADO DESDE PILAR")
        self.assertEqual(fila.status_display, "NO LLEGÓ · ENVIADO DESDE PILAR")

    def test_no_llego_sigue_ligado_al_lote(self):
        lote = self._lote(2)
        work = lote["works"][0]
        marcado = self.tracking.mark_not_arrived(work.id, responsible="Ana")
        self.assertEqual(marcado.shipment_id, lote["shipment"].id)

    def test_no_llego_bloquea_el_salto_pero_deja_resolver(self):
        """RC26: bloquear el avance no puede significar dejarlo sin salida."""
        work = self._lote(1)["works"][0]
        self.tracking.mark_not_arrived(work.id, responsible="Ana")
        self.assertEqual(
            self.tracking.next_action_for([work.id])["action"],
            NextAction.RESOLVE_RECEPTION)
        # No puede saltar al laboratorio mientras la discrepancia siga abierta.
        with self.assertRaises(InvalidCashDayError):
            self.tracking.send_to_laboratory(
                work.id, self.lab.id, expected_date=HOY, responsible="Ana")
        # Pero la resolucion —recibirlo cuando aparece— si esta disponible.
        self.tracking.apply_next_action([work.id], responsible="Ana")
        recuperado = self.repository.get_tracked_work(work.id)
        self.assertIs(recuperado.status, TrackingStatus.RECEIVED_IN_ASUNCION)
        self.assertIsNone(recuperado.reception_issue)

    def test_marcar_no_llego_es_masivo(self):
        works = self._lote(5)["works"]
        marcados = self.tracking.mark_batch_not_arrived(
            [w.id for w in works[:3]], responsible="Ana")
        self.assertEqual(len(marcados), 3)
        self.assertTrue(all(
            w.reception_issue is ReceptionIssue.NOT_ARRIVED for w in marcados))

    def test_marcar_no_llego_sin_seleccion_lo_dice(self):
        with self.assertRaises(InvalidCashDayError):
            self.tracking.mark_batch_not_arrived([], responsible="Ana")

    def test_no_estaba_en_lista_tambien_se_lee_en_la_fila(self):
        lote = self._lote(1)
        extra = self._pedidos(1, prefijo="EXTRA")[0]
        agregado = self.tracking.add_unlisted_reception(
            extra.id, responsible="Ana", shipment_id=lote["shipment"].id)
        fila = self._fila(agregado.id)
        self.assertEqual(fila.alert, "NO ESTABA EN LISTA")
        self.assertEqual(fila.physical_status, "RECIBIDO EN ASUNCIÓN")


class BusquedaDelFisicoTests(Base):
    def test_se_busca_por_sobre(self):
        self._pedidos(3)
        encontrados = self.tracking.search_receivable_orders("TEST-P-002")
        self.assertEqual([p.envelope for p in encontrados], ["TEST-P-002"])

    def test_se_busca_tambien_por_cliente(self):
        self._pedidos(3)
        encontrados = self.tracking.search_receivable_orders("Cliente Prueba 03")
        self.assertEqual([p.envelope for p in encontrados], ["TEST-P-003"])

    def test_lo_que_ya_esta_en_el_circuito_no_se_vuelve_a_ofrecer(self):
        """No se puede colgar dos veces el mismo trabajo."""
        self._lote(3)
        self.assertEqual(self.tracking.search_receivable_orders("TEST-P"), [])

    def test_sin_termino_no_devuelve_el_padron_entero(self):
        self._pedidos(5)
        self.assertEqual(self.tracking.search_receivable_orders("   "), [])

    def test_el_pedido_encontrado_se_reutiliza_sin_recargar_nada(self):
        lote = self._lote(1)
        extra = self._pedidos(1, prefijo="EXTRA")[0]
        candidato = self.tracking.search_receivable_orders("EXTRA-001")[0]
        agregado = self.tracking.add_unlisted_reception(
            candidato.id, responsible="Ana", shipment_id=lote["shipment"].id)
        self.assertEqual(agregado.order_id, extra.id)
        self.assertEqual(agregado.envelope, extra.envelope)
        self.assertEqual(agregado.customer_name, extra.customer_name)
        self.assertEqual(agregado.observations, extra.observations)

    def test_queda_registrado_quien_lo_agrego_y_cuando(self):
        lote = self._lote(1)
        extra = self._pedidos(1, prefijo="EXTRA")[0]
        agregado = self.tracking.add_unlisted_reception(
            extra.id, responsible="Ana", shipment_id=lote["shipment"].id)
        self.assertEqual(agregado.created_by, "Ana")
        self.assertIsNotNone(agregado.created_at)
        self.assertEqual(agregado.transitions[-1].responsible, "Ana")
        self.assertIsNotNone(agregado.transitions[-1].recorded_at)


# ---------------------------------------------------------------- Mision 3

class BindingsCanonicosTests(Base):
    def test_las_tres_cajas_conocidas_saben_en_que_local_estan(self):
        self.assertEqual(self.tracking.branch_of_register("PC"), "ASUNCION")
        self.assertEqual(self.tracking.branch_of_register("P2"), "PILAR")
        self.assertEqual(self.tracking.branch_of_register("PILAR"), "PILAR")


class AlertaPrincipalTests(Base):
    def test_la_alerta_es_de_la_sucursal_y_trae_cantidad_y_destino(self):
        self._lote(15)
        pendientes = self.tracking.pending_actions_for_branch("ASUNCION")
        principal = pendientes["principal"]
        self.assertEqual(principal["cantidad"], 15)
        self.assertEqual(principal["texto"], "15 por recibir desde Pilar")
        self.assertEqual(principal["grupo"], "por_recibir")

    def test_pilar_no_ve_como_pendiente_lo_que_le_toca_a_asuncion(self):
        self._lote(15)
        self.assertIsNone(self.tracking.pending_actions_for_branch("PILAR")["principal"])

    def test_el_mismo_trabajo_alerta_en_pilar_recien_cuando_va_en_camino(self):
        works = self._lote(2)["works"]
        ids = [w.id for w in works]
        self.tracking.apply_next_action(ids, responsible="Ana")
        self.tracking.apply_next_action(
            ids, responsible="Ana", laboratory_id=self.lab.id,
            expected_date=MANANA, expected_time="15:00")
        self.tracking.apply_next_action(ids, responsible="Ana")
        self.assertIsNone(self.tracking.pending_actions_for_branch("PILAR")["principal"])
        self.tracking.send_batch_to_pilar(ids, responsible="Ana")
        principal = self.tracking.pending_actions_for_branch("PILAR")["principal"]
        self.assertEqual(principal["grupo"], "por_recibir_pilar")
        self.assertEqual(principal["cantidad"], 2)

    def test_sin_nada_pendiente_no_hay_alerta_que_mostrar(self):
        self.assertIsNone(
            self.tracking.pending_actions_for_branch("ASUNCION")["principal"])

    def test_toda_alerta_sabe_a_donde_lleva(self):
        """O a un grupo, o al filtro de atrasados. Nunca a ningun lado."""
        works = self._lote(3)["works"]
        self.tracking.apply_next_action([works[0].id], responsible="Ana")
        self.tracking.send_to_laboratory(
            works[0].id, self.lab.id, expected_date=AYER, expected_time="15:00",
            responsible="Ana")
        pendientes = self.tracking.pending_actions_for_branch(
            "ASUNCION", now=momento(HOY, "10:00"))
        claves = {clave for clave, _t, _e in GRUPOS_SEGUIMIENTO}
        for alerta in pendientes["alertas"]:
            self.assertTrue(alerta["grupo"] in claves or alerta["filtro"] == "Atrasados")

    def test_el_atraso_encabeza_porque_exige_una_llamada_ahora(self):
        works = self._lote(3)["works"]
        self.tracking.apply_next_action([works[0].id], responsible="Ana")
        self.tracking.send_to_laboratory(
            works[0].id, self.lab.id, expected_date=AYER, expected_time="15:00",
            responsible="Ana")
        pendientes = self.tracking.pending_actions_for_branch(
            "ASUNCION", now=momento(HOY, "10:00"))
        self.assertEqual(pendientes["principal"]["clave"], "atrasados")


class AgrupacionTests(Base):
    def test_son_los_seis_grupos_del_circuito_en_orden(self):
        self.assertEqual([t for _c, t, _e in GRUPOS_SEGUIMIENTO], [
            "Por recibir", "Para laboratorio", "En laboratorio",
            "Para enviar a Pilar", "Por recibir en Pilar", "Completados"])

    def test_cada_fila_sabe_a_que_grupo_pertenece(self):
        work = self._lote(1)["works"][0]
        self.assertEqual(self.tracking.board()["rows"][0].group, "por_recibir")
        self.assertEqual(
            self.tracking.board()["rows"][0].group_title, "Por recibir")
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.assertEqual(self.tracking.board()["rows"][0].group, "para_laboratorio")

    def test_el_tablero_cuenta_cada_grupo(self):
        works = self._lote(5)["works"]
        self.tracking.apply_next_action(
            [w.id for w in works[:2]], responsible="Ana")
        grupos = self.tracking.board()["groups"]
        self.assertEqual(grupos["por_recibir"], 3)
        self.assertEqual(grupos["para_laboratorio"], 2)
        self.assertEqual(grupos["en_laboratorio"], 0)

    def test_enfocar_un_grupo_devuelve_exactamente_esos_trabajos(self):
        works = self._lote(5)["works"]
        self.tracking.apply_next_action(
            [w.id for w in works[:2]], responsible="Ana")
        filas = self.tracking.board(group="por_recibir")["rows"]
        self.assertEqual(len(filas), 3)
        self.assertTrue(all(f.group == "por_recibir" for f in filas))

    def test_un_trabajo_completado_cae_en_completados(self):
        work = self._lote(1)["works"][0]
        for paso in range(5):
            if paso == 1:
                self.tracking.send_to_laboratory(
                    work.id, self.lab.id, expected_date=MANANA, responsible="Ana")
            elif paso == 0:
                self.tracking.receive_in_asuncion(work.id, responsible="Ana")
            elif paso == 2:
                self.tracking.receive_from_laboratory(work.id, responsible="Ana")
            elif paso == 3:
                self.tracking.send_batch_to_pilar([work.id], responsible="Nidia")
            else:
                self.tracking.receive_in_pilar(work.id, responsible="Nidia")
        fila = self.tracking.board(scope="COMPLETADOS")["rows"][0]
        self.assertEqual(fila.group, "completados")

    def test_el_orden_de_las_filas_sigue_poniendo_las_excepciones_primero(self):
        """Agrupar es presentacion: no puede enterrar un atrasado."""
        works = self._lote(3)["works"]
        self.tracking.apply_next_action([works[0].id], responsible="Ana")
        self.tracking.send_to_laboratory(
            works[0].id, self.lab.id, expected_date=AYER, expected_time="15:00",
            responsible="Ana")
        filas = self.tracking.board(now=momento(HOY, "10:00"))["rows"]
        self.assertTrue(filas[0].overdue)


class ObservacionOperativaTests(Base):
    def _fila(self, work_id, **kw):
        return next(f for f in self.tracking.board(**kw)["rows"] if f.work.id == work_id)

    def _en_laboratorio(self, expected_date=None):
        work = self._lote(1)["works"][0]
        self.tracking.receive_in_asuncion(work.id, responsible="Ana")
        self.tracking.send_to_laboratory(
            work.id, self.lab.id, expected_date=expected_date or MANANA,
            expected_time="15:00", responsible="Ana")
        return work

    def test_los_dias_relativos_se_nombran(self):
        self.assertEqual(etiqueta_dia(HOY, HOY), "Hoy")
        self.assertEqual(etiqueta_dia(MANANA, HOY), "Mañana")
        self.assertEqual(etiqueta_dia(HOY + timedelta(days=4), HOY),
                         (HOY + timedelta(days=4)).strftime("%d-%m"))

    def test_mas_tarde_hoy_se_lee_como_hoy_y_la_hora(self):
        work = self._en_laboratorio()
        self.tracking.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=HOY,
            next_expected_time="17:30", result="")
        self.assertIn("Hoy 17:30", self._fila(work.id, now=momento(HOY, "10:00")).observation)

    def test_manana_se_lee_como_manana_y_la_hora(self):
        work = self._en_laboratorio()
        self.tracking.confirm_for_next_day(
            work.id, operator="Ana", next_expected_date=MANANA,
            next_expected_time="15:00", result="")
        self.assertIn("Mañana 15:00",
                      self._fila(work.id, now=momento(HOY, "10:00")).observation)

    def test_la_ultima_respuesta_del_laboratorio_se_lee_sin_abrir_el_detalle(self):
        work = self._en_laboratorio()
        self.tracking.register_contact(
            work.id, operator="Ana", result="Lab confirmó salida 14:30",
            recorded_at=momento(HOY, "13:12"))
        self.assertIn("Lab confirmó salida 14:30",
                      self._fila(work.id, now=momento(HOY, "14:00")).observation)

    def test_el_medio_de_contacto_se_distingue_de_un_vistazo(self):
        llamada = self._en_laboratorio()
        self.tracking.register_contact(
            llamada.id, operator="Ana", channel="LLAMADA", result="Sale hoy",
            recorded_at=momento(HOY, "10:00"))
        whatsapp = self._en_laboratorio()
        self.tracking.register_contact(
            whatsapp.id, operator="Ana", channel="WHATSAPP", result="Sale hoy",
            recorded_at=momento(HOY, "10:00"))
        ahora = momento(HOY, "11:00")
        self.assertTrue(self._fila(llamada.id, now=ahora).observation.startswith("☎"))
        self.assertTrue(self._fila(whatsapp.id, now=ahora).observation.startswith("✆"))

    def test_el_plazo_comprometido_tambien_se_lee_en_dias_relativos(self):
        work = self._en_laboratorio(expected_date=MANANA)
        self.assertIn("Mañana 15:00",
                      self._fila(work.id, now=momento(HOY, "10:00")).observation)

    def test_el_detalle_conserva_la_fecha_absoluta(self):
        """En el detalle se verifica un dato, no se barre una lista."""
        work = self._en_laboratorio(expected_date=MANANA)
        detalle = self.tracking.work_detail(work.id, now=momento(HOY, "10:00"))
        self.assertEqual(detalle["expected"], f"{MANANA.strftime('%d-%m')} 15:00")


# ---------------------------------------------------------------- Interfaz

class InterfazRecepcionTests(unittest.TestCase):
    def test_la_barra_de_recepcion_trae_las_dos_discrepancias(self):
        barra = FUENTE[
            FUENTE.index("barra_recepcion = ctk.CTkFrame"):
            FUENTE.index("marco_seguimiento = ctk.CTkFrame")
        ]
        self.assertIn('text="No llegó"', barra)
        self.assertIn('text="+ No estaba en lista"', barra)
        self.assertIn("etiqueta_conciliacion", barra)

    def test_recibir_no_duplica_boton_porque_ya_es_la_accion_siguiente(self):
        barra = FUENTE[
            FUENTE.index("barra_recepcion = ctk.CTkFrame"):
            FUENTE.index("marco_seguimiento = ctk.CTkFrame")
        ]
        self.assertNotIn('text="Recibir"', barra)

    def test_la_conciliacion_sale_del_servicio_y_no_se_recalcula_en_la_ui(self):
        self.assertIn("controller.tracking.current_reception(sucursal)", FUENTE)
        self.assertIn('etiqueta_conciliacion.configure(text=recepcion_actual["line"])',
                      FUENTE)

    def test_marcar_no_llego_es_masivo_en_la_ui(self):
        bloque = FUENTE[FUENTE.index("def marcar_no_llego"):]
        self.assertIn("controller.tracking.mark_batch_not_arrived(", bloque[:1400])
        self.assertIn("seleccion_actual()", bloque[:400])

    def test_no_estaba_en_lista_busca_antes_de_pedir_datos(self):
        bloque = FUENTE[
            FUENTE.index("def abrir_no_estaba_en_lista"):
            FUENTE.index("def accion_seguimiento")
        ]
        self.assertIn("controller.tracking.search_receivable_orders(", bloque)
        self.assertIn("controller.tracking.add_unlisted_reception(", bloque)
        # No se vuelve a pedir cliente ni receta: se reutiliza el pedido.
        for campo in ("Cliente:", "Receta", "customer_name="):
            self.assertNotIn(campo, bloque)

    def test_la_barra_de_recepcion_solo_aparece_durante_una_recepcion(self):
        self.assertIn("barra_recepcion.pack_forget()", FUENTE)


class InterfazAlertaTests(unittest.TestCase):
    def test_la_alerta_vive_en_la_franja_siempre_visible(self):
        """En la barra superior, no en la cabecera de Caja.

        En la cabecera competia por el ancho con los seis importes de RC18 y
        terminaba recortando Gastos y Entregado. Arriba esta siempre delante y
        no le quita lugar a ningun dato.
        """
        barra = FUENTE[
            FUENTE.index("barra_superior = ctk.CTkFrame"):
            FUENTE.index("privacidad = FinancialPrivacy")
        ]
        self.assertIn("aviso_seguimiento = ctk.CTkButton", barra)
        self.assertIn("command=lambda: ir_a_pendientes_sucursal()", barra)

    def test_la_alerta_no_le_quita_ancho_a_los_seis_importes(self):
        cabecera = FUENTE[
            FUENTE.index('text="RESUMEN DE CAJA"'):
            FUENTE.index("columnas_operativas = COLUMNAS_OPERATIVAS")
        ]
        self.assertNotIn("aviso_seguimiento", cabecera)
        self.assertIn("cabecera.grid_columnconfigure(8, weight=1)", FUENTE)

    def test_la_alerta_muestra_cantidad_y_es_clicable(self):
        bloque = FUENTE[FUENTE.index("def refrescar_aviso_seguimiento"):]
        self.assertIn("""text=f"⚠ {principal['texto']} — clic para ver",""",
                      bloque[:2000])
        self.assertIn("pending_actions_for_branch(sucursal)", bloque[:1200])

    def test_la_alerta_es_de_la_sucursal_de_esta_caja(self):
        bloque = FUENTE[FUENTE.index("def refrescar_aviso_seguimiento"):]
        self.assertIn('sucursal = contexto_sucursal["sucursal"]', bloque[:900])
        self.assertIn("aviso_seguimiento.pack_forget()", bloque[:1100])

    def test_el_clic_abre_seguimiento_ya_filtrado(self):
        # El cierre del bloque se ancla al comentario que abre Seguimiento:
        # `refrescar_avisos()` dejó de ser único desde que Pedidos también lo
        # llama al avanzar o corregir un pedido.
        inicio = FUENTE.index("def ir_a_pendientes_sucursal")
        bloque = FUENTE[inicio:FUENTE.index("# ---- Seguimiento RC19", inicio)]
        self.assertIn('seleccionar_pestaña("Seguimiento")', bloque)
        self.assertIn("ir_a_atrasados()", bloque)
        self.assertIn('contexto_alerta["grupo"] = aviso_principal.get("grupo")', bloque)

    def test_la_alerta_aplica_el_grupo_sin_tocar_atrasados_a_mano(self):
        bloque = FUENTE[FUENTE.index("def ir_a_atrasados"):]
        self.assertIn('contexto_grupo["foco"] = grupo', bloque[:800])

    def test_la_cabecera_y_la_pestaña_no_pueden_discrepar(self):
        """Ambas leen la misma fuente y se refrescan juntas.

        Una definicion y exactamente dos invocaciones: la de `refrescar_avisos`
        (cabecera de Caja) y la del final de `refrescar_seguimiento`.
        """
        llamadas = [
            linea.strip() for linea in FUENTE.splitlines()
            if linea.strip() == "refrescar_aviso_seguimiento()"
        ]
        self.assertEqual(len(llamadas), 2)
        self.assertIn("def refrescar_aviso_seguimiento():", FUENTE)


class InterfazAgrupacionTests(unittest.TestCase):
    def test_los_seis_grupos_son_secciones_de_una_lista(self):
        self.assertIn("for clave_grupo, titulo_grupo, _etapa in GRUPOS_SEGUIMIENTO:", FUENTE)
        self.assertIn("cabecera_grupo = ctk.CTkFrame(", FUENTE)
        # RC26 reutiliza el encabezado, asi que el rotulo se arma al repintarlo.
        self.assertIn('text=f"  {titulo_grupo}  ·  {cantidad}"', FUENTE)
        self.assertIn("pintar_grupo(clave_grupo, titulo_grupo, len(filas_grupo), indice)",
                      FUENTE)

    def test_no_se_crearon_seis_barras_de_botones_ni_seis_pantallas(self):
        barra = FUENTE[
            FUENTE.index("botones_seguimiento = {}"):
            FUENTE.index("etiqueta_sucursal = ctk.CTkLabel")
        ]
        self.assertIn('FILTROS_VISIBLES = ("Activos", "Completados", "Todos")', FUENTE)
        self.assertIn("if nombre_filtro not in FILTROS_VISIBLES:", barra)

    def test_los_tres_botones_principales_siguen_siendo_tres(self):
        accion = FUENTE[
            FUENTE.index("boton_accion_siguiente = ctk.CTkButton"):
            FUENTE.index("etiqueta_seleccion = ctk.CTkLabel")
        ]
        self.assertEqual(accion.count("ctk.CTkButton("), 3)

    def test_la_seleccion_multiple_sigue_viva(self):
        for pieza in ("def alternar_marca", "def seleccionar_todo",
                      "def limpiar_seleccion", "ctk.CTkCheckBox("):
            self.assertIn(pieza, FUENTE)

    def test_un_grupo_enfocado_se_puede_deshacer(self):
        bloque = FUENTE[FUENTE.index("def enfocar_grupo"):]
        self.assertIn('contexto_grupo["foco"] = None if contexto_grupo["foco"] == clave',
                      bloque[:400])
        self.assertIn("clic para ver todo", FUENTE)

    def test_el_foco_de_grupo_llega_al_tablero(self):
        self.assertIn('group=contexto_grupo["foco"]', FUENTE)


if __name__ == "__main__":
    unittest.main()
