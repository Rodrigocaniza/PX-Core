"""BC-CAJA-PEDIDOS-ATENCION-002.

Contrato del slice, portado sobre la línea canónica rc.14: Pedidos responde
"qué requiere atención ahora", la entrada nunca es una hoja vacía, hay como
máximo tres acciones principales y "Corregir estado" no acepta un estado libre.
"""

from datetime import date
from pathlib import Path
import tempfile
import unittest

import CajaDiaria
from modulos.caja_diaria.application.services import (
    ATTENTION_FILTER, ATTENTION_GROUP_OVERDUE, ATTENTION_GROUP_TODAY,
    ATTENTION_GROUP_UPCOMING,
)
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import OrderStatus, allowed_order_transitions

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")
HOY = "17-08-2026"


class AttentionQueryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.directory.name) / "caja.sqlite3")
        self.base = {
            "fecha": HOY, "unidad": "PC", "caja_inicial": "500000",
            "cliente_documento": "4.123.456", "cliente_telefono": "0981 555 444",
            "sobre": "583", "vendedora": "Ana", "notas": "", "arm_org": "", "cod": "",
            "armazon": "100000", "cristal": "200000", "laboratorio": "LAB",
            "receta_dr": "DR", "total": "300000", "efectivo": "300000",
            "tarjeta_cheque": "", "ordenes": "", "cuotas": "", "saldo": "", "gastos": "",
        }

    def tearDown(self):
        self.controller.service.repository.close()
        self.directory.cleanup()

    def _pedido(self, cliente, entrega):
        _, entry = self.controller.add_manual_entry(
            {**self.base, "descripcion": cliente, "fecha_entrega": entrega}
        )
        return entry

    def _por_cliente(self, nombre):
        return next(
            order for order in self.controller.list_orders("Todos", today=HOY)
            if order.customer_name == nombre
        )

    def test_attention_filter_returns_only_undelivered_due_or_overdue(self):
        self._pedido("Atrasado", "14-08-2026")
        self._pedido("De hoy", HOY)
        self._pedido("Futuro", "20-08-2026")
        atencion = self.controller.list_orders(ATTENTION_FILTER, today=HOY)
        self.assertEqual(
            [order.customer_name for order in atencion], ["Atrasado", "De hoy"]
        )

        entregado = self._por_cliente("De hoy")
        self.controller.update_order_status(
            entregado.id, "LISTO", reason="Avance operativo", responsible="Ana"
        )
        self.controller.update_order_status(
            self._por_cliente("De hoy").id, "ENTREGADO",
            reason="Avance operativo", responsible="Ana",
        )
        restante = self.controller.list_orders(ATTENTION_FILTER, today=HOY)
        self.assertEqual([order.customer_name for order in restante], ["Atrasado"])

    def test_groups_are_ordered_and_never_leave_an_empty_sheet(self):
        self._pedido("Futuro", "20-08-2026")
        grupos = dict(self.controller.order_attention_groups(today=HOY))
        self.assertEqual(
            list(grupos), [ATTENTION_GROUP_OVERDUE, ATTENTION_GROUP_TODAY, ATTENTION_GROUP_UPCOMING]
        )
        # Sin atrasados ni entregas de hoy, Pedidos todavía tiene algo útil que mostrar.
        self.assertEqual(grupos[ATTENTION_GROUP_OVERDUE], [])
        self.assertEqual(grupos[ATTENTION_GROUP_TODAY], [])
        self.assertEqual([order.customer_name for order in grupos[ATTENTION_GROUP_UPCOMING]], ["Futuro"])

        self._pedido("Atrasado viejo", "10-08-2026")
        self._pedido("Atrasado nuevo", "15-08-2026")
        atrasados = dict(self.controller.order_attention_groups(today=HOY))[ATTENTION_GROUP_OVERDUE]
        self.assertEqual(
            [order.customer_name for order in atrasados], ["Atrasado viejo", "Atrasado nuevo"]
        )

    def test_alert_count_matches_exactly_what_the_alert_opens(self):
        self._pedido("Atrasado", "14-08-2026")
        self._pedido("De hoy", HOY)
        self._pedido("Futuro", "20-08-2026")
        grupos = dict(self.controller.order_attention_groups(today=HOY))
        contados = len(grupos[ATTENTION_GROUP_OVERDUE]) + len(grupos[ATTENTION_GROUP_TODAY])
        self.assertEqual(contados, len(self.controller.list_orders(ATTENTION_FILTER, today=HOY)))

    def test_latest_revision_is_one_query_and_keeps_the_last_entry(self):
        self._pedido("Cliente", HOY)
        pedido = self._por_cliente("Cliente")
        self.assertEqual(self.controller.latest_order_revisions(), {})
        self.controller.update_order_status(
            pedido.id, "LISTO", reason="Llegó del laboratorio", responsible="Ana"
        )
        self.controller.update_order_status(
            pedido.id, "PENDIENTE", reason="Cristal rayado", responsible="Sol"
        )
        ultima = self.controller.latest_order_revisions()[pedido.id]
        self.assertEqual(
            (ultima["previous_status"], ultima["new_status"], ultima["responsible"], ultima["reason"]),
            ("LISTO", "PENDIENTE", "Sol", "Cristal rayado"),
        )


