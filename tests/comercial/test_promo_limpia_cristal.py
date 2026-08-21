"""El limpia-cristal de regalo, sobre el artículo real. Slice 13.

Pruebas dirigidas escritas antes de tocar nada.

La óptica venía representando el regalo con un artículo inventado —«LIMPIA
CRISTAL OBSEQUIO», precio cero clavado en el catálogo y su propio stock— y eso
producía dos mentiras a la vez: un producto que no existe y un depósito que no
se corresponde con lo que hay en el mostrador. El regalo es el mismo frasco que
se vende; lo que cambia es cuánto se cobra por él.

Lo que se verifica acá gira alrededor de una pregunta: si mañana alguien mira el
depósito y le faltan frascos, ¿va a poder saber por qué? Si el regalo no
descontara stock, si no dejara rastro de que fue bonificado, o si el artículo
retirado siguiera apareciendo para vender, la respuesta sería no.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.comercial_controller import build_comercial_controller
from modulos.comercial.application.stock_ledger import StockLedgerService
from modulos.comercial.application.ventas import StockInsuficiente, VentasLedgerIntegrator
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

PROMO = "PROMO_CRISTAL_ARMAZON_LIMPIA"


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
def armazon(catalogo):
    return catalogo.save_article(Article(
        sku="ARM-001", name="Armazón metal", nature=ArticleNature.PRODUCTO_STOCKEABLE))


@pytest.fixture()
def cristal(catalogo):
    return catalogo.save_article(Article(
        sku="CRIS-ORG", name="Cristal orgánico recetado",
        nature=ArticleNature.TRABAJO_BAJO_PEDIDO))


@pytest.fixture()
def limpia(catalogo):
    """El frasco real. El mismo que se vende y el mismo que se regala."""
    return catalogo.save_article(Article(
        sku="000010", name="Limpia Cristal", nature=ArticleNature.PRODUCTO_STOCKEABLE,
        sale_price=15000))


@pytest.fixture()
def obsequio(catalogo):
    """El artículo inventado que esta misión viene a retirar."""
    return catalogo.save_article(Article(
        sku="000037", name="LIMPIA CRISTAL OBSEQUIO",
        nature=ArticleNature.PRODUCTO_STOCKEABLE))


def _dar_stock(ledger, articulo, cantidad, destino=Destination.ASUNCION, clave=None):
    ledger.registrar(StockMovement(
        article_id=articulo.id, destination=destino,
        kind=StockMovementKind.INGRESO_COMPRA, quantity=cantidad, actor="rodrigo",
        idempotency_key=clave or f"alta:{articulo.id}:{destino.value}"))


def _linea_venta(armazon, cristal, precio_armazon=280000, precio_cristal=250000):
    return SaleItem(description="Armazón + cristal", frame_price=precio_armazon,
                    lens_price=precio_cristal, article_id=armazon.id,
                    lens_article_id=cristal.id)


def _linea_regalo(limpia):
    """La línea del obsequio: artículo real, sin costo, con el motivo escrito."""
    return SaleItem(description=f"Limpia Cristal — obsequio {PROMO}",
                    frame_price=15000, no_cost=True, article_id=limpia.id)


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
# El regalo sale del stock real
# --------------------------------------------------------------------------


def test_el_regalo_descuenta_una_unidad_del_articulo_real(caja, ledger, armazon, cristal, limpia):
    """Regalar es entregar. Lo que se entrega sale del depósito."""
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)

    _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))

    assert ledger.stock(limpia.id, Destination.ASUNCION) == 9
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 2


def test_el_regalo_no_cobra_nada(limpia):
    """La línea vale cero aunque el artículo tenga precio."""
    assert _linea_regalo(limpia).subtotal == 0


def test_la_venta_no_suma_el_precio_del_regalo(caja, ledger, armazon, cristal, limpia):
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)

    dia = _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))

    assert dia.entries[0].total == 530000  # 280.000 + 250.000, el regalo no suma


def test_el_movimiento_del_regalo_dice_que_fue_obsequio(caja, ruta, ledger, armazon,
                                                        cristal, limpia):
    """Sin esto, dentro de un año nadie sabría por qué faltaba ese frasco."""
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)

    _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))

    with _conexion(ruta) as conexion:
        nota = conexion.execute(
            "SELECT sm.note FROM stock_movements sm WHERE sm.article_id = ?"
            " AND sm.kind = 'VENTA'", (limpia.id,)).fetchone()["note"]
    assert PROMO in nota


def test_el_regalo_queda_marcado_sin_costo_en_la_linea(caja, ruta, ledger, armazon,
                                                       cristal, limpia):
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)

    _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))

    with _conexion(ruta) as conexion:
        filas = conexion.execute(
            "SELECT no_cost, article_id FROM sale_items WHERE article_id = ?",
            (limpia.id,)).fetchall()
    assert len(filas) == 1
    assert filas[0]["no_cost"] == 1


def test_una_venta_sin_promocion_no_regala_nada(caja, ledger, armazon, cristal, limpia):
    """El obsequio no es automático: si no se agrega, no sale del depósito."""
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)

    _vender(caja, _linea_venta(armazon, cristal))

    assert ledger.stock(limpia.id, Destination.ASUNCION) == 10


def test_vender_el_limpia_cristal_normalmente_sigue_funcionando(caja, ledger, limpia):
    """El mismo artículo se cobra cuando no es regalo."""
    _dar_stock(ledger, limpia, 10)

    dia = _vender(caja, SaleItem(description="Limpia Cristal", frame_price=15000,
                                 article_id=limpia.id))

    assert dia.entries[0].total == 15000
    assert ledger.stock(limpia.id, Destination.ASUNCION) == 9


# --------------------------------------------------------------------------
# No se puede regalar lo que no hay
# --------------------------------------------------------------------------


def test_no_se_regala_si_no_hay_stock(caja, ledger, armazon, cristal, limpia):
    """Un obsequio no es excusa para dejar el depósito en negativo."""
    _dar_stock(ledger, armazon, 3)
    # el limpia-cristal no tiene una sola unidad

    with pytest.raises(StockInsuficiente):
        _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))

    assert ledger.stock(limpia.id, Destination.ASUNCION) == 0


def test_dos_regalos_en_la_misma_venta_piden_dos_unidades(caja, ledger, armazon,
                                                          cristal, limpia):
    """Duplicar el regalo no sale gratis: se le pide al depósito lo que se lleva."""
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 1)

    with pytest.raises(StockInsuficiente):
        _vender(caja, _linea_venta(armazon, cristal),
                _linea_regalo(limpia), _linea_regalo(limpia))

    assert ledger.stock(limpia.id, Destination.ASUNCION) == 1


# --------------------------------------------------------------------------
# Anular devuelve el regalo
# --------------------------------------------------------------------------


def test_anular_la_venta_devuelve_el_frasco_regalado(caja, ledger, armazon, cristal, limpia):
    """Si la venta se anula, el obsequio vuelve al depósito como cualquier unidad."""
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)
    dia = _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))
    assert ledger.stock(limpia.id, Destination.ASUNCION) == 9

    entry_id = dia.entries[0].id
    dia.void_entry(entry_id, "Cargada por error")
    caja.save(dia, audit_reason="Cargada por error", edited_by="rodrigo")

    assert ledger.stock(limpia.id, Destination.ASUNCION) == 10


def test_al_anular_el_movimiento_original_del_regalo_no_se_borra(caja, ruta, ledger,
                                                                armazon, cristal, limpia):
    """La devolución es un hecho nuevo, no un borrado del anterior."""
    _dar_stock(ledger, armazon, 3)
    _dar_stock(ledger, limpia, 10)
    dia = _vender(caja, _linea_venta(armazon, cristal), _linea_regalo(limpia))
    dia.void_entry(dia.entries[0].id, "Cargada por error")
    caja.save(dia, audit_reason="Cargada por error", edited_by="rodrigo")

    with _conexion(ruta) as conexion:
        tipos = [f["kind"] for f in conexion.execute(
            "SELECT kind FROM stock_movements WHERE article_id = ? ORDER BY occurred_at",
            (limpia.id,))]
    assert "VENTA" in tipos
    assert "AJUSTE_POSITIVO" in tipos


# --------------------------------------------------------------------------
# El artículo inventado se retira
# --------------------------------------------------------------------------


def test_el_obsequio_retirado_no_aparece_para_vender(ruta, catalogo, ledger_repo,
                                                     integrador, obsequio, limpia):
    """Retirado quiere decir que la operadora ya no lo encuentra."""
    controlador = build_comercial_controller(ruta)
    try:
        controlador.desactivar_articulo(obsequio.id, actor="rodrigo",
                                        motivo="mecanismo ficticio retirado en V1-013")
        encontrados = {o.sku for o in controlador.buscar_para_venta("LIMPIA", unidad="PC")}
    finally:
        controlador.close()

    assert "000037" not in encontrados
    assert "000010" in encontrados


def test_retirar_el_obsequio_no_borra_su_historia(ruta, catalogo, ledger, ledger_repo,
                                                  integrador, obsequio):
    """Sigue existiendo, inactivo, con sus movimientos donde estaban."""
    _dar_stock(ledger, obsequio, 210)
    ledger.registrar(StockMovement(
        article_id=obsequio.id, destination=Destination.ASUNCION,
        kind=StockMovementKind.AJUSTE_NEGATIVO, quantity=210, actor="rodrigo",
        reason_code="ERROR_INVENTARIO", note="stock ficticio compensado",
        idempotency_key="compensa:ficticio"))
    controlador = build_comercial_controller(ruta)
    try:
        controlador.desactivar_articulo(obsequio.id, actor="rodrigo", motivo="V1-013")
        recuperado = controlador.obtener_articulo(obsequio.id)
    finally:
        controlador.close()

    assert recuperado is not None
    assert recuperado.active is False
    assert ledger.stock(obsequio.id, Destination.ASUNCION) == 0
    assert len(ledger.movimientos(article_id=obsequio.id)) == 2


def test_no_se_puede_retirar_el_obsequio_con_stock_encima(ruta, catalogo, ledger,
                                                          ledger_repo, integrador, obsequio):
    """Primero se compensa; recién después se retira. El producto ya lo exige."""
    from modulos.comercial.application.comercial_controller import ArticuloEnUso

    _dar_stock(ledger, obsequio, 210)
    controlador = build_comercial_controller(ruta)
    try:
        with pytest.raises(ArticuloEnUso):
            controlador.desactivar_articulo(obsequio.id, actor="rodrigo", motivo="V1-013")
    finally:
        controlador.close()
