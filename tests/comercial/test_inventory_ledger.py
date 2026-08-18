"""Ledger canónico y auditable de inventario, slice 2.

Pruebas dirigidas escritas antes de la implementación.

Lo que fijan es una sola idea: el stock no es un número que alguien edita, es
la suma de movimientos que ocurrieron. Todo lo demás —que una compra vieja no
se toque para sacar una unidad rota, que un cristal no genere unidades, que un
evento repetido no descuente dos veces— sale de ahí.
"""

from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.backfill import planificar_backfill_historico
from modulos.comercial.application.stock_ledger import (
    ArticuloNoStockeable,
    MotivoRequerido,
    StockInsuficiente,
    StockLedgerService,
)
from modulos.comercial.domain.eventos import DomainEvent, EventProcessingState
from modulos.comercial.domain.models import (
    _NATURALEZAS_QUE_MUEVEN_STOCK,
    Article,
    ArticleNature,
    Destination,
    StockMovement,
    StockMovementKind,
    Supplier,
)
from modulos.comercial.infrastructure.sqlite_catalog_repository import (
    SQLiteCatalogRepository,
)
from modulos.comercial.infrastructure.sqlite_stock_ledger import (
    SQLiteStockLedgerRepository,
)


@pytest.fixture()
def base(tmp_path):
    ruta = tmp_path / "bc_caja.sqlite3"
    SQLiteCashDayRepository(ruta)  # aplica la cadena 001..023
    return ruta


@pytest.fixture()
def catalogo(base):
    repo = SQLiteCatalogRepository(base)
    yield repo
    repo.close()


@pytest.fixture()
def ledger(base, catalogo):
    repo = SQLiteStockLedgerRepository(base)
    yield StockLedgerService(repo, catalogo)
    repo.close()


@pytest.fixture()
def armazon(catalogo):
    return catalogo.save_article(Article(
        sku="ARM-001", name="Armazón metal", nature=ArticleNature.PRODUCTO_STOCKEABLE))


@pytest.fixture()
def limpia_cristales(catalogo):
    return catalogo.save_article(Article(
        sku="PROD-LIMP", name="Limpia cristales", nature=ArticleNature.PRODUCCION_INTERNA))


@pytest.fixture()
def compostura(catalogo):
    return catalogo.save_article(Article(
        sku="SERV-COMP", name="Compostura", nature=ArticleNature.SERVICIO_NO_STOCKEABLE))


@pytest.fixture()
def cristal(catalogo):
    return catalogo.save_article(Article(
        sku="CRIS-ORG", name="Cristal orgánico recetado",
        nature=ArticleNature.TRABAJO_BAJO_PEDIDO))


def _entrada(articulo, cantidad, clave, *, kind=StockMovementKind.INGRESO_COMPRA,
             destino=Destination.ASUNCION, **extra):
    return StockMovement(
        article_id=articulo.id, destination=destino, kind=kind, quantity=cantidad,
        actor="rodrigo", idempotency_key=clave, **extra)


def _sql_de(base, nombre, tipo="table") -> str:
    conexion = sqlite3.connect(str(base))
    try:
        fila = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE type=? AND name=?", (tipo, nombre)
        ).fetchone()
    finally:
        conexion.close()
    assert fila is not None, f"falta el {tipo} {nombre}"
    return fila[0]


# --------------------------------------------------------------------------
# El vocabulario del ledger
# --------------------------------------------------------------------------


def test_los_tipos_de_movimiento_cubren_entradas_y_salidas_pedidas():
    assert {k.value for k in StockMovementKind} == {
        "INGRESO_COMPRA",
        "INGRESO_PRODUCCION",
        "INGRESO_ADMINISTRATIVO",
        "AJUSTE_POSITIVO",
        "TRANSFERENCIA_ENTRADA",
        "VENTA",
        "SALIDA_ADMINISTRATIVA",
        "DEVOLUCION_PROVEEDOR",
        "AJUSTE_NEGATIVO",
        "TRANSFERENCIA_SALIDA",
    }


