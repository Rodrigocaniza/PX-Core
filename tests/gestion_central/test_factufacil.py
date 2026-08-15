from dataclasses import replace
from pathlib import Path

import pytest

from modulos.gestion_central.factufacil import FACTUFACIL_STATES, FIELD_ORDER, FactuFacilSale, FactuFacilService
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied, CentralManagementService


SOL=Principal("sol",Role.ADMIN_CENTRAL);AUDITOR=Principal("audit",Role.AUDITOR)


def sample(**changes):
    values=dict(branch="Casa Central",source_sale_id="sale-001",customer="Cliente Sintético",document="RUC-001",receipt_number="B-001",date="2099-04-10",cashbox="CAJA-01",envelope="S-001",prescription="OD -1.25\nOI -1.00\nDP 62",items=({"description":"Armazón sintético","price":400000},{"description":"Cristales sintéticos","price":600000}),total=1000000,payment_method="EFECTIVO + TARJETA",paid=900000,balance=100000,saleswoman="Vendedora Piloto")
    values.update(changes);return FactuFacilSale(**values)


@pytest.fixture
def service(tmp_path):return FactuFacilService(CentralManagementService(CentralRepository(tmp_path/"central.sqlite3")))


def test_register_filters_multibranch_and_persistence(service):
    first=service.register(SOL,sample());assert first[1]
    assert service.register(SOL,sample())==(first[0],False)
    service.register(SOL,sample(branch="Pilar",source_sale_id="sale-002",envelope="S-002",customer="Otra Persona"))
    assert len(service.list_sales(SOL))==2
    assert len(service.list_sales(SOL,start="2099-04-01",end="2099-04-30",branch="Pilar",envelope="002",customer="Otra",status="PARA_CARGAR"))==1
    restarted=FactuFacilService(CentralManagementService(CentralRepository(service.repository.database_path)))
    assert len(restarted.list_sales(SOL))==2


def test_ordered_copy_contract_and_multiline_prescription(service):
    sale_id,_=service.register(SOL,sample());export=service.ordered_export(SOL,sale_id)
    assert tuple(field["name"] for field in export["fields"])==FIELD_ORDER
    prescription=next(field["value"] for field in export["fields"] if field["name"]=="prescription")
    assert prescription=="OD -1.25\nOI -1.00\nDP 62"
    items=next(field["value"] for field in export["fields"] if field["name"]=="items")
    assert items[1]=={"description":"Cristales sintéticos","price":600000}


def test_loaded_duplicate_idempotency_and_prior_warning(service):
    sale_id,_=service.register(SOL,sample());service.start(SOL,sale_id)
    assert service.mark_loaded(SOL,sale_id,"Leti","FAC-100");assert not service.mark_loaded(SOL,sale_id,"Leti","FAC-100")
    with pytest.raises(ValueError,match="ya cargada por Leti.*FAC-100"):service.mark_loaded(SOL,sale_id,"Ana","FAC-101")
    row=service.get(SOL,sale_id);assert row["status"]=="CARGADO" and row["loaded_by"]=="Leti"


def test_revert_requires_reason_and_history_is_append_only(service):
    sale_id,_=service.register(SOL,sample());service.mark_loaded(SOL,sale_id,"Dayana","FAC-200")
    with pytest.raises(ValueError,match="motivo"):service.revert(SOL,sale_id," ")
    service.revert(SOL,sale_id,"Comprobante digitado incorrectamente");service.prepare_again(SOL,sale_id)
    history=service.history(SOL,sale_id);assert [h["action"] for h in history]==["SALE_REGISTERED","MARKED_LOADED","LOAD_REVERTED","PREPARED_AGAIN"]


def test_loaded_sale_source_edit_becomes_observed_and_versions_remain(service):
    sale_id,_=service.register(SOL,sample());service.mark_loaded(SOL,sale_id,"Leti","FAC-300")
    updated=replace(sample(),prescription="Línea 1 original\nLínea 2 corregida")
    assert service.register(SOL,updated)==(sale_id,True)
    row=service.get(SOL,sale_id);assert row["status"]=="OBSERVADO" and row["version"]==2
    with service.repository.connection() as con:assert con.execute("SELECT count(*) FROM factufacil_versions WHERE sale_id=?",(sale_id,)).fetchone()[0]==2


def test_same_branch_envelope_cannot_silently_duplicate(service):
    service.register(SOL,sample())
    with pytest.raises(ValueError,match="sobre ya registrado"):service.register(SOL,sample(source_sale_id="other-sale"))


def test_permissions_and_state_contract(service):
    sale_id,_=service.register(SOL,sample());assert set(FACTUFACIL_STATES)=={"PARA_CARGAR","EN_PROCESO","CARGADO","OBSERVADO","REVERTIDO"};assert service.get(AUDITOR,sale_id)
    with pytest.raises(AccessDenied):service.mark_loaded(AUDITOR,sale_id,"Audit","X")
    with pytest.raises(AccessDenied):service.list_sales(Principal("local",Role.OPERADOR_LOCAL))


def test_no_external_provider_or_secrets_in_module():
    source=Path("modulos/gestion_central/factufacil.py").read_text(encoding="utf-8").lower()
    for forbidden in ("requests","selenium","playwright","http://","https://","password","token"):assert forbidden not in source
