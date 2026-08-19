# -*- coding: utf-8 -*-
"""Laboratorio por defecto de cada cristal. Slice 12.

Un cristal se manda casi siempre al mismo laboratorio. Hasta ahora ese dato no
estaba en ningun lado y la operadora lo escribia de memoria en cada venta; por
eso en las diez lineas que existen conviven 'Optilab', 'optilab', 'SI' y 'asasa'.

Lo que se agrega es una preferencia, y las pruebas que siguen son casi todas
sobre esa palabra: una preferencia se sugiere pero no se impone, se puede
cambiar en la venta, y cambiarla manana no puede tocar lo que ya se mando.
"""

from __future__ import annotations

from datetime import date

import pytest

from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.domain.tracking import Laboratory
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.comercial_controller import (
    ComercialError,
    build_comercial_controller,
)
from modulos.comercial.domain.models import ArticleNature, Destination

ACTOR = "prueba"
OPTILAB, SERVI, CRISTAL = "Laboratorio Optilab", "ServiOptica", "Laboratorio Cristal"


@pytest.fixture()
def ruta(tmp_path):
    destino = tmp_path / "bc_caja.sqlite3"
    SQLiteCashDayRepository(destino).close()  # aplica la cadena 001..028
    return destino


@pytest.fixture()
def ctrl(ruta):
    controlador = build_comercial_controller(ruta)
    yield controlador
    controlador.close()


def _vender(caja, *items, descripcion="Venta mostrador"):
    total = sum(i.subtotal for i in items)
    dia = CashDay(business_date=date(2026, 8, 19), unit="PC", opening_cash=0,
                  opened_by=ACTOR,
                  entries=[CashEntry(description=descripcion, saleswoman="ana",
                                     total=total, cash=total, items=tuple(items))])
    caja.save(dia)
    return caja.get_by_date_and_unit(dia.business_date, "PC")


def _cristal(ctrl, sku, nombre, precio=250000):
    return ctrl.guardar_articulo(
        sku=sku, name=nombre, nature=ArticleNature.TRABAJO_BAJO_PEDIDO,
        actor=ACTOR, sale_price=precio)


# --------------------------------------------------------------------------
# 1-3. Los tres laboratorios, una sola vez cada uno
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", [OPTILAB, SERVI, CRISTAL])
def test_el_laboratorio_se_crea_o_se_reusa_una_sola_vez(ctrl, nombre):
    primero = ctrl.laboratorio_por_nombre(nombre)
    segundo = ctrl.laboratorio_por_nombre(nombre)
    assert primero.id == segundo.id
    assert [l.name for l in ctrl.listar_laboratorios(solo_activos=False)] == [nombre]


@pytest.mark.parametrize("variante", [
    "laboratorio optilab", "LABORATORIO OPTILAB", "  Laboratorio Optilab  "])
def test_no_se_duplica_por_mayusculas_ni_espacios(ctrl, variante):
    original = ctrl.laboratorio_por_nombre(OPTILAB)
    assert ctrl.laboratorio_por_nombre(variante).id == original.id
    assert len(ctrl.listar_laboratorios(solo_activos=False)) == 1


def test_reusa_el_laboratorio_que_ya_existia_del_seguimiento(ctrl, ruta):
    """El catalogo es el de la migracion 003, el del circuito de seguimiento.
    Si Optilab ya estaba cargado con su telefono, no se crea otro."""
    caja = SQLiteCashDayRepository(ruta)
    previo = caja.save_laboratory(Laboratory(name=OPTILAB, phone_line="021-555-000"))
    caja.close()
    encontrado = ctrl.laboratorio_por_nombre(OPTILAB)
    assert encontrado.id == previo.id
    assert encontrado.phone_line == "021-555-000"
    assert len(ctrl.listar_laboratorios(solo_activos=False)) == 1


def test_un_laboratorio_sin_nombre_no_se_crea(ctrl):
    with pytest.raises(ComercialError):
        ctrl.laboratorio_por_nombre("   ")