def test_el_signo_lo_decide_el_tipo_y_no_una_columna_aparte():
    """Guardar el signo al lado del tipo permitiría una venta que suma."""
    assert StockMovementKind.INGRESO_COMPRA.signo == 1
    assert StockMovementKind.VENTA.signo == -1
    assert all(kind.signo in (1, -1) for kind in StockMovementKind)


def test_la_transferencia_tiene_dos_patas_declaradas():
    """Un único TRANSFERENCIA no podía expresar de qué lado está el destino."""
    assert StockMovementKind.TRANSFERENCIA_SALIDA.signo == -1
    assert StockMovementKind.TRANSFERENCIA_ENTRADA.signo == 1


def test_el_check_de_la_base_conoce_los_mismos_tipos_que_el_dominio(base):
    sql = _sql_de(base, "stock_movements")
    for kind in StockMovementKind:
        assert f"'{kind.value}'" in sql


def test_la_base_deriva_stock_de_la_misma_naturaleza_que_el_dominio(base):
    """El trigger no puede tener su propia idea de qué mueve stock."""
    sql = _sql_de(base, "stock_movements_solo_articulos_stockeables", tipo="trigger")
    for naturaleza in _NATURALEZAS_QUE_MUEVEN_STOCK:
        assert f"'{naturaleza.value}'" in sql
    for naturaleza in set(ArticleNature) - _NATURALEZAS_QUE_MUEVEN_STOCK:
        assert f"'{naturaleza.value}'" not in sql


# --------------------------------------------------------------------------
# Entradas
# --------------------------------------------------------------------------


def test_una_compra_ingresa_stock(ledger, armazon):
    ledger.registrar(_entrada(armazon, 5, "compra-1"))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


def test_la_produccion_interna_ingresa_sin_proveedor_ni_factura(ledger, limpia_cristales):
    movimiento = ledger.registrar(_entrada(
        limpia_cristales, 12, "prod-1", kind=StockMovementKind.INGRESO_PRODUCCION,
        note="lote 2026-08"))
    assert movimiento.supplier_id is None
    assert movimiento.document_id is None
    assert ledger.stock(limpia_cristales.id, Destination.ASUNCION) == 12


def test_produccion_interna_solo_para_articulos_de_produccion_interna(ledger, armazon):
    """Un armazón no se produce adentro: entraría por compra."""
    with pytest.raises(ValueError):
        ledger.registrar(_entrada(
            armazon, 1, "prod-mal", kind=StockMovementKind.INGRESO_PRODUCCION))


def test_ingreso_administrativo_exige_motivo_y_observacion(ledger, armazon):
    with pytest.raises(MotivoRequerido):
        ledger.registrar(_entrada(
            armazon, 1, "adm-sin-motivo", kind=StockMovementKind.INGRESO_ADMINISTRATIVO))
    with pytest.raises(MotivoRequerido):
        ledger.registrar(_entrada(
            armazon, 1, "adm-sin-nota", kind=StockMovementKind.INGRESO_ADMINISTRATIVO,
            reason_code="STOCK_ENCONTRADO"))


def test_ingreso_administrativo_no_crea_una_compra_ficticia(ledger, armazon):
    movimiento = ledger.registrar(_entrada(
        armazon, 2, "adm-1", kind=StockMovementKind.INGRESO_ADMINISTRATIVO,
        reason_code="STOCK_ENCONTRADO", note="aparecieron en el depósito"))
    assert movimiento.supplier_id is None
    assert movimiento.document_kind is None
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 2


def test_los_motivos_de_ingreso_administrativo_estan_sembrados(base):
    conexion = sqlite3.connect(str(base))
    try:
        codigos = {fila[0] for fila in conexion.execute(
            "SELECT code FROM administrative_entry_reasons")}
    finally:
        conexion.close()
    assert codigos == {"STOCK_ENCONTRADO", "CORRECCION_INVENTARIO",
                       "FUERA_DE_CIRCUITO", "OTRO"}


