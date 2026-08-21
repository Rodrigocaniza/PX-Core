# -*- coding: utf-8 -*-
"""Actualización parcial de artículos. Slice 14.

Estas pruebas existen por un daño real. Durante V1-010 y V1-013 se cambió la
naturaleza de cuatro artículos y las notas de un quinto llamando a
`guardar_articulo` con los cuatro campos que interesaban. Como esa operación
reemplaza el artículo entero, los campos que nadie nombró volvieron a su valor
por defecto: cinco artículos perdieron categoría y marca sin que nada avisara.

No se perdió stock ni dinero —eran etiquetas—, pero la próxima vez podía tocarle
al precio. Lo que se fija acá no es el dato: es que la operación de tocar unos
pocos campos exista y conserve el resto.
"""

from __future__ import annotations

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.comercial.application.comercial_controller import (
    ComercialError,
    build_comercial_controller,
)
from modulos.comercial.domain.models import ArticleNature

ACTOR = "prueba"


@pytest.fixture()
def ruta(tmp_path):
    destino = tmp_path / "bc_caja.sqlite3"
    SQLiteCashDayRepository(destino).close()  # aplica la cadena 001..027
    return destino


@pytest.fixture()
def ctrl(ruta):
    controlador = build_comercial_controller(ruta)
    yield controlador
    controlador.close()


@pytest.fixture()
def completo(ctrl):
    """Un artículo con todos los campos puestos, como los del catálogo real."""
    categoria = ctrl.crear_categoria("Compostura", actor=ACTOR)
    marca = ctrl.crear_marca("Optica San Cayetano", actor=ACTOR)
    return ctrl.guardar_articulo(
        sku="2000056", name="Par de patillas",
        nature=ArticleNature.PRODUCTO_STOCKEABLE, actor=ACTOR,
        category_id=categoria.id, brand_id=marca.id, unit="PAR",
        sale_price=45000, location="Vitrina 3", min_stock=2,
        barcode="7790001234567", notes="importado de Inventario P2, fila 118")


# --------------------------------------------------------------------------
# El defecto que causó el daño
# --------------------------------------------------------------------------


def test_guardar_articulo_reemplaza_todo_y_por_eso_borro_los_metadatos(ctrl, completo):
    """La reproducción exacta de lo que pasó en V1-010: no es un accidente
    aleatorio, es lo que hace un reemplazo cuando se lo usa como si fuera una
    modificación parcial. Queda fijado para que nadie lo confunda con un bug
    intermitente."""
    ctrl.guardar_articulo(
        sku=completo.sku, name=completo.name,
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE, actor=ACTOR,
        notes="corregido", article_id=completo.id)
    quedo = ctrl.obtener_articulo(completo.id)
    assert quedo.nature is ArticleNature.SERVICIO_NO_STOCKEABLE
    assert quedo.category_id is None and quedo.brand_id is None
    assert quedo.sale_price is None and quedo.barcode is None


# --------------------------------------------------------------------------
# La operación que lo vuelve imposible
# --------------------------------------------------------------------------


def test_cambiar_la_naturaleza_no_borra_categoria_ni_marca(ctrl, completo):
    """El caso literal de V1-010 sobre Par de patillas, Hilo, Tornillo y
    Plaqueta: pasan a servicio y siguen siendo de Compostura."""
    quedo = ctrl.actualizar_articulo(
        completo.id, actor=ACTOR, nature=ArticleNature.SERVICIO_NO_STOCKEABLE)
    assert quedo.nature is ArticleNature.SERVICIO_NO_STOCKEABLE
    assert quedo.category_id == completo.category_id
    assert quedo.brand_id == completo.brand_id


def test_cambiar_las_notas_no_borra_nada_mas(ctrl, completo):
    """El caso literal de 000010: se le agregó la evidencia del recuento."""
    quedo = ctrl.actualizar_articulo(
        completo.id, actor=ACTOR, notes="100 unidades estimadas, sin conteo exacto")
    assert quedo.notes == "100 unidades estimadas, sin conteo exacto"
    for campo in ("sku", "name", "nature", "category_id", "brand_id", "unit",
                  "sale_price", "location", "min_stock", "barcode", "active"):
        assert getattr(quedo, campo) == getattr(completo, campo), campo


def test_no_borra_el_precio(ctrl, completo):
    """Lo que hubiera pasado si estos artículos hubieran tenido precio."""
    quedo = ctrl.actualizar_articulo(completo.id, actor=ACTOR, location="Vitrina 5")
    assert quedo.sale_price == 45000
    assert quedo.location == "Vitrina 5"


