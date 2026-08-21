# -*- coding: utf-8 -*-
"""Limpieza de marcas que en realidad son laboratorios. Slice 15.

La columna «Marca» de las planillas de la Óptica trae el laboratorio cuando el
artículo es un cristal, y así entró al catálogo. La migración 028 le dio al
laboratorio su propio campo, y recién entonces esa marca se pudo sacar sin
perder el dato.

Lo que se fija acá son dos cosas distintas. Una es la clasificación: qué caso se
limpia solo, cuál toma la marca de la fuente corregida y cuál espera a una
persona. La otra es que limpiar la marca no arrastre nada más — el laboratorio
por defecto, la naturaleza, el precio, las notas, el stock, la línea de venta que
ya se hizo. Esa segunda parte existe por el daño de V1-010, donde tocar cuatro
campos borró dos que nadie nombró.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.comercial_controller import build_comercial_controller
from modulos.comercial.domain.models import (
    ArticleNature,
    Destination,
    StockMovement,
    StockMovementKind,
)

RAIZ = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "limpieza_marcas_laboratorio_optica",
    RAIZ / "tools" / "limpieza_marcas_laboratorio_optica.py")
herramienta = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = herramienta
_spec.loader.exec_module(herramienta)

ACTOR = "prueba"
PUPPILENT = "Óptica Puppilent`s"


@pytest.fixture()
def base(tmp_path):
    destino = tmp_path / "bc_caja.sqlite3"
    SQLiteCashDayRepository(destino).close()
    return destino


@pytest.fixture()
def ctrl(base):
    controlador = build_comercial_controller(base)
    yield controlador
    controlador.close()


@pytest.fixture()
def optica(ctrl):
    """Una copia chica de la Óptica: los casos que importan, con todo puesto.

    No es producción y no pretende serlo. Es la forma del problema —un cristal
    con el laboratorio en la marca y el laboratorio también en su campo, una
    compostura con la misma marca, un armazón que no encaja en ninguna regla y
    un artículo con marca legítima— para poder probar la herramienta sin la base
    de la Óptica delante.
    """
    cristales = ctrl.crear_categoria("Cristales", actor=ACTOR)
    compostura = ctrl.crear_categoria("Compostura", actor=ACTOR)
    armazones = ctrl.crear_categoria("Armazones", actor=ACTOR)
    optilab_marca = ctrl.crear_marca("Laboratorio Optilab", actor=ACTOR)
    servi_marca = ctrl.crear_marca("Laboratorio Servi Optical", actor=ACTOR)
    ctrl.crear_marca(PUPPILENT, actor=ACTOR)
    ctrl.crear_marca("Optica San Cayetano", actor=ACTOR)
    optilab = ctrl.laboratorio_por_nombre("Laboratorio Optilab")
    ctrl.laboratorio_por_nombre("ServiOptica")
    ctrl.laboratorio_por_nombre("Laboratorio Cristal")

    hechos = {}
    hechos["2000060"] = ctrl.guardar_articulo(
        sku="2000060", name="Organico UVX", nature=ArticleNature.TRABAJO_BAJO_PEDIDO,
        actor=ACTOR, category_id=cristales.id, brand_id=optilab_marca.id,
        default_laboratory_id=optilab.id, sale_price=180000, unit="PAR",
        location="Mostrador", min_stock=0, barcode="2000060",
        notes="origen: PILAR=P2 - Inventario.xlsx#845@2026-08-10")
    hechos["2000075"] = ctrl.guardar_articulo(
        sku="2000075", name="Futurex Protec", nature=ArticleNature.TRABAJO_BAJO_PEDIDO,
        actor=ACTOR, category_id=cristales.id, brand_id=servi_marca.id,
        sale_price=250000, notes="origen: PILAR=P2 - Inventario.xlsx#861@2026-08-10")
    hechos["2000070"] = ctrl.guardar_articulo(
        sku="2000070", name="Hilo", nature=ArticleNature.SERVICIO_NO_STOCKEABLE,
        actor=ACTOR, category_id=compostura.id, brand_id=optilab_marca.id,
        sale_price=15000, notes="naturaleza por decisión humana")
    hechos["2000212"] = ctrl.guardar_articulo(
        sku="2000212", name="ST Fotocromatico", nature=ArticleNature.PRODUCTO_STOCKEABLE,
        actor=ACTOR, category_id=armazones.id, brand_id=optilab_marca.id,
        sale_price=90000, notes="sin laboratorio por defecto, a propósito")
    hechos["2000056"] = ctrl.guardar_articulo(
        sku="2000056", name="Par de patillas", nature=ArticleNature.SERVICIO_NO_STOCKEABLE,
        actor=ACTOR, category_id=compostura.id,
        brand_id=ctrl.crear_marca("Optica San Cayetano", actor=ACTOR).id)
    return hechos


def plan_por_sku(base, corregidas=None):
    plan, catalogo = herramienta.construir_plan(base, corregidas)
    return {p["sku"]: p for p in plan}, catalogo


def correr(base, *, confirmar=False, corregidas=None):
    argv = ["prog", "--base", str(base)]
    if confirmar:
        argv.append("--confirmar")
    herramienta.lineas.clear()
    herramienta.fallas.clear()
    viejo = sys.argv
    sys.argv = argv
    try:
        return herramienta.main()
    finally:
        sys.argv = viejo


# --------------------------------------------------------------------------
# Clasificación
# --------------------------------------------------------------------------

def test_un_cristal_con_el_laboratorio_en_la_marca_se_limpia(base, optica):
    plan, _ = plan_por_sku(base)
    caso = plan["2000060"]
    assert caso["clase"] == herramienta.CONFIRMADO
    assert caso["marca_propuesta"] is None
    assert caso["cambia"] is True


def test_las_dos_grafias_de_laboratorio_cuentan(base, optica):
    """«Laboratorio Servi Optical» no coincide con ningún laboratorio del
    catálogo —el catálogo dice «ServiOptica»— y aun así nombra uno. Que se
    limpie no sale de un parecido: sale de la lista autorizada."""
    plan, _ = plan_por_sku(base)
    assert plan["2000075"]["clase"] == herramienta.CONFIRMADO


def test_una_marca_que_no_es_laboratorio_no_entra_en_el_plan(base, optica):
    """«Optica San Cayetano» se parece a un laboratorio lo suficiente como para
    que una heurística amplia se la lleve puesta. No entra."""
    plan, _ = plan_por_sku(base)
    assert "2000056" not in plan


def test_la_compostura_toma_la_marca_de_la_fuente_corregida(base, optica):
    plan, _ = plan_por_sku(base)
    caso = plan["2000070"]
    assert caso["clase"] == herramienta.FUENTE_REAL
    assert caso["marca_propuesta"] == PUPPILENT
    assert caso["marca_destino_id"] is not None, "la marca ya existe, no se crea"


def test_el_armazon_queda_ambiguo_y_no_se_toca(base, optica):
    plan, _ = plan_por_sku(base)
    caso = plan["2000212"]
    assert caso["clase"] == herramienta.AMBIGUO
    assert caso["cambia"] is False


def test_la_fuente_corregida_manda_sobre_la_regla_de_cristales(base, optica):
    """Si el archivo del 19/08 está a mano y le da una marca real a un cristal,
    esa marca gana: la regla de limpiar a NULL era para cuando no hay ninguna."""
    plan, _ = plan_por_sku(base, {"2000060": "Optica San Cayetano"})
    caso = plan["2000060"]
    assert caso["clase"] == herramienta.FUENTE_REAL
    assert caso["marca_propuesta"] == "Optica San Cayetano"


def test_una_fuente_corregida_que_repite_el_laboratorio_no_es_marca_real(base, optica):
    plan, _ = plan_por_sku(base, {"2000060": "Laboratorio Optilab"})
    assert plan["2000060"]["clase"] == herramienta.CONFIRMADO
    assert plan["2000060"]["marca_propuesta"] is None


def test_una_marca_laboratorio_nueva_se_denuncia_pero_no_se_limpia(base, optica, ctrl):
    """Si mañana aparece «Laboratorio Cristal» como marca, la herramienta lo dice
    y no lo toca. Ampliar el alcance es una decisión, no un efecto."""
    marca = ctrl.crear_marca("Laboratorio Cristal", actor=ACTOR)
    cristales = ctrl.listar_categorias()[0]
    ctrl.guardar_articulo(sku="2000999", name="Cristal nuevo",
                          nature=ArticleNature.TRABAJO_BAJO_PEDIDO, actor=ACTOR,
                          category_id=cristales.id, brand_id=marca.id)
    plan, catalogo = plan_por_sku(base)
    assert "2000999" not in plan
    assert "Laboratorio Cristal" in herramienta.marcas_sospechosas_no_listadas(catalogo)


# --------------------------------------------------------------------------
# Que limpiar la marca no arrastre nada más
# --------------------------------------------------------------------------

def _fila(base, sku):
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        return dict(c.execute("SELECT * FROM articles WHERE sku=?", (sku,)).fetchone())
    finally:
        c.close()


def test_cambiar_la_marca_no_borra_ningun_otro_campo(base, optica):
    antes = _fila(base, "2000060")
    assert correr(base, confirmar=True) == 0
    despues = _fila(base, "2000060")
    cambiados = {k for k in antes
                 if k not in ("updated_at",) and antes[k] != despues[k]}
    assert cambiados == {"brand_id"}, cambiados
    assert despues["brand_id"] is None


def test_el_laboratorio_por_defecto_sobrevive_a_la_limpieza(base, optica):
    antes = _fila(base, "2000060")["default_laboratory_id"]
    assert antes is not None
    correr(base, confirmar=True)
    assert _fila(base, "2000060")["default_laboratory_id"] == antes


def test_la_naturaleza_del_cristal_sigue_siendo_trabajo_bajo_pedido(base, optica):
    correr(base, confirmar=True)
    assert _fila(base, "2000060")["nature"] == "TRABAJO_BAJO_PEDIDO"


def test_la_compostura_sigue_siendo_servicio_despues_de_recuperar_su_marca(base, optica):
    correr(base, confirmar=True)
    fila = _fila(base, "2000070")
    assert fila["nature"] == "SERVICIO_NO_STOCKEABLE"
    assert fila["brand_id"] is not None, "recuperó una marca real, no quedó en blanco"


def test_no_se_crea_ninguna_marca_nueva(base, optica):
    contar = lambda: sqlite3.connect(str(base)).execute(  # noqa: E731
        "SELECT COUNT(*) FROM brands").fetchone()[0]
    antes = contar()
    correr(base, confirmar=True)
    assert contar() == antes


def test_el_stock_y_los_movimientos_no_se_mueven(base, optica, ctrl):
    armazon = optica["2000212"]
    ctrl.ledger.registrar(StockMovement(
        article_id=armazon.id, destination=Destination.ASUNCION,
        kind=StockMovementKind.INGRESO_COMPRA, quantity=5, actor=ACTOR,
        idempotency_key=f"alta:{armazon.id}"))
    antes = herramienta.radiografia(base)
    correr(base, confirmar=True)
    despues = herramienta.radiografia(base)
    for clave in ("movimientos", "asuncion", "pilar", "entradas", "suma_caja",
                  "sale_items", "articulos", "activos", "con_default"):
        assert antes[clave] == despues[clave], clave


def test_la_categoria_no_se_pierde(base, optica):
    """El daño de V1-010 exactamente: tocar un campo y perder la categoría."""
    antes = _fila(base, "2000070")["category_id"]
    correr(base, confirmar=True)
    assert _fila(base, "2000070")["category_id"] == antes


def test_las_notas_el_precio_y_la_unidad_siguen_ahi(base, optica):
    antes = _fila(base, "2000060")
    correr(base, confirmar=True)
    despues = _fila(base, "2000060")
    for campo in ("notes", "sale_price", "unit", "location", "min_stock", "barcode",
                  "supplier_id", "name", "sku", "active"):
        assert antes[campo] == despues[campo], campo


# --------------------------------------------------------------------------
# Dry-run, idempotencia, bitácora
# --------------------------------------------------------------------------

def test_sin_confirmar_no_escribe_nada(base, optica):
    antes = _fila(base, "2000060")
    assert correr(base) == 0
    assert _fila(base, "2000060") == antes


def test_una_segunda_corrida_no_cambia_nada(base, optica):
    correr(base, confirmar=True)
    primera = _fila(base, "2000060")
    assert correr(base, confirmar=True) == 0
    assert _fila(base, "2000060") == primera


def test_despues_de_limpiar_solo_queda_el_ambiguo(base, optica):
    correr(base, confirmar=True)
    plan, _ = plan_por_sku(base)
    assert [p["sku"] for p in plan.values()] == ["2000212"]
    assert plan["2000212"]["clase"] == herramienta.AMBIGUO


def test_queda_asentado_quien_cambio_que(base, optica):
    correr(base, confirmar=True)
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        filas = c.execute(
            "SELECT COUNT(*) FROM admin_audit_log WHERE action=?",
            (herramienta.ACCION,)).fetchone()[0]
    finally:
        c.close()
    assert filas == 3, "los dos cristales y la compostura"


def test_una_venta_de_agosto_no_se_reescribe_al_limpiar_la_marca(base, optica):
    """El invariante que más importa. `2000075` es uno de los que se limpian, y
    tiene una venta con el laboratorio que realmente hizo ese trabajo escrito en
    la línea. Vaciar la marca del artículo no puede tocar esa línea: el default
    es una preferencia de hoy y la línea es un hecho de agosto."""
    caja = SQLiteCashDayRepository(base)
    try:
        caja.bind_register_to_branch("PC", "ASUNCION", assigned_by=ACTOR)
        item = SaleItem(description="Futurex Protec", lens_price=250000,
                        lens_article_id=optica["2000075"].id, laboratory="ServiOptica")
        caja.save(CashDay(business_date=date(2026, 8, 19), unit="PC", opening_cash=0,
                          opened_by=ACTOR,
                          entries=[CashEntry(description="Venta de agosto",
                                             saleswoman="ana", total=250000,
                                             cash=250000, items=(item,))]))
    finally:
        caja.close()

    correr(base, confirmar=True)

    caja = SQLiteCashDayRepository(base)
    try:
        recargada = caja.get_by_date_and_unit(date(2026, 8, 19), "PC")
    finally:
        caja.close()
    linea = recargada.entries[0].items[0]
    assert linea.laboratory == "ServiOptica", "limpiar la marca reescribió una venta"
    assert linea.lens_article_id == optica["2000075"].id
    assert recargada.entries[0].total == 250000
    assert _fila(base, "2000075")["brand_id"] is None


# --------------------------------------------------------------------------
# El caso ambiguo, aislado
# --------------------------------------------------------------------------

def test_una_celda_vacia_en_la_fuente_no_limpia_un_armazon(base, optica):
    """Una celda «Marca» en blanco dice «no sé», no «no tiene marca». Para un
    cristal confirma lo que ya sabíamos; para `2000212`, que es un armazón y
    podría tener un fabricante real, no alcanza. Se queda como está."""
    plan, _ = plan_por_sku(base, {"2000212": "", "2000060": ""})
    assert plan["2000212"]["clase"] == herramienta.AMBIGUO
    assert plan["2000212"]["cambia"] is False
    assert plan["2000060"]["clase"] == herramienta.CONFIRMADO


def test_la_fuente_corregida_puede_cerrar_el_caso_del_armazon(base, optica):
    """Si la planilla del 19/08 le da al mismo código una marca real, el gate se
    cierra solo: no hace falta que nadie decida nada."""
    plan, _ = plan_por_sku(base, {"2000212": "Optica San Cayetano"})
    caso = plan["2000212"]
    assert caso["clase"] == herramienta.FUENTE_REAL
    assert caso["marca_propuesta"] == "Optica San Cayetano"


def test_el_ambiguo_no_frena_a_los_demas(base, optica):
    """`2000212` queda sin resolver y los otros se aplican igual. Un caso que
    espera una decisión no es un motivo para no hacer el resto."""
    antes = _fila(base, "2000212")
    assert correr(base, confirmar=True) == 0
    assert _fila(base, "2000212") == antes, "se tocó el que había que dejar quieto"
    assert _fila(base, "2000060")["brand_id"] is None
    assert _fila(base, "2000070")["brand_id"] is not None
