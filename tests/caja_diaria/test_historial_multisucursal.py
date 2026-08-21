from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest
import bc_historial

from modulos.historial_externo.global_history import (
    GlobalHistoryService, HistoryAccessDenied, HistoryAccessPolicy,
    HistoryPrincipal, VIEW_GLOBAL,
)
from modulos.historial_externo.history import HistoryEvent, HistoryQuery, PersonHistory
from modulos.historial_externo.sqlite_reader import SQLiteHistoryReader


class FakeSource:
    def __init__(self, *events):
        self.events = events

    def search(self, _query, *, limit=200):
        return PersonHistory(events=tuple(self.events[:limit]))


def event(branch, reference, *, document="1234567", name="Ana López", phone="0981"):
    return HistoryEvent(
        "2026-08-21T10:00:00" if branch == "ASUNCION" else "2026-08-20T10:00:00",
        "VENTA", branch=branch, envelope=reference, description="Cristales",
        identity_document=document, identity_name=name, identity_phone=phone,
        source_reference=reference)


def principal(branch, role="OPERADOR", permissions=frozenset({VIEW_GLOBAL})):
    return HistoryPrincipal("persona-1", role, branch, permissions)


def test_a_compra_asuncion_visible_desde_pilar():
    result = GlobalHistoryService([FakeSource(event("ASUNCION", "A-1"))]).search(
        principal("PILAR"), HistoryQuery(document="1234567"))
    assert result.selected.events[0].branch == "ASUNCION"


def test_b_compra_pilar_visible_desde_asuncion():
    result = GlobalHistoryService([FakeSource(event("PILAR", "P-1"))]).search(
        principal("ASUNCION"), HistoryQuery(document="1234567"))
    assert result.selected.events[0].branch == "PILAR"


def test_c_identidad_fuerte_une_eventos_de_ambas_sucursales():
    service = GlobalHistoryService([
        FakeSource(event("ASUNCION", "A-1", document="1.234.567")),
        FakeSource(event("PILAR", "P-1", document="1234567"))])
    result = service.search(principal("PILAR"), HistoryQuery(document="1234567"))
    assert result.identity_resolution == "STRONG_DOCUMENT"
    assert len(result.candidates) == 1
    assert [item.branch for item in result.selected.events] == ["ASUNCION", "PILAR"]


def test_d_cada_evento_conserva_sucursal_fecha_tipo_y_sobre():
    result = GlobalHistoryService([FakeSource(
        event("ASUNCION", "A-1"), event("PILAR", "P-1"))]).search(
            principal("ASUNCION"), HistoryQuery(document="1234567"))
    assert {(item.branch, item.occurred_at, item.kind, item.envelope)
            for item in result.selected.events} == {
                ("ASUNCION", "2026-08-21T10:00:00", "VENTA", "A-1"),
                ("PILAR", "2026-08-20T10:00:00", "VENTA", "P-1")}


@pytest.mark.parametrize("origin,target", [("ASUNCION", "PILAR"), ("PILAR", "ASUNCION")])
def test_e_f_operador_no_modifica_sucursal_ajena(origin, target):
    policy = HistoryAccessPolicy()
    assert policy.can_modify_branch(principal(origin), origin)
    assert not policy.can_modify_branch(principal(origin), target)


def test_g_direccion_puede_operar_ambas_segun_rol_admin():
    policy = HistoryAccessPolicy(); admin = principal("ASUNCION", "ADMIN")
    assert policy.can_modify_branch(admin, "ASUNCION")
    assert policy.can_modify_branch(admin, "PILAR")


def test_h_proyeccion_operativa_no_expone_campos_administrativos():
    exposed = {item.name for item in fields(HistoryEvent)}
    forbidden = {"unit_cost", "cost", "margin", "commission", "cash_closure",
                 "configuration", "credentials", "internal_audit"}
    assert exposed.isdisjoint(forbidden)


def test_identidad_debil_no_fusiona_homonimos():
    service = GlobalHistoryService([
        FakeSource(event("ASUNCION", "A-1", document="", name="Juan Pérez")),
        FakeSource(event("PILAR", "P-1", document="", name="Juan Pérez"))])
    result = service.search(principal("ASUNCION"), HistoryQuery(name="Juan Pérez"))
    assert result.identity_resolution == "AMBIGUOUS"
    assert result.selected is None
    assert len(result.candidates) == 2


def test_consulta_global_exige_claim_autorizado():
    service = GlobalHistoryService([FakeSource(event("ASUNCION", "A-1"))])
    with pytest.raises(HistoryAccessDenied):
        service.search(principal("ASUNCION", permissions=frozenset()), HistoryQuery(name="Ana"))


def test_cli_falla_cerrada_y_no_acepta_roles_autodeclarados():
    with pytest.raises(SystemExit, match="sesión autenticada"):
        bc_historial.main([])
    with pytest.raises(SystemExit):
        bc_historial.build_parser().parse_args(["--role", "ADMIN"])


def test_i_j_k_adaptador_permanece_read_only_sin_db_ni_migracion_paralela():
    source = Path(SQLiteHistoryReader.__module__.replace(".", "/") + ".py")
    repository_source = (Path(__file__).parents[2] / source).read_text(encoding="utf-8")
    assert "mode=ro" in repository_source and "query_only" in repository_source
    for mutation in ("CREATE TABLE", "INSERT INTO", "UPDATE ", "DELETE FROM", ".migrate("):
        assert mutation not in repository_source
