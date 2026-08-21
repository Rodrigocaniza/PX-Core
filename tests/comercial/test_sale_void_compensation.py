"""Anulación compensatoria de una venta que ya movió stock, slice 6.

Pruebas dirigidas escritas antes de la implementación.

Hasta la 025 esto estaba prohibido, y estaba bien que lo estuviera: media
reversión improvisada es peor que ninguna. Lo que este slice agrega no es
permiso para reescribir, es el circuito que compensa:

    el hecho original permanece
    -> se registra un hecho compensatorio
    -> que produce efectos compensatorios
    -> y el estado derivado queda correcto

Todo lo que se verifica acá gira alrededor de una sola pregunta: después de
anular, ¿alguien puede reconstruir qué pasó? Si la venta desapareciera, si el
movimiento se borrara o si la unidad volviera sin nada que la explique, la
respuesta sería no.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.stock_ledger import StockLedgerService
from modulos.comercial.application.ventas import (
    AnulacionSinResponsable,
    VentaIntegradaNoEditable,
    VentasLedgerIntegrator,
)
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
    repo.bind_register_to_branch("P2", "PILAR", assigned_by="prueba")
    yield repo
    repo.close()


@pytest.fixture()
def armazon(catalogo):
    return catalogo.save_article(Article(
        sku="ARM-001", name="Armazón metal", nature=ArticleNature.PRODUCTO_STOCKEABLE))


@pytest.fixture()
def cadenilla(catalogo):
    return catalogo.save_article(Article(
        sku="ACC-CAD", name="Cadenilla", nature=ArticleNature.PRODUCTO_STOCKEABLE))


@pytest.fixture()
def cristal(catalogo):
    return catalogo.save_article(Article(
        sku="CRIS-ORG", name="Cristal orgánico recetado",
        nature=ArticleNature.TRABAJO_BAJO_PEDIDO))


@pytest.fixture()
def compostura(catalogo):
    return catalogo.save_article(Article(
        sku="SERV-COMP", name="Compostura",
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE))


def _dar_stock(ledger, articulo, cantidad, destino=Destination.ASUNCION, clave=None):
    ledger.registrar(StockMovement(
        article_id=articulo.id, destination=destino,
        kind=StockMovementKind.INGRESO_COMPRA, quantity=cantidad, actor="rodrigo",
        idempotency_key=clave or f"alta:{articulo.id}:{destino.value}"))


def _dia(unidad="PC", entradas=()):
    return CashDay(business_date=date(2026, 8, 18), unit=unidad, opening_cash=0,
                   opened_by="rodrigo", entries=list(entradas))


def _venta(*items, descripcion="Venta mostrador", total=None):
    return CashEntry(
        description=descripcion, saleswoman="ana",
        total=total if total is not None else sum(i.subtotal for i in items),
        cash=total if total is not None else sum(i.subtotal for i in items),
        items=tuple(items))


def _linea(*, armazon=None, cristal=None, precio_armazon=None, precio_cristal=None,
           descripcion="Armazón/org"):
    return SaleItem(
        description=descripcion,
        frame_price=precio_armazon, lens_price=precio_cristal,
        article_id=armazon.id if armazon is not None else None,
        lens_article_id=cristal.id if cristal is not None else None)


def _vender(caja, *items, unidad="PC", descripcion="Venta mostrador"):
    """Deja una venta guardada e integrada, y devuelve el día recargado."""
    dia = _dia(unidad=unidad, entradas=[_venta(*items, descripcion=descripcion)])
    caja.save(dia)
    return caja.get_by_date_and_unit(dia.business_date, unidad)


def _anular(caja, dia, entry_id, motivo="Cargada por error", quien="rodrigo"):
    dia.void_entry(entry_id, motivo)
    caja.save(dia, audit_reason=motivo, edited_by=quien)
    return caja.get_by_date_and_unit(dia.business_date, dia.unit)


def _conexion(ruta):
    conexion = sqlite3.connect(str(ruta))
    conexion.row_factory = sqlite3.Row
    return conexion


# --------------------------------------------------------------------------
# El hecho original permanece
# --------------------------------------------------------------------------


def test_la_venta_anulada_sigue_estando(caja, ruta, armazon, ledger):
    """Anular no hace desaparecer la venta del día: la marca."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    entrada = dia.entries[0]
    recargado = _anular(caja, dia, entrada.id)

    assert [e.id for e in recargado.entries] == [entrada.id]
    anulada = recargado.entries[0]
    assert anulada.status.value == "VOIDED"
    assert anulada.void_reason == "Cargada por error"
    assert anulada.voided_at is not None
    assert anulada.total == entrada.total


