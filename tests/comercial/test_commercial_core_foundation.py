"""Foundation canónica del núcleo comercial: catálogos y naturalezas de ítem.

Pruebas dirigidas escritas antes de la implementación. Fijan el vocabulario del
que van a colgar Compras, Stock, Ventas y Trabajos, de modo que esos slices no
tengan que migrar dos veces.
"""

from __future__ import annotations

import sqlite3

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.importer import planificar_importacion
from modulos.comercial.application.ports import CatalogRepository
from modulos.comercial.domain.models import (
    CONSUMIDOR_FINAL,
    AdministrativeExitReason,
    Article,
    ArticleNature,
    Brand,
    Category,
    CostStatus,
    Destination,
    Supplier,
    nombre_de_cliente,
)
from modulos.comercial.infrastructure.sqlite_catalog_repository import (
    SQLiteCatalogRepository,
)


@pytest.fixture()
def repo(tmp_path):
    ruta = tmp_path / "bc_caja.sqlite3"
    SQLiteCashDayRepository(ruta)  # aplica la cadena de migraciones, 001..022
    catalogo = SQLiteCatalogRepository(ruta)
    yield catalogo
    catalogo.close()


# --------------------------------------------------------------------------
# Naturalezas
# --------------------------------------------------------------------------


def test_las_naturalezas_son_exactamente_cuatro():
    assert {n.value for n in ArticleNature} == {
        "PRODUCTO_STOCKEABLE",
        "SERVICIO_NO_STOCKEABLE",
        "TRABAJO_BAJO_PEDIDO",
        "PRODUCCION_INTERNA",
    }


@pytest.mark.parametrize(
    "naturaleza, mueve_stock",
    [
        (ArticleNature.PRODUCTO_STOCKEABLE, True),
        (ArticleNature.PRODUCCION_INTERNA, True),
        (ArticleNature.SERVICIO_NO_STOCKEABLE, False),
        (ArticleNature.TRABAJO_BAJO_PEDIDO, False),
    ],
)
def test_tracks_stock_se_deriva_de_la_naturaleza(naturaleza, mueve_stock):
    articulo = Article(sku="X-1", name="cualquiera", nature=naturaleza)
    assert articulo.tracks_stock is mueve_stock


def test_tracks_stock_no_es_seteable():
    """Una columna libre dejaria un armazon que no mueve stock y una compostura
    que si. Es exactamente el error que este modelo existe para impedir."""
    with pytest.raises(TypeError):
        Article(sku="X-1", name="cualquiera",
                nature=ArticleNature.SERVICIO_NO_STOCKEABLE, tracks_stock=True)


def test_una_compostura_es_servicio_y_no_mueve_stock():
    compostura = Article(sku="SERV-COMP", name="Compostura",
                         nature=ArticleNature.SERVICIO_NO_STOCKEABLE)
    assert compostura.tracks_stock is False


def test_un_cristal_es_trabajo_bajo_pedido_y_no_mueve_stock():
    cristal = Article(sku="CRIS-ORG", name="Cristal organico recetado",
                      nature=ArticleNature.TRABAJO_BAJO_PEDIDO)
    assert cristal.tracks_stock is False


def test_naturaleza_desconocida_se_rechaza():
    with pytest.raises(ValueError):
        Article(sku="X-1", name="cualquiera", nature="INVENTADA")


def test_el_costo_sin_dato_real_es_pendiente_de_conciliacion():
    """No se inventa costo: cuando no hay dato real queda declarado como tal."""
    assert CostStatus.PENDIENTE_DE_CONCILIACION.value == "PENDIENTE_DE_CONCILIACION"
    assert {c.value for c in CostStatus} == {"CONOCIDO", "PENDIENTE_DE_CONCILIACION"}


# --------------------------------------------------------------------------
# Destinos: se reutiliza el vocabulario que ya existe
# --------------------------------------------------------------------------


def test_los_destinos_reusan_el_vocabulario_de_sucursales_existente():
    assert {d.value for d in Destination} == {"ASUNCION", "PILAR"}


def test_no_se_creo_una_tabla_de_sucursales_paralela(repo):
    """cash_register_branches ya liga caja -> sucursal. Duplicarla seria el
    sistema paralelo que se pidio evitar."""
    tablas = repo.nombres_de_tablas()
    assert "cash_register_branches" in tablas
    for inventada in ("branches", "sucursales", "commercial_destinations"):
        assert inventada not in tablas


# --------------------------------------------------------------------------
# Catálogos
# --------------------------------------------------------------------------


def test_el_repositorio_cumple_el_puerto(repo):
    assert isinstance(repo, CatalogRepository)