# --------------------------------------------------------------------------
# Salidas
# --------------------------------------------------------------------------


def test_una_venta_descuenta_stock(ledger, armazon):
    ledger.registrar(_entrada(armazon, 5, "compra-1"))
    ledger.registrar(_entrada(armazon, 2, "venta-1", kind=StockMovementKind.VENTA))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 3


def test_salida_administrativa_exige_motivo(ledger, armazon):
    ledger.registrar(_entrada(armazon, 1, "compra-1"))
    with pytest.raises(MotivoRequerido):
        ledger.registrar(_entrada(
            armazon, 1, "salida-sin-motivo",
            kind=StockMovementKind.SALIDA_ADMINISTRATIVA))


def test_salida_administrativa_no_borra_la_compra_original(ledger, armazon):
    """Compra +1, después roto -1. Las dos cosas pasaron y las dos quedan."""
    compra = ledger.registrar(_entrada(armazon, 1, "compra-1"))
    ledger.registrar(_entrada(
        armazon, 1, "roto-1", kind=StockMovementKind.SALIDA_ADMINISTRATIVA,
        reason_code="ROTO"))
    historial = ledger.movimientos(article_id=armazon.id)
    assert [m.kind for m in historial] == [
        StockMovementKind.INGRESO_COMPRA, StockMovementKind.SALIDA_ADMINISTRATIVA]
    assert ledger.obtener(compra.id) is not None
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 0


def test_devolucion_a_proveedor_descuenta_y_guarda_a_quien(ledger, catalogo, armazon):
    proveedor = catalogo.save_supplier(Supplier(name="Óptica Mayorista"))
    ledger.registrar(_entrada(armazon, 3, "compra-1", supplier_id=proveedor.id))
    devolucion = ledger.registrar(_entrada(
        armazon, 1, "dev-1", kind=StockMovementKind.DEVOLUCION_PROVEEDOR,
        supplier_id=proveedor.id, note="vino fallado"))
    assert devolucion.supplier_id == proveedor.id
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 2


def test_los_ajustes_suman_y_restan(ledger, armazon):
    ledger.registrar(_entrada(
        armazon, 4, "aj+", kind=StockMovementKind.AJUSTE_POSITIVO,
        reason_code="ERROR_INVENTARIO", note="recuento"))
    ledger.registrar(_entrada(
        armazon, 1, "aj-", kind=StockMovementKind.AJUSTE_NEGATIVO,
        reason_code="ERROR_INVENTARIO", note="recuento"))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 3


# --------------------------------------------------------------------------
# Naturaleza: lo que no es stockeable no toca el ledger
# --------------------------------------------------------------------------


def test_un_servicio_no_mueve_stock(ledger, compostura):
    with pytest.raises(ArticuloNoStockeable):
        ledger.registrar(_entrada(compostura, 1, "comp-1"))


def test_un_cristal_no_mueve_stock(ledger, cristal):
    with pytest.raises(ArticuloNoStockeable):
        ledger.registrar(_entrada(cristal, 1, "cris-1"))


def test_la_base_tambien_rechaza_el_no_stockeable_aunque_se_escriba_directo(base, catalogo):
    """La regla no puede vivir sólo en Python: cualquier escritor la respeta."""
    servicio = catalogo.save_article(Article(
        sku="SERV-X", name="Ajuste", nature=ArticleNature.SERVICIO_NO_STOCKEABLE))
    conexion = sqlite3.connect(str(base))
    conexion.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO stock_movements(id, article_id, destination, kind, quantity,"
                " actor, occurred_at, recorded_at, idempotency_key)"
                " VALUES ('x', ?, 'ASUNCION', 'INGRESO_COMPRA', 1, 'a', 'x', 'x', 'k')",
                (servicio.id,))
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Aislamiento por destino
# --------------------------------------------------------------------------


