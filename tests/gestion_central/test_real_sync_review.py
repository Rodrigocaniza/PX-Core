from pathlib import Path

import pytest

from bc_gestion_central import import_readonly_snapshot
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.real_sync import REVIEW_FIELDS, ReviewService
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied


ADMIN = Principal("sol", Role.ADMIN_CENTRAL)
AUDITOR = Principal("auditora", Role.AUDITOR)
LOCAL_PILAR = Principal("sucursal.pilar", Role.OPERADOR_LOCAL)


def make_snapshot(path: Path, *, changed=False):
    repo = SQLiteCashDayRepository(path)
    with repo._connection() as con:
        con.execute("INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at,closed_at,version) VALUES('day','2099-02-20','PC',500000,'CLOSED','2099-02-20T08:00:00-03:00','2099-02-20T18:00:00-03:00',1)")
        for index in range(3):
            name = "Cliente Sintético Ajustado" if changed and index == 0 else f"Cliente Sintético {index + 1}"
            con.execute("""INSERT INTO cash_entries(id,cash_day_id,description,envelope,total,cash,card_check,agreement_amount,balance_text,customer_document,customer_phone,saleswoman,delivery_date,observations,performed_by,created_at,updated_at,revision)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(f"sale-{index}","day",name,f"S-{index+1:03d}",1000000+index,500000,300000,200000,"0",f"DOC-{index}",f"09810000{index}","Vendedora Piloto","2099-02-25","Observación sintética","operador.piloto","2099-02-20T10:00:00-03:00","2099-02-20T10:00:00-03:00",2 if changed and index==0 else 1))
            con.execute("INSERT INTO sale_items(id,cash_entry_id,position,description,code,item_type,frame_price,lens_price,laboratory,prescription_doctor) VALUES(?,?,?,?,?,?,?,?,?,?)",(f"item-{index}",f"sale-{index}",0,"Armazón sintético",f"COD-{index}","ARMAZON",400000,600000,"Laboratorio Piloto","Dra. Prueba"))
        con.commit()
    repo.close()
    return path


@pytest.fixture
def review(tmp_path):
    snapshot = make_snapshot(tmp_path / "snapshot.sqlite3")
    service = ReviewService(CentralRepository(tmp_path / "central.sqlite3"))
    return service, snapshot, tmp_path


def test_import_latest_closed_snapshot_integrity_and_idempotency(review):
    service, snapshot, _ = review
    first=service.import_snapshot(ADMIN,snapshot,organization="BC",branch="Pilar")
    second=service.import_snapshot(ADMIN,snapshot,organization="BC",branch="Pilar")
    assert (first.period,first.unit,first.processed,first.inserted)==("2099-02-20","PC",3,3)
    assert (second.inserted,second.unchanged,second.changed)==(0,3,0)
    assert len(service.list_sales(ADMIN))==3
    assert len(service.snapshot_hash(snapshot))==64


def test_individual_complete_bulk_and_idempotent_review(review):
    service,snapshot,_=review; service.import_snapshot(ADMIN,snapshot); ids=[r["identity"] for r in service.list_sales(ADMIN)]
    assert service.mark_fields(ADMIN,ids[0],["customer_name","envelope"])=="IN_REVIEW"
    assert service.reviewed_fields(ADMIN,ids[0])=={"customer_name","envelope"}
    assert service.mark_complete(ADMIN,ids[0])=="REVIEWED"
    assert service.mark_many(ADMIN,ids[1:])==2
    assert service.mark_many(ADMIN,ids[1:])==2
    assert service.progress(ADMIN)=={"total":3,"reviewed":3,"pending":0,"observations":0,"percent":100}


def test_notes_reopen_alerts_are_append_only_and_do_not_touch_source(review):
    service,snapshot,_=review; before=service.snapshot_hash(snapshot); service.import_snapshot(ADMIN,snapshot); identity=service.list_sales(ADMIN)[0]["identity"]
    service.mark_complete(ADMIN,identity); service.add_note(ADMIN,identity,"Revisar receta",field_name="prescription"); service.add_note(ADMIN,identity,"Segunda observación")
    service.require_correction(ADMIN,identity,"Dato requiere corrección local")
    key=service.create_branch_alert(ADMIN,identity,"Verificar dato en sucursal")
    assert len(service.notes(ADMIN,identity))==2
    assert service.list_sales(ADMIN)[0]["review_status"]=="REQUIRES_CORRECTION"
    assert len(key)==64 and service.snapshot_hash(snapshot)==before
    with service.repository.connection() as con:
        assert con.execute("SELECT status FROM review_alert_outbox").fetchone()[0]=="PENDING"
    assert {e["action"] for e in service.events(ADMIN,identity)} >= {"FIELDS_REVIEWED","NOTE_ADDED","REOPEN_CORRECTION"}


def test_changed_version_invalidates_only_affected_review(review):
    service,snapshot,tmp=review; service.import_snapshot(ADMIN,snapshot); identity=service.list_sales(ADMIN)[0]["identity"]
    service.mark_fields(ADMIN,identity,["customer_name","envelope","total"])
    changed=make_snapshot(tmp/"changed.sqlite3",changed=True); result=service.import_snapshot(ADMIN,changed)
    assert result.changed==1
    assert service.reviewed_fields(ADMIN,identity)=={"envelope","total"}
    row=next(r for r in service.list_sales(ADMIN) if r["identity"]==identity)
    assert row["review_status"]=="CORRECTED_PENDING_REVALIDATION"
    event=next(e for e in service.events(ADMIN,identity) if e["action"]=="SOURCE_CHANGED")
    assert "customer_name" in event["details_json"]


def test_filters_branch_isolation_and_permissions(review):
    service,snapshot,_=review; service.import_snapshot(ADMIN,snapshot,branch="Pilar"); service.import_snapshot(ADMIN,snapshot,branch="Asunción")
    assert len(service.list_sales(ADMIN,cashbox="PC"))==6
    assert len(service.list_sales(ADMIN,date="2099-02-20",saleswoman="Piloto",envelope="S-001"))==2
    with pytest.raises(AccessDenied): service.mark_complete(AUDITOR,service.list_sales(AUDITOR)[0]["identity"])
    with pytest.raises(AccessDenied): service.list_sales(LOCAL_PILAR)
    assert len(service.list_sales(AUDITOR))==6


def test_review_state_persists_after_service_restart(review):
    service,snapshot,_=review; service.import_snapshot(ADMIN,snapshot); identity=service.list_sales(ADMIN)[0]["identity"]; service.mark_complete(ADMIN,identity)
    restarted=ReviewService(service.repository)
    assert restarted.list_sales(ADMIN)[0]["review_status"]=="REVIEWED"
    assert restarted.reviewed_fields(ADMIN,identity)==set(REVIEW_FIELDS)


def test_no_mail_or_telegram_capability_in_real_sync_module():
    source=Path("modulos/gestion_central/real_sync.py").read_text(encoding="utf-8").lower()
    assert "smtplib" not in source and "telegram" not in source and "requests" not in source


def test_cli_snapshot_import_writes_safe_local_evidence(tmp_path):
    snapshot = make_snapshot(tmp_path / "source.sqlite3")
    source_before = snapshot.read_bytes()
    data_dir = tmp_path / "central-data"
    assert import_readonly_snapshot(
        data_dir, snapshot, organization="BC", branch="Pilar", period="2099-02-20",
    ) == 0
    evidence = (data_dir / "RealSync" / "last-import.local.json").read_text(encoding="utf-8")
    assert '"source_mode": "SQLITE_SNAPSHOT_QUERY_ONLY"' in evidence
    assert '"production_write": false' in evidence
    assert snapshot.read_bytes() == source_before