def test_alta_y_lectura_de_articulo_con_sus_catalogos(repo):
    categoria = repo.save_category(Category(name="Armazones"))
    marca = repo.save_brand(Brand(name="Vulk"))
    proveedor = repo.save_supplier(Supplier(name="Distribuidora Sur"))

    guardado = repo.save_article(Article(
        sku="ARM-001",
        name="Armazon Vulk metal",
        nature=ArticleNature.PRODUCTO_STOCKEABLE,
        category_id=categoria.id,
        brand_id=marca.id,
        supplier_id=proveedor.id,
        sale_price=450000,
    ))

    leido = repo.get_article(guardado.id)
    assert leido is not None
    assert leido.sku == "ARM-001"
    assert leido.nature is ArticleNature.PRODUCTO_STOCKEABLE
    assert leido.tracks_stock is True
    assert leido.sale_price == 450000
    assert leido.category_id == categoria.id
    assert leido.brand_id == marca.id
    assert leido.supplier_id == proveedor.id


def test_el_sku_es_unico_sin_importar_mayusculas(repo):
    repo.save_article(Article(sku="ARM-001", name="uno",
                              nature=ArticleNature.PRODUCTO_STOCKEABLE))
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_article(Article(sku="arm-001", name="otro distinto",
                                  nature=ArticleNature.PRODUCTO_STOCKEABLE))


def test_el_nombre_de_marca_es_unico_sin_importar_mayusculas(repo):
    repo.save_brand(Brand(name="Vulk"))
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_brand(Brand(name="vulk"))


def test_listar_articulos_activos_deja_afuera_los_dados_de_baja(repo):
    vivo = repo.save_article(Article(sku="A-1", name="vivo",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE))
    repo.save_article(Article(sku="A-2", name="de baja",
                              nature=ArticleNature.PRODUCTO_STOCKEABLE, active=False))
    activos = repo.list_articles(only_active=True)
    assert [a.id for a in activos] == [vivo.id]
    assert len(repo.list_articles(only_active=False)) == 2


def test_un_proveedor_puede_apuntar_al_laboratorio_canonico(repo):
    """laboratories ya es el catalogo canonico: se referencia, no se duplica."""
    laboratorio_id = repo.asegurar_laboratorio("Optilab")
    proveedor = repo.save_supplier(
        Supplier(name="Optilab", kind="LABORATORIO", laboratory_id=laboratorio_id))
    leido = repo.get_supplier(proveedor.id)
    assert leido.laboratory_id == laboratorio_id