def test_el_sale_completed_original_no_se_toca(caja, ruta, armazon, ledger):
    """El hecho de que la venta ocurrió sigue siendo verdad. Lo que se agrega
    es el hecho de que después se anuló."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    conexion = _conexion(ruta)
    try:
        antes = conexion.execute(
            "SELECT * FROM domain_events WHERE event_type = 'SALE_COMPLETED'"
        ).fetchone()
    finally:
        conexion.close()

    _anular(caja, dia, dia.entries[0].id)

    conexion = _conexion(ruta)
    try:
        despues = conexion.execute(
            "SELECT * FROM domain_events WHERE event_type = 'SALE_COMPLETED'"
        ).fetchone()
        assert dict(despues) == dict(antes)
        assert conexion.execute(
            "SELECT COUNT(*) FROM domain_events WHERE event_type = 'SALE_VOIDED'"
        ).fetchone()[0] == 1
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_stock_integrations").fetchone()[0] == 1
    finally:
        conexion.close()


def test_los_movimientos_venta_originales_no_se_tocan(caja, ruta, armazon, ledger):
    """El ledger es append-only también cuando lo que se corrige es una venta."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    antes = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA]

    _anular(caja, dia, dia.entries[0].id)

    despues = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA]
    assert [m.id for m in despues] == [m.id for m in antes]
    assert [m.quantity for m in despues] == [m.quantity for m in antes]
    assert [m.occurred_at for m in despues] == [m.occurred_at for m in antes]


