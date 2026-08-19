"""Delivery / Envío como servicio. Slice 11.

Pruebas dirigidas escritas antes de tocar nada.

Un envío no es una cosa: no hay envíos en el depósito, no se agotan, y cobrar uno
no deja un hueco en ningún estante. Lo único que tiene de particular es que cuesta
distinto cada vez —según a dónde va, o según qué se acordó con el cliente—, así
que el precio pertenece a la venta y no al catálogo.

Las dos mitades de eso ya existían en el sistema: la naturaleza decide si algo
mueve stock, y el precio vive en la línea. Lo que se verifica acá es que las dos
se comporten juntas como corresponde, y que el concepto no se duplique.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.comercial_controller import build_comercial_controller
from modulos.comercial.application.stock_ledger import StockLedgerService
from modulos.comercial.application.ventas import VentasLedgerIntegrator
from modulos.comercial.domain.models import (
    Article,
    ArticleNature,
    Destination,
    StockMovement,
    StockMovementKind,
)
from modulos.comercial.infrastructure.sqlite_catalog_repository import (
    SQLiteCatalogRepository,
)
from modulos.comercial.infrastructure.sqlite_stock_ledger import (
    SQLiteStockLedgerRepository,
)

SKU_DELIVERY = "SERV-DELIVERY"
PRECIO_SUGERIDO = 20000


# --------------------------------------------------------------------------
# Montaje
# --------------------------------------------------------------------------


@pytest.fixture()
def ruta(tmp_path):
    return tmp_path / "bc_caja.sqlite3"


@pytest.fixture()
def catalogo(ruta):
    SQLiteCashDayRepository(ruta).close()  # aplica la cadena 001..027
    repo = SQLiteCatalogRepository(ruta)
    yield repo
    repo.close()


@pytest.fixture()
def ledger_repo(ruta, catalogo):
    repo = SQLiteStockLedgerRepository(ruta)
    yield repo
    repo.close()


@pytest.fixture()
def ledger(ledger_repo, catalogo):
    return StockLedgerService(ledger_repo, catalogo)


@pytest.fixture()
def integrador(catalogo, ledger_repo):
    return VentasLedgerIntegrator(catalogo, ledger_repo)


@pytest.fixture()
def caja(ruta, integrador):
    repo = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    repo.bind_register_to_branch("PC", "ASUNCION", assigned_by="prueba")
    yield repo
    repo.close()


@pytest.fixture()
def delivery(catalogo):
    """El concepto tal como lo va a dar de alta la misión."""
    return catalogo.save_article(Article(
        sku=SKU_DELIVERY, name="Delivery / Envío",
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE, sale_price=PRECIO_SUGERIDO))


@pytest.fixture()
def armazon(catalogo):
    return catalogo.save_article(Article(
        sku="ARM-001", name="Armazón metal", nature=ArticleNature.PRODUCTO_STOCKEABLE))


@pytest.fixture()
def cristal(catalogo):
    return catalogo.save_article(Article(
        sku="CRIS-ORG", name="Cristal orgánico recetado",
        nature=ArticleNature.TRABAJO_BAJO_PEDIDO))


def _dar_stock(ledger, articulo, cantidad, destino=Destination.ASUNCION):
    ledger.registrar(StockMovement(
        article_id=articulo.id, destination=destino,
        kind=StockMovementKind.INGRESO_COMPRA, quantity=cantidad, actor="rodrigo",
        idempotency_key=f"alta:{articulo.id}:{destino.value}"))


def _linea_delivery(delivery, precio=PRECIO_SUGERIDO):
    return SaleItem(description="Delivery / Envío", item_type="DELIVERY",
                    code=SKU_DELIVERY, frame_price=precio, article_id=delivery.id)


def _vender(caja, *items, descripcion="Venta mostrador"):
    total = sum(i.subtotal for i in items)
    dia = CashDay(business_date=date(2026, 8, 19), unit="PC", opening_cash=0,
                  opened_by="rodrigo",
                  entries=[CashEntry(description=descripcion, saleswoman="ana",
                                     total=total, cash=total, items=tuple(items))])
    caja.save(dia)
    return caja.get_by_date_and_unit(dia.business_date, "PC")


def _conexion(ruta):
    conexion = sqlite3.connect(str(ruta))
    conexion.row_factory = sqlite3.Row
    return conexion


# --------------------------------------------------------------------------
# El precio es de la venta, no del catálogo
# --------------------------------------------------------------------------


def test_delivery_a_veinte_mil(caja, delivery):
    """El valor sugerido, que es el caso normal."""
    dia = _vender(caja, _linea_delivery(delivery))
    assert dia.entries[0].total == 20000


def test_delivery_cambiado_a_quince_mil(caja, delivery):
    """Más cerca, más barato. El catálogo sugiere; la venta decide."""
    dia = _vender(caja, _linea_delivery(delivery, 15000))
    assert dia.entries[0].total == 15000


def test_delivery_cambiado_a_veinticinco_mil(caja, delivery):
    dia = _vender(caja, _linea_delivery(delivery, 25000))
    assert dia.entries[0].total == 25000


def test_el_precio_sugerido_del_catalogo_no_cambia_lo_ya_cobrado(caja, catalogo, delivery, ruta):
    """Subir la tarifa mañana no reescribe lo que se cobró ayer."""
    _vender(caja, _linea_delivery(delivery, 15000))
    catalogo.save_article(Article(
        sku=SKU_DELIVERY, name="Delivery / Envío",
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE, sale_price=30000, id=delivery.id))

    with _conexion(ruta) as conexion:
        cobrado = conexion.execute(
            "SELECT frame_price FROM sale_items WHERE article_id = ?",
            (delivery.id,)).fetchone()["frame_price"]
        sugerido = conexion.execute(
            "SELECT sale_price FROM articles WHERE id = ?", (delivery.id,)).fetchone()["sale_price"]
    assert cobrado == 15000
    assert sugerido == 30000


# --------------------------------------------------------------------------
# No toca el inventario
# --------------------------------------------------------------------------


def test_delivery_no_genera_movimiento_de_stock(caja, ruta, delivery):
    _vender(caja, _linea_delivery(delivery))

    with _conexion(ruta) as conexion:
        movimientos = conexion.execute(
            "SELECT COUNT(*) c FROM stock_movements WHERE article_id = ?",
            (delivery.id,)).fetchone()["c"]
    assert movimientos == 0


def test_delivery_no_aparece_en_stock_actual(caja, ruta, delivery):
    """No es que tenga cero: es que no tiene fila. Un envío no se cuenta."""
    _vender(caja, _linea_delivery(delivery))

    with _conexion(ruta) as conexion:
        filas = conexion.execute(
            "SELECT COUNT(*) c FROM stock_actual WHERE article_id = ?",
            (delivery.id,)).fetchone()["c"]
    assert filas == 0


def test_delivery_no_altera_el_stock_de_los_demas(caja, ledger, armazon, delivery):
    _dar_stock(ledger, armazon, 5)

    _vender(caja, SaleItem(description="Armazón", frame_price=280000, article_id=armazon.id),
            _linea_delivery(delivery))

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4  # sólo el armazón


def test_vender_solo_delivery_no_mueve_nada(caja, ruta, delivery):
    """Un envío suelto es una operación válida y no deja rastro en el depósito."""
    dia = _vender(caja, _linea_delivery(delivery), descripcion="Solo envío")

    assert dia.entries[0].total == 20000
    with _conexion(ruta) as conexion:
        assert conexion.execute("SELECT COUNT(*) c FROM stock_movements").fetchone()["c"] == 0


# --------------------------------------------------------------------------
# Convive con lo demás
# --------------------------------------------------------------------------


def test_producto_mas_delivery(caja, ledger, armazon, delivery):
    _dar_stock(ledger, armazon, 5)

    dia = _vender(caja, SaleItem(description="Armazón", frame_price=280000,
                                 article_id=armazon.id),
                  _linea_delivery(delivery))

    assert dia.entries[0].total == 300000
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


def test_cristal_mas_delivery(caja, ruta, cristal, delivery):
    """El cristal es trabajo bajo pedido: tampoco mueve stock, y el envío menos."""
    dia = _vender(caja, SaleItem(description="Cristal recetado", lens_price=250000,
                                 lens_article_id=cristal.id),
                  _linea_delivery(delivery, 25000))

    assert dia.entries[0].total == 275000
    with _conexion(ruta) as conexion:
        assert conexion.execute("SELECT COUNT(*) c FROM stock_movements").fetchone()["c"] == 0


def test_servicio_mas_delivery(caja, catalogo, delivery):
    compostura = catalogo.save_article(Article(
        sku="SERV-COMP", name="Compostura simple",
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE, sale_price=30000))

    dia = _vender(caja, SaleItem(description="Compostura", frame_price=30000,
                                 article_id=compostura.id),
                  _linea_delivery(delivery))

    assert dia.entries[0].total == 50000


# --------------------------------------------------------------------------
# Anular no devuelve envíos
# --------------------------------------------------------------------------


def test_anular_una_venta_con_delivery_no_compensa_inventario(caja, ruta, ledger,
                                                              armazon, delivery):
    """Se devuelve el armazón, que salió. El envío no salió de ningún lado."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, SaleItem(description="Armazón", frame_price=280000,
                                 article_id=armazon.id),
                  _linea_delivery(delivery))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4

    dia.void_entry(dia.entries[0].id, "Cargada por error")
    caja.save(dia, audit_reason="Cargada por error", edited_by="rodrigo")

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    with _conexion(ruta) as conexion:
        assert conexion.execute(
            "SELECT COUNT(*) c FROM stock_movements WHERE article_id = ?",
            (delivery.id,)).fetchone()["c"] == 0