def test_asuncion_y_pilar_no_se_mezclan(ledger, armazon):
    ledger.registrar(_entrada(armazon, 5, "asu-1", destino=Destination.ASUNCION))
    ledger.registrar(_entrada(armazon, 2, "pil-1", destino=Destination.PILAR))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    assert ledger.stock(armazon.id, Destination.PILAR) == 2
    assert ledger.stock_por_destino(armazon.id) == {
        Destination.ASUNCION: 5, Destination.PILAR: 2}


def test_no_se_puede_vender_en_pilar_lo_que_esta_en_asuncion(ledger, armazon):
    ledger.registrar(_entrada(armazon, 1, "asu-1", destino=Destination.ASUNCION))
    with pytest.raises(StockInsuficiente):
        ledger.registrar(_entrada(
            armazon, 1, "pil-venta", kind=StockMovementKind.VENTA,
            destino=Destination.PILAR))


# --------------------------------------------------------------------------
# Stock negativo
# --------------------------------------------------------------------------


def test_una_venta_no_puede_dejar_el_stock_en_negativo(ledger, armazon):
    ledger.registrar(_entrada(armazon, 1, "compra-1"))
    with pytest.raises(StockInsuficiente):
        ledger.registrar(_entrada(armazon, 2, "venta-1", kind=StockMovementKind.VENTA))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 1


def test_una_venta_nunca_puede_pedir_la_excepcion_administrativa(ledger, armazon):
    """La excepción existe para el inventario, no para seguir vendiendo."""
    with pytest.raises(ValueError):
        ledger.registrar(_entrada(
            armazon, 1, "venta-forzada", kind=StockMovementKind.VENTA,
            negative_override=True, reason_code="ERROR_INVENTARIO", note="no"))


def test_la_excepcion_administrativa_es_explicita_y_auditada(ledger, armazon):
    movimiento = ledger.registrar(_entrada(
        armazon, 1, "aj-forzado", kind=StockMovementKind.AJUSTE_NEGATIVO,
        negative_override=True, reason_code="ERROR_INVENTARIO",
        note="la unidad nunca existió; se corrige contra recuento"))
    assert movimiento.negative_override is True
    assert ledger.stock(armazon.id, Destination.ASUNCION) == -1


def test_la_excepcion_sin_motivo_ni_observacion_se_rechaza(ledger, armazon):
    with pytest.raises(MotivoRequerido):
        ledger.registrar(_entrada(
            armazon, 1, "aj-mudo", kind=StockMovementKind.AJUSTE_NEGATIVO,
            negative_override=True))


def test_la_base_bloquea_el_negativo_silencioso_aunque_se_escriba_directo(base, catalogo):
    articulo = catalogo.save_article(Article(
        sku="ARM-Z", name="Armazón", nature=ArticleNature.PRODUCTO_STOCKEABLE))
    conexion = sqlite3.connect(str(base))
    conexion.execute("PRAGMA foreign_keys = ON")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO stock_movements(id, article_id, destination, kind, quantity,"
                " actor, occurred_at, recorded_at, idempotency_key)"
                " VALUES ('x', ?, 'ASUNCION', 'VENTA', -1, 'a', 'x', 'x', 'k')",
                (articulo.id,))
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Append-only: no hay DELETE económico
# --------------------------------------------------------------------------


def test_el_ledger_no_admite_delete(ledger, armazon, base):
    ledger.registrar(_entrada(armazon, 1, "compra-1"))
    conexion = sqlite3.connect(str(base))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM stock_movements")
    finally:
        conexion.close()


def test_el_ledger_no_admite_update(ledger, armazon, base):
    ledger.registrar(_entrada(armazon, 1, "compra-1"))
    conexion = sqlite3.connect(str(base))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE stock_movements SET quantity = 99")
    finally:
        conexion.close()


def test_el_servicio_no_expone_forma_de_borrar(ledger):
    assert not hasattr(ledger, "eliminar")
    assert not hasattr(ledger, "borrar")


