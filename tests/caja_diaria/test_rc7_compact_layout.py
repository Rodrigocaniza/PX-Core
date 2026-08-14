from pathlib import Path
import CajaDiaria

SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def test_rc7_detail_restores_rc5_height_and_six_rows():
    assert len(CajaDiaria.PRODUCTO_TRABAJO) == 6
    assert 'form_preferido, form_minimo = 212, 172' in SOURCE
    assert '"armazon": (4, 0), "cristal": (4, 3), "receta_dr": (5, 0)' in SOURCE
    assert 'row=4, column=columna' in SOURCE
    assert 'width=42' in SOURCE
    assert '"P. Armazón / Desc. %"' in SOURCE
    assert '"P. Cristal / Desc. %"' in SOURCE


def test_rc7_add_and_no_cost_share_one_row():
    assert 'row=7, column=0, columnspan=2' in SOURCE
    assert 'row=7, column=2, columnspan=4' in SOURCE


def test_rc7_uses_three_independent_containers():
    assert 'lista_productos = ctk.CTkFrame(tab_manual' in SOURCE
    assert 'panel_total_draft = ctk.CTkFrame(\n        tab_manual' in SOURCE
    assert 'zona_secundaria = ctk.CTkFrame(tab_manual' in SOURCE
    assert 'lista_productos.configure(width=ancho_izquierdo_actual, height=draft_actual)' in SOURCE
    assert 'panel_total_draft.configure(width=ancho_derecho_actual, height=draft_actual + alto_sec + sep)' in SOURCE
    assert 'zona_secundaria.configure(width=ancho_izquierdo_actual, height=alto_sec)' in SOURCE


def test_rc7_preserves_outflow_clear_filters_and_five_rows():
    for marker in ('text="Guardar salida"', 'text="Limpiar todo"',
                   '"Todos", "Ventas", "Salidas", "Pendientes"',
                   'filas_minimas = 5', 'TAMANO_LOTE_GRILLA = 250'):
        assert marker in SOURCE
    assert 'limpiar_operacion(confirmar=False)' in SOURCE
