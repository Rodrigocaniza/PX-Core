# -*- coding: utf-8 -*-
"""FactuFácil dentro de BC Caja. Slice 16.

La chica que atiende no sabía qué ventas faltaban cargar en FactuFácil: esa
cuenta la llevaba otra persona, en otro sistema. Lo que se prueba acá es que la
lista salga de las ventas que ya están en Caja, que marcar una no toque un solo
guaraní del día, y que revertir deje dicho por qué.
"""

from __future__ import annotations

from datetime import date

import pytest

from modulos.caja_diaria.application.factufacil import (
    CARGADA,
    PARA_CARGAR,
    FactuFacilService,
)
from modulos.caja_diaria.application.carry_forward import (
    PreviousClosedDayCarryForwardPolicy,
)
from modulos.caja_diaria.application.services import CashDayService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import CashDay, CashEntry, SaleItem
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

ACTOR = "ana"


@pytest.fixture()
def ruta(tmp_path):
    return tmp_path / "bc_caja.sqlite3"


@pytest.fixture()
def repo(ruta):
    repositorio = SQLiteCashDayRepository(ruta)
    repositorio.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    repositorio.bind_register_to_branch("P2", "PILAR", assigned_by="admin")
    yield repositorio
    repositorio.close()


@pytest.fixture()
def ff(repo):
    return FactuFacilService(repo)


def _venta(descripcion="Maria Gonzalez", *, sobre="1001", total=450000,
           vendedora="ana", documento="1234567", telefono="0981111222",
           observaciones="", items=()):
    return CashEntry(
        description=descripcion, envelope=sobre, total=total, cash=total,
        saleswoman=vendedora, customer_document=documento,
        customer_phone=telefono, observations=observaciones, items=tuple(items))


def _guardar(repo, *entradas, dia=date(2026, 8, 19), caja="PC", abierto=0):
    jornada = CashDay(business_date=dia, unit=caja, opening_cash=abierto,
                      opened_by=ACTOR, entries=tuple(entradas))
    repo.save(jornada)
    return repo.get_by_date_and_unit(dia, caja)


# --------------------------------------------------------------------------
# 1-2. Qué entra en PARA CARGAR y qué no
# --------------------------------------------------------------------------

def test_una_venta_valida_aparece_en_para_cargar(repo, ff):
    _guardar(repo, _venta())
    pendientes = ff.listar(estado=PARA_CARGAR)
    assert [f.cliente for f in pendientes] == ["Maria Gonzalez"]
    assert pendientes[0].estado == PARA_CARGAR
    assert pendientes[0].etiqueta_estado == "PARA CARGAR"


def test_una_venta_anulada_no_aparece(repo, ff):
    """Se anula por el mismo camino que usa la pantalla, no a mano."""
    dia = _guardar(repo, _venta(), _venta("Jose Ramirez", sobre="1002"))
    servicio = CashDayService(repo, PreviousClosedDayCarryForwardPolicy())
    anulada = servicio.void_entry(dia.id, dia.entries[0].id,
                                  "el cliente se arrepintió", user=ACTOR)
    assert [f.sobre for f in ff.listar()] == ["1002"]
    assert ff.obtener(anulada.id) is None


def test_anular_despues_de_cargar_la_saca_de_las_dos_listas(repo, ff):
    """Y su historia queda: nadie borra que alguien la había cargado."""
    dia = _guardar(repo, _venta())
    entrada = dia.entries[0]
    ff.marcar_cargada(entrada.id, actor="rosa")
    CashDayService(repo, PreviousClosedDayCarryForwardPolicy()).void_entry(
        dia.id, entrada.id, "se anuló después de facturar", user=ACTOR)
    assert ff.listar() == ()
    assert [h["to_state"] for h in ff.historial(entrada.id)] == [CARGADA]


def test_un_gasto_no_es_una_venta_para_facturar(repo, ff):
    _guardar(repo, _venta(), CashEntry(description="Nafta", expenses=50000))
    assert [f.cliente for f in ff.listar()] == ["Maria Gonzalez"]


def test_una_entrega_a_administracion_tampoco(repo, ff):
    _guardar(repo, _venta(),
             CashEntry(description="Entrega a Sol", withdrawal=200000,
                       withdrawal_destination="ADMINISTRACION"))
    assert len(ff.listar()) == 1


def test_una_venta_sin_importe_no_esta_para_cargar(repo, ff):
    """La política, escrita y probada: sin importe no hay nada que facturar."""
    _guardar(repo, _venta(), _venta("Borrador", sobre="1002", total=0))
    assert [f.sobre for f in ff.listar()] == ["1001"]


# --------------------------------------------------------------------------
# 3-7. Marcar, persistir, y que cambie de lista
# --------------------------------------------------------------------------

@pytest.fixture()
def venta_guardada(repo, ff):
    _guardar(repo, _venta())
    return ff.listar()[0]