def test_una_correccion_es_un_movimiento_compensatorio(ledger, armazon):
    """Corregir no es reescribir: el error y su corrección quedan los dos."""
    error = ledger.registrar(_entrada(armazon, 10, "compra-mal"))
    correccion = ledger.compensar(
        error.id, reason_code="ERROR_INVENTARIO",
        note="se cargaron 10 y habían llegado 0", actor="rodrigo")
    assert correccion.compensates_id == error.id
    assert correccion.signed_quantity == -error.signed_quantity
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 0
    assert len(ledger.movimientos(article_id=armazon.id)) == 2


def test_un_movimiento_no_se_compensa_dos_veces(ledger, armazon):
    error = ledger.registrar(_entrada(armazon, 10, "compra-mal"))
    ledger.compensar(error.id, reason_code="ERROR_INVENTARIO", note="x", actor="r")
    with pytest.raises(ValueError):
        ledger.compensar(error.id, reason_code="ERROR_INVENTARIO", note="x", actor="r")


# --------------------------------------------------------------------------
# Event Spine
# --------------------------------------------------------------------------


def test_un_hecho_registrado_guarda_su_trazabilidad_completa(ledger, armazon):
    evento = DomainEvent(
        event_type="PURCHASE_CONFIRMED", source="COMPRAS", entity_type="PURCHASE",
        entity_id="fact-001", destination=Destination.ASUNCION, actor="rodrigo",
        idempotency_key="fact-001", payload={"factura": "001-001-0000123"})
    ledger.registrar(_entrada(armazon, 5, "fact-001:l1"), evento=evento)
    guardado = ledger.evento(evento.event_id)
    assert guardado.event_type == "PURCHASE_CONFIRMED"
    assert guardado.source == "COMPRAS"
    assert guardado.entity_id == "fact-001"
    assert guardado.actor == "rodrigo"
    assert guardado.destination is Destination.ASUNCION
    assert guardado.occurred_at is not None
    assert json.loads(guardado.payload_json)["factura"] == "001-001-0000123"
    assert guardado.processing_state is EventProcessingState.PROCESADO


def test_el_movimiento_apunta_al_hecho_que_lo_produjo(ledger, armazon):
    evento = DomainEvent(
        event_type="PURCHASE_CONFIRMED", source="COMPRAS", entity_type="PURCHASE",
        entity_id="fact-002", actor="rodrigo", idempotency_key="fact-002")
    movimiento = ledger.registrar(_entrada(armazon, 5, "fact-002:l1"), evento=evento)
    assert movimiento.event_id == evento.event_id
    efectos = ledger.efectos_de(evento.event_id)
    assert [(e.effect_kind, e.effect_id) for e in efectos] == [
        ("STOCK_MOVEMENT", movimiento.id)]


def test_el_mismo_evento_no_produce_dos_efectos(ledger, armazon):
    """Reprocesar PURCHASE_CONFIRMED no puede duplicar el stock."""
    evento = DomainEvent(
        event_type="PURCHASE_CONFIRMED", source="COMPRAS", entity_type="PURCHASE",
        entity_id="fact-003", actor="rodrigo", idempotency_key="fact-003")
    primero = ledger.registrar(_entrada(armazon, 5, "fact-003:l1"), evento=evento)
    repetido = ledger.registrar(_entrada(armazon, 5, "fact-003:l1"), evento=evento)
    assert repetido.id == primero.id
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5
    assert len(ledger.efectos_de(evento.event_id)) == 1


def test_el_evento_es_inmutable_y_no_se_borra(ledger, armazon, base):
    evento = DomainEvent(
        event_type="SALE_COMPLETED", source="CAJA", entity_type="SALE",
        entity_id="v-1", actor="rodrigo", idempotency_key="v-1")
    ledger.registrar(_entrada(armazon, 1, "c"))
    ledger.registrar(_entrada(armazon, 1, "v-1:l1", kind=StockMovementKind.VENTA),
                     evento=evento)
    conexion = sqlite3.connect(str(base))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM domain_events")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE domain_events SET payload = '{\"otro\": 1}'")
    finally:
        conexion.close()