def test_un_articulo_no_puede_referenciar_una_categoria_inexistente(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_article(Article(sku="A-9", name="huerfano",
                                  nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                  category_id="no-existe"))


# --------------------------------------------------------------------------
# Motivos de salida administrativa
# --------------------------------------------------------------------------


def test_los_motivos_de_salida_estan_sembrados_completos(repo):
    codigos = {m.code for m in repo.list_administrative_exit_reasons()}
    assert codigos == {
        "ROTO", "RAYADO", "PERDIDA", "DETERIORO",
        "USO_INTERNO", "ERROR_INVENTARIO", "OTRO",
        # Reservado, sembrado por la 027: explica la devolución al depósito de
        # una venta anulada y no se elige a mano.
        "VENTA_ANULADA",
    }


def test_el_enum_de_motivos_coincide_con_lo_sembrado(repo):
    assert {r.value for r in AdministrativeExitReason} == {
        m.code for m in repo.list_administrative_exit_reasons()
    }


# --------------------------------------------------------------------------
# Consumidor final
# --------------------------------------------------------------------------


@pytest.mark.parametrize("vacio", ["", "   ", None])
def test_una_venta_sin_cliente_normaliza_a_consumidor_final(vacio):
    assert nombre_de_cliente(vacio) == CONSUMIDOR_FINAL


def test_un_cliente_real_no_se_toca():
    assert nombre_de_cliente("  Sol Blaires ") == "Sol Blaires"


def test_consumidor_final_no_es_un_cliente_en_tabla(repo):
    """No se crea un cliente ficticio por caso: es una constante de dominio."""
    assert "customers" not in repo.nombres_de_tablas()
    assert "clientes" not in repo.nombres_de_tablas()


# --------------------------------------------------------------------------
# Importador: contrato y plan, sin carga masiva
# --------------------------------------------------------------------------


def test_el_plan_de_importacion_no_escribe_nada(repo):
    antes = len(repo.list_articles(only_active=False))
    planificar_importacion(
        [{"sku": "IMP-1", "name": "importado", "nature": "PRODUCTO_STOCKEABLE"}],
        existentes_por_sku={},
    )
    assert len(repo.list_articles(only_active=False)) == antes


def test_el_plan_separa_altas_actualizaciones_y_rechazos():
    plan = planificar_importacion(
        [
            {"sku": "NUEVO-1", "name": "alta", "nature": "PRODUCTO_STOCKEABLE"},
            {"sku": "VIEJO-1", "name": "actualiza", "nature": "PRODUCTO_STOCKEABLE"},
            {"sku": "", "name": "sin sku", "nature": "PRODUCTO_STOCKEABLE"},
            {"sku": "MALA-1", "name": "naturaleza inventada", "nature": "NI_IDEA"},
            {"sku": "NUEVO-1", "name": "sku repetido en el archivo",
             "nature": "PRODUCTO_STOCKEABLE"},
        ],
        existentes_por_sku={"VIEJO-1": "id-viejo"},
    )
    assert [a.sku for a in plan.altas] == ["NUEVO-1"]
    assert [a.sku for a in plan.actualizaciones] == ["VIEJO-1"]
    assert len(plan.rechazos) == 3
    motivos = " ".join(r.motivo for r in plan.rechazos).lower()
    assert "sku" in motivos and "naturaleza" in motivos and "repetido" in motivos


def test_el_plan_es_aplicable_solo_si_no_hay_rechazos():
    limpio = planificar_importacion(
        [{"sku": "OK-1", "name": "ok", "nature": "PRODUCTO_STOCKEABLE"}],
        existentes_por_sku={},
    )
    sucio = planificar_importacion(
        [{"sku": "", "name": "roto", "nature": "PRODUCTO_STOCKEABLE"}],
        existentes_por_sku={},
    )
    assert limpio.aplicable is True
    assert sucio.aplicable is False


def test_el_sku_del_plan_ignora_mayusculas_y_espacios():
    plan = planificar_importacion(
        [{"sku": "  viejo-1 ", "name": "actualiza", "nature": "PRODUCTO_STOCKEABLE"}],
        existentes_por_sku={"VIEJO-1": "id-viejo"},
    )
    assert [a.sku for a in plan.actualizaciones] == ["VIEJO-1"]


# --------------------------------------------------------------------------
# Compatibilidad con la base productiva de rc.31
# --------------------------------------------------------------------------


def test_la_migracion_022_es_aditiva_y_no_pierde_filas(tmp_path):
    """Se arma una base en el estado de rc.31, se le mete una venta con sus
    lineas y despues se migra: nada se pierde y sale_items gana la columna
    nullable que enlaza con el catalogo."""
    ruta = tmp_path / "productiva.sqlite3"
    caja = SQLiteCashDayRepository(ruta)

    conexion = sqlite3.connect(ruta)
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute(
        "INSERT INTO cash_days(id, business_date, unit, opening_cash, status,"
        " opened_at) VALUES('d1','2026-08-18','PC',0,'OPEN', CURRENT_TIMESTAMP)")
    conexion.execute(
        "INSERT INTO cash_entries(id, cash_day_id, description, total,"
        " created_at, updated_at) VALUES('e1','d1','venta real',500000,"
        " CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    conexion.execute(
        "INSERT INTO sale_items(id, cash_entry_id, position, description)"
        " VALUES('s1','e1',0,'armazon escrito a mano')")
    conexion.commit()

    filas_antes = conexion.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0]
    total_antes = conexion.execute("SELECT SUM(total) FROM cash_entries").fetchone()[0]
    conexion.close()

    caja.migrate()  # idempotente: vuelve a pasar la cadena entera

    conexion = sqlite3.connect(ruta)
    assert conexion.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0] == filas_antes
    assert conexion.execute("SELECT SUM(total) FROM cash_entries").fetchone()[0] == total_antes
    columnas = {c[1] for c in conexion.execute("PRAGMA table_info(sale_items)")}
    assert "article_id" in columnas
    assert conexion.execute(
        "SELECT article_id FROM sale_items WHERE id='s1'").fetchone()[0] is None
    assert conexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conexion.execute("PRAGMA foreign_key_check").fetchall() == []
    conexion.close()


def test_la_cadena_de_migraciones_incluye_la_022_completa(tmp_path):
    """Que la 022 este aplicada y que la cadena este entera, no que termine ahi.

    Contaba las migraciones a mano, que es exactamente lo que este slice le
    corrigio a otros seis contratos ajenos. La intencion era "la 022 se aplico
    y no falta ninguna", no "nunca va a haber una 023".
    """
    from tests.migration_chain import versiones_esperadas

    ruta = tmp_path / "bc.sqlite3"
    SQLiteCashDayRepository(ruta)
    conexion = sqlite3.connect(ruta)
    versiones = {v[0] for v in conexion.execute("SELECT version FROM schema_migrations")}
    conexion.close()
    assert "022" in versiones
    assert versiones == set(versiones_esperadas())
