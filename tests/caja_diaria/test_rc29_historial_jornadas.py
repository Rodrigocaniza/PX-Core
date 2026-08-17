"""BC-CAJA-RC29: cada jornada de Historial se lee como una unidad visual.

Ajuste exclusivamente visual. El dominio, las fórmulas, qué registros aparecen
y en qué orden no se tocan: lo único que cambia es que la jornada deja de ser
una cabecera suelta seguida de filas hermanas y pasa a ser una tarjeta que
contiene todo lo del día.

Estas pruebas fijan dos cosas: que la agrupación existe en el código, y que el
contenido económico sigue siendo idéntico al de antes del cambio.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from modulos.caja_diaria.domain.models import (
    BUSINESS_TIMEZONE,
    CashDay,
    CashDayStatus,
    CashEntry,
)

FUENTE = open("CajaDiaria.py", encoding="utf-8").read()
HISTORIAL = FUENTE[
    FUENTE.index("    def consultar_historial():"):
    FUENTE.index("    def rango_rapido(")
]


class ContenidoIntactoTests(unittest.TestCase):
    """El texto de la jornada es el mismo que producía `texto_estado`."""

    def _dia(self, cerrado=False):
        dia = CashDay(business_date=date(2026, 8, 12), unit="PC", opening_cash=100_000)
        dia = dia.add_entry(CashEntry(
            description="Venta 1", total=700_000, cash=300_000,
            card_check=200_000, expenses=0))
        if cerrado:
            dia = dia.close(
                closed_at=datetime(2026, 8, 12, 18, 30, tzinfo=BUSINESS_TIMEZONE))
        return dia

    def test_la_composicion_reproduce_el_texto_original(self):
        """`texto_estado` = estado · resumen [+ detalle]. Sin cambios."""
        import re
        bloque = FUENTE[
            FUENTE.index("    def texto_estado(cash_day):"):
            FUENTE.index("    def tiene_saldo_cliente(")
        ]
        self.assertIn(
            'texto = f"{estado_dia(cash_day)}   ·   {resumen_economico_dia(cash_day)}"',
            bloque)
        self.assertIn('return f"{texto}\\n\\n{detalle}" if detalle else texto', bloque)

    def test_el_resumen_conserva_sus_seis_cifras(self):
        bloque = FUENTE[
            FUENTE.index("    def resumen_economico_dia(cash_day):"):
            FUENTE.index("    def detalle_sesion_dia(cash_day):")
        ]
        for rotulo in ("Efectivo actual", "Total ventas", "Gastos",
                       "Entregado a administración", "Efectivo final"):
            self.assertIn(rotulo, bloque)
        self.assertIn("totales = cash_day.totals()", bloque)
        # Ninguna cifra se recalcula: sigue saliendo de totals().
        self.assertNotIn("sum(", bloque)

    def test_el_detalle_de_sesion_conserva_sus_cuatro_datos(self):
        bloque = FUENTE[
            FUENTE.index("    def detalle_sesion_dia(cash_day):"):
            FUENTE.index("    def texto_estado(cash_day):")
        ]
        for rotulo in ("Apertura real", "Cierre real", "Duración", "Hora extra"):
            self.assertIn(rotulo, bloque)
        # Sigue vacío mientras la jornada no cerró.
        self.assertIn("if cash_day.closed_at is None", bloque)

    def test_el_aviso_de_cierre_sigue_usando_texto_estado(self):
        self.assertIn('messagebox.showinfo("Caja cerrada", texto_estado(cash_day)',
                      FUENTE)


class JornadaComoUnidadTests(unittest.TestCase):
    def test_cada_jornada_es_una_tarjeta(self):
        self.assertIn("tarjeta = ctk.CTkFrame(", HISTORIAL)
        self.assertIn("tarjeta._bc_jornada_historial = True", HISTORIAL)
        self.assertIn("border_width=1", HISTORIAL)

    def test_todo_lo_del_dia_cuelga_de_su_tarjeta(self):
        """Cabecera, resumen, detalle y movimientos son hijos de la jornada."""
        self.assertIn("cabecera = ctk.CTkFrame(tarjeta,", HISTORIAL)
        self.assertIn("fila = ctk.CTkFrame(tarjeta,", HISTORIAL)
        # Antes colgaban del scroll y eran hermanas de la cabecera.
        self.assertNotIn("ctk.CTkFrame(lista_historial, fg_color=color_fila)", HISTORIAL)
        self.assertNotIn('cabecera = ctk.CTkFrame(lista_historial', HISTORIAL)

    def test_hay_separacion_vertical_entre_jornadas(self):
        self.assertIn('tarjeta.pack(fill="x", padx=4, pady=(0, 10))', HISTORIAL)

    def test_la_fecha_manda_sobre_el_resto(self):
        self.assertIn('text=cash_day.business_date.strftime("%d-%m-%Y")', HISTORIAL)
        self.assertIn('size=perfil["fuente"] + 3, weight="bold"', HISTORIAL)
        # Ya no va todo en una sola etiqueta junto al estado y las cifras.
        self.assertNotIn(
            "text=f\"{cash_day.business_date.strftime('%d-%m-%Y')} · "
            "{texto_estado(cash_day)}\"", HISTORIAL)

    def test_el_estado_es_un_chip_compacto_y_no_pinta_el_bloque(self):
        self.assertIn('text=f"  {estado_dia(cash_day)}  ", corner_radius=7', HISTORIAL)
        self.assertIn('abierto = estado_dia(cash_day) == "ABIERTO"', HISTORIAL)
        # El fondo de la tarjeta es neutro, no un color por estado.
        self.assertIn('fg_color="#FFFFFF", corner_radius=8', HISTORIAL)

    def test_abierto_y_cerrado_se_distinguen(self):
        self.assertIn('fg_color="#FFF3CD" if abierto else "#DDF5E8"', HISTORIAL)
        self.assertIn('text_color="#7A4B00" if abierto else "#17633A"', HISTORIAL)

    def test_el_detalle_de_sesion_queda_secundario_y_compacto(self):
        self.assertIn("detalle_sesion = detalle_sesion_dia(cash_day)", HISTORIAL)
        self.assertIn('detalle_sesion.replace("\\n", "    ")', HISTORIAL)
        self.assertIn("text_color=color_suave", HISTORIAL)

    def test_editar_caja_sigue_a_la_derecha(self):
        bloque = HISTORIAL[HISTORIAL.index('text="Editar caja"'):]
        self.assertIn('.pack(side="right")', bloque[:400])


class MovimientosIntactosTests(unittest.TestCase):
    def test_la_fila_conserva_todos_sus_datos(self):
        for pieza in ("{entry.description}", "Total {formatear_monto(entry.total or 0)}",
                      "Efectivo {formatear_monto(entry.cash or 0)}",
                      "Tarj./Cheq. {formatear_monto(entry.card_check or 0)}",
                      "Gastos {formatear_monto(entry.expenses or 0)}",
                      "{estado_texto}"):
            self.assertIn(pieza, HISTORIAL)

    def test_editar_y_anular_siguen_en_la_fila(self):
        self.assertIn('text="Editar", width=65, state=habilitado', HISTORIAL)
        self.assertIn('text="Anular", width=65, state=habilitado', HISTORIAL)
        self.assertIn("cargar_para_editar(d, e)", HISTORIAL)
        self.assertIn("anular_desde_historial(d, e)", HISTORIAL)

    def test_la_habilitacion_no_cambio(self):
        self.assertIn(
            'if cash_day.status.value == "OPEN" and entry.status.value == "ACTIVE"',
            HISTORIAL)

    def test_los_anulados_conservan_su_rojo_dentro_del_dia(self):
        self.assertIn('color_fila = "#FDECEC" if es_anulado', HISTORIAL)
        self.assertIn('text_color="#A32626" if es_anulado', HISTORIAL)
        self.assertIn("if entry.void_reason:", HISTORIAL)
        # Y la fila anulada sigue colgando de la tarjeta del dia.
        self.assertIn("fila = ctk.CTkFrame(tarjeta,", HISTORIAL)

    def test_el_orden_cronologico_no_se_toca(self):
        self.assertIn("for cash_day in cash_days:", HISTORIAL)
        self.assertIn("for indice_entry, entry in enumerate(cash_day.entries):", HISTORIAL)
        for residuo in ("sorted(cash_days", "reversed(cash_days",
                        "sorted(cash_day.entries"):
            self.assertNotIn(residuo, HISTORIAL)

    def test_los_registros_que_aparecen_son_los_mismos(self):
        self.assertIn("controller.list_history_range(", HISTORIAL)
        self.assertIn('resumen_historial.configure(text=f"{len(cash_days)} jornadas',
                      HISTORIAL)


class DensidadYFiltrosTests(unittest.TestCase):
    def test_historial_sigue_en_un_scroll_continuo(self):
        self.assertIn("lista_historial = ctk.CTkScrollableFrame(tab_historial", FUENTE)
        for residuo in ("paginacion_historial", "pagina_historial", "historial_page"):
            self.assertNotIn(residuo, FUENTE)

    def test_los_filtros_superiores_no_se_tocaron(self):
        for texto in ('text="Consultar"', '("Hoy", lambda: rango_rapido(1))',
                      '("7 días", lambda: rango_rapido(7))',
                      '("Este mes", lambda: rango_rapido(mes=True))'):
            self.assertIn(texto, FUENTE)

    def test_no_se_introdujo_datepicker_en_historial(self):
        bloque = FUENTE[
            FUENTE.index("    filtros_historial = ctk.CTkFrame"):
            FUENTE.index("    def cargar_para_editar(")
        ]
        for residuo in ("DateEntry", "Calendar(", "abrir_selector_fecha_historial"):
            self.assertNotIn(residuo, bloque)


if __name__ == "__main__":
    unittest.main()