def test_un_movimiento_sin_evento_igual_deja_rastro_de_origen(ledger, armazon):
    """El ledger nace usable antes de que Compras exista, pero nunca anónimo."""
    movimiento = ledger.registrar(_entrada(armazon, 1, "manual-1"))
    assert movimiento.actor == "rodrigo"
    assert movimiento.recorded_at is not None
    assert movimiento.idempotency_key == "manual-1"


def test_un_movimiento_sin_actor_se_rechaza(armazon):
    with pytest.raises(ValueError):
        StockMovement(article_id=armazon.id, destination=Destination.ASUNCION,
                      kind=StockMovementKind.INGRESO_COMPRA, quantity=1,
                      actor="   ", idempotency_key="k")


def test_cantidad_cero_o_negativa_se_rechaza_en_el_dominio(armazon):
    """El signo lo pone el tipo: la cantidad que se declara es siempre positiva."""
    for cantidad in (0, -3):
        with pytest.raises(ValueError):
            StockMovement(article_id=armazon.id, destination=Destination.ASUNCION,
                          kind=StockMovementKind.INGRESO_COMPRA, quantity=cantidad,
                          actor="rodrigo", idempotency_key="k")


# --------------------------------------------------------------------------
# Idempotencia
# --------------------------------------------------------------------------


def test_la_misma_clave_no_descuenta_dos_veces(ledger, armazon):
    ledger.registrar(_entrada(armazon, 5, "compra-1"))
    ledger.registrar(_entrada(armazon, 5, "compra-1"))
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 5


def test_la_misma_clave_devuelve_el_movimiento_original(ledger, armazon):
    primero = ledger.registrar(_entrada(armazon, 5, "compra-1"))
    segundo = ledger.registrar(_entrada(armazon, 5, "compra-1"))
    assert segundo.id == primero.id


def test_la_base_tambien_impide_la_clave_repetida(base, catalogo):
    articulo = catalogo.save_article(Article(
        sku="ARM-Y", name="Armazón", nature=ArticleNature.PRODUCTO_STOCKEABLE))
    sentencia = (
        "INSERT INTO stock_movements(id, article_id, destination, kind, quantity,"
        " actor, occurred_at, recorded_at, idempotency_key)"
        " VALUES (?, ?, 'ASUNCION', 'INGRESO_COMPRA', 1, 'a', 'x', 'x', 'misma')")
    conexion = sqlite3.connect(str(base))
    try:
        conexion.execute(sentencia, ("m1", articulo.id))
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(sentencia, ("m2", articulo.id))
        conexion.commit()
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Concurrencia
# --------------------------------------------------------------------------