# --------------------------------------------------------------------------
# 4-5. Cada cristal recibe el suyo, y 2000212 no recibe ninguno
# --------------------------------------------------------------------------


def test_cada_cristal_recibe_el_default_correcto(ctrl):
    optilab = ctrl.laboratorio_por_nombre(OPTILAB)
    servi = ctrl.laboratorio_por_nombre(SERVI)
    cristal_lab = ctrl.laboratorio_por_nombre(CRISTAL)
    esperado = {
        "2000073": optilab, "2000067": optilab, "2000064": optilab,
        "2000075": servi, "2000076": servi, "2000214": servi,
        "2000126": cristal_lab,
    }
    for sku, lab in esperado.items():
        art = _cristal(ctrl, sku, f"Cristal {sku}")
        ctrl.asignar_laboratorio_por_defecto(art.id, lab.id, actor=ACTOR)
    for sku, lab in esperado.items():
        art = ctrl.articulo_por_sku(sku)
        assert ctrl.laboratorio_por_defecto(art.id).name == lab.name, sku


def test_2000212_queda_sin_laboratorio_por_defecto(ctrl):
    """No se le inventa uno. Nulo significa «nadie definio a donde va esto»,
    que es distinto de «no va a ningun lado»."""
    art = _cristal(ctrl, "2000212", "ST Fotocromatico")
    assert art.default_laboratory_id is None
    assert ctrl.laboratorio_por_defecto(art.id) is None


def test_asignar_a_un_laboratorio_que_no_existe_falla(ctrl):
    art = _cristal(ctrl, "2000073", "Multiblue")
    with pytest.raises(ComercialError):
        ctrl.asignar_laboratorio_por_defecto(art.id, "no-existe", actor=ACTOR)
    assert ctrl.obtener_articulo(art.id).default_laboratory_id is None


def test_el_default_se_puede_quitar(ctrl):
    art = _cristal(ctrl, "2000073", "Multiblue")
    lab = ctrl.laboratorio_por_nombre(OPTILAB)
    ctrl.asignar_laboratorio_por_defecto(art.id, lab.id, actor=ACTOR)
    ctrl.asignar_laboratorio_por_defecto(art.id, None, actor=ACTOR)
    assert ctrl.laboratorio_por_defecto(art.id) is None


# --------------------------------------------------------------------------
# 6-9. En la venta
# --------------------------------------------------------------------------


def test_seleccionar_cristal_precarga_el_default(ctrl):
    """Lo que hace la pantalla al elegir el cristal: preguntar por su
    laboratorio. Que el campo se llene solo es toda la mision."""
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    sugerido = ctrl.laboratorio_por_defecto(art.id)
    linea = SaleItem(description="Futurex Protec", lens_price=250000,
                     lens_article_id=art.id, laboratory=sugerido.name)
    assert linea.laboratory == "ServiOptica"


def test_un_cristal_sin_default_no_inventa_laboratorio(ctrl):
    art = _cristal(ctrl, "2000212", "ST Fotocromatico")
    sugerido = ctrl.laboratorio_por_defecto(art.id)
    assert sugerido is None
    linea = SaleItem(description="ST Fotocromatico", lens_price=250000,
                     lens_article_id=art.id,
                     laboratory=sugerido.name if sugerido else "")
    assert linea.laboratory == ""


def test_la_operadora_puede_cambiar_el_laboratorio_en_la_venta(ctrl, ruta):
    """El default es una sugerencia. Esta vez el trabajo va a otro lado y eso
    es lo que tiene que quedar guardado."""
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)

    caja = SQLiteCashDayRepository(ruta)
    try:
        caja.bind_register_to_branch("PC", "ASUNCION", assigned_by=ACTOR)
        guardado = _vender(caja, SaleItem(
            description="Futurex Protec", lens_price=250000,
            lens_article_id=art.id, laboratory=OPTILAB))
        linea = guardado.entries[0].items[0]
        assert linea.laboratory == OPTILAB, "no quedo el laboratorio que se eligio"
        assert linea.lens_article_id == art.id
        assert ctrl.laboratorio_por_defecto(art.id).name == SERVI, "cambio el default"
    finally:
        caja.close()