class ClosedStateCorrectionTests(unittest.TestCase):
    def test_allowed_transitions_are_a_closed_list_derived_from_the_domain(self):
        self.assertEqual(allowed_order_transitions(OrderStatus.PENDING), (OrderStatus.READY,))
        self.assertEqual(
            allowed_order_transitions("LISTO"), (OrderStatus.PENDING, OrderStatus.DELIVERED)
        )
        # El retroceso auditado desde ENTREGADO sigue permitido.
        self.assertEqual(allowed_order_transitions("ENTREGADO"), (OrderStatus.PENDING,))

    def test_free_text_states_are_rejected_before_reaching_the_repository(self):
        with self.assertRaises(ValueError):
            allowed_order_transitions("EN CAMINO")

    def test_controller_exposes_the_same_closed_list_as_plain_strings(self):
        from modulos.caja_diaria.ui.controller import CashDayUIController

        self.assertEqual(CashDayUIController.allowed_order_transitions("LISTO"), ("PENDIENTE", "ENTREGADO"))


class AuditedCorrectionPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.controller = build_cash_day_controller(Path(self.directory.name) / "caja.sqlite3")
        _, self.entry = self.controller.add_manual_entry({
            "fecha": HOY, "unidad": "PC", "caja_inicial": "500000",
            "descripcion": "Cliente", "cliente_documento": "", "cliente_telefono": "0981 555 444",
            "sobre": "9", "vendedora": "Ana", "fecha_entrega": HOY, "notas": "",
            "arm_org": "", "cod": "", "armazon": "100000", "cristal": "0",
            "laboratorio": "", "receta_dr": "", "total": "100000", "efectivo": "100000",
            "tarjeta_cheque": "", "ordenes": "", "cuotas": "", "saldo": "", "gastos": "",
        })
        self.order = self.controller.list_orders("Todos", today=HOY)[0]

    def tearDown(self):
        self.controller.service.repository.close()
        self.directory.cleanup()

    def test_delivered_to_pending_still_requires_reason_and_responsible(self):
        self.controller.update_order_status(self.order.id, "LISTO", reason="Listo", responsible="Ana")
        self.controller.update_order_status(self.order.id, "ENTREGADO", reason="Entregado", responsible="Ana")
        with self.assertRaisesRegex(InvalidCashDayError, "motivo"):
            self.controller.update_order_status(self.order.id, "PENDIENTE", reason="", responsible="Ana")
        with self.assertRaisesRegex(InvalidCashDayError, "responsable"):
            self.controller.update_order_status(self.order.id, "PENDIENTE", reason="Se rompió", responsible="")

    def test_invalid_transition_is_refused_by_the_domain(self):
        with self.assertRaisesRegex(InvalidCashDayError, "transición de pedido inválida"):
            self.controller.update_order_status(
                self.order.id, "ENTREGADO", reason="Salto", responsible="Ana"
            )


