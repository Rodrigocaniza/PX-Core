"""Contrato del slice BC-CAJA-APERTURA-CAJA-001.

La caja se abre siempre con la fecha y la hora de hoy. El histórico se mira por
`Consultar otro día`, en sólo lectura.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from modulos.caja_diaria.bootstrap import build_cash_day_controller

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_la_fecha_operativa_no_se_tipea_y_arranca_en_hoy():
    assert 'campos_manual["fecha"].insert(0, fecha_de_hoy())' in SOURCE
    assert 'campos_manual["fecha"].bind("<Key>", lambda _event: "break")' in SOURCE
    assert 'def fecha_de_hoy():' in SOURCE
    assert 'return date.today().strftime(FORMATO_FECHA_OPERATIVA)' in SOURCE
    # La fecha ya no se escribe a mano en ninguna parte de la cabecera.
    assert 'campos_manual["fecha"].insert(0, date.today()' not in SOURCE


def test_abrir_caja_usa_siempre_el_dia_de_hoy():
    assert 'texto_abrir = "ABRIR CAJA" if compacta else "ABRIR CAJA DE HOY"' in SOURCE
    assert "text=texto_abrir, command=abrir_caja_hoy" in SOURCE
    assert "ABRIR / CONSULTAR" not in SOURCE
    apertura = SOURCE[SOURCE.index("def abrir_caja_hoy():"):SOURCE.index("def volver_a_hoy():")]
    assert "if not es_dia_de_hoy():" in apertura
    assert "fijar_fecha_operativa(fecha_de_hoy())" in apertura


def test_no_se_puede_abrir_una_caja_que_no_sea_la_de_hoy():
    guardia = SOURCE[SOURCE.index("def abrir_o_consultar():"):SOURCE.index("def cerrar_caja():")]
    assert "if not es_dia_de_hoy():" in guardia
    assert "Sólo se puede abrir la caja de hoy." in guardia
    # El arqueo de apertura sólo se ofrece después de pasar la guardia.
    assert guardia.index("if not es_dia_de_hoy():") < guardia.index(
        'solicitar_conteo_obligatorio("Arqueo de apertura")'
    )


def test_consultar_otro_dia_es_el_unico_acceso_al_historico_y_es_solo_lectura():
    assert 'texto_otro_dia = "Otro día" if compacta else "Consultar otro día"' in SOURCE
    assert "text=texto_otro_dia, command=consultar_otro_dia" in SOURCE
    assert 'text="Volver a hoy"' in SOURCE
    consulta = SOURCE[SOURCE.index("def consultar_otro_dia():"):SOURCE.index("boton_abrir = ctk.CTkButton(")]
    assert "controller.load_day(texto" in consulta
    assert "No hay caja registrada el" in consulta
    assert "controller.admin.open_from_count" not in consulta
    assert 'text="SÓLO LECTURA", width=92' in SOURCE
    assert "operable = abierta and es_dia_de_hoy()" in SOURCE
    assert 'estado_control = "normal" if operable else "disabled"' in SOURCE
    assert 'estado_edicion["caja_abierta"] = operable' in SOURCE


def test_caja_inicial_esta_destacada_en_la_cabecera():
    cabecera = SOURCE[SOURCE.index("controles_cabecera = ["):SOURCE.index("FORMATO_FECHA_OPERATIVA")]
    assert 'destacado = clave == "caja_inicial"' in cabecera
    assert "text_color=color_azul if destacado else COLOR_TEXTO_SUAVE" in cabecera
    assert "border_width=2, border_color=color_azul" in cabecera


def test_la_hora_de_apertura_se_muestra_y_no_se_pide():
    assert "def sufijo_hora_apertura(cash_day):" in SOURCE
    assert 'return " · " + cash_day.opened_at.astimezone().strftime("%H:%M")' in SOURCE
    assert 'text=("Estado: ABIERTO" + sufijo_hora_apertura(cash_day) if abierta' in SOURCE
    # La hora nunca se pide: no hay campo ni selector de hora en la apertura.
    assert 'campos_manual["hora"]' not in SOURCE


def test_el_datepicker_compartido_y_factufacil_no_se_tocaron():
    assert "def abrir_selector_fecha_entrega():" in SOURCE
    assert 'campos_manual["fecha_entrega"].insert(0, valor.strftime("%d-%m-%Y"))' in SOURCE
    assert "FactuFacil" not in SOURCE and "FactuFácil" not in SOURCE


def test_el_esquema_no_cambia():
    migrations = sorted(Path("modulos/caja_diaria/infrastructure/migrations").glob("*.sql"))
    assert len(migrations) == 15
    assert migrations[-1].name == "015_admin_counts_notifications.sql"


def test_la_apertura_registra_hora_automatica_y_la_conserva(tmp_path):
    controller = build_cash_day_controller(tmp_path / "cash.sqlite3")
    antes = datetime.now(timezone.utc)
    day = controller.open_or_load_day("14-08-2026", "PC", "100000")
    despues = datetime.now(timezone.utc)

    assert day.opened_at.tzinfo is not None
    assert antes - timedelta(seconds=5) <= day.opened_at <= despues + timedelta(seconds=5)

    recargada = controller.load_day("14-08-2026", "PC")
    assert recargada.opened_at == day.opened_at
    assert recargada.opening_cash == day.opening_cash
    controller.service.repository.close()


def test_consultar_un_dia_sin_caja_no_crea_nada(tmp_path):
    controller = build_cash_day_controller(tmp_path / "cash.sqlite3")
    with pytest.raises(Exception):
        controller.load_day("01-01-2020", "PC")
    with pytest.raises(Exception):
        controller.load_day("01-01-2020", "PC")
    controller.service.repository.close()
