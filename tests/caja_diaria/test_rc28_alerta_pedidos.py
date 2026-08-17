"""BC-CAJA-RC28: la alerta de Pedidos transporta el filtro que la originó.

Bug real de producción: la cabecera mostraba `Trabajos 2` contando `Hoy` más
`Atrasados`, pero el clic aplicaba solamente el filtro `Hoy`. Con los dos
pendientes vencidos, la pantalla abría en blanco y la operadora tenía que
volver a buscar a mano lo que el sistema ya sabía que necesitaba atención.

La regla: toda alerta operativa lleva el contexto exacto que la generó.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from modulos.caja_diaria.application.services import (
    FILTRO_REQUIEREN_ATENCION,
    CashDayService,
)
from modulos.caja_diaria.domain.models import Order, OrderOrigin, OrderStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.caja_diaria.ui.controller import CashDayUIController

HOY = date.today()
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)
FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


class Base(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteCashDayRepository(":memory:")
        self.service = CashDayService(self.repository)
        self.controller = CashDayUIController(self.service)

    def tearDown(self):
        self.repository.close()

    def _pedido(self, envelope, entrega, estado=OrderStatus.PENDING, branch="PC"):
        pedido = Order(
            delivery_date=entrega, branch=branch, customer_name=f"Cliente {envelope}",
            saleswoman="Ana", envelope=envelope, origin=OrderOrigin.CASH_REGISTER,
            status=estado)
        self.repository.save_order(pedido)
        return pedido

    def _caso_real(self):
        """El escenario exacto de producción: dos vencidos, nada para hoy."""
        return [self._pedido("2999", AYER - timedelta(days=2)),
                self._pedido("0239", AYER)]


class AlertaTransportaSuContextoTests(Base):
    def test_la_alerta_cuenta_lo_que_requiere_atencion(self):
        self._caso_real()
        self._pedido("FUTURO", MANANA)
        alerta = self.controller.orders_alert()
        self.assertEqual(alerta["cantidad"], 2)
        self.assertEqual(alerta["filtro"], FILTRO_REQUIEREN_ATENCION)

    def test_el_filtro_de_la_alerta_abre_exactamente_esos_pedidos(self):
        """El bug: la alerta decía 2 y el clic abría 0."""
        esperados = {p.envelope for p in self._caso_real()}
        self._pedido("FUTURO", MANANA)
        alerta = self.controller.orders_alert()
        abiertos = self.controller.list_orders(alerta["filtro"])
        self.assertEqual(len(abiertos), alerta["cantidad"])
        self.assertEqual({p.envelope for p in abiertos}, esperados)

    def test_el_filtro_viejo_habria_abierto_vacio(self):
        """Deja constancia de por qué no alcanzaba con `Hoy`."""
        self._caso_real()
        self.assertEqual(len(self.controller.list_orders("Hoy")), 0)
        self.assertEqual(self.controller.orders_alert()["cantidad"], 2)

    def test_ningun_pedido_ajeno_al_grupo_aparece(self):
        self._caso_real()
        self._pedido("PROXIMO", MANANA)
        self._pedido("ENTREGADO-HOY", HOY, estado=OrderStatus.DELIVERED)
        abiertos = self.controller.list_orders(FILTRO_REQUIEREN_ATENCION)
        sobres = {p.envelope for p in abiertos}
        self.assertNotIn("PROXIMO", sobres)
        self.assertNotIn("ENTREGADO-HOY", sobres)

    def test_lo_entregado_no_cuenta_como_pendiente(self):
        """`Trabajos` es lo que falta entregar, no lo que ya se entregó."""
        self._pedido("YA", HOY, estado=OrderStatus.DELIVERED)
        self.assertEqual(self.controller.orders_alert()["cantidad"], 0)

    def test_lo_de_hoy_sin_entregar_si_cuenta(self):
        self._pedido("HOY-1", HOY)
        self._pedido("HOY-2", HOY, estado=OrderStatus.READY)
        self.assertEqual(self.controller.orders_alert()["cantidad"], 2)

    def test_la_alerta_trae_los_ids_de_lo_que_la_origino(self):
        pedidos = self._caso_real()
        self.assertEqual(set(self.controller.orders_alert()["ids"]),
                         {p.id for p in pedidos})

    def test_sin_pendientes_la_alerta_es_cero(self):
        self._pedido("PROXIMO", MANANA)
        alerta = self.controller.orders_alert()
        self.assertEqual(alerta["cantidad"], 0)
        self.assertEqual(alerta["ids"], [])


class SucursalRespetadaTests(Base):
    def test_la_alerta_es_de_la_caja_actual(self):
        self._caso_real()                                    # PC
        self._pedido("PIL-1", AYER, branch="PILAR")
        self.assertEqual(self.controller.orders_alert(branch="PC")["cantidad"], 2)
        self.assertEqual(self.controller.orders_alert(branch="PILAR")["cantidad"], 1)
        self.assertEqual(self.controller.orders_alert()["cantidad"], 3)

    def test_el_clic_abre_los_de_su_caja_y_no_los_del_otro_local(self):
        self._caso_real()
        self._pedido("PIL-1", AYER, branch="PILAR")
        abiertos = self.controller.list_orders(FILTRO_REQUIEREN_ATENCION, branch="PC")
        self.assertEqual({p.envelope for p in abiertos}, {"2999", "0239"})

    def test_la_sucursal_no_distingue_mayusculas(self):
        self._caso_real()
        self.assertEqual(
            len(self.controller.list_orders(FILTRO_REQUIEREN_ATENCION, branch="pc")), 2)

    def test_ver_todos_no_filtra_por_sucursal_ni_por_grupo(self):
        self._caso_real()
        self._pedido("PIL-1", AYER, branch="PILAR")
        self._pedido("PROXIMO", MANANA)
        self.assertEqual(len(self.controller.list_orders("Todos")), 4)


class FiltrosPreviosIntactosTests(Base):
    def test_hoy_atrasados_y_proximos_conservan_su_semantica(self):
        self._pedido("VENCIDO", AYER)
        self._pedido("DE-HOY", HOY)
        self._pedido("FUTURO", MANANA)
        self.assertEqual(
            [p.envelope for p in self.controller.list_orders("Atrasados")], ["VENCIDO"])
        self.assertEqual(
            [p.envelope for p in self.controller.list_orders("Hoy")], ["DE-HOY"])
        self.assertEqual(
            [p.envelope for p in self.controller.list_orders("Próximos")], ["FUTURO"])

    def test_requieren_atencion_es_la_union_de_atrasados_y_hoy_sin_entregar(self):
        self._pedido("VENCIDO", AYER)
        self._pedido("DE-HOY", HOY)
        self._pedido("FUTURO", MANANA)
        atencion = {p.envelope for p in
                    self.controller.list_orders(FILTRO_REQUIEREN_ATENCION)}
        self.assertEqual(atencion, {"VENCIDO", "DE-HOY"})


class InterfazTests(unittest.TestCase):
    def test_la_alerta_navega_con_su_propio_filtro(self):
        self.assertIn("command=lambda: abrir_pedidos_desde_alerta()", FUENTE)
        bloque = FUENTE[FUENTE.index("def abrir_pedidos_desde_alerta"):]
        self.assertIn('seleccionar_pestaña("Pedidos")', bloque[:500])
        self.assertIn('aviso_pedidos.get("filtro")', bloque[:500])
        # El desvio fijo a "Hoy" era el bug.
        self.assertNotIn('refrescar_pedidos("Hoy")', FUENTE)

    def test_la_alerta_y_la_vista_leen_la_misma_consulta(self):
        bloque = FUENTE[FUENTE.index("def refrescar_avisos"):]
        self.assertIn("controller.orders_alert(", bloque[:900])
        self.assertIn("aviso_pedidos.update(alerta)", bloque[:900])

    def test_pedidos_abre_en_lo_que_requiere_atencion(self):
        self.assertIn("filtro_pedidos = ctk.StringVar(value=FILTRO_REQUIEREN_ATENCION)",
                      FUENTE)

    def test_el_contexto_del_filtro_queda_visible(self):
        bloque = FUENTE[FUENTE.index("def refrescar_pedidos"):]
        self.assertIn('text=f"Mostrando: {activo} ({len(pedidos)})"', bloque[:2200])
        self.assertIn("contexto_pedidos.pack(", bloque[:2200])

    def test_ver_todos_quita_el_filtro(self):
        bloque = FUENTE[
            FUENTE.index("contexto_pedidos = ctk.CTkFrame"):
            FUENTE.index("marco_pedidos = ctk.CTkFrame")
        ]
        self.assertIn('text="Ver todos"', bloque)
        self.assertIn('command=lambda: refrescar_pedidos("Todos")', bloque)
        # Con "Todos" el contexto no tiene nada que decir y se retira.
        self.assertIn("contexto_pedidos.pack_forget()", FUENTE)

    def test_el_vacio_es_explicito(self):
        self.assertIn('"No hay pedidos pendientes."', FUENTE)
        self.assertIn("vacio_pedidos.place(", FUENTE)

    def test_pedidos_respeta_la_caja_actual(self):
        bloque = FUENTE[FUENTE.index("def refrescar_pedidos"):]
        self.assertIn('caja = contexto_sucursal["caja"] or None', bloque[:1200])
        self.assertIn('sucursal = caja if activo != "Todos" else None', bloque[:1200])

    def test_el_filtro_del_grupo_esta_entre_los_botones(self):
        self.assertIn(
            'for nombre in (FILTRO_REQUIEREN_ATENCION, "Hoy", "Atrasados", '
            '"Próximos", "Todos"):', FUENTE)


if __name__ == "__main__":
    unittest.main()
