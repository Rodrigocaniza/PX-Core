"""Enlace venta → artículo y derivación del stock, slice 4.

Pruebas dirigidas escritas antes de la implementación.

Este slice cierra el circuito: compra → `INGRESO_COMPRA` → stock → venta →
`SALE_COMPLETED` → `VENTA` → stock restante. Lo hace **sin reescribir** el
subsistema de ventas de BC Caja: la línea de venta sigue siendo la misma fila
de `sale_items` que la Óptica usa hoy, con su armazón y su cristal, y lo único
que se agrega es el vínculo con el artículo canónico.

Nada de lo que ya existe empieza a mover stock por sí solo. Una venta sin
artículo vinculado se comporta exactamente como hoy, que es la condición para
que rc.31 siga siendo rc.31.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from modulos.caja_diaria.domain.models import (
    CashDay,
    CashEntry,
    CashEntryStatus,
    SaleItem,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.stock_ledger import StockLedgerService
from modulos.comercial.application.ventas import (
    SucursalNoResoluble,
    VentaIntegradaNoEditable,
    VentasLedgerIntegrator,
    VentasService,
)
from modulos.comercial.domain.eventos import EventProcessingState
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
    SQLiteCashDayRepository(ruta).close()  # aplica la cadena 001..025
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
    """El repositorio productivo, con el enganche del ledger conectado."""
    repo = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    repo.bind_register_to_branch("PC", "ASUNCION", assigned_by="prueba")
    repo.bind_register_to_branch("P2", "PILAR", assigned_by="prueba")
    yield repo
    repo.close()


@pytest.fixture()
def caja_sin_enganche(ruta):
    """El mismo repositorio tal como corre hoy en producción."""
    repo = SQLiteCashDayRepository(ruta)
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
        sku="SERV-COMP", name="Compostura", nature=ArticleNature.SERVICIO_NO_STOCKEABLE))


@pytest.fixture()
def limpia_cristales(catalogo):
    return catalogo.save_article(Article(
        sku="PROD-LIMP", name="Limpia cristales",
        nature=ArticleNature.PRODUCCION_INTERNA))


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


def _guardar(caja, dia):
    caja.save(dia)
    return dia


# --------------------------------------------------------------------------
# El vínculo, sin reescribir la venta
# --------------------------------------------------------------------------


def test_la_linea_de_venta_sigue_siendo_la_misma_fila(ruta, caja, armazon, cristal, ledger):
    """`sale_items` no se reemplazó: se le agregó el vínculo y nada más."""
    conexion = sqlite3.connect(str(ruta))
    try:
        columnas = {f[1] for f in conexion.execute("PRAGMA table_info(sale_items)")}
    finally:
        conexion.close()
    for de_siempre in ("cash_entry_id", "position", "description", "code", "item_type",
                       "frame_price", "lens_price", "laboratory"):
        assert de_siempre in columnas
    assert {"article_id", "lens_article_id"} <= columnas


def test_una_linea_lleva_el_articulo_del_armazon_y_el_del_cristal(
        caja, armazon, cristal, ledger):
    """La línea de la Óptica tiene dos componentes y siempre los tuvo. El
    vínculo respeta esa forma en vez de partir la venta en dos filas."""
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, cristal=cristal,
                                       precio_armazon=280_000, precio_cristal=250_000))])
    _guardar(caja, dia)
    guardado = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    item = guardado.entries[0].items[0]
    assert item.article_id == armazon.id
    assert item.lens_article_id == cristal.id


def test_la_naturaleza_decide_el_stock_y_no_el_texto_de_la_linea(
        caja, armazon, cristal, ledger):
    """La descripción dice «Armazón/org uvx» y el laboratorio dice «Optilab».
    Ninguna de esas dos cosas decide nada: decide la naturaleza del artículo."""
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(
        armazon=armazon, cristal=cristal, precio_armazon=280_000,
        precio_cristal=250_000, descripcion="Armazon/org uvx"))])
    _guardar(caja, dia)
    ventas = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA]
    assert [m.article_id for m in ventas] == [armazon.id]
    assert ledger.movimientos(article_id=cristal.id) == []


def test_sin_articulo_vinculado_la_venta_se_comporta_como_hoy(caja, ledger, ruta):
    """La condición para que rc.31 siga siendo rc.31: lo que ya existe no
    empieza a mover stock por su cuenta."""
    dia = _dia(entradas=[_venta(_linea(precio_armazon=280_000, precio_cristal=250_000))])
    _guardar(caja, dia)
    assert ledger.movimientos() == []
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_stock_integrations").fetchone()[0] == 0
    finally:
        conexion.close()


def test_el_repositorio_sin_enganche_es_el_de_hoy(caja_sin_enganche, ruta, armazon):
    """Producción corre sin integrador hasta que se lo conecte. Que el default
    sea «no integrar» es lo que hace seguro instalar esto."""
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    caja_sin_enganche.save(dia)
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 0
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# SALE_COMPLETED
# --------------------------------------------------------------------------


def test_una_venta_de_producto_emite_el_hecho_y_descuenta(
        caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    _guardar(caja, dia)

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    movimientos = ledger.movimientos()
    assert len(movimientos) == 2  # el ingreso de stock y la venta
    venta = [m for m in movimientos if m.kind is StockMovementKind.VENTA][0]
    assert venta.quantity == 1
    assert venta.signed_quantity == -1


def test_el_hecho_existe_aunque_la_venta_sea_toda_servicio(
        caja, compostura, ledger, ruta):
    """Un hecho no depende de tener efectos."""
    dia = _dia(entradas=[_venta(_linea(armazon=compostura, precio_armazon=30_000))])
    _guardar(caja, dia)

    conexion = sqlite3.connect(str(ruta))
    try:
        eventos = conexion.execute(
            "SELECT event_type, entity_id FROM domain_events").fetchall()
    finally:
        conexion.close()
    assert [e[0] for e in eventos] == ["SALE_COMPLETED"]
    assert ledger.movimientos() == []


def test_el_hecho_existe_aunque_la_venta_sea_todo_trabajo(caja, cristal, ledger, ruta):
    dia = _dia(entradas=[_venta(_linea(cristal=cristal, precio_cristal=250_000))])
    _guardar(caja, dia)
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM domain_events WHERE event_type='SALE_COMPLETED'"
        ).fetchone()[0] == 1
    finally:
        conexion.close()
    assert ledger.movimientos() == []


def test_el_hecho_guarda_la_trazabilidad_pedida(caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000))
    dia = _dia(entradas=[entrada])
    _guardar(caja, dia)

    repo = SQLiteStockLedgerRepository(ruta)
    try:
        evento = repo.evento_por_clave(f"VENTA:{entrada.id}")
        assert evento is not None
        assert evento.event_type == "SALE_COMPLETED"
        assert evento.source == "CAJA"
        assert evento.entity_type == "SALE"
        assert evento.entity_id == entrada.id
        assert evento.destination is Destination.ASUNCION
        assert evento.actor == "ana"
        assert evento.occurred_at is not None
        assert evento.processing_state is EventProcessingState.PROCESADO
        efectos = repo.efectos_de(evento.event_id)
        assert [e.effect_kind for e in efectos] == ["STOCK_MOVEMENT"]
    finally:
        repo.close()


def test_una_venta_mixta_emite_un_solo_hecho_y_mueve_solo_lo_que_mueve(
        caja, armazon, cristal, compostura, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(
        _linea(armazon=armazon, cristal=cristal,
               precio_armazon=280_000, precio_cristal=250_000),
        _linea(armazon=compostura, precio_armazon=30_000, descripcion="Compostura"))
    _guardar(caja, _dia(entradas=[entrada]))

    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 1
    finally:
        conexion.close()
    ventas = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA]
    assert [m.article_id for m in ventas] == [armazon.id]
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


def test_dos_lineas_stockeables_generan_dos_salidas(
        caja, armazon, cadenilla, ledger):
    _dar_stock(ledger, armazon, 5, clave="alta-arm")
    _dar_stock(ledger, cadenilla, 5, clave="alta-cad")
    entrada = _venta(
        _linea(armazon=armazon, precio_armazon=280_000),
        _linea(armazon=cadenilla, precio_armazon=70_000, descripcion="Cadenilla"))
    _guardar(caja, _dia(entradas=[entrada]))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    assert ledger.stock(cadenilla.id, Destination.ASUNCION) == 4


def test_una_produccion_interna_sale_igual_que_cualquier_producto(
        caja, limpia_cristales, ledger):
    _dar_stock(ledger, limpia_cristales, 3)
    _guardar(caja, _dia(entradas=[
        _venta(_linea(armazon=limpia_cristales, precio_armazon=25_000))]))
    assert ledger.stock(limpia_cristales.id, Destination.ASUNCION) == 2


def test_una_entrada_anulada_no_mueve_stock(caja, armazon, ledger):
    """Anular es lo contrario de vender: no puede descontar."""
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000))
    anulada = entrada.void(reason="cargada por error")
    _guardar(caja, _dia(entradas=[anulada]))
    assert ledger.movimientos(article_id=armazon.id) == [
        m for m in ledger.movimientos() if m.kind is StockMovementKind.INGRESO_COMPRA]
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


# --------------------------------------------------------------------------
# Referencia durable y trazabilidad inversa
# --------------------------------------------------------------------------


def test_el_movimiento_referencia_la_venta_la_linea_y_el_articulo(
        caja, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000))
    _guardar(caja, _dia(entradas=[entrada]))
    venta = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA][0]
    assert venta.document_kind == "VENTA"
    assert venta.document_id == entrada.id
    assert venta.document_line_id == entrada.items[0].id
    assert venta.article_id == armazon.id
    assert venta.destination is Destination.ASUNCION
    assert venta.actor == "ana"


def test_se_puede_ir_de_una_salida_de_stock_hasta_la_venta(caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000),
                     descripcion="Venta Juana Pérez")
    _guardar(caja, _dia(entradas=[entrada]))
    venta = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA][0]

    conexion = sqlite3.connect(str(ruta))
    conexion.row_factory = sqlite3.Row
    try:
        fila = conexion.execute(
            "SELECT * FROM stock_origen_venta WHERE movement_id = ?",
            (venta.id,)).fetchone()
    finally:
        conexion.close()
    assert fila is not None
    assert fila["cash_entry_id"] == entrada.id
    assert fila["entry_description"] == "Venta Juana Pérez"
    assert fila["business_date"] == "2026-08-18"
    assert fila["unit"] == "PC"
    assert fila["destination"] == "ASUNCION"
    assert fila["event_type"] == "SALE_COMPLETED"
    assert fila["saleswoman"] == "ana"


# --------------------------------------------------------------------------
# Sucursal
# --------------------------------------------------------------------------


def test_la_salida_ocurre_en_la_sucursal_de_la_caja(caja, armazon, ledger):
    _dar_stock(ledger, armazon, 5, destino=Destination.PILAR, clave="alta-pilar")
    _guardar(caja, _dia(unidad="P2", entradas=[
        _venta(_linea(armazon=armazon, precio_armazon=280_000))]))
    assert ledger.stock(armazon.id, Destination.PILAR) == 4
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 0


def test_la_operadora_no_elige_de_donde_sale_el_stock(caja, armazon, ledger):
    """El destino se deriva del vínculo caja → sucursal, que es administrativo.
    No hay forma de pedir que salga del otro local."""
    _dar_stock(ledger, armazon, 5, destino=Destination.ASUNCION)
    from modulos.comercial.application import ventas
    assert not hasattr(ventas.VentasLedgerIntegrator, "set_destination")
    firma = ventas.VentasLedgerIntegrator.integrar_en.__code__.co_varnames
    assert "destination" not in firma and "destino" not in firma


def test_una_caja_sin_sucursal_no_puede_vender_stock(ruta, integrador, armazon, ledger):
    """Inventarle una sucursal sacaría stock del local equivocado."""
    _dar_stock(ledger, armazon, 5)
    repo = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    try:
        with pytest.raises(SucursalNoResoluble):
            repo.save(_dia(unidad="CAJA-NUEVA", entradas=[
                _venta(_linea(armazon=armazon, precio_armazon=280_000))]))
    finally:
        repo.close()
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


def test_una_caja_sin_sucursal_si_puede_vender_servicios(ruta, integrador, compostura):
    """Sin efecto de inventario, la sucursal no hace falta para nada."""
    repo = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    try:
        repo.save(_dia(unidad="CAJA-NUEVA", entradas=[
            _venta(_linea(armazon=compostura, precio_armazon=30_000))]))
    finally:
        repo.close()


# --------------------------------------------------------------------------
# Stock insuficiente
# --------------------------------------------------------------------------


def test_una_venta_sin_stock_no_se_integra(caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 1)
    entrada = _venta(
        _linea(armazon=armazon, precio_armazon=280_000),
        _linea(armazon=armazon, precio_armazon=280_000, descripcion="segundo"))
    from modulos.comercial.application.stock_ledger import StockInsuficiente
    with pytest.raises(StockInsuficiente):
        _guardar(caja, _dia(entradas=[entrada]))

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 1
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_stock_integrations").fetchone()[0] == 0
    finally:
        conexion.close()


def test_se_puede_avisar_antes_de_llegar_a_guardar(caja, armazon, ledger, integrador):
    """Rechazar al guardar es correcto pero tardío. Esto deja preguntarlo antes,
    que es lo que la UI necesita para no sorprender a la operadora."""
    _dar_stock(ledger, armazon, 1)
    entrada = _venta(
        _linea(armazon=armazon, precio_armazon=280_000),
        _linea(armazon=armazon, precio_armazon=280_000, descripcion="segundo"))
    faltantes = integrador.faltantes_de_stock(entrada, unidad="PC")
    assert len(faltantes) == 1
    assert faltantes[0].article_id == armazon.id
    assert faltantes[0].disponible == 1
    assert faltantes[0].pedido == 2
    assert faltantes[0].destination is Destination.ASUNCION


def test_sin_faltantes_la_consulta_previa_no_dice_nada(caja, armazon, ledger, integrador):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000))
    assert integrador.faltantes_de_stock(entrada, unidad="PC") == ()


def test_una_venta_no_puede_pedir_la_excepcion_administrativa(integrador):
    """Las únicas excepciones de stock negativo siguen siendo las administrativas."""
    fuente = __import__("inspect").getsource(
        __import__("modulos.comercial.application.ventas", fromlist=["x"]))
    assert "negative_override" not in fuente


# --------------------------------------------------------------------------
# Atomicidad
# --------------------------------------------------------------------------


def test_si_falla_el_segundo_movimiento_no_queda_media_venta(
        caja, armazon, cadenilla, ledger, ruta, monkeypatch, integrador):
    _dar_stock(ledger, armazon, 5, clave="alta-arm")
    _dar_stock(ledger, cadenilla, 5, clave="alta-cad")
    entrada = _venta(
        _linea(armazon=armazon, precio_armazon=280_000),
        _linea(armazon=cadenilla, precio_armazon=70_000, descripcion="Cadenilla"))

    original = integrador._ledger.registrar_en
    llamadas = {"n": 0}

    def falla_en_el_segundo(*args, **kwargs):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise sqlite3.OperationalError("disco lleno a mitad de la venta")
        return original(*args, **kwargs)

    monkeypatch.setattr(integrador._ledger, "registrar_en", falla_en_el_segundo)

    with pytest.raises(sqlite3.OperationalError):
        _guardar(caja, _dia(entradas=[entrada]))

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    assert ledger.stock(cadenilla.id, Destination.ASUNCION) == 5
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM event_effects").fetchone()[0] == 0
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_stock_integrations").fetchone()[0] == 0
    finally:
        conexion.close()


def test_la_integracion_va_en_la_transaccion_de_la_venta(integrador):
    """Una segunda transacción independiente podría dejar la venta guardada y
    el stock no, o al revés. El enganche recibe la conexión, no la abre."""
    firma = VentasLedgerIntegrator.integrar_en.__code__.co_varnames
    assert "connection" in firma
    fuente = __import__("inspect").getsource(VentasLedgerIntegrator)
    assert "BEGIN" not in fuente
    assert "COMMIT" not in fuente


# --------------------------------------------------------------------------
# Idempotencia
# --------------------------------------------------------------------------


def test_guardar_dos_veces_no_descuenta_dos_veces(caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    _guardar(caja, dia)
    _guardar(caja, dia)
    _guardar(caja, dia)

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 1
        assert conexion.execute("SELECT COUNT(*) FROM event_effects").fetchone()[0] == 1
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE kind='VENTA'").fetchone()[0] == 1
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_stock_integrations").fetchone()[0] == 1
    finally:
        conexion.close()


def test_reabrir_desde_la_base_y_volver_a_guardar_tampoco_duplica(
        caja, armazon, ledger, ruta):
    """Es el caso real: se cierra la ventana, se reabre y se sigue trabajando."""
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    _guardar(caja, dia)

    recargado = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    recargado.add_entry(_venta(_linea(precio_armazon=50_000),
                               descripcion="Otra venta sin artículo"))
    caja.save(recargado)

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE kind='VENTA'").fetchone()[0] == 1
    finally:
        conexion.close()


def test_la_clave_de_idempotencia_es_durable_no_una_bandera_en_memoria(
        caja, armazon, ledger, ruta, integrador):
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    _guardar(caja, dia)

    # Un repositorio nuevo, sin nada en memoria, como después de un crash.
    otro = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    try:
        otro.save(otro.get_by_date_and_unit(dia.business_date, dia.unit))
    finally:
        otro.close()
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


# --------------------------------------------------------------------------
# Edición después de que la venta movió stock
# --------------------------------------------------------------------------


def test_no_se_puede_cambiar_una_linea_que_ya_movio_stock(caja, armazon, cadenilla, ledger):
    _dar_stock(ledger, armazon, 5, clave="alta-arm")
    _dar_stock(ledger, cadenilla, 5, clave="alta-cad")
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000))
    dia = _dia(entradas=[entrada])
    _guardar(caja, dia)

    recargado = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    from dataclasses import replace
    entrada_editada = replace(
        recargado.entries[0],
        items=(_linea(armazon=cadenilla, precio_armazon=70_000),))
    recargado.entries[0] = entrada_editada
    with pytest.raises(VentaIntegradaNoEditable):
        caja.save(recargado)
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4
    assert ledger.stock(cadenilla.id, Destination.ASUNCION) == 5


def test_los_campos_que_no_tocan_el_inventario_se_siguen_editando(
        caja, armazon, ledger):
    """El teléfono del cliente no cambia el stock. Congelar la venta entera
    sería castigar a la operadora por una corrección inocente."""
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    _guardar(caja, dia)

    recargado = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    from dataclasses import replace
    recargado.entries[0] = replace(
        recargado.entries[0], customer_phone="0981 111 222",
        observations="pasa a retirar el viernes")
    caja.save(recargado)

    releido = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    assert releido.entries[0].customer_phone == "0981 111 222"
    assert releido.entries[0].observations == "pasa a retirar el viernes"
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


def test_una_venta_integrada_se_anula_compensando(caja, armazon, ledger):
    """Este era el boundary del slice 4: anular estaba prohibido porque el
    circuito compensatorio no existía. La 027 lo construyó, así que ahora
    anular devuelve la mercadería en la misma transacción. Lo que sigue siendo
    imposible es que la unidad quede afuera sin nada que la explique — eso se
    verifica entero en `test_sale_void_compensation.py`."""
    _dar_stock(ledger, armazon, 5)
    dia = _dia(entradas=[_venta(_linea(armazon=armazon, precio_armazon=280_000))])
    _guardar(caja, dia)
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4

    recargado = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    recargado.void_entry(recargado.entries[0].id, "me equivoqué")
    caja.save(recargado, audit_reason="me equivoqué", edited_by="rodrigo")

    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    devuelto = [m for m in ledger.movimientos() if m.compensates_id]
    assert len(devuelto) == 1
    assert devuelto[0].note == "me equivoqué"


def test_la_base_impide_borrar_las_lineas_de_una_venta_integrada(
        caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000))
    _guardar(caja, _dia(entradas=[entrada]))

    conexion = sqlite3.connect(str(ruta))
    try:
        for sentencia in (
            "DELETE FROM sale_items",
            "UPDATE sale_items SET article_id = NULL",
            "DELETE FROM sale_stock_integrations",
            "UPDATE sale_stock_integrations SET event_id = 'otro'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conexion.execute(sentencia)
    finally:
        conexion.close()


def test_el_movimiento_de_venta_sigue_siendo_append_only(caja, armazon, ledger, ruta):
    """La protección del slice 2 vale igual para las salidas por venta."""
    _dar_stock(ledger, armazon, 5)
    _guardar(caja, _dia(entradas=[
        _venta(_linea(armazon=armazon, precio_armazon=280_000))]))
    conexion = sqlite3.connect(str(ruta))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM stock_movements WHERE kind='VENTA'")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE stock_movements SET quantity = -9")
    finally:
        conexion.close()


def test_el_integrador_no_expone_forma_de_revertir(integrador):
    for prohibido in ("revertir", "anular", "desintegrar", "eliminar", "borrar"):
        assert not hasattr(integrador, prohibido)


# --------------------------------------------------------------------------
# Histórico
# --------------------------------------------------------------------------


def test_no_se_backfillea_lo_viejo(caja, ruta, ledger):
    """Las líneas históricas no dicen qué artículo se vendió. Elegir uno sería
    inventarlo, y encima cambiaría el stock de hoy."""
    conexion = sqlite3.connect(str(ruta))
    try:
        conexion.execute(
            "INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at,"
            " version) VALUES('d-viejo','2026-01-10','PC',0,'OPEN','2026-01-10',0)")
        conexion.execute(
            "INSERT INTO cash_entries(id,cash_day_id,description,total,created_at,"
            " updated_at) VALUES('e-viejo','d-viejo','Armazon/org uvx',530000,"
            " '2026-01-10','2026-01-10')")
        conexion.execute(
            "INSERT INTO sale_items(id,cash_entry_id,position,description,code,"
            " item_type,frame_price,lens_price) VALUES('i-viejo','e-viejo',0,"
            " 'Armazon/org uvx','104256','Armazon/org uvx',280000,250000)")
        conexion.commit()
    finally:
        conexion.close()

    from modulos.comercial.application.ventas import planificar_backfill_de_ventas
    plan = planificar_backfill_de_ventas(ruta)
    assert plan.aplicable is False
    assert plan.movimientos_a_crear == 0
    assert plan.lineas_sin_articulo == 1
    assert "no atribuible" in plan.motivo.lower()
    assert ledger.movimientos() == []


def test_una_linea_historica_sin_articulo_se_sigue_leyendo(caja, ruta):
    conexion = sqlite3.connect(str(ruta))
    try:
        conexion.execute(
            "INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at,"
            " version) VALUES('d-v2','2026-01-11','PC',0,'OPEN','2026-01-11',0)")
        conexion.execute(
            "INSERT INTO cash_entries(id,cash_day_id,description,total,created_at,"
            " updated_at) VALUES('e-v2','d-v2','armazones',300000,'2026-01-11','2026-01-11')")
        conexion.execute(
            "INSERT INTO sale_items(id,cash_entry_id,position,description,code,"
            " item_type,frame_price) VALUES('i-v2','e-v2',0,'armazones','222555',"
            " 'armazones',300000)")
        conexion.commit()
    finally:
        conexion.close()
    dia = caja.get_by_date_and_unit(date(2026, 1, 11), "PC")
    assert dia.entries[0].items[0].description == "armazones"
    assert dia.entries[0].items[0].article_id is None


# --------------------------------------------------------------------------
# Dinero
# --------------------------------------------------------------------------


def test_la_salida_de_stock_no_toca_los_totales_de_caja(caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, precio_armazon=280_000), total=280_000)
    dia = _dia(entradas=[entrada])
    _guardar(caja, dia)

    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute(
            "SELECT SUM(total) FROM cash_entries").fetchone()[0] == 280_000
        assert conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 1
        assert conexion.execute("SELECT COUNT(*) FROM cash_counts").fetchone()[0] == 0
    finally:
        conexion.close()
    releido = caja.get_by_date_and_unit(dia.business_date, dia.unit)
    assert releido.totals().total == 280_000


def test_el_movimiento_de_venta_no_es_un_segundo_movimiento_de_dinero(
        caja, armazon, ledger):
    _dar_stock(ledger, armazon, 5)
    _guardar(caja, _dia(entradas=[
        _venta(_linea(armazon=armazon, precio_armazon=280_000), total=280_000)]))
    venta = [m for m in ledger.movimientos() if m.kind is StockMovementKind.VENTA][0]
    for atributo in dir(venta):
        assert "price" not in atributo and "total" not in atributo
    fuente = __import__("inspect").getsource(
        __import__("modulos.comercial.application.ventas", fromlist=["x"]))
    for tabla in ("cash_entries", "cash_days", "cash_counts"):
        assert f"INSERT INTO {tabla}" not in fuente
        assert f"UPDATE {tabla}" not in fuente


# --------------------------------------------------------------------------
# Preparado para lo que viene, sin hacerlo todavía
# --------------------------------------------------------------------------


def test_el_hecho_queda_disponible_para_derivar_mas_consecuencias(
        caja, armazon, cristal, ledger, ruta):
    """FactuFácil, Trabajos y Gestión Central van a colgar del mismo hecho. Su
    payload ya lleva lo que necesitan; este slice no deriva ninguna."""
    _dar_stock(ledger, armazon, 5)
    entrada = _venta(_linea(armazon=armazon, cristal=cristal,
                            precio_armazon=280_000, precio_cristal=250_000))
    _guardar(caja, _dia(entradas=[entrada]))

    repo = SQLiteStockLedgerRepository(ruta)
    try:
        evento = repo.evento_por_clave(f"VENTA:{entrada.id}")
        import json
        payload = json.loads(evento.payload_json)
        assert payload["cash_day_id"]
        assert payload["business_date"] == "2026-08-18"
        assert payload["unit"] == "PC"
        assert payload["total"] == entrada.total
        assert len(payload["lines"]) == 1
        linea = payload["lines"][0]
        assert linea["article_id"] == armazon.id
        assert linea["lens_article_id"] == cristal.id
        assert linea["tracks_stock"] is True
        assert repo.efectos_de(evento.event_id)[0].effect_kind == "STOCK_MOVEMENT"
    finally:
        repo.close()


def test_este_slice_no_deriva_factufacil_ni_pedidos(caja, armazon, ledger, ruta):
    _dar_stock(ledger, armazon, 5)
    _guardar(caja, _dia(entradas=[
        _venta(_linea(armazon=armazon, precio_armazon=280_000))]))
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
        efectos = {f[0] for f in conexion.execute(
            "SELECT DISTINCT effect_kind FROM event_effects")}
    finally:
        conexion.close()
    assert efectos == {"STOCK_MOVEMENT"}


# --------------------------------------------------------------------------
# Migración
# --------------------------------------------------------------------------


def test_la_cadena_de_migraciones_incluye_la_025_completa(ruta, caja):
    from tests.migration_chain import afirmar_cadena_completa_con
    conexion = sqlite3.connect(str(ruta))
    try:
        afirmar_cadena_completa_con(conexion, "025")
    finally:
        conexion.close()


def test_la_025_es_aditiva():
    from tests.migration_chain import MIGRATIONS_DIR
    sql = (MIGRATIONS_DIR / "025_sales_article_link.sql").read_text(
        encoding="utf-8").upper()
    for prohibido in ("DROP ", "DELETE FROM"):
        assert prohibido not in sql, f"la migración no puede contener {prohibido}"
    for linea in sql.splitlines():
        if "ALTER TABLE" in linea:
            assert "ADD COLUMN" in linea and "SALE_ITEMS" in linea, linea
        if "UPDATE " in linea:
            assert "BEFORE UPDATE ON" in linea, linea