def test_las_lineas_historicas_siguen_ahi(caja, ruta, armazon, cristal, ledger):
    """La línea que produjo el movimiento no se borra: el movimiento apunta a ella."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, cristal=cristal,
                               precio_armazon=280_000, precio_cristal=250_000))
    entrada = dia.entries[0]
    recargado = _anular(caja, dia, entrada.id)

    assert len(recargado.entries[0].items) == 1
    item = recargado.entries[0].items[0]
    assert item.id == entrada.items[0].id
    assert item.article_id == armazon.id
    assert item.lens_article_id == cristal.id


# --------------------------------------------------------------------------
# El efecto compensatorio
# --------------------------------------------------------------------------


def test_la_anulacion_devuelve_exactamente_lo_que_la_venta_saco(
        caja, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4

    _anular(caja, dia, dia.entries[0].id)
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


def test_la_devolucion_es_un_movimiento_nuevo_que_apunta_al_que_compensa(
        caja, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    venta = [m for m in ledger.movimientos()
             if m.kind is StockMovementKind.VENTA][0]

    _anular(caja, dia, dia.entries[0].id, motivo="Cliente se arrepintió")

    compensacion = [m for m in ledger.movimientos()
                    if m.compensates_id == venta.id]
    assert len(compensacion) == 1
    devuelto = compensacion[0]
    assert devuelto.kind is StockMovementKind.AJUSTE_POSITIVO
    assert devuelto.quantity == venta.quantity
    assert devuelto.article_id == venta.article_id
    assert devuelto.destination is venta.destination
    assert devuelto.reason_code == "VENTA_ANULADA"
    assert devuelto.note == "Cliente se arrepintió"
    assert devuelto.actor == "rodrigo"
    assert devuelto.document_kind == "VENTA"
    assert devuelto.document_id == dia.entries[0].id
    assert devuelto.document_line_id == venta.document_line_id


def test_el_hecho_compensatorio_es_durable_y_esta_ligado_a_sus_efectos(
        caja, ruta, armazon, cadenilla, ledger):
    _dar_stock(ledger, armazon, 5)
    _dar_stock(ledger, cadenilla, 5)
    dia = _vender(caja,
                  _linea(armazon=armazon, precio_armazon=280_000),
                  _linea(armazon=cadenilla, precio_armazon=30_000,
                         descripcion="Cadenilla"))
    entrada = dia.entries[0]
    _anular(caja, dia, entrada.id, motivo="Duplicada")

    conexion = _conexion(ruta)
    try:
        evento = conexion.execute(
            "SELECT * FROM domain_events WHERE event_type = 'SALE_VOIDED'"
        ).fetchone()
        assert evento["entity_type"] == "SALE"
        assert evento["entity_id"] == entrada.id
        assert evento["source"] == "CAJA"
        assert evento["actor"] == "rodrigo"
        assert evento["destination"] == "ASUNCION"
        assert evento["processing_state"] == "PROCESADO"
        assert evento["idempotency_key"] == f"VENTA:{entrada.id}:ANULACION"

        efectos = conexion.execute(
            "SELECT * FROM event_effects WHERE event_id = ?",
            (evento["event_id"],)).fetchall()
        assert len(efectos) == 2
        assert {f["effect_table"] for f in efectos} == {"stock_movements"}

        registro = conexion.execute(
            "SELECT * FROM sale_void_compensations").fetchone()
        assert registro["cash_entry_id"] == entrada.id
        assert registro["void_event_id"] == evento["event_id"]
        assert registro["movement_count"] == 2
        assert registro["voided_by"] == "rodrigo"
        assert registro["note"] == "Duplicada"
        assert registro["destination"] == "ASUNCION"
    finally:
        conexion.close()


def test_se_puede_ir_de_la_unidad_devuelta_hasta_la_venta(caja, ruta, armazon, ledger):
    """Sin trazabilidad, «apareció una unidad» sería todo lo que se puede decir."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    _anular(caja, dia, dia.entries[0].id, motivo="Cargada por error")

    conexion = _conexion(ruta)
    try:
        fila = conexion.execute("SELECT * FROM stock_origen_anulacion").fetchone()
        assert fila["article_id"] == armazon.id
        assert fila["quantity"] == 1
        assert fila["entry_description"] == "Venta mostrador"
        assert fila["entry_status"] == "VOIDED"
        assert fila["void_reason"] == "Cargada por error"
        assert fila["voided_by"] == "rodrigo"
        assert fila["unit"] == "PC"
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Naturaleza del artículo: no se inventa stock
# --------------------------------------------------------------------------


def test_anular_una_venta_de_puro_servicio_no_inventa_movimientos(
        caja, ruta, compostura, ledger):
    """Una venta de servicios emite su `SALE_COMPLETED` y no mueve una unidad.
    Anularla emite su `SALE_VOIDED` y tampoco mueve ninguna: el hecho es
    durable aunque no produzca efectos, y devolver algo sería crear inventario
    de la nada."""
    dia = _vender(caja, _linea(armazon=compostura, precio_armazon=30_000,
                               descripcion="Compostura"))
    _anular(caja, dia, dia.entries[0].id)

    assert ledger.movimientos() == []
    conexion = _conexion(ruta)
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT movement_count FROM sale_void_compensations").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT COUNT(*) FROM domain_events WHERE event_type='SALE_VOIDED'"
        ).fetchone()[0] == 1
        assert conexion.execute(
            "SELECT COUNT(*) FROM event_effects").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT status FROM cash_entries").fetchone()[0] == "VOIDED"
    finally:
        conexion.close()


