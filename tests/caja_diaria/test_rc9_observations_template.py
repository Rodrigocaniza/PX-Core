from pathlib import Path

import CajaDiaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import SaleItem

EXPECTED = """Nombre:
Armazón:
Cristal:
OD:
OI:
ADD:
Altura:
DI:
N.º FACTURA:
RAZÓN SOCIAL:
RUC:"""
SOURCE = Path("CajaDiaria.py").read_text(encoding="utf-8")


def sale_values(observations):
    return {
        "fecha": "14-08-2026", "unidad": "PC", "caja_inicial": "0",
        "descripcion": "Pagador distinto", "cliente_documento": "800000-1",
        "vendedora": "Ana", "total": "100000", "efectivo": "100000",
        "tarjeta_cheque": "0", "transferencia": "0", "monto_convenio": "0",
        "notas": observations,
        "items": (SaleItem(description="Cristal", item_type="Recetado", lens_price=100000),),
    }


def test_template_is_exact_editable_text_and_neutral_only_when_untouched():
    assert CajaDiaria.PLANTILLA_RECETA_OBSERVACIONES == EXPECTED
    assert CajaDiaria.observaciones_son_plantilla_neutra(EXPECTED)
    assert not CajaDiaria.observaciones_son_plantilla_neutra(EXPECTED.replace("Nombre:", "Nombre: María"))
    assert not CajaDiaria.observaciones_son_plantilla_neutra("")
    assert 'placeholder_text=PLANTILLA_RECETA_OBSERVACIONES' not in SOURCE


def test_recipe_round_trip_preserves_unicode_lines_and_does_not_copy_payer(tmp_path):
    recipe = EXPECTED.replace("Nombre:", "Nombre: María José").replace(
        "Armazón:", "Armazón: metálico"
    ).replace("Cristal:", "Cristal: orgánico").replace("OD:", "OD: +1,25").replace(
        "N.º FACTURA:", "N.º FACTURA: 001-001-42"
    ).replace("RAZÓN SOCIAL:", "RAZÓN SOCIAL: Óptica Ñandutí")
    controller = build_cash_day_controller(tmp_path / "rc9.sqlite3")
    controller.open_or_load_day("14-08-2026", "PC", "0")
    _, saved = controller.add_manual_entry(sale_values(recipe))
    reopened = controller.load_day("14-08-2026", "PC").entries[0]
    assert reopened.observations == recipe
    assert "Pagador distinto" not in reopened.observations
    assert "800000-1" not in reopened.observations
    assert reopened.source_reference == recipe
    revisions = controller.service.repository.list_entry_revisions(saved.id)
    assert revisions[0]["snapshot"]["observations"] == recipe
    controller.service.repository.close()


def test_historical_empty_observations_remain_empty_until_explicit_save(tmp_path):
    controller = build_cash_day_controller(tmp_path / "history.sqlite3")
    controller.open_or_load_day("14-08-2026", "PC", "0")
    _, saved = controller.add_manual_entry(sale_values(""))
    before = controller.load_day("14-08-2026", "PC").entries[0]
    assert before.observations == ""
    assert len(controller.service.repository.list_entry_revisions(saved.id)) == 1
    assert '"notas": entry.observations,' in SOURCE
    assert 'entry.observations or entry.source_reference' not in SOURCE[SOURCE.index('def cargar_para_editar'):]
    controller.service.repository.close()


def test_new_sale_clear_save_and_edit_contract_use_template_without_duplication():
    assert 'campos_manual["notas"].insert("1.0", PLANTILLA_RECETA_OBSERVACIONES)' in SOURCE
    assert 'campos_manual[clave].insert("1.0", PLANTILLA_RECETA_OBSERVACIONES)' in SOURCE
    assert 'or (clave == "notas" and observaciones_son_plantilla_neutra(valor))' in SOURCE
    assert 'limpiar_operacion(confirmar=False)' in SOURCE
    assert 'campo.insert("1.0", "" if valor is None else str(valor))' in SOURCE
    assert 'PLANTILLA_RECETA_OBSERVACIONES + entry.observations' not in SOURCE