def test_dos_salidas_simultaneas_no_dejan_el_stock_en_negativo(base, catalogo):
    articulo = catalogo.save_article(Article(
        sku="ARM-C", name="Armazón único", nature=ArticleNature.PRODUCTO_STOCKEABLE))
    inicial = SQLiteStockLedgerRepository(base)
    StockLedgerService(inicial, catalogo).registrar(_entrada(articulo, 1, "compra-1"))
    inicial.close()

    resultados: list[object] = []
    barrera = threading.Barrier(2)

    def vender(indice: int) -> None:
        repo = SQLiteStockLedgerRepository(base)
        servicio = StockLedgerService(repo, catalogo)
        barrera.wait()
        try:
            servicio.registrar(_entrada(
                articulo, 1, f"venta-{indice}", kind=StockMovementKind.VENTA))
            resultados.append("ok")
        except Exception as error:  # noqa: BLE001 -- se clasifica en el assert
            resultados.append(error)
        finally:
            repo.close()

    hilos = [threading.Thread(target=vender, args=(indice,)) for indice in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert resultados.count("ok") == 1, resultados
    verificacion = SQLiteStockLedgerRepository(base)
    try:
        assert StockLedgerService(verificacion, catalogo).stock(
            articulo.id, Destination.ASUNCION) == 0
    finally:
        verificacion.close()


# --------------------------------------------------------------------------
# Compatibilidad con lo histórico
# --------------------------------------------------------------------------


def test_las_lineas_de_venta_sin_articulo_siguen_funcionando(base):
    """Las 10 líneas que ya existen en producción no tienen artículo y no se
    les inventa uno. El ledger no puede haberlas roto."""
    conexion = sqlite3.connect(str(base))
    try:
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(sale_items)")}
        assert "article_id" in columnas
        assert conexion.execute(
            "SELECT COUNT(*) FROM sale_items WHERE article_id IS NOT NULL"
        ).fetchone()[0] == 0
    finally:
        conexion.close()


def test_el_backfill_historico_falla_cerrado_y_no_escribe(base, ledger):
    """No hay evidencia de qué artículo se vendió. Inventarla sería peor que
    no tener stock histórico."""
    plan = planificar_backfill_historico(base)
    assert plan.aplicable is False
    assert plan.movimientos_a_crear == 0
    assert plan.lineas_sin_articulo >= 0
    assert "no atribuible" in plan.motivo.lower()
    conexion = sqlite3.connect(str(base))
    try:
        assert conexion.execute(
            "SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 0
    finally:
        conexion.close()


def test_el_ledger_arranca_vacio_y_no_inventa_historia(ledger, armazon):
    assert ledger.movimientos() == []
    assert ledger.stock(armazon.id, Destination.ASUNCION) == 0


# --------------------------------------------------------------------------
# Referencias durables, para que Compras enganche sin migrar de nuevo
# --------------------------------------------------------------------------


def test_el_movimiento_acepta_la_referencia_que_compras_va_a_necesitar(
        ledger, catalogo, armazon):
    proveedor = catalogo.save_supplier(Supplier(name="Distribuidora Sur"))
    movimiento = ledger.registrar(_entrada(
        armazon, 6, "fact-9:l1",
        supplier_id=proveedor.id, document_kind="COMPRA", document_id="compra-9",
        document_line_id="linea-1", document_number="001-001-0000456"))
    guardado = ledger.obtener(movimiento.id)
    assert guardado.supplier_id == proveedor.id
    assert guardado.document_kind == "COMPRA"
    assert guardado.document_id == "compra-9"
    assert guardado.document_line_id == "linea-1"
    assert guardado.document_number == "001-001-0000456"


def test_se_puede_ir_del_origen_a_sus_movimientos(ledger, armazon):
    ledger.registrar(_entrada(armazon, 6, "fact-9:l1", document_kind="COMPRA",
                              document_id="compra-9"))
    ledger.registrar(_entrada(armazon, 2, "fact-9:l2", document_kind="COMPRA",
                              document_id="compra-9", destino=Destination.PILAR))
    trazados = ledger.movimientos_de_documento("COMPRA", "compra-9")
    assert {m.destination for m in trazados} == {Destination.ASUNCION, Destination.PILAR}
    assert sum(m.signed_quantity for m in trazados) == 8


# --------------------------------------------------------------------------
# La migración no toca nada de lo que ya había
# --------------------------------------------------------------------------


def test_la_cadena_de_migraciones_llega_a_023(base):
    conexion = sqlite3.connect(str(base))
    try:
        versiones = [fila[0] for fila in conexion.execute(
            "SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        conexion.close()
    assert versiones[-1] == "023"


def test_la_023_es_aditiva():
    """Sólo crea cosas nuevas. Ni siquiera un ALTER: nada de lo que ya está en
    producción se toca, así que ninguna fila productiva puede perderse."""
    from tests.migration_chain import MIGRATIONS_DIR
    sql = (MIGRATIONS_DIR / "023_inventory_ledger.sql").read_text(encoding="utf-8").upper()
    for prohibido in ("DROP ", "DELETE FROM", "ALTER TABLE"):
        assert prohibido not in sql, f"la migración no puede contener {prohibido}"
    # Lo único que escribe filas es la siembra de su propio catálogo nuevo.
    assert sql.count("INSERT OR IGNORE INTO") == 2  # motivos nuevos + schema_migrations
