"""BC-CAJA-RC18: jerarquia y agrupacion del resumen de caja.

Contrato de presentacion unicamente. Ninguna prueba de este modulo toca
calculos, servicios, SQLite, correo ni cierre.
"""

import unittest

from CajaDiaria import (
    KPI_PRINCIPALES,
    KPI_SECUNDARIOS,
    metricas_resumen_kpi,
    perfil_visual,
)

COMPACTO = perfil_visual(1366, 768)
FULL_HD = perfil_visual(1920, 1080)


class ResumenKpiContractTests(unittest.TestCase):
    def test_los_seis_importes_canonicos_siguen_presentes(self):
        claves = [clave for clave, _t, _c in KPI_PRINCIPALES + KPI_SECUNDARIOS]
        self.assertEqual(
            sorted(claves),
            ["efectivo", "entregado", "esperado", "gastos", "tarjeta", "ventas"],
        )
        self.assertEqual(len(set(claves)), 6)

    def test_los_importes_que_gobiernan_la_operacion_son_los_principales(self):
        self.assertEqual(
            [clave for clave, _t, _c in KPI_PRINCIPALES],
            ["ventas", "efectivo", "esperado"],
        )

    def test_full_hd_jerarquiza_el_importe_principal_sobre_el_secundario(self):
        metricas = metricas_resumen_kpi(FULL_HD)
        self.assertEqual(metricas["fuente_principal"], FULL_HD["fuente_kpi"])
        self.assertGreater(metricas["fuente_principal"], metricas["fuente_secundaria"])
        self.assertGreater(metricas["fuente_principal"], metricas["fuente_titulo"])

    def test_viewsonic_24_gana_legibilidad_frente_al_perfil_compacto(self):
        # Antes de RC18 el importe se dibujaba a 10 px en ambos perfiles.
        self.assertGreater(
            metricas_resumen_kpi(FULL_HD)["fuente_principal"],
            metricas_resumen_kpi(COMPACTO)["fuente_principal"],
        )
        self.assertGreater(metricas_resumen_kpi(FULL_HD)["fuente_principal"], 10)

    def test_las_alturas_de_cabecera_conservan_el_piso_ya_validado(self):
        # El alto efectivo lo fija el contenido medido del resumen (smoke GUI
        # real: 55 px en full-hd, 44 px en compacto). Estas constantes son el
        # piso heredado de RC15/RC17 y no deben crecer por si solas.
        self.assertEqual(metricas_resumen_kpi(COMPACTO)["cabecera_alto"], 42)
        self.assertEqual(metricas_resumen_kpi(FULL_HD)["cabecera_alto"], 52)

    def test_la_cabecera_se_ajusta_al_contenido_real_del_resumen(self):
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertEqual(fuente.count("resumen_compacto.winfo_reqheight() + 8"), 2)

    def test_las_etiquetas_kpi_declaran_altura_propia(self):
        # Sin altura explicita CTkLabel pide 28 px y la tarjeta ocupa 59 px en
        # todos los perfiles, anulando la jerarquia y desbordando la cabecera.
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn("height=tam_titulo + 6", fuente)
        self.assertIn("height=tam_valor + 8", fuente)

    def test_el_resumen_se_agrupa_en_bloques_separados(self):
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        self.assertIn("bloque_kpi_principal", fuente)
        self.assertIn("bloque_kpi_secundario", fuente)
        self.assertIn("alto_cabecera_full_hd", fuente)

    def _region(self, fuente, inicio, fin):
        return fuente[fuente.index(inicio):fuente.index(fin)]

    def test_el_contexto_de_cabecera_escala_con_el_perfil(self):
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        contexto = self._region(
            fuente, 'text="RESUMEN DE CAJA"', "columnas_operativas = COLUMNAS_OPERATIVAS",
        )
        self.assertEqual(contexto.count("fuente_chrome_cabecera"), 3)
        self.assertNotIn('size=10, weight="bold"', contexto)

    def test_los_controles_de_estado_escalan_con_el_perfil(self):
        fuente = open("CajaDiaria.py", encoding="utf-8").read()
        estado = self._region(
            fuente, "estado_operativo = ctk.CTkFrame", "resumen_compacto = ctk.CTkFrame",
        )
        self.assertEqual(estado.count("size=fuente_estado"), 3)
        for residuo in ('size=9, weight="bold"', "height=24,", "height=20,"):
            self.assertNotIn(residuo, estado, residuo)

    def test_no_se_alteran_las_metricas_economicas_del_perfil(self):
        self.assertEqual((COMPACTO["fuente"], COMPACTO["fila"]), (9, 27))
        self.assertEqual(FULL_HD["fuente_kpi"], 20)


if __name__ == "__main__":
    unittest.main()
