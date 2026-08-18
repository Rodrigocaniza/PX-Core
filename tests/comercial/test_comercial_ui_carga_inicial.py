"""UI comercial y carga inicial, slice 5.

Pruebas dirigidas escritas antes de la implementación.

Los slices 1 a 4 dejaron el circuito cerrado y sin una sola pantalla desde donde
usarlo. Este slice no agrega dominio: hace operable lo que ya existe, y resuelve
el prerrequisito duro de todo lo demás — poder cargar los ~3.000 artículos
reales de la Óptica sin tipearlos a mano y sin inventar lo que el archivo no
diga.

La regla que ordena la carga inicial: **catálogo no es stock**. Que un artículo
exista no significa que haya unidades en el depósito. Las unidades entran por un
hecho explícito, auditado y compensable, nunca por el solo hecho de existir.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.carga_inicial import (
    CargaInicialError,
    leer_archivo_de_articulos,
)
from modulos.comercial.application.comercial_controller import (
    ArticuloEnUso,
    ComercialController,
    build_comercial_controller,
)
from modulos.comercial.domain.models import (
    Article,
    ArticleNature,
    Destination,
    StockMovementKind,
)


FUENTE_UI = Path("modulos/comercial/ui/comercial_window.py")
FUENTE_CAJA = Path("CajaDiaria.py")


@pytest.fixture()
def ruta(tmp_path):
    return tmp_path / "bc_caja.sqlite3"


@pytest.fixture()
def ctrl(ruta):
    controlador = build_comercial_controller(ruta)
    controlador.vincular_caja_a_sucursal("PC", "ASUNCION", actor="admin")
    controlador.vincular_caja_a_sucursal("P2", "PILAR", actor="admin")
    yield controlador
    controlador.close()


# --------------------------------------------------------------------------
# ABM de artículos
# --------------------------------------------------------------------------


def test_se_da_de_alta_un_articulo_con_lo_que_la_operacion_necesita(ctrl):
    articulo = ctrl.guardar_articulo(
        sku="ARM-001", name="Armazón metal negro",
        nature=ArticleNature.PRODUCTO_STOCKEABLE,
        sale_price=280_000, location="Góndola 3 / Fila B", min_stock=2,
        barcode="7790001234567", actor="admin")
    guardado = ctrl.obtener_articulo(articulo.id)
    assert guardado.sku == "ARM-001"
    assert guardado.location == "Góndola 3 / Fila B"
    assert guardado.min_stock == 2
    assert guardado.barcode == "7790001234567"
    assert guardado.active is True


def test_el_sku_no_se_repite(ctrl):
    ctrl.guardar_articulo(sku="ARM-001", name="Uno",
                          nature=ArticleNature.PRODUCTO_STOCKEABLE, actor="admin")
    with pytest.raises(sqlite3.IntegrityError):
        ctrl.guardar_articulo(sku="arm-001", name="Otro",
                              nature=ArticleNature.PRODUCTO_STOCKEABLE, actor="admin")


def test_el_codigo_de_barras_no_se_repite_pero_puede_faltar(ctrl):
    """Sin código de barras no hay duplicado que detectar: no se inventa uno."""
    ctrl.guardar_articulo(sku="A-1", name="Uno", nature=ArticleNature.PRODUCTO_STOCKEABLE,
                          barcode="7790001", actor="admin")
    ctrl.guardar_articulo(sku="A-2", name="Dos", nature=ArticleNature.PRODUCTO_STOCKEABLE,
                          actor="admin")
    ctrl.guardar_articulo(sku="A-3", name="Tres", nature=ArticleNature.PRODUCTO_STOCKEABLE,
                          actor="admin")
    with pytest.raises(sqlite3.IntegrityError):
        ctrl.guardar_articulo(sku="A-4", name="Cuatro",
                              nature=ArticleNature.PRODUCTO_STOCKEABLE,
                              barcode="7790001", actor="admin")


def test_la_edicion_administrativa_queda_auditada(ctrl, ruta):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     sale_price=100_000, actor="admin")
    ctrl.guardar_articulo(sku="ARM-001", name="Armazón metal",
                          nature=ArticleNature.PRODUCTO_STOCKEABLE,
                          sale_price=150_000, article_id=articulo.id, actor="rodrigo")
    historial = ctrl.historial_de_articulo(articulo.id)
    assert len(historial) == 2
    assert historial[-1].actor == "rodrigo"
    assert "150" in historial[-1].detalle or "150000" in historial[-1].detalle


def test_un_articulo_se_desactiva_no_se_borra(ctrl):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    ctrl.desactivar_articulo(articulo.id, actor="admin", motivo="descontinuado")
    assert ctrl.obtener_articulo(articulo.id).active is False
    assert not hasattr(ctrl, "borrar_articulo")
    assert not hasattr(ctrl, "eliminar_articulo")


def test_no_se_desactiva_un_articulo_que_todavia_tiene_stock(ctrl):
    """Desactivarlo lo saca de las búsquedas y el stock queda huérfano."""
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    ctrl.cargar_stock_inicial(
        [(articulo.id, Destination.ASUNCION, 5)],
        actor="admin", origen="recuento inicial")
    with pytest.raises(ArticuloEnUso):
        ctrl.desactivar_articulo(articulo.id, actor="admin", motivo="ya no se vende")


def test_la_busqueda_encuentra_por_codigo_y_por_descripcion(ctrl):
    ctrl.guardar_articulo(sku="ARM-VULK-01", name="Armazón Vulk negro",
                          nature=ArticleNature.PRODUCTO_STOCKEABLE, actor="admin")
    ctrl.guardar_articulo(sku="ACC-CAD-01", name="Cadenilla dorada",
                          nature=ArticleNature.PRODUCTO_STOCKEABLE, actor="admin")
    assert len(ctrl.buscar_articulos("vulk")) == 1
    assert len(ctrl.buscar_articulos("ARM-")) == 1
    assert len(ctrl.buscar_articulos("cadenilla")) == 1
    assert len(ctrl.buscar_articulos("")) == 2


def test_la_busqueda_filtra_por_naturaleza_y_por_activo(ctrl):
    ctrl.guardar_articulo(sku="A-1", name="Armazón",
                          nature=ArticleNature.PRODUCTO_STOCKEABLE, actor="admin")
    servicio = ctrl.guardar_articulo(sku="S-1", name="Compostura",
                                     nature=ArticleNature.SERVICIO_NO_STOCKEABLE,
                                     actor="admin")
    ctrl.desactivar_articulo(servicio.id, actor="admin", motivo="x")
    assert len(ctrl.buscar_articulos("", naturaleza=ArticleNature.PRODUCTO_STOCKEABLE)) == 1
    assert len(ctrl.buscar_articulos("", solo_activos=True)) == 1
    assert len(ctrl.buscar_articulos("", solo_activos=False)) == 2


# --------------------------------------------------------------------------
# Categorías y marcas inline
# --------------------------------------------------------------------------


def test_se_crea_una_categoria_sin_salir_del_flujo(ctrl):
    categoria = ctrl.crear_categoria("Armazones", actor="admin")
    articulo = ctrl.guardar_articulo(sku="A-1", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     category_id=categoria.id, actor="admin")
    assert ctrl.obtener_articulo(articulo.id).category_id == categoria.id
    assert [c.name for c in ctrl.listar_categorias()] == ["Armazones"]


def test_se_crea_una_marca_sin_salir_del_flujo(ctrl):
    marca = ctrl.crear_marca("Vulk", actor="admin")
    articulo = ctrl.guardar_articulo(sku="A-1", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     brand_id=marca.id, actor="admin")
    assert ctrl.obtener_articulo(articulo.id).brand_id == marca.id
    assert [m.name for m in ctrl.listar_marcas()] == ["Vulk"]


def test_una_categoria_repetida_devuelve_la_que_ya_estaba(ctrl):
    """Escribirla de nuevo no puede crear un duplicado con otra mayúscula."""
    primera = ctrl.crear_categoria("Armazones", actor="admin")
    segunda = ctrl.crear_categoria("armazones", actor="admin")
    assert segunda.id == primera.id
    assert len(ctrl.listar_categorias()) == 1


def test_una_marca_repetida_devuelve_la_que_ya_estaba(ctrl):
    primera = ctrl.crear_marca("Vulk", actor="admin")
    assert ctrl.crear_marca("VULK", actor="admin").id == primera.id


# --------------------------------------------------------------------------
# El costo no es un dato del artículo
# --------------------------------------------------------------------------


def test_el_costo_se_deriva_de_la_ultima_compra(ctrl):
    """Guardarlo en el artículo sería una segunda verdad frente a la factura."""
    proveedor = ctrl.guardar_proveedor(name="Distribuidora Sur", document="80012345-6",
                                       actor="admin")
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000123", condition="CONTADO",
        lineas=[{"article_id": articulo.id, "quantity": 10, "unit_cost": 50_000,
                 "distribucion": {Destination.ASUNCION: 10}}],
        actor="admin")
    ctrl.confirmar_compra(compra.id, actor="admin")

    costo = ctrl.costo_de_referencia(articulo.id)
    assert costo.valor == 50_000
    assert costo.estado == "CONOCIDO"
    assert costo.document_number == "001-001-0000123"


def test_un_articulo_nunca_comprado_no_tiene_costo_inventado(ctrl):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    costo = ctrl.costo_de_referencia(articulo.id)
    assert costo.valor is None
    assert costo.estado == "PENDIENTE_DE_CONCILIACION"


def test_el_articulo_no_tiene_columna_de_costo(ruta, ctrl):
    conexion = sqlite3.connect(str(ruta))
    try:
        columnas = {f[1] for f in conexion.execute("PRAGMA table_info(articles)")}
    finally:
        conexion.close()
    assert "cost" not in columnas
    assert "unit_cost" not in columnas
    assert {"location", "min_stock", "barcode"} <= columnas


# --------------------------------------------------------------------------
# Proveedores
# --------------------------------------------------------------------------


def test_alta_busqueda_y_baja_logica_de_proveedores(ctrl):
    proveedor = ctrl.guardar_proveedor(
        name="Distribuidora Sur S.A.", document="80012345-6",
        phone="021 555 000", address="Av. España 1234", actor="admin")
    assert len(ctrl.buscar_proveedores("sur")) == 1
    assert len(ctrl.buscar_proveedores("80012")) == 1
    ctrl.desactivar_proveedor(proveedor.id, actor="admin", motivo="dejó de vender")
    assert ctrl.obtener_proveedor(proveedor.id).active is False
    assert not hasattr(ctrl, "borrar_proveedor")


# --------------------------------------------------------------------------
# Compras desde la UI
# --------------------------------------------------------------------------


@pytest.fixture()
def compra_lista(ctrl):
    proveedor = ctrl.guardar_proveedor(name="Distribuidora Sur", document="80012345-6",
                                       actor="admin")
    armazon = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                    nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                    actor="admin")
    cristal = ctrl.guardar_articulo(sku="CRIS-ORG", name="Cristal orgánico",
                                    nature=ArticleNature.TRABAJO_BAJO_PEDIDO,
                                    actor="admin")
    return proveedor, armazon, cristal


def test_una_compra_se_carga_y_se_confirma_desde_el_controlador(ctrl, compra_lista):
    proveedor, armazon, _ = compra_lista
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000123", stamped_number="12345678",
        condition="CONTADO",
        lineas=[{"article_id": armazon.id, "quantity": 10, "unit_cost": 50_000,
                 "distribucion": {Destination.ASUNCION: 6, Destination.PILAR: 4}}],
        actor="admin")
    resultado = ctrl.confirmar_compra(compra.id, actor="admin")
    assert resultado.evento.event_type == "PURCHASE_CONFIRMED"
    assert ctrl.stock(armazon.id, Destination.ASUNCION) == 6
    assert ctrl.stock(armazon.id, Destination.PILAR) == 4


def test_el_vencimiento_a_credito_se_muestra_derivado(ctrl, compra_lista):
    proveedor, armazon, _ = compra_lista
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000124", condition="CREDITO", credit_days=30,
        lineas=[{"article_id": armazon.id, "quantity": 1, "unit_cost": 1_000,
                 "distribucion": {Destination.ASUNCION: 1}}],
        actor="admin")
    assert ctrl.obtener_compra(compra.id).due_date == date(2026, 9, 17)


def test_una_linea_no_stock_no_ofrece_distribucion(ctrl, compra_lista):
    proveedor, _, cristal = compra_lista
    assert ctrl.linea_necesita_distribucion(cristal.id) is False
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000125", condition="CONTADO",
        lineas=[{"article_id": cristal.id, "quantity": 4, "unit_cost": 120_000}],
        actor="admin")
    ctrl.confirmar_compra(compra.id, actor="admin")
    assert ctrl.movimientos_de_articulo(cristal.id) == []


def test_la_pantalla_puede_contrastar_los_dos_totales_antes_de_confirmar(
        ctrl, compra_lista):
    proveedor, armazon, _ = compra_lista
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000126", condition="CONTADO",
        document_total=999_999,
        lineas=[{"article_id": armazon.id, "quantity": 10, "unit_cost": 50_000,
                 "distribucion": {Destination.ASUNCION: 10}}],
        actor="admin")
    revision = ctrl.revisar_compra(compra.id)
    assert revision.total_documento == 999_999
    assert revision.total_lineas == 500_000
    assert revision.confirmable is False
    assert any("total" in p.lower() for p in revision.problemas)


def test_la_revision_avisa_de_la_distribucion_incompleta(ctrl, compra_lista):
    proveedor, armazon, _ = compra_lista
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000127", condition="CONTADO",
        lineas=[{"article_id": armazon.id, "quantity": 10, "unit_cost": 50_000,
                 "distribucion": {Destination.ASUNCION: 6}}],
        actor="admin")
    revision = ctrl.revisar_compra(compra.id)
    assert revision.confirmable is False
    assert any("reparte" in p.lower() or "distribu" in p.lower()
               for p in revision.problemas)


def test_una_compra_lista_se_declara_confirmable(ctrl, compra_lista):
    proveedor, armazon, cristal = compra_lista
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000128", condition="CONTADO",
        lineas=[
            {"article_id": armazon.id, "quantity": 10, "unit_cost": 50_000,
             "distribucion": {Destination.ASUNCION: 10}},
            {"article_id": cristal.id, "quantity": 2, "unit_cost": 100_000}],
        actor="admin")
    revision = ctrl.revisar_compra(compra.id)
    assert revision.confirmable is True
    assert revision.problemas == ()


def test_la_ui_no_reimplementa_la_confirmacion(ctrl):
    """El dominio del slice 3 es el único que confirma. La UI lo llama."""
    import inspect
    from modulos.comercial.application import comercial_controller
    fuente = inspect.getsource(comercial_controller)
    assert "PURCHASE_CONFIRMED" not in fuente
    assert "INSERT INTO stock_movements" not in fuente
    assert "INSERT INTO purchases" not in fuente


# --------------------------------------------------------------------------
# Selector de artículos en la venta
# --------------------------------------------------------------------------


def test_el_selector_muestra_lo_que_la_operadora_necesita_para_decidir(ctrl):
    categoria = ctrl.crear_categoria("Armazones", actor="admin")
    marca = ctrl.crear_marca("Vulk", actor="admin")
    articulo = ctrl.guardar_articulo(
        sku="ARM-001", name="Armazón Vulk negro",
        nature=ArticleNature.PRODUCTO_STOCKEABLE, category_id=categoria.id,
        brand_id=marca.id, sale_price=280_000, location="Góndola 3", actor="admin")
    ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 4)],
                              actor="admin", origen="recuento inicial")

    opciones = ctrl.buscar_para_venta("vulk", unidad="PC")
    assert len(opciones) == 1
    opcion = opciones[0]
    assert opcion.sku == "ARM-001"
    assert opcion.name == "Armazón Vulk negro"
    assert opcion.category == "Armazones"
    assert opcion.brand == "Vulk"
    assert opcion.sale_price == 280_000
    assert opcion.location == "Góndola 3"
    assert opcion.stock == 4
    assert opcion.mueve_stock is True
    assert opcion.estado == "DISPONIBLE"


def test_el_selector_dice_sin_stock_en_vez_de_esconder(ctrl):
    """Esconderlo haría pensar que el artículo no existe."""
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    opcion = ctrl.buscar_para_venta("armazón", unidad="PC")[0]
    assert opcion.stock == 0
    assert opcion.estado == "SIN_STOCK"


def test_el_selector_muestra_el_stock_de_la_sucursal_de_esta_caja(ctrl):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 7)],
                              actor="admin", origen="recuento")
    assert ctrl.buscar_para_venta("arma", unidad="PC")[0].stock == 7
    assert ctrl.buscar_para_venta("arma", unidad="P2")[0].stock == 0


def test_un_servicio_no_muestra_stock_ni_cero(ctrl):
    """Un servicio no tiene stock cero: no tiene stock."""
    ctrl.guardar_articulo(sku="SERV-COMP", name="Compostura",
                          nature=ArticleNature.SERVICIO_NO_STOCKEABLE, actor="admin")
    opcion = ctrl.buscar_para_venta("compostura", unidad="PC")[0]
    assert opcion.mueve_stock is False
    assert opcion.stock is None
    assert opcion.estado == "NO_LLEVA_STOCK"


def test_un_cristal_tampoco_muestra_stock(ctrl):
    ctrl.guardar_articulo(sku="CRIS-ORG", name="Cristal orgánico",
                          nature=ArticleNature.TRABAJO_BAJO_PEDIDO, actor="admin")
    opcion = ctrl.buscar_para_venta("cristal", unidad="PC")[0]
    assert opcion.stock is None
    assert opcion.estado == "NO_LLEVA_STOCK"


def test_un_articulo_inactivo_se_marca_y_no_se_puede_vender(ctrl):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    ctrl.desactivar_articulo(articulo.id, actor="admin", motivo="descontinuado")
    assert ctrl.buscar_para_venta("armazón", unidad="PC") == ()
    opciones = ctrl.buscar_para_venta("armazón", unidad="PC", incluir_inactivos=True)
    assert opciones[0].estado == "INACTIVO"
    assert opciones[0].vendible is False


def test_una_caja_sin_sucursal_no_finge_saber_el_stock(ctrl):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    opcion = ctrl.buscar_para_venta("armazón", unidad="CAJA-SIN-VINCULO")[0]
    assert opcion.stock is None
    assert opcion.estado == "SUCURSAL_DESCONOCIDA"


# --------------------------------------------------------------------------
# Carga inicial: catálogo
# --------------------------------------------------------------------------


def _archivo_csv(tmp_path, contenido: str) -> Path:
    ruta = tmp_path / "articulos.csv"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_se_lee_un_archivo_de_articulos_con_las_columnas_del_contrato(tmp_path):
    archivo = _archivo_csv(tmp_path, (
        "sku,name,nature,category,brand,sale_price,location,min_stock,barcode\n"
        "ARM-001,Armazón Vulk negro,PRODUCTO_STOCKEABLE,Armazones,Vulk,280000,G3,2,7790001\n"
        "SERV-01,Compostura,SERVICIO_NO_STOCKEABLE,Servicios,,30000,,,\n"))
    filas = leer_archivo_de_articulos(archivo)
    assert len(filas) == 2
    assert filas[0]["sku"] == "ARM-001"
    assert filas[0]["sale_price"] == 280000
    assert filas[0]["min_stock"] == 2
    assert filas[1]["brand"] == ""


def test_un_archivo_sin_las_columnas_obligatorias_se_rechaza_entero(tmp_path):
    archivo = _archivo_csv(tmp_path, "codigo,descripcion\nA-1,Armazón\n")
    with pytest.raises(CargaInicialError) as error:
        leer_archivo_de_articulos(archivo)
    assert "sku" in str(error.value)


def test_el_plan_de_carga_no_escribe_nada(ctrl, tmp_path, ruta):
    archivo = _archivo_csv(tmp_path, (
        "sku,name,nature\n"
        "ARM-001,Armazón,PRODUCTO_STOCKEABLE\n"
        "ARM-002,Armazón dos,PRODUCTO_STOCKEABLE\n"))
    plan = ctrl.planificar_carga_de_articulos(archivo)
    assert plan.aplicable is True
    assert len(plan.altas) == 2
    assert ctrl.buscar_articulos("") == ()


def test_una_fila_con_naturaleza_invalida_frena_el_archivo_entero(ctrl, tmp_path):
    """Cargar 1.999 de 2.000 deja un catálogo que nadie sabe describir."""
    archivo = _archivo_csv(tmp_path, (
        "sku,name,nature\n"
        "ARM-001,Armazón,PRODUCTO_STOCKEABLE\n"
        "ARM-002,Armazón dos,LO_QUE_SEA\n"))
    plan = ctrl.planificar_carga_de_articulos(archivo)
    assert plan.aplicable is False
    assert len(plan.rechazos) == 1
    assert plan.rechazos[0].fila == 2
    with pytest.raises(CargaInicialError):
        ctrl.aplicar_carga_de_articulos(plan, actor="admin")
    assert ctrl.buscar_articulos("") == ()


def test_la_naturaleza_no_se_adivina_cuando_falta(ctrl, tmp_path):
    """Inferirla del texto pondría a un cristal a descontar stock."""
    archivo = _archivo_csv(tmp_path, "sku,name,nature\nARM-001,Armazón metal,\n")
    plan = ctrl.planificar_carga_de_articulos(archivo)
    assert plan.aplicable is False
    assert "naturaleza" in plan.rechazos[0].motivo.lower()


def test_aplicar_el_plan_crea_categorias_y_marcas_que_faltaban(ctrl, tmp_path):
    archivo = _archivo_csv(tmp_path, (
        "sku,name,nature,category,brand\n"
        "ARM-001,Armazón Vulk,PRODUCTO_STOCKEABLE,Armazones,Vulk\n"
        "ARM-002,Armazón Ray,PRODUCTO_STOCKEABLE,Armazones,RayBan\n"))
    plan = ctrl.planificar_carga_de_articulos(archivo)
    ctrl.aplicar_carga_de_articulos(plan, actor="admin")
    assert {c.name for c in ctrl.listar_categorias()} == {"Armazones"}
    assert {m.name for m in ctrl.listar_marcas()} == {"Vulk", "RayBan"}
    assert len(ctrl.buscar_articulos("")) == 2


def test_la_carga_queda_auditada_con_el_archivo_que_la_origino(ctrl, tmp_path, ruta):
    archivo = _archivo_csv(tmp_path, "sku,name,nature\nARM-001,Armazón,PRODUCTO_STOCKEABLE\n")
    plan = ctrl.planificar_carga_de_articulos(archivo)
    corrida = ctrl.aplicar_carga_de_articulos(plan, actor="admin")
    conexion = sqlite3.connect(str(ruta))
    conexion.row_factory = sqlite3.Row
    try:
        fila = conexion.execute("SELECT * FROM import_runs WHERE id = ?",
                                (corrida.id,)).fetchone()
    finally:
        conexion.close()
    assert fila["file_name"] == "articulos.csv"
    assert len(fila["file_sha256"]) == 64
    assert fila["rows_imported"] == 1
    assert fila["administrator"] == "admin"


def test_el_mismo_archivo_no_se_carga_dos_veces(ctrl, tmp_path):
    archivo = _archivo_csv(tmp_path, "sku,name,nature\nARM-001,Armazón,PRODUCTO_STOCKEABLE\n")
    plan = ctrl.planificar_carga_de_articulos(archivo)
    ctrl.aplicar_carga_de_articulos(plan, actor="admin")
    plan_repetido = ctrl.planificar_carga_de_articulos(archivo)
    with pytest.raises(CargaInicialError) as error:
        ctrl.aplicar_carga_de_articulos(plan_repetido, actor="admin")
    assert "ya se cargó" in str(error.value).lower() or "ya se cargo" in str(error.value).lower()


def test_cargar_el_catalogo_no_crea_una_sola_unidad_de_stock(ctrl, tmp_path, ruta):
    """Catálogo no es stock. Que un artículo exista no lo pone en el depósito."""
    archivo = _archivo_csv(tmp_path, (
        "sku,name,nature\n"
        "ARM-001,Armazón,PRODUCTO_STOCKEABLE\n"
        "ARM-002,Armazón dos,PRODUCTO_STOCKEABLE\n"))
    ctrl.aplicar_carga_de_articulos(
        ctrl.planificar_carga_de_articulos(archivo), actor="admin")
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 2
        assert conexion.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == 0
    finally:
        conexion.close()


# --------------------------------------------------------------------------
# Carga inicial: stock, que es otro hecho
# --------------------------------------------------------------------------


def test_el_stock_inicial_entra_como_ingreso_administrativo_auditado(ctrl, ruta):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    corrida = ctrl.cargar_stock_inicial(
        [(articulo.id, Destination.ASUNCION, 12)],
        actor="rodrigo", origen="recuento físico Asunción 18/08/2026")

    movimientos = ctrl.movimientos_de_articulo(articulo.id)
    assert len(movimientos) == 1
    movimiento = movimientos[0]
    assert movimiento.kind is StockMovementKind.INGRESO_ADMINISTRATIVO
    assert movimiento.quantity == 12
    assert movimiento.destination is Destination.ASUNCION
    assert movimiento.actor == "rodrigo"
    assert movimiento.reason_code == "INVENTARIO_INICIAL"
    assert "recuento físico" in movimiento.note
    assert movimiento.document_kind == "CARGA_INICIAL"
    assert movimiento.document_id == corrida.id
    assert movimiento.occurred_at is not None
    assert ctrl.stock(articulo.id, Destination.ASUNCION) == 12


def test_el_stock_inicial_no_finge_ser_una_compra(ctrl, ruta):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 5)],
                              actor="admin", origen="recuento")
    conexion = sqlite3.connect(str(ruta))
    try:
        assert conexion.execute("SELECT COUNT(*) FROM purchases").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0
    finally:
        conexion.close()
    assert ctrl.movimientos_de_articulo(articulo.id)[0].supplier_id is None


def test_el_stock_inicial_exige_decir_de_donde_salio(ctrl):
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    with pytest.raises(CargaInicialError):
        ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 5)],
                                  actor="admin", origen="")


def test_el_stock_inicial_de_un_no_stockeable_se_rechaza(ctrl):
    servicio = ctrl.guardar_articulo(sku="SERV-01", name="Compostura",
                                     nature=ArticleNature.SERVICIO_NO_STOCKEABLE,
                                     actor="admin")
    with pytest.raises(Exception):
        ctrl.cargar_stock_inicial([(servicio.id, Destination.ASUNCION, 5)],
                                  actor="admin", origen="recuento")


def test_el_stock_inicial_es_idempotente_por_corrida(ctrl):
    """Volver a apretar el botón no puede duplicar el inventario."""
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    corrida = ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 12)],
                                        actor="admin", origen="recuento",
                                        run_id="recuento-asuncion-2026-08-18")
    otra = ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 12)],
                                     actor="admin", origen="recuento",
                                     run_id="recuento-asuncion-2026-08-18")
    assert otra.id == corrida.id
    assert ctrl.stock(articulo.id, Destination.ASUNCION) == 12


def test_el_stock_inicial_no_se_corrige_borrando(ctrl):
    """Si el recuento estuvo mal, se compensa. El movimiento queda."""
    articulo = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                     nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                     actor="admin")
    ctrl.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 12)],
                              actor="admin", origen="recuento")
    movimiento = ctrl.movimientos_de_articulo(articulo.id)[0]
    ctrl.compensar_movimiento(movimiento.id, actor="admin",
                              motivo="ERROR_INVENTARIO",
                              observacion="el recuento contó una caja dos veces")
    assert len(ctrl.movimientos_de_articulo(articulo.id)) == 2
    assert ctrl.stock(articulo.id, Destination.ASUNCION) == 0


# --------------------------------------------------------------------------
# El escenario completo, punta a punta
# --------------------------------------------------------------------------


def test_circuito_completo_compra_stock_venta(ctrl, ruta):
    from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem

    # 1. catálogo
    proveedor = ctrl.guardar_proveedor(name="Distribuidora Sur", document="80012345-6",
                                       actor="admin")
    armazon = ctrl.guardar_articulo(sku="ARM-001", name="Armazón Vulk",
                                    nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                    sale_price=280_000, actor="admin")
    cristal = ctrl.guardar_articulo(sku="CRIS-ORG", name="Cristal orgánico",
                                    nature=ArticleNature.TRABAJO_BAJO_PEDIDO,
                                    sale_price=250_000, actor="admin")

    # 2. compra distribuida y confirmada
    compra = ctrl.crear_compra_borrador(
        supplier_id=proveedor.id, document_date=date(2026, 8, 18),
        document_number="001-001-0000123", condition="CONTADO",
        lineas=[{"article_id": armazon.id, "quantity": 10, "unit_cost": 150_000,
                 "distribucion": {Destination.ASUNCION: 6, Destination.PILAR: 4}}],
        actor="admin")
    assert ctrl.revisar_compra(compra.id).confirmable is True
    ctrl.confirmar_compra(compra.id, actor="admin")
    assert ctrl.stock(armazon.id, Destination.ASUNCION) == 6
    assert ctrl.stock(armazon.id, Destination.PILAR) == 4

    # 3. venta en Asunción, armazón + cristal
    caja = ctrl.repositorio_de_caja()
    dia = CashDay(business_date=date(2026, 8, 18), unit="PC", opening_cash=0,
                  opened_by="ana")
    dia.add_entry(CashEntry(
        description="Venta Juana Pérez", saleswoman="ana", total=530_000,
        cash=530_000,
        items=(SaleItem(description="Armazón Vulk + cristal",
                        frame_price=280_000, lens_price=250_000,
                        article_id=armazon.id, lens_article_id=cristal.id),)))
    caja.save(dia)

    # 4. el stock bajó sólo en Asunción y sólo el armazón
    assert ctrl.stock(armazon.id, Destination.ASUNCION) == 5
    assert ctrl.stock(armazon.id, Destination.PILAR) == 4
    assert ctrl.movimientos_de_articulo(cristal.id) == []

    # 5. trazabilidad de punta a punta
    salida = [m for m in ctrl.movimientos_de_articulo(armazon.id)
              if m.kind is StockMovementKind.VENTA][0]
    origen_venta = ctrl.origen_de_movimiento(salida.id)
    assert origen_venta["entry_description"] == "Venta Juana Pérez"
    assert origen_venta["unit"] == "PC"

    entrada = [m for m in ctrl.movimientos_de_articulo(armazon.id)
               if m.kind is StockMovementKind.INGRESO_COMPRA
               and m.destination is Destination.ASUNCION][0]
    origen_compra = ctrl.origen_de_movimiento(entrada.id)
    assert origen_compra["document_number"] == "001-001-0000123"
    assert origen_compra["supplier_name"] == "Distribuidora Sur"


def test_una_venta_sin_stock_se_rechaza_en_el_circuito(ctrl):
    from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
    from modulos.comercial.application.stock_ledger import StockInsuficiente

    armazon = ctrl.guardar_articulo(sku="ARM-001", name="Armazón",
                                    nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                    actor="admin")
    caja = ctrl.repositorio_de_caja()
    dia = CashDay(business_date=date(2026, 8, 18), unit="PC", opening_cash=0,
                  opened_by="ana")
    dia.add_entry(CashEntry(
        description="Venta", saleswoman="ana", total=280_000, cash=280_000,
        items=(SaleItem(description="Armazón", frame_price=280_000,
                        article_id=armazon.id),)))
    with pytest.raises(StockInsuficiente):
        caja.save(dia)
    assert ctrl.stock(armazon.id, Destination.ASUNCION) == 0


def test_todo_sobrevive_a_reabrir_la_aplicacion(ruta):
    """Nada de esto vive en memoria."""
    primero = build_comercial_controller(ruta)
    primero.vincular_caja_a_sucursal("PC", "ASUNCION", actor="admin")
    articulo = primero.guardar_articulo(sku="ARM-001", name="Armazón",
                                        nature=ArticleNature.PRODUCTO_STOCKEABLE,
                                        actor="admin")
    primero.cargar_stock_inicial([(articulo.id, Destination.ASUNCION, 9)],
                                 actor="admin", origen="recuento")
    primero.close()

    segundo = build_comercial_controller(ruta)
    try:
        assert segundo.obtener_articulo(articulo.id).sku == "ARM-001"
        assert segundo.stock(articulo.id, Destination.ASUNCION) == 9
        assert segundo.buscar_para_venta("armazón", unidad="PC")[0].stock == 9
    finally:
        segundo.close()


# --------------------------------------------------------------------------
# La pantalla
# --------------------------------------------------------------------------


def test_existe_la_ventana_comercial_con_sus_tres_pestanas():
    fuente = FUENTE_UI.read_text(encoding="utf-8")
    assert "class VentanaComercial" in fuente
    for pestana in ("Artículos", "Proveedores", "Compras"):
        assert f'"{pestana}"' in fuente


def test_la_pantalla_no_le_muestra_ids_tecnicos_al_operador():
    fuente = FUENTE_UI.read_text(encoding="utf-8")
    for tecnico in ("event_effects", "idempotency_key", "event_id",
                    "PURCHASE_CONFIRMED", "SALE_COMPLETED"):
        assert f'text="{tecnico}"' not in fuente
        assert f'values=("{tecnico}"' not in fuente


def test_la_pantalla_permite_crear_categoria_y_marca_sin_irse():
    fuente = FUENTE_UI.read_text(encoding="utf-8")
    assert "+ Crear" in fuente
    assert "crear_categoria" in fuente
    assert "crear_marca" in fuente


def test_la_pantalla_usa_el_mismo_toolkit_que_caja():
    fuente = FUENTE_UI.read_text(encoding="utf-8")
    assert "import customtkinter as ctk" in fuente


def test_la_venta_tiene_buscador_de_articulo_en_caja():
    fuente = FUENTE_CAJA.read_text(encoding="utf-8")
    assert "def abrir_buscador_de_articulo" in fuente
    assert "article_id" in fuente
    assert "lens_article_id" in fuente


def test_el_item_de_venta_lleva_el_articulo_elegido():
    """El vínculo tiene que llegar al SaleItem o el selector no sirve de nada."""
    fuente = FUENTE_CAJA.read_text(encoding="utf-8")
    inicio = fuente.index("def construir_item_producto_visible")
    fin = fuente.index("\ndef ", inicio + 10)
    constructor = fuente[inicio:fin]
    assert "article_id=" in constructor
    assert "lens_article_id=" in constructor


# --------------------------------------------------------------------------
# Migración
# --------------------------------------------------------------------------


def test_la_cadena_de_migraciones_incluye_la_026_completa(ruta, ctrl):
    from tests.migration_chain import afirmar_cadena_completa_con
    conexion = sqlite3.connect(str(ruta))
    try:
        afirmar_cadena_completa_con(conexion, "026")
    finally:
        conexion.close()


def test_la_026_es_aditiva():
    from tests.migration_chain import MIGRATIONS_DIR
    sql = (MIGRATIONS_DIR / "026_comercial_ui_carga_inicial.sql").read_text(
        encoding="utf-8").upper()
    for prohibido in ("DROP ", "DELETE FROM"):
        assert prohibido not in sql, f"la migración no puede contener {prohibido}"
    for linea in sql.splitlines():
        if "ALTER TABLE" in linea:
            assert "ADD COLUMN" in linea and "ARTICLES" in linea, linea
        if "UPDATE " in linea:
            assert "BEFORE UPDATE ON" in linea, linea


def test_el_motivo_de_inventario_inicial_esta_sembrado(ruta, ctrl):
    conexion = sqlite3.connect(str(ruta))
    conexion.row_factory = sqlite3.Row
    try:
        fila = conexion.execute(
            "SELECT * FROM administrative_entry_reasons WHERE code='INVENTARIO_INICIAL'"
        ).fetchone()
    finally:
        conexion.close()
    assert fila is not None
    assert fila["requires_note"] == 1