def test_marcar_como_cargada(ff, venta_guardada):
    assert ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa") is True
    assert ff.obtener(venta_guardada.cash_entry_id).estado == CARGADA


def test_actor_y_timestamp_quedan_guardados(ff, venta_guardada):
    ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    fila = ff.obtener(venta_guardada.cash_entry_id)
    assert fila.cargada_por == "rosa"
    assert fila.cargada_el, "sin hora no se sabe cuándo se cargó"
    historia = ff.historial(venta_guardada.cash_entry_id)
    assert [h["to_state"] for h in historia] == [CARGADA]
    assert historia[0]["actor"] == "rosa"


def test_reiniciar_la_app_conserva_el_estado(ruta, repo, venta_guardada):
    FactuFacilService(repo).marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    repo.close()
    otro = SQLiteCashDayRepository(ruta)
    try:
        fila = FactuFacilService(otro).obtener(venta_guardada.cash_entry_id)
        assert fila.estado == CARGADA and fila.cargada_por == "rosa"
    finally:
        otro.close()


def test_una_cargada_desaparece_de_para_cargar(ff, venta_guardada):
    ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    assert ff.listar(estado=PARA_CARGAR) == ()


def test_una_cargada_aparece_en_cargadas(ff, venta_guardada):
    ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    cargadas = ff.listar(estado=CARGADA)
    assert [f.cash_entry_id for f in cargadas] == [venta_guardada.cash_entry_id]


# --------------------------------------------------------------------------
# 8-9. Revertir
# --------------------------------------------------------------------------

def test_revertir_exige_motivo(ff, venta_guardada):
    ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    with pytest.raises(InvalidCashDayError, match="motivo"):
        ff.revertir(venta_guardada.cash_entry_id, actor="rosa", motivo="   ")


def test_una_revertida_vuelve_a_para_cargar(ff, venta_guardada):
    ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    ff.revertir(venta_guardada.cash_entry_id, actor="sol", motivo="se cargó el sobre equivocado")
    fila = ff.obtener(venta_guardada.cash_entry_id)
    assert fila.estado == PARA_CARGAR
    assert fila.cargada_por == "", "la marca vigente se limpia"
    assert [f.cash_entry_id for f in ff.listar(estado=PARA_CARGAR)] == [venta_guardada.cash_entry_id]


def test_revertir_no_borra_la_historia(ff, venta_guardada):
    ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa")
    ff.revertir(venta_guardada.cash_entry_id, actor="sol", motivo="sobre equivocado")
    historia = ff.historial(venta_guardada.cash_entry_id)
    assert [(h["from_state"], h["to_state"]) for h in historia] == [
        (PARA_CARGAR, CARGADA), (CARGADA, PARA_CARGAR)]
    assert historia[1]["reason"] == "sobre equivocado"
    assert historia[0]["actor"] == "rosa", "quién la cargó sigue estando"


def test_no_se_puede_revertir_algo_que_no_se_cargo(ff, venta_guardada):
    with pytest.raises(InvalidCashDayError):
        ff.revertir(venta_guardada.cash_entry_id, actor="sol", motivo="por las dudas")


# --------------------------------------------------------------------------
# 10-12. Filtros
# --------------------------------------------------------------------------

@pytest.fixture()
def varias(repo, ff):
    _guardar(repo, _venta("Maria Gonzalez", sobre="1001", vendedora="ana"),
             dia=date(2026, 8, 18), caja="PC")
    _guardar(repo, _venta("Jose Ramirez", sobre="1002", vendedora="rosa"),
             dia=date(2026, 8, 19), caja="PC")
    _guardar(repo, _venta("Ana Duarte", sobre="2001", vendedora="ana"),
             dia=date(2026, 8, 19), caja="P2")
    return ff


def test_filtro_por_rango_de_fechas(varias):
    assert len(varias.listar(desde="2026-08-19")) == 2
    assert len(varias.listar(hasta="2026-08-18")) == 1
    assert len(varias.listar(desde="2026-08-18", hasta="2026-08-18")) == 1


def test_filtro_por_sucursal(varias):
    assert [f.sobre for f in varias.listar(sucursal="PILAR")] == ["2001"]
    assert len(varias.listar(sucursal="ASUNCION")) == 2


def test_filtro_por_sobre(varias):
    assert [f.cliente for f in varias.listar(sobre="1002")] == ["Jose Ramirez"]


def test_filtro_por_cliente_y_vendedora(varias):
    assert [f.sobre for f in varias.listar(cliente="Duarte")] == ["2001"]
    assert len(varias.listar(vendedora="ana")) == 2


def test_los_filtros_se_combinan(varias):
    filas = varias.listar(sucursal="ASUNCION", vendedora="ana")
    assert [f.sobre for f in filas] == ["1001"]