def test_anular_una_venta_de_solo_delivery_no_rompe(caja, ruta, delivery):
    """Una venta sin una sola unidad se anula igual, y sigue registrada."""
    dia = _vender(caja, _linea_delivery(delivery), descripcion="Solo envío")
    entry_id = dia.entries[0].id

    dia.void_entry(entry_id, "Cargada por error")
    caja.save(dia, audit_reason="Cargada por error", edited_by="rodrigo")

    recargado = caja.get_by_date_and_unit(date(2026, 8, 19), "PC")
    assert any(e.id == entry_id for e in recargado.entries)
    with _conexion(ruta) as conexion:
        assert conexion.execute("SELECT COUNT(*) c FROM stock_movements").fetchone()["c"] == 0


# --------------------------------------------------------------------------
# El concepto, en el catálogo
# --------------------------------------------------------------------------


def test_delivery_es_servicio_y_no_lleva_stock(delivery):
    assert delivery.nature is ArticleNature.SERVICIO_NO_STOCKEABLE
    assert delivery.tracks_stock is False


def test_delivery_nace_sin_una_sola_unidad(ledger, delivery):
    """Dar de alta el concepto no inventa inventario."""
    assert ledger.stock_por_destino(delivery.id) == {}


def test_delivery_se_puede_elegir_en_la_linea_de_venta(ruta, catalogo, delivery):
    controlador = build_comercial_controller(ruta)
    try:
        opciones = {o.sku: o for o in controlador.buscar_para_venta("Delivery", unidad="PC")}
    finally:
        controlador.close()

    assert SKU_DELIVERY in opciones
    assert opciones[SKU_DELIVERY].sale_price == PRECIO_SUGERIDO


def test_el_concepto_no_se_duplica(ruta, catalogo, delivery):
    """Volver a darlo de alta con el mismo SKU actualiza, no crea otro."""
    catalogo.save_article(Article(
        sku=SKU_DELIVERY, name="Delivery / Envío",
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE, sale_price=PRECIO_SUGERIDO,
        id=delivery.id))

    con_ese_sku = [a for a in catalogo.list_articles(only_active=False)
                   if a.sku == SKU_DELIVERY]
    assert len(con_ese_sku) == 1