class PedidosUiContractTests(unittest.TestCase):
    def test_columns_trade_noise_for_context(self):
        claves = [clave for clave, _t, _a, _an in CajaDiaria.ORDER_COLUMN_SPECS]
        self.assertEqual(
            claves,
            ["entrega", "cliente", "telefono", "sobre", "sucursal", "vendedora", "estado", "novedad"],
        )
        self.assertNotIn("documento", claves)
        self.assertNotIn("origen", claves)

    def test_attention_is_the_default_view_and_the_alert_target(self):
        self.assertIn('filtro_pedidos = ctk.StringVar(value=ATTENTION_FILTER)', SOURCE)
        self.assertIn('refrescar_pedidos(ATTENTION_FILTER)', SOURCE)
        # La grilla se puebla al abrir la ventana, no recién al tocar un filtro.
        self.assertIn("    refrescar_avisos()\n    refrescar_pedidos()\n", SOURCE)

    def test_exactly_three_primary_actions_and_three_filters(self):
        acciones = [
            texto for texto in ("Corregir estado", "Marcar entregado", "Marcar listo")
            if f'"{texto}"' in SOURCE
        ]
        self.assertEqual(len(acciones), 3)
        self.assertNotIn('"Marcar pendiente"', SOURCE)
        self.assertIn(
            'for nombre in (ATTENTION_FILTER, ATTENTION_GROUP_UPCOMING, "Todos"):', SOURCE
        )

    def test_correction_dialog_uses_a_readonly_closed_selector(self):
        self.assertIn('destinos = controller.allowed_order_transitions(actual)', SOURCE)
        self.assertIn('cuerpo, values=list(destinos), state="readonly", width=340,', SOURCE)
        self.assertIn('text="Observación / motivo (obligatorio)"', SOURCE)

    def test_group_headers_are_not_actionable_rows(self):
        self.assertIn('if not seleccion or seleccion[0].startswith(ORDER_ROW_PREFIX_GROUP):', SOURCE)
        self.assertIn('if iid.startswith(ORDER_ROW_PREFIX_GROUP):', SOURCE)

    def test_color_is_reserved_for_overdue_and_state(self):
        self.assertIn('grilla_pedidos.tag_configure("grupo_atrasado", background="#FDECEC", foreground="#A32626")', SOURCE)
        self.assertIn('grilla_pedidos.tag_configure("atrasado", foreground="#A32626")', SOURCE)

    def test_schema_is_unchanged_at_the_rc14_baseline(self):
        # El port no agrega migraciones: usa order_status_revisions (014) tal cual
        # y conserva la 015 que trajo el administrador con arqueos por correo.
        migraciones = sorted(Path("modulos/caja_diaria/infrastructure/migrations").glob("*.sql"))
        self.assertEqual(len(migraciones), 15)
        self.assertEqual(migraciones[-1].name, "015_admin_counts_notifications.sql")
        self.assertIn("014_order_status_revisions.sql", [ruta.name for ruta in migraciones])


class WhatsAppLinkTests(unittest.TestCase):
    def test_paraguayan_numbers_are_accepted_in_the_formats_actually_typed(self):
        for texto in ("0981 555 444", "+595 981-555444", "595981555444", "981555444"):
            self.assertEqual(CajaDiaria.enlace_whatsapp(texto), "https://wa.me/595981555444", texto)

    def test_unusable_phones_return_none_instead_of_a_broken_link(self):
        for texto in ("", None, "sin datos", "123", "0981555444123456"):
            self.assertIsNone(CajaDiaria.enlace_whatsapp(texto), texto)


if __name__ == "__main__":
    unittest.main()