def test_el_estado_tiene_que_ser_uno_de_los_dos(varias):
    with pytest.raises(InvalidCashDayError):
        varias.listar(estado="EN_PROCESO")


# --------------------------------------------------------------------------
# 13-14. Copiar y observaciones
# --------------------------------------------------------------------------

def test_copiar_no_modifica_nada(repo, ff):
    _guardar(repo, _venta())
    venta = ff.listar()[0]
    antes = ff.obtener(venta.cash_entry_id)
    texto = ff.texto_para_copiar(venta.cash_entry_id)
    assert texto
    assert ff.obtener(venta.cash_entry_id) == antes
    assert ff.historial(venta.cash_entry_id) == ()


def test_el_texto_copiado_trae_los_campos_que_pide_factufacil(repo, ff):
    _guardar(repo, _venta(observaciones="OD -2.00 OI -1.75 add 2.00"))
    texto = ff.texto_para_copiar(ff.listar()[0].cash_entry_id)
    for rotulo in ("Cliente:", "CI/RUC:", "Teléfono:", "Fecha:", "Sucursal:",
                   "Sobre:", "Vendedora:", "Observaciones:", "Total:"):
        assert rotulo in texto
    assert "Maria Gonzalez" in texto and "ASUNCION" in texto
    assert "450.000" in texto, "el importe se lee como lo lee una persona"


def test_las_observaciones_van_completas(repo, ff):
    receta = ("OD esf -2.00 cil -0.75 eje 90 · OI esf -1.75 cil -0.50 eje 85 · "
              "adición 2.00 · armazón del cliente · avisar cuando llegue")
    _guardar(repo, _venta(observaciones=receta))
    fila = ff.listar()[0]
    assert fila.observaciones == receta, "la receta no se corta"
    assert receta in fila.texto_para_copiar()


# --------------------------------------------------------------------------
# 15-17. No duplicar, no pisar, no tocar la caja
# --------------------------------------------------------------------------

def test_no_duplica_ventas(repo, ff):
    _guardar(repo, _venta(), _venta("Jose Ramirez", sobre="1002"))
    assert len(ff.listar()) == 2
    ff.marcar_cargada(ff.listar()[0].cash_entry_id, actor="rosa")
    assert len(ff.listar()) == 2, "marcar no crea ni borra filas"


def test_marcar_dos_veces_no_duplica_ni_pisa(ff, venta_guardada):
    assert ff.marcar_cargada(venta_guardada.cash_entry_id, actor="rosa") is True
    assert ff.marcar_cargada(venta_guardada.cash_entry_id, actor="sol") is False
    fila = ff.obtener(venta_guardada.cash_entry_id)
    assert fila.cargada_por == "rosa", "la segunda no reescribe quién hizo el trabajo"
    assert len(ff.historial(venta_guardada.cash_entry_id)) == 1


def test_marcar_no_cambia_la_caja_del_dia(repo, ff):
    dia = _guardar(repo, _venta(), _venta("Jose Ramirez", sobre="1002", total=300000))
    antes = dia.totals()
    for fila in ff.listar():
        ff.marcar_cargada(fila.cash_entry_id, actor="rosa")
    despues = repo.get_by_date_and_unit(date(2026, 8, 19), "PC")
    assert despues.totals() == antes
    assert [e.total for e in despues.entries] == [e.total for e in dia.entries]
    assert all(e.revision == 0 for e in despues.entries), "la venta no se revisó"


def test_marcar_exige_responsable(ff, venta_guardada):
    with pytest.raises(InvalidCashDayError, match="responsable"):
        ff.marcar_cargada(venta_guardada.cash_entry_id, actor="  ")


def test_una_venta_editada_despues_de_cargar_se_avisa(repo, ff):
    """No es un estado nuevo ni bloquea: es que lo que se cargó allá dejó de
    coincidir con lo que dice Caja, y alguien tiene que mirarlo."""
    dia = _guardar(repo, _venta())
    entrada = dia.entries[0]
    ff.marcar_cargada(entrada.id, actor="rosa")
    assert ff.obtener(entrada.id).editada_despues_de_cargar is False

    corregida = entrada.edited(description="María González Benítez")
    repo.save(CashDay(id=dia.id, business_date=dia.business_date, unit=dia.unit,
                      opening_cash=dia.opening_cash, opened_by=ACTOR,
                      entries=(corregida,)))
    fila = ff.obtener(entrada.id)
    assert fila.estado == CARGADA, "sigue cargada: nadie la descargó"
    assert fila.editada_despues_de_cargar is True


def test_los_conteos_alimentan_los_chips(repo, ff):
    _guardar(repo, _venta(), _venta("Jose Ramirez", sobre="1002"))
    ff.marcar_cargada(ff.listar()[0].cash_entry_id, actor="rosa")
    assert ff.conteos() == {PARA_CARGAR: 1, CARGADA: 1}