def test_la_venta_historica_conserva_su_laboratorio_aunque_cambie_el_default(ctrl, ruta):
    """La prueba que justifica todo el diseño. Si el default viviera en la
    linea, cambiar de laboratorio reescribiria agosto."""
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    optilab = ctrl.laboratorio_por_nombre(OPTILAB)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)

    caja = SQLiteCashDayRepository(ruta)
    try:
        caja.bind_register_to_branch("PC", "ASUNCION", assigned_by=ACTOR)
        _vender(caja, SaleItem(description="Futurex Protec", lens_price=250000,
                               lens_article_id=art.id, laboratory=SERVI),
                descripcion="Venta de agosto")

        # La Optica cambia de laboratorio para ese cristal.
        ctrl.asignar_laboratorio_por_defecto(art.id, optilab.id, actor=ACTOR)

        recargada = caja.get_by_date_and_unit(date(2026, 8, 19), "PC")
        assert recargada.entries[0].items[0].laboratory == SERVI,             "cambiar la preferencia reescribio una venta de agosto"
        assert ctrl.laboratorio_por_defecto(art.id).name == OPTILAB
    finally:
        caja.close()


# --------------------------------------------------------------------------
# 10-12. Lo que no tiene que pasar
# --------------------------------------------------------------------------


def test_ningun_cristal_genera_stock(ctrl):
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    assert art.tracks_stock is False
    for destino in Destination:
        assert ctrl.ledger.stock(art.id, destino) == 0
    assert ctrl.ledger.stock_por_destino(art.id) == {}


def test_ningun_laboratorio_se_convierte_en_marca(ctrl):
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    assert [m.name for m in ctrl.listar_marcas(solo_activas=False)] == []
    assert ctrl.obtener_articulo(art.id).brand_id is None


def test_asignar_el_default_no_pisa_ningun_otro_campo(ctrl):
    """Se apoya en la modificacion parcial de V1-014: cambiar la preferencia no
    puede volver a borrar la categoria."""
    categoria = ctrl.crear_categoria("Cristales", actor=ACTOR)
    marca = ctrl.crear_marca("Essilor", actor=ACTOR)
    art = ctrl.guardar_articulo(
        sku="2000075", name="Futurex Protec",
        nature=ArticleNature.TRABAJO_BAJO_PEDIDO, actor=ACTOR,
        category_id=categoria.id, brand_id=marca.id, sale_price=250000,
        notes="origen: P2 - Inventario.xlsx#120")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    quedo = ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    assert quedo.category_id == categoria.id
    assert quedo.brand_id == marca.id
    assert quedo.sale_price == 250000
    assert quedo.notes == "origen: P2 - Inventario.xlsx#120"
    assert quedo.nature is ArticleNature.TRABAJO_BAJO_PEDIDO


def test_asignar_dos_veces_lo_mismo_no_cambia_nada(ctrl):
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    primero = ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    segundo = ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    assert primero.default_laboratory_id == segundo.default_laboratory_id
    assert len(ctrl.listar_laboratorios(solo_activos=False)) == 1


def test_el_default_queda_auditado(ctrl):
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor="rodrigo")
    assert [c.accion for c in ctrl.historial_de_articulo(art.id)][-1] == "EDITA_ARTICULO"


def test_desactivar_un_cristal_conserva_su_laboratorio(ctrl):
    """La baja logica pasa por la modificacion parcial: no puede perder la
    preferencia, porque el articulo puede volver."""
    art = _cristal(ctrl, "2000075", "Futurex Protec")
    servi = ctrl.laboratorio_por_nombre(SERVI)
    ctrl.asignar_laboratorio_por_defecto(art.id, servi.id, actor=ACTOR)
    dado_de_baja = ctrl.desactivar_articulo(art.id, actor=ACTOR, motivo="discontinuado")
    assert dado_de_baja.default_laboratory_id == servi.id