def test_una_venta_mixta_devuelve_solo_la_parte_que_movio_stock(
        caja, armazon, cristal, compostura, ledger):
    """El cristal es trabajo bajo pedido y la compostura es servicio. Ninguno
    de los dos salió del depósito, así que ninguno vuelve."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja,
                  _linea(armazon=armazon, cristal=cristal,
                         precio_armazon=280_000, precio_cristal=250_000),
                  _linea(armazon=compostura, precio_armazon=30_000,
                         descripcion="Compostura"))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4

    _anular(caja, dia, dia.entries[0].id)

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    assert ledger.movimientos(article_id=cristal.id) == []
    assert ledger.movimientos(article_id=compostura.id) == []
    compensaciones = [m for m in ledger.movimientos() if m.compensates_id]
    assert len(compensaciones) == 1


# --------------------------------------------------------------------------
# Sucursal
# --------------------------------------------------------------------------


def test_la_mercaderia_vuelve_al_local_del_que_salio(caja, armazon, ledger):
    """Devolverla al otro local sería stock que el sistema dice tener y que
    físicamente no está ahí."""
    _dar_stock(ledger, armazon, 5, destino=Destination.PILAR, clave="alta-pilar")
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000), unidad="P2")
    assert ledger.stock(armazon.id, Destination.PILAR) == 4

    _anular(caja, dia, dia.entries[0].id)

    assert ledger.stock(armazon.id, Destination.PILAR) == 5
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 0


# --------------------------------------------------------------------------
# Idempotencia
# --------------------------------------------------------------------------


def test_guardar_dos_veces_la_anulacion_no_devuelve_el_stock_dos_veces(
        caja, ruta, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    recargado = _anular(caja, dia, dia.entries[0].id)
    caja.save(recargado, edited_by="rodrigo")
    caja.save(caja.get_by_date_and_unit(recargado.business_date, recargado.unit),
              edited_by="rodrigo")

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    conexion = _conexion(ruta)
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM domain_events WHERE event_type='SALE_VOIDED'"
        ).fetchone()[0] == 1
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE compensates_id IS NOT NULL"
        ).fetchone()[0] == 1
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_void_compensations").fetchone()[0] == 1
    finally:
        conexion.close()


def test_una_anulacion_manual_previa_del_ledger_no_se_duplica(
        caja, armazon, ledger):
    """La clave de compensación es la misma la dispare quien la dispare: dos
    caminos hacia la misma corrección siguen siendo una sola corrección."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    venta = [m for m in ledger.movimientos()
             if m.kind is StockMovementKind.VENTA][0]
    ledger.compensar(venta.id, reason_code="ERROR_INVENTARIO",
                     note="corregido a mano", actor="admin")
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5

    _anular(caja, dia, dia.entries[0].id)

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    assert len([m for m in ledger.movimientos() if m.compensates_id]) == 1


def test_reintentar_despues_de_una_falla_no_duplica_efectos(
        caja, ruta, armazon, ledger, monkeypatch):
    """Un corte a mitad del guardado deja el sistema como estaba, no a medias.
    El reintento produce exactamente una devolución."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    entrada_id = dia.entries[0].id

    original = SQLiteCashDayRepository._record_entry_revisions
    fallas = {"restantes": 1}

    def _falla_una_vez(self, *args, **kwargs):
        if fallas["restantes"]:
            fallas["restantes"] -= 1
            raise RuntimeError("corte simulado despues de compensar")
        return original(*args, **kwargs)  # `original` ya viene ligado a la clase

    monkeypatch.setattr(
        SQLiteCashDayRepository, "_record_entry_revisions", _falla_una_vez)

    dia.void_entry(entrada_id, "Cargada por error")
    with pytest.raises(RuntimeError):
        caja.save(dia, edited_by="rodrigo")

    # Nada quedó a medias: ni la devolución ni la anulación.
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    conexion = _conexion(ruta)
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_void_compensations").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT COUNT(*) FROM domain_events WHERE event_type='SALE_VOIDED'"
        ).fetchone()[0] == 0
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE compensates_id IS NOT NULL"
        ).fetchone()[0] == 0
        assert conexion.execute(
            "SELECT status FROM cash_entries WHERE id = ?",
            (entrada_id,)).fetchone()[0] == "ACTIVE"
    finally:
        conexion.close()

    caja.save(dia, edited_by="rodrigo")

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    conexion = _conexion(ruta)
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE compensates_id IS NOT NULL"
        ).fetchone()[0] == 1
        assert conexion.execute(
            "SELECT status FROM cash_entries WHERE id = ?",
            (entrada_id,)).fetchone()[0] == "VOIDED"
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Actor y motivo
# --------------------------------------------------------------------------


def test_sin_responsable_la_anulacion_se_rechaza(ruta, integrador, armazon, ledger):
    """Stock que vuelve sin nadie que lo firme es stock aparecido."""
    repo = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    repo.bind_register_to_branch("PC", "ASUNCION", assigned_by="prueba")
    try:
        _dar_stock(ledger, armazon, 5)
        dia = CashDay(business_date=date(2026, 8, 18), unit="PC", opening_cash=0,
                      opened_by="", entries=[CashEntry(
                          description="Venta mostrador", saleswoman="",
                          total=280_000, cash=280_000,
                          items=(_linea(armazon=armazon, precio_armazon=280_000),))])
        repo.save(dia)
        recargado = repo.get_by_date_and_unit(dia.business_date, "PC")
        recargado.void_entry(recargado.entries[0].id, "Cargada por error")
        with pytest.raises(AnulacionSinResponsable):
            repo.save(recargado, edited_by="")
    finally:
        repo.close()

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


def test_el_motivo_es_obligatorio_desde_el_dominio(caja, armazon, ledger):
    """No hace falta llegar al ledger para saber que una anulación sin motivo
    no es una anulación."""
    from modulos.caja_diaria.domain.models import InvalidCashDayError

    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    with pytest.raises(InvalidCashDayError):
        dia.void_entry(dia.entries[0].id, "   ")


def test_el_motivo_escrito_viaja_hasta_el_movimiento(caja, armazon, ledger):
    """La observación del movimiento no es un texto fijo: es lo que la operadora
    escribió, que es lo único que explica por qué la unidad volvió."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    _anular(caja, dia, dia.entries[0].id, motivo="El cliente devolvió el armazón")

    devuelto = [m for m in ledger.movimientos() if m.compensates_id][0]
    assert devuelto.note == "El cliente devolvió el armazón"