def test_no_borra_proveedor_ni_unidad_que_el_formulario_no_muestra(ctrl, completo):
    """La UI no tiene campo para proveedor ni para unidad. Antes, editar desde
    el formulario los reseteaba igual."""
    quedo = ctrl.actualizar_articulo(completo.id, actor=ACTOR, name="Par de patillas metal")
    assert quedo.unit == "PAR"
    assert quedo.name == "Par de patillas metal"


def test_varios_campos_a_la_vez(ctrl, completo):
    quedo = ctrl.actualizar_articulo(
        completo.id, actor=ACTOR, sale_price=52000, min_stock=5)
    assert (quedo.sale_price, quedo.min_stock) == (52000, 5)
    assert quedo.category_id == completo.category_id


def test_sin_campos_no_cambia_nada(ctrl, completo):
    quedo = ctrl.actualizar_articulo(completo.id, actor=ACTOR)
    for campo in ("sku", "name", "nature", "category_id", "brand_id", "supplier_id",
                  "unit", "sale_price", "location", "min_stock", "barcode",
                  "notes", "active"):
        assert getattr(quedo, campo) == getattr(completo, campo), campo


def test_none_explicito_si_vacia_el_campo(ctrl, completo):
    """La diferencia está entre no nombrar un campo y nombrarlo en blanco. Sin
    esto no habría forma de sacarle la marca a un artículo mal clasificado."""
    quedo = ctrl.actualizar_articulo(completo.id, actor=ACTOR, brand_id=None)
    assert quedo.brand_id is None
    assert quedo.category_id == completo.category_id


def test_restaurar_categoria_y_marca_es_lo_unico_que_toca(ctrl, completo):
    """El movimiento de esta misión, en chico: se rompe y se repara, y lo demás
    queda como estaba después de la rotura."""
    ctrl.guardar_articulo(
        sku=completo.sku, name=completo.name,
        nature=ArticleNature.SERVICIO_NO_STOCKEABLE, actor=ACTOR,
        notes="corregido", article_id=completo.id)
    roto = ctrl.obtener_articulo(completo.id)
    reparado = ctrl.actualizar_articulo(
        completo.id, actor=ACTOR,
        category_id=completo.category_id, brand_id=completo.brand_id)
    assert reparado.category_id == completo.category_id
    assert reparado.brand_id == completo.brand_id
    # No revive la naturaleza vieja ni las notas viejas: el backup es fuente de
    # los campos perdidos, no del registro entero.
    assert reparado.nature is ArticleNature.SERVICIO_NO_STOCKEABLE
    assert reparado.notes == roto.notes


def test_no_acepta_campos_que_el_articulo_no_tiene(ctrl, completo):
    with pytest.raises(ComercialError):
        ctrl.actualizar_articulo(completo.id, actor=ACTOR, precio=1000)


def test_no_acepta_tocar_el_id(ctrl, completo):
    with pytest.raises(ComercialError):
        ctrl.actualizar_articulo(completo.id, actor=ACTOR, id="otro")


def test_un_articulo_que_no_existe_falla_sin_crear_nada(ctrl):
    antes = len(ctrl.buscar_articulos(solo_activos=False))
    with pytest.raises(ComercialError):
        ctrl.actualizar_articulo("no-existe", actor=ACTOR, notes="x")
    assert len(ctrl.buscar_articulos(solo_activos=False)) == antes


def test_queda_auditado_como_edicion(ctrl, completo):
    ctrl.actualizar_articulo(completo.id, actor="rodrigo", notes="cambio")
    acciones = [c.accion for c in ctrl.historial_de_articulo(completo.id)]
    assert acciones[-1] == "EDITA_ARTICULO"


def test_la_baja_logica_conserva_categoria_y_marca(ctrl, completo):
    """`desactivar_articulo` pasó a apoyarse en la modificación parcial: la baja
    de los 766 ausentes de V1-010 no debía perder nada, y sigue sin perderlo."""
    dado_de_baja = ctrl.desactivar_articulo(
        completo.id, actor=ACTOR, motivo="ausente del inventario corregido")
    assert dado_de_baja.active is False
    assert dado_de_baja.category_id == completo.category_id
    assert dado_de_baja.brand_id == completo.brand_id
    assert dado_de_baja.sale_price == 45000
    assert "[baja] ausente del inventario corregido" in dado_de_baja.notes
    assert completo.notes in dado_de_baja.notes
