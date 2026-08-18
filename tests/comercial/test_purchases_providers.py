"""Proveedores y Compras, slice 3.

Pruebas dirigidas escritas antes de la implementación.

La idea que las ordena a todas: **una factura real se registra una sola vez** y
todo lo demás se deriva. El stock que aparece después de confirmar una compra no
se carga: es la consecuencia de un hecho que quedó registrado, y se puede ir
desde cualquier unidad en el depósito hasta la factura, la línea, el proveedor y
la persona que confirmó.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.compras import (
    CompraNoEditable,
    ComprasService,
    DistribucionInvalida,
    TotalNoCuadra,
)
from modulos.comercial.application.stock_ledger import StockLedgerService
from modulos.comercial.domain.compras import (
    Distribution,
    Purchase,
    PurchaseCondition,
    PurchaseLine,
    PurchaseStatus,
)
from modulos.comercial.domain.eventos import EventProcessingState
from modulos.comercial.domain.models import (
    Article,
    ArticleNature,
    Destination,
    StockMovementKind,
    Supplier,
)
from modulos.comercial.infrastructure.sqlite_catalog_repository import (
    SQLiteCatalogRepository,
)
from modulos.comercial.infrastructure.sqlite_purchase_repository import (
    SQLitePurchaseRepository,
)
from modulos.comercial.infrastructure.sqlite_stock_ledger import (
    SQLiteStockLedgerRepository,
)


@pytest.fixture()
def base(tmp_path):
    ruta = tmp_path / "bc_caja.sqlite3"
    SQLiteCashDayRepository(ruta)  # aplica la cadena 001..024
    return ruta


@pytest.fixture()
def catalogo(base):
    repo = SQLiteCatalogRepository(base)
    yield repo
    repo.close()


@pytest.fixture()
def ledger_repo(base):
    repo = SQLiteStockLedgerRepository(base)
    yield repo
    repo.close()


@pytest.fixture()
def ledger(ledger_repo, catalogo):
    return StockLedgerService(ledger_repo, catalogo)


@pytest.fixture()
def compras(base, catalogo, ledger_repo):
    repo = SQLitePurchaseRepository(base)
    yield ComprasService(repo, catalogo, ledger_repo)
    repo.close()


@pytest.fixture()
def proveedor(compras):
    return compras.guardar_proveedor(Supplier(
        name="Distribuidora Sur S.A.", document="80012345-6", phone="021 555 000"))


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
def compostura(catalogo):
    return catalogo.save_article(Article(
        sku="SERV-COMP", name="Compostura", nature=ArticleNature.SERVICIO_NO_STOCKEABLE))


def _linea(articulo, cantidad, costo, *, numero=1, distribucion=()):
    return PurchaseLine(
        article_id=articulo.id, line_number=numero, quantity=cantidad,
        unit_cost=costo, description=articulo.name,
        distributions=tuple(Distribution(destination=d, quantity=q)
                            for d, q in distribucion))


def _compra(proveedor, lineas, *, numero="001-001-0000123",
            condicion=PurchaseCondition.CONTADO, dias=None,
            fecha=date(2026, 8, 18), total=None):
    lineas = tuple(lineas)
    return Purchase(
        supplier_id=proveedor.id, document_date=fecha, document_number=numero,
        stamped_number="12345678", condition=condicion, credit_days=dias,
        document_total=sum(l.quantity * l.unit_cost for l in lineas)
        if total is None else total,
        lines=lineas, created_by="rodrigo")


# --------------------------------------------------------------------------
# Proveedores
# --------------------------------------------------------------------------


def test_un_proveedor_se_guarda_y_se_recupera(compras):
    guardado = compras.guardar_proveedor(Supplier(
        name="Óptica Mayorista", document="80099999-1", phone="021 111 222"))
    recuperado = compras.obtener_proveedor(guardado.id)
    assert recuperado.name == "Óptica Mayorista"
    assert recuperado.document == "80099999-1"
    assert recuperado.active is True


def test_dos_proveedores_no_pueden_compartir_el_ruc(compras):
    """Cuando hay identidad fiscal fiable, el duplicado se bloquea."""
    compras.guardar_proveedor(Supplier(name="Distribuidora A", document="80012345-6"))
    with pytest.raises(sqlite3.IntegrityError):
        compras.guardar_proveedor(Supplier(name="Distribuidora B", document="80012345-6"))


def test_varios_proveedores_pueden_no_tener_ruc(compras):
    """Sin identidad fiscal no hay duplicado que detectar: no se inventa uno."""
    compras.guardar_proveedor(Supplier(name="Vendedor ambulante 1", document=""))
    compras.guardar_proveedor(Supplier(name="Vendedor ambulante 2", document=""))
    assert len(compras.listar_proveedores()) == 2


def test_el_proveedor_guarda_contacto_sin_volverse_un_crm(compras):
    guardado = compras.guardar_proveedor(Supplier(
        name="Distribuidora Norte", document="80055555-0", phone="021 333 444",
        address="Av. España 1234", email="ventas@norte.com.py",
        contact_name="Marta Giménez"))
    recuperado = compras.obtener_proveedor(guardado.id)
    assert recuperado.address == "Av. España 1234"
    assert recuperado.email == "ventas@norte.com.py"
    assert recuperado.contact_name == "Marta Giménez"


def test_un_proveedor_se_desactiva_no_se_borra(compras, proveedor):
    compras.guardar_proveedor(Supplier(
        name=proveedor.name, document=proveedor.document, active=False,
        id=proveedor.id))
    assert compras.obtener_proveedor(proveedor.id).active is False
    assert not hasattr(compras, "borrar_proveedor")


# --------------------------------------------------------------------------
# La factura
# --------------------------------------------------------------------------


def test_una_compra_contado_no_tiene_vencimiento(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])]))
    assert compra.condition is PurchaseCondition.CONTADO
    assert compra.credit_days is None
    assert compra.due_date is None


def test_una_compra_a_credito_deriva_el_vencimiento(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(
        proveedor,
        [_linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])],
        condicion=PurchaseCondition.CREDITO, dias=30, fecha=date(2026, 8, 18)))
    assert compra.due_date == date(2026, 9, 17)


def test_el_vencimiento_no_se_carga_a_mano(proveedor, armazon):
    """Es derivado. Si se pudiera escribir, podría contradecir al plazo."""
    with pytest.raises(TypeError):
        Purchase(supplier_id=proveedor.id, document_date=date(2026, 8, 18),
                 document_number="X", condition=PurchaseCondition.CREDITO,
                 credit_days=30, due_date=date(2030, 1, 1), document_total=0,
                 lines=(), created_by="rodrigo")


def test_credito_sin_plazo_se_rechaza(proveedor, armazon):
    with pytest.raises(ValueError):
        _compra(proveedor, [_linea(armazon, 1, 100)],
                condicion=PurchaseCondition.CREDITO, dias=None)


def test_contado_con_plazo_se_rechaza(proveedor, armazon):
    with pytest.raises(ValueError):
        _compra(proveedor, [_linea(armazon, 1, 100)],
                condicion=PurchaseCondition.CONTADO, dias=30)


def test_la_misma_factura_del_mismo_proveedor_no_se_carga_dos_veces(
        compras, proveedor, armazon):
    """Una factura real existe una sola vez. Cargarla de nuevo por sucursal
    sería justamente el sistema paralelo que se quiere evitar."""
    linea = [_linea(armazon, 5, 10_000, distribucion=[(Destination.ASUNCION, 5)])]
    compras.guardar_borrador(_compra(proveedor, linea, numero="001-001-0000999"))
    with pytest.raises(sqlite3.IntegrityError):
        compras.guardar_borrador(_compra(proveedor, linea, numero="001-001-0000999"))


def test_el_total_del_documento_es_el_del_papel_y_se_contrasta(
        compras, proveedor, armazon):
    """El total de la factura es un dato con origen; la suma de las líneas es
    derivada. Que no coincidan es un hecho a mostrar, no a corregir solo."""
    compra = compras.guardar_borrador(_compra(
        proveedor,
        [_linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])],
        total=999_999))
    with pytest.raises(TotalNoCuadra):
        compras.confirmar(compra.id, actor="rodrigo")


# --------------------------------------------------------------------------
# Líneas
# --------------------------------------------------------------------------


def test_una_linea_referencia_el_articulo_canonico(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])]))
    guardada = compras.obtener(compra.id)
    assert guardada.lines[0].article_id == armazon.id
    assert guardada.lines[0].quantity == 10
    assert guardada.lines[0].unit_cost == 50_000
    assert guardada.lines[0].line_total == 500_000


def test_una_linea_no_stock_pertenece_legitimamente_a_la_factura(
        compras, proveedor, cristal):
    """El laboratorio factura cristales. La línea existe y conserva su costo."""
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(cristal, 4, 120_000)]))
    guardada = compras.obtener(compra.id)
    assert guardada.lines[0].article_id == cristal.id
    assert guardada.lines[0].line_total == 480_000
    assert guardada.lines[0].distributions == ()


def test_una_linea_de_servicio_tampoco_se_distribuye(compras, proveedor, compostura):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(compostura, 1, 30_000)]))
    assert compras.obtener(compra.id).lines[0].distributions == ()


def test_cantidad_o_costo_invalidos_se_rechazan(armazon):
    with pytest.raises(ValueError):
        _linea(armazon, 0, 100)
    with pytest.raises(ValueError):
        _linea(armazon, -1, 100)
    with pytest.raises(ValueError):
        _linea(armazon, 1, -100)


# --------------------------------------------------------------------------
# Distribución física
# --------------------------------------------------------------------------


def test_una_linea_se_reparte_entre_asuncion_y_pilar(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 4)])]))
    reparto = {d.destination: d.quantity for d in compras.obtener(compra.id).lines[0].distributions}
    assert reparto == {Destination.ASUNCION: 6, Destination.PILAR: 4}


def test_la_distribucion_tiene_que_sumar_lo_comprado(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 3)])]))
    with pytest.raises(DistribucionInvalida):
        compras.confirmar(compra.id, actor="rodrigo")


def test_no_se_puede_distribuir_mas_de_lo_comprado(compras, proveedor, armazon):
    with pytest.raises((DistribucionInvalida, sqlite3.IntegrityError)):
        compras.guardar_borrador(_compra(proveedor, [
            _linea(armazon, 10, 50_000,
                   distribucion=[(Destination.ASUNCION, 8), (Destination.PILAR, 5)])]))


def test_una_cantidad_distribuida_no_puede_ser_cero_ni_negativa(armazon):
    for cantidad in (0, -3):
        with pytest.raises(ValueError):
            Distribution(destination=Destination.ASUNCION, quantity=cantidad)


def test_un_destino_no_se_repite_en_la_misma_linea(armazon):
    with pytest.raises(ValueError):
        _linea(armazon, 10, 100,
               distribucion=[(Destination.ASUNCION, 6), (Destination.ASUNCION, 4)])


def test_una_linea_no_stock_no_admite_distribucion(compras, proveedor, cristal):
    """Un cristal no genera unidades: repartirlo no significa nada."""
    with pytest.raises((DistribucionInvalida, sqlite3.IntegrityError)):
        compras.guardar_borrador(_compra(proveedor, [
            _linea(cristal, 4, 120_000, distribucion=[(Destination.ASUNCION, 4)])]))


def test_una_linea_stock_sin_distribucion_no_se_confirma(compras, proveedor, armazon):
    """No se inventa un destino cuando la factura no lo determina: se pide."""
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000)]))
    with pytest.raises(DistribucionInvalida):
        compras.confirmar(compra.id, actor="rodrigo")


def test_la_base_rechaza_distribuir_un_no_stockeable_aunque_se_escriba_directo(
        base, compras, proveedor, cristal):
    compra = compras.guardar_borrador(_compra(proveedor, [_linea(cristal, 4, 120_000)]))
    linea_id = compras.obtener(compra.id).lines[0].id
    conexion = sqlite3.connect(str(base))
    conexion.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO purchase_line_distributions(id, purchase_line_id,"
                " destination, quantity, created_at)"
                " VALUES('d1', ?, 'ASUNCION', 4, '2026-08-18')", (linea_id,))
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Confirmación: el hecho y sus consecuencias
# --------------------------------------------------------------------------


def test_confirmar_emite_un_purchase_confirmed(compras, proveedor, armazon, ledger):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 4)])]))
    resultado = compras.confirmar(compra.id, actor="rodrigo")
    evento = ledger.evento(resultado.evento.event_id)
    assert evento.event_type == "PURCHASE_CONFIRMED"
    assert evento.source == "COMPRAS"
    assert evento.entity_type == "PURCHASE"
    assert evento.entity_id == compra.id
    assert evento.actor == "rodrigo"
    assert evento.processing_state is EventProcessingState.PROCESADO


def test_confirmar_genera_un_ingreso_por_linea_y_destino(compras, proveedor, armazon, ledger):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 4)])]))
    compras.confirmar(compra.id, actor="rodrigo")
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 6
    assert ledger.stock(armazon.id, Destination.PILAR) == 4
    movimientos = ledger.movimientos(article_id=armazon.id)
    assert len(movimientos) == 2
    assert {m.kind for m in movimientos} == {StockMovementKind.INGRESO_COMPRA}


def test_una_linea_no_stock_no_genera_movimiento(compras, proveedor, cristal, ledger):
    compra = compras.guardar_borrador(_compra(proveedor, [_linea(cristal, 4, 120_000)]))
    compras.confirmar(compra.id, actor="rodrigo")
    assert ledger.movimientos(article_id=cristal.id) == []


def test_una_factura_mixta_solo_mueve_lo_que_mueve(
        compras, proveedor, armazon, cristal, ledger):
    """La misma factura trae armazones y cristales. Es una sola factura."""
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000, numero=1,
               distribucion=[(Destination.ASUNCION, 10)]),
        _linea(cristal, 4, 120_000, numero=2)]))
    compras.confirmar(compra.id, actor="rodrigo")
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 10
    assert ledger.movimientos(article_id=cristal.id) == []
    assert len(ledger.movimientos()) == 1


def test_los_movimientos_quedan_enlazados_al_evento(compras, proveedor, armazon, ledger):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 4)])]))
    resultado = compras.confirmar(compra.id, actor="rodrigo")
    efectos = ledger.efectos_de(resultado.evento.event_id)
    assert len(efectos) == 2
    assert {e.effect_kind for e in efectos} == {"STOCK_MOVEMENT"}
    for movimiento in ledger.movimientos(article_id=armazon.id):
        assert movimiento.event_id == resultado.evento.event_id


def test_la_compra_confirmada_apunta_a_su_evento(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 3, 10_000, distribucion=[(Destination.ASUNCION, 3)])]))
    resultado = compras.confirmar(compra.id, actor="rodrigo")
    guardada = compras.obtener(compra.id)
    assert guardada.status is PurchaseStatus.CONFIRMADA
    assert guardada.event_id == resultado.evento.event_id
    assert guardada.confirmed_by == "rodrigo"
    assert guardada.confirmed_at is not None


# --------------------------------------------------------------------------
# Trazabilidad mecánica
# --------------------------------------------------------------------------


def test_se_puede_ir_de_una_unidad_en_stock_hasta_la_factura(
        compras, proveedor, armazon, ledger):
    compra = compras.guardar_borrador(_compra(
        proveedor,
        [_linea(armazon, 10, 50_000, distribucion=[(Destination.PILAR, 10)])],
        numero="001-001-0000777"))
    compras.confirmar(compra.id, actor="rodrigo")
    movimiento = ledger.movimientos(article_id=armazon.id)[0]

    origen = compras.trazabilidad(movimiento.id)
    assert origen.document_number == "001-001-0000777"
    assert origen.supplier_name == "Distribuidora Sur S.A."
    assert origen.supplier_document == "80012345-6"
    assert origen.purchase_id == compra.id
    assert origen.purchase_line_id == compras.obtener(compra.id).lines[0].id
    assert origen.destination is Destination.PILAR
    assert origen.event_id == compras.obtener(compra.id).event_id
    assert origen.event_type == "PURCHASE_CONFIRMED"
    assert origen.confirmed_by == "rodrigo"
    assert origen.confirmed_at is not None
    assert origen.quantity == 10


def test_el_movimiento_guarda_la_referencia_durable_del_documento(
        compras, proveedor, armazon, ledger):
    compra = compras.guardar_borrador(_compra(
        proveedor,
        [_linea(armazon, 2, 5_000, distribucion=[(Destination.ASUNCION, 2)])],
        numero="001-001-0000555"))
    compras.confirmar(compra.id, actor="rodrigo")
    movimiento = ledger.movimientos(article_id=armazon.id)[0]
    assert movimiento.supplier_id == proveedor.id
    assert movimiento.document_kind == "COMPRA"
    assert movimiento.document_id == compra.id
    assert movimiento.document_number == "001-001-0000555"
    assert movimiento.document_line_id == compras.obtener(compra.id).lines[0].id


# --------------------------------------------------------------------------
# Idempotencia y atomicidad
# --------------------------------------------------------------------------


def test_confirmar_dos_veces_no_duplica_nada(compras, proveedor, armazon, ledger, base):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 4)])]))
    primero = compras.confirmar(compra.id, actor="rodrigo")
    segundo = compras.confirmar(compra.id, actor="rodrigo")

    assert segundo.evento.event_id == primero.evento.event_id
    assert {m.id for m in segundo.movimientos} == {m.id for m in primero.movimientos}
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 6
    assert ledger.stock(armazon.id, Destination.PILAR) == 4

    conexion = sqlite3.connect(str(base))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 1
        assert conexion.execute("SELECT COUNT(*) FROM event_effects").fetchone()[0] == 2
        assert conexion.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 2
    finally:
        conexion.close()


def test_si_falla_a_mitad_no_queda_nada_a_medias(
        compras, proveedor, armazon, ledger, base, monkeypatch):
    """Confirmar es todo o nada: media factura confirmada sería peor que
    ninguna, porque el stock parcial se ve igual que el stock correcto."""
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000,
               distribucion=[(Destination.ASUNCION, 6), (Destination.PILAR, 4)])]))

    original = compras._ledger.registrar_en
    llamadas = {"n": 0}

    def falla_en_el_segundo(*args, **kwargs):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise sqlite3.OperationalError("disco lleno a mitad de la confirmación")
        return original(*args, **kwargs)

    monkeypatch.setattr(compras._ledger, "registrar_en", falla_en_el_segundo)

    with pytest.raises(sqlite3.OperationalError):
        compras.confirmar(compra.id, actor="rodrigo")

    assert compras.obtener(compra.id).status is PurchaseStatus.BORRADOR
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 0
    conexion = sqlite3.connect(str(base))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM event_effects").fetchone()[0] == 0
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Después de confirmar, la historia no se reescribe
# --------------------------------------------------------------------------


def test_una_compra_confirmada_no_se_edita(compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])]))
    compras.confirmar(compra.id, actor="rodrigo")
    with pytest.raises(CompraNoEditable):
        compras.guardar_borrador(_compra(
            proveedor,
            [_linea(armazon, 99, 1, distribucion=[(Destination.ASUNCION, 99)])],
            numero="001-001-0000123"))


def test_la_base_impide_reescribir_una_compra_confirmada(
        base, compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])]))
    compras.confirmar(compra.id, actor="rodrigo")
    conexion = sqlite3.connect(str(base))
    try:
        for sentencia in (
            "UPDATE purchases SET document_total = 1",
            "DELETE FROM purchases",
            "UPDATE purchase_lines SET quantity = 99",
            "DELETE FROM purchase_lines",
            "DELETE FROM purchase_line_distributions",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conexion.execute(sentencia)
    finally:
        conexion.close()


def test_no_se_agregan_lineas_a_una_compra_confirmada(base, compras, proveedor, armazon):
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 1, 1_000, distribucion=[(Destination.ASUNCION, 1)])]))
    compras.confirmar(compra.id, actor="rodrigo")
    conexion = sqlite3.connect(str(base))
    conexion.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO purchase_lines(id, purchase_id, line_number, article_id,"
                " description, quantity, unit_cost, created_at, updated_at)"
                " VALUES('l-nueva', ?, 9, ?, '', 1, 1, '2026-08-18', '2026-08-18')",
                (compra.id, armazon.id))
    finally:
        conexion.close()


def test_el_servicio_no_expone_forma_de_anular_ni_borrar(compras):
    """Notas de crédito y devoluciones exceden el slice. En vez de improvisar
    media anulación, la mutación destructiva queda bloqueada."""
    for prohibido in ("anular", "eliminar", "borrar", "revertir"):
        assert not hasattr(compras, prohibido)


def test_la_factura_original_sobrevive_a_una_salida_de_stock(
        compras, proveedor, armazon, ledger):
    """Sacar una unidad rota no borra la compra: se registra la salida."""
    from modulos.comercial.domain.models import StockMovement
    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 5, 10_000, distribucion=[(Destination.ASUNCION, 5)])]))
    compras.confirmar(compra.id, actor="rodrigo")
    ledger.registrar(StockMovement(
        article_id=armazon.id, destination=Destination.ASUNCION,
        kind=StockMovementKind.SALIDA_ADMINISTRATIVA, quantity=1,
        actor="rodrigo", idempotency_key="roto-1", reason_code="ROTO"))
    assert compras.obtener(compra.id).status is PurchaseStatus.CONFIRMADA
    assert compras.obtener(compra.id).lines[0].quantity == 5
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 4


# --------------------------------------------------------------------------
# Dinero y stock son dimensiones separadas
# --------------------------------------------------------------------------


def test_registrar_y_confirmar_una_compra_no_toca_caja(
        base, compras, proveedor, armazon):
    conexion = sqlite3.connect(str(base))
    tablas_de_caja = ("cash_days", "cash_entries", "cash_counts",
                      "cash_day_corrections")
    antes = {t: conexion.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in tablas_de_caja}
    conexion.close()

    compra = compras.guardar_borrador(_compra(proveedor, [
        _linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])]))
    compras.confirmar(compra.id, actor="rodrigo")

    conexion = sqlite3.connect(str(base))
    try:
        despues = {t: conexion.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                   for t in tablas_de_caja}
    finally:
        conexion.close()
    assert antes == despues


def test_una_compra_a_credito_no_genera_un_egreso_de_caja(
        base, compras, proveedor, armazon):
    """La factura a crédito es una obligación, no una salida de dinero de hoy.
    Cuentas por Pagar excede este slice y no se improvisa."""
    compra = compras.guardar_borrador(_compra(
        proveedor,
        [_linea(armazon, 10, 50_000, distribucion=[(Destination.ASUNCION, 10)])],
        condicion=PurchaseCondition.CREDITO, dias=30))
    compras.confirmar(compra.id, actor="rodrigo")
    conexion = sqlite3.connect(str(base))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM cash_days").fetchone()[0] == 0
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Migración
# --------------------------------------------------------------------------


def test_la_cadena_de_migraciones_incluye_la_024_completa(base):
    from tests.migration_chain import afirmar_cadena_completa_con

    conexion = sqlite3.connect(str(base))
    try:
        afirmar_cadena_completa_con(conexion, "024")
    finally:
        conexion.close()


def test_la_024_no_reescribe_nada_de_lo_que_ya_estaba():
    from tests.migration_chain import MIGRATIONS_DIR
    sql = (MIGRATIONS_DIR / "024_purchases_providers.sql").read_text(
        encoding="utf-8").upper()
    for prohibido in ("DROP ", "DELETE FROM"):
        assert prohibido not in sql, f"la migración no puede contener {prohibido}"
    for linea in sql.splitlines():
        # Lo único que toca de lo existente es agregar columnas a suppliers.
        if "ALTER TABLE" in linea:
            assert "ADD COLUMN" in linea and "SUPPLIERS" in linea, linea
        # Y el único UPDATE que aparece es el de los triggers que lo prohíben.
        if "UPDATE " in linea:
            assert "BEFORE UPDATE ON" in linea, linea