# --------------------------------------------------------------------------
# Lo que la base impide por su cuenta
# --------------------------------------------------------------------------


def test_el_registro_de_anulacion_es_append_only(caja, ruta, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    _anular(caja, dia, dia.entries[0].id)

    conexion = _conexion(ruta)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "UPDATE sale_void_compensations SET movement_count = 9")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM sale_void_compensations")
    finally:
        conexion.close()


def test_una_venta_integrada_no_se_anula_sin_compensar(caja, ruta, armazon, ledger):
    """El bloqueo sigue existiendo para cualquier escritor que intente anular
    por su cuenta, sin devolver la mercadería."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))

    conexion = _conexion(ruta)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "UPDATE cash_entries SET status='VOIDED', voided_at='2026-08-18',"
                " void_reason='a mano' WHERE id = ?", (dia.entries[0].id,))
    finally:
        conexion.close()
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


def test_una_anulacion_parcial_se_rechaza_entera(caja, ruta, armazon, cadenilla,
                                                 ledger):
    """Devolver una unidad de dos dejaría el depósito en un estado que nadie
    puede explicar. La base no acepta el registro si falta una."""
    _dar_stock(ledger, armazon, 5)
    _dar_stock(ledger, cadenilla, 5)
    dia = _vender(caja,
                  _linea(armazon=armazon, precio_armazon=280_000),
                  _linea(armazon=cadenilla, precio_armazon=30_000,
                         descripcion="Cadenilla"))
    entrada = dia.entries[0]
    venta = [m for m in ledger.movimientos()
             if m.kind is StockMovementKind.VENTA][0]
    ledger.compensar(venta.id, reason_code="ERROR_INVENTARIO", note="una sola",
                     actor="admin")

    conexion = _conexion(ruta)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO sale_void_compensations(cash_entry_id, sale_event_id,"
                " void_event_id, destination, reason_code, note, movement_count,"
                " voided_at, voided_by) SELECT ?, event_id, event_id, 'ASUNCION',"
                " 'VENTA_ANULADA', 'parcial', 1, '2026-08-18', 'admin'"
                " FROM sale_stock_integrations WHERE cash_entry_id = ?",
                (entrada.id, entrada.id))
    finally:
        conexion.close()


def test_una_anulacion_no_puede_declarar_efectos_que_no_ocurrieron(
        caja, ruta, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    entrada = dia.entries[0]

    conexion = _conexion(ruta)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO sale_void_compensations(cash_entry_id, sale_event_id,"
                " void_event_id, destination, reason_code, note, movement_count,"
                " voided_at, voided_by) SELECT ?, event_id, event_id, 'ASUNCION',"
                " 'VENTA_ANULADA', 'inventada', 3, '2026-08-18', 'admin'"
                " FROM sale_stock_integrations WHERE cash_entry_id = ?",
                (entrada.id, entrada.id))
    finally:
        conexion.close()


def test_venta_anulada_es_un_motivo_reservado(caja, armazon, ledger):
    """Sin esto, cualquiera podría ingresar mercadería a mano diciendo que una
    venta se anuló, sin que ninguna venta se hubiera anulado."""
    from modulos.comercial.application.stock_ledger import LedgerError

    _dar_stock(ledger, armazon, 5)
    with pytest.raises(LedgerError):
        ledger.registrar(StockMovement(
            article_id=armazon.id, destination=Destination.ASUNCION,
            kind=StockMovementKind.AJUSTE_POSITIVO, quantity=3, actor="admin",
            reason_code="VENTA_ANULADA", note="aparecieron",
            idempotency_key="inventado"))
    with pytest.raises(LedgerError):
        ledger.registrar(StockMovement(
            article_id=armazon.id, destination=Destination.ASUNCION,
            kind=StockMovementKind.SALIDA_ADMINISTRATIVA, quantity=1, actor="admin",
            reason_code="VENTA_ANULADA", note="se fue",
            idempotency_key="inventado-2"))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


def test_el_enum_de_motivos_marca_venta_anulada_como_reservado():
    from modulos.comercial.domain.models import AdministrativeExitReason

    assert AdministrativeExitReason.VENTA_ANULADA.reservado
    assert not AdministrativeExitReason.ROTO.reservado


def test_una_venta_anulada_no_revive(caja, ruta, armazon, ledger):
    """Revivirla descontaría el stock una segunda vez sin un hecho nuevo."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    entrada_id = dia.entries[0].id
    _anular(caja, dia, entrada_id)

    conexion = _conexion(ruta)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "UPDATE cash_entries SET status='ACTIVE', voided_at=NULL,"
                " void_reason='' WHERE id = ?", (entrada_id,))
    finally:
        conexion.close()
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


def test_las_lineas_de_una_venta_anulada_siguen_congeladas(caja, ruta, armazon,
                                                           ledger):
    """Anular no reabre la edición: la corrección de una venta equivocada es
    una venta nueva, no una reescritura de la vieja."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    recargado = _anular(caja, dia, dia.entries[0].id)

    from dataclasses import replace
    entrada = recargado.entries[0]
    recargado.entries[0] = replace(entrada, items=())
    with pytest.raises(VentaIntegradaNoEditable):
        caja.save(recargado, edited_by="rodrigo")


# --------------------------------------------------------------------------
# Corrección: compensar y volver a consecuenciar, nunca mutar
# --------------------------------------------------------------------------


def test_corregir_una_venta_es_anularla_y_cargar_la_correcta(
        caja, ruta, armazon, cadenilla, ledger):
    """Se vendió el artículo equivocado. La corrección no reescribe la venta:
    la compensa y registra la venta que realmente ocurrió. Quedan las dos, y el
    stock de los dos artículos termina donde tiene que terminar."""
    _dar_stock(ledger, armazon, 5)
    _dar_stock(ledger, cadenilla, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4

    dia.void_entry(dia.entries[0].id, "Se cargó el artículo equivocado")
    dia.add_entry(_venta(_linea(armazon=cadenilla, precio_armazon=30_000,
                                descripcion="Cadenilla"),
                         descripcion="Venta corregida"))
    caja.save(dia, audit_reason="corrección", edited_by="rodrigo")

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    assert ledger.stock(cadenilla.id, Destination.ASUNCION) == 4

    recargado = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    estados = {e.description: e.status.value for e in recargado.entries}
    assert estados == {"Venta mostrador": "VOIDED", "Venta corregida": "ACTIVE"}
    assert recargado.totals().total == 30_000

    conexion = _conexion(ruta)
    try:
        tipos = [f[0] for f in conexion.execute(
            "SELECT event_type FROM domain_events ORDER BY recorded_at, rowid")]
        assert tipos.count("SALE_COMPLETED") == 2
        assert tipos.count("SALE_VOIDED") == 1
    finally:
        conexion.close()


def test_editar_las_lineas_de_una_venta_integrada_sigue_bloqueado(
        caja, armazon, cadenilla, ledger):
    """Cambiar el artículo en el lugar dejaría el movimiento que sacó la unidad
    apuntando a una línea que ya dice otra cosa. Eso es reescribir el pasado, y
    es exactamente lo que la compensación existe para no hacer."""
    from dataclasses import replace

    _dar_stock(ledger, armazon, 5)
    _dar_stock(ledger, cadenilla, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    entrada = dia.entries[0]
    dia.entries[0] = replace(
        entrada,
        items=(replace(entrada.items[0], article_id=cadenilla.id),))

    with pytest.raises(VentaIntegradaNoEditable):
        caja.save(dia, edited_by="rodrigo")
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    assert ledger.stock(cadenilla.id, Destination.ASUNCION) == 5


# --------------------------------------------------------------------------
# Caja: el dinero no se toca dos veces
# --------------------------------------------------------------------------


def test_la_devolucion_de_stock_no_mueve_un_guarani(caja, ruta, armazon, ledger):
    """Un movimiento de inventario mueve unidades y no mueve plata. El hecho
    económico de la anulación ya lo resuelve Caja sacando la entrada del total;
    si además apareciera acá, se contaría dos veces."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    assert dia.totals().total == 280_000

    recargado = _anular(caja, dia, dia.entries[0].id)

    totales = recargado.totals()
    assert totales.total == 0
    assert totales.cash == 0
    assert totales.entry_count == 0

    conexion = _conexion(ruta)
    try:
        columnas = {f[1] for f in conexion.execute("PRAGMA table_info(stock_movements)")}
        assert not columnas & {"amount", "total", "cash", "price", "importe"}
        assert conexion.execute(
            "SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 1
    finally:
        conexion.close()


def test_la_anulacion_no_agrega_entradas_de_caja(caja, ruta, armazon, ledger):
    """La compensación es de inventario. No crea una entrada negativa en el día."""
    _dar_stock(ledger, armazon, 5)
    dia = _vender(caja, _linea(armazon=armazon, precio_armazon=280_000))
    recargado = _anular(caja, dia, dia.entries[0].id)

    assert len(recargado.entries) == 1
    conexion = _conexion(ruta)
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_items").fetchone()[0] == 1
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Lo que no cambió para quien todavía no vincula artículos
# --------------------------------------------------------------------------


def test_una_venta_sin_articulo_se_anula_como_siempre(caja, ruta, ledger):
    """Es el caso de todo lo que ya existe en producción. Instalar esto no
    cambia el comportamiento de una caja que todavía no vincula artículos."""
    dia = _dia(entradas=[_venta(SaleItem(description="Armazon/org uvx",
                                         frame_price=280_000))])
    caja.save(dia)
    recargado = caja.get_by_date_and_unit(dia.business_date, "PC")
    recargado.void_entry(recargado.entries[0].id, "Carga duplicada")
    caja.save(recargado, edited_by="rodrigo")

    final = caja.get_by_date_and_unit(dia.business_date, "PC")
    assert final.entries[0].status.value == "VOIDED"
    assert ledger.movimientos() == []
    conexion = _conexion(ruta)
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_void_compensations").fetchone()[0] == 0
    finally:
        conexion.close()


def test_la_compensacion_va_en_la_transaccion_de_la_anulacion(integrador):
    """Una segunda transacción independiente podría dejar la venta anulada y el
    stock afuera, o al revés. El circuito recibe la conexión, no la abre."""
    firma = VentasLedgerIntegrator.compensar_anulaciones_en.__code__.co_varnames
    assert "connection" in firma
    fuente = __import__("inspect").getsource(VentasLedgerIntegrator)
    assert "BEGIN" not in fuente
    assert "COMMIT" not in fuente
