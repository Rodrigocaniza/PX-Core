import shutil

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.caja_diaria.review_corrections import CajaCorrectionInbox
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.real_sync import ReviewService
from modulos.gestion_central.repository import CentralRepository
from tests.gestion_central.test_real_sync_review import make_snapshot


SOL = Principal("sol", Role.ADMIN_CENTRAL)


def setup_flow(tmp_path, *, branch="Pilar", sales=1):
    source = make_snapshot(tmp_path / f"{branch}.sqlite3", sales=sales)
    service = ReviewService(CentralRepository(tmp_path / "central.sqlite3"))
    service.import_snapshot(SOL, source, branch=branch)
    return service, source


def test_correcto_consolida_una_vez_y_conserva_origen_y_medios(tmp_path):
    service, _ = setup_flow(tmp_path)
    row = service.list_sales(SOL)[0]
    assert service.mark_complete(SOL, row["identity"]) == "REVIEWED"
    assert service.mark_complete(SOL, row["identity"]) == "REVIEWED"
    movements = service.daily_movements(SOL)
    assert len(movements) == 1
    movement = movements[0]
    assert movement["source_entry_id"] == "sale-0"
    assert (movement["total"], movement["cash"], movement["card_transfer"], movement["agreement"]) == (1_000_000, 500_000, 300_000, 200_000)


def test_dos_sucursales_y_dos_dias_no_colisionan(tmp_path):
    service, pilar = setup_flow(tmp_path, branch="Pilar")
    asuncion = make_snapshot(tmp_path / "asuncion.sqlite3", sales=1)
    service.import_snapshot(SOL, asuncion, branch="Asuncion")
    for row in service.list_sales(SOL):
        service.mark_complete(SOL, row["identity"])
    assert {m["branch"] for m in service.daily_movements(SOL)} == {"Pilar", "Asuncion"}
    assert len(service.daily_movements(SOL)) == 2


def test_requiere_correccion_no_consolida_y_outbox_es_idempotente(tmp_path):
    service, _ = setup_flow(tmp_path)
    identity = service.list_sales(SOL)[0]["identity"]
    first = service.require_correction(SOL, identity, "Corregir documento", "customer_document")
    second = service.require_correction(SOL, identity, "Corregir documento", "customer_document")
    assert first == second
    assert service.daily_movements(SOL) == []
    pending = service.pending_corrections(SOL, branch="Pilar")
    assert len(pending) == 1 and pending[0]["reason"] == "Corregir documento"
    assert "Corregir documento" in service.events(SOL, identity)[-1]["details_json"]


def test_correccion_vuelve_a_revision_y_revalidacion_reconsolida_una_vez(tmp_path):
    service, source = setup_flow(tmp_path)
    row = service.list_sales(SOL)[0]
    service.mark_complete(SOL, row["identity"])
    service.require_correction(SOL, row["identity"], "Corregir cliente")
    with SQLiteCashDayRepository(source)._connection() as con:
        con.execute("UPDATE cash_entries SET description='Cliente corregido',revision=revision+1 WHERE id='sale-0'")
        con.commit()
    result = service.import_snapshot(SOL, source, branch="Pilar")
    assert result.changed == 1
    assert service.list_sales(SOL)[0]["review_status"] == "CORRECTED_PENDING_REVALIDATION"
    service.mark_complete(SOL, row["identity"])
    service.mark_complete(SOL, row["identity"])
    assert len(service.daily_movements(SOL)) == 1
    assert len(service.daily_movements(SOL, status="COMPENSATED")) == 1


def test_anulacion_posterior_compensa_y_no_puede_revalidarse(tmp_path):
    service, source = setup_flow(tmp_path)
    identity = service.list_sales(SOL)[0]["identity"]
    service.mark_complete(SOL, identity)
    with SQLiteCashDayRepository(source)._connection() as con:
        con.execute("UPDATE cash_entries SET status='VOIDED',void_reason='prueba',revision=revision+1 WHERE id='sale-0'")
        con.commit()
    service.import_snapshot(SOL, source, branch="Pilar")
    assert service.list_sales(SOL)[0]["review_status"] == "ANNULLED"
    assert service.daily_movements(SOL) == []
    assert len(service.daily_movements(SOL, status="COMPENSATED")) == 1
    with pytest.raises(ValueError):
        service.mark_complete(SOL, identity)


def test_fallo_parcial_hace_rollback_y_retry_seguro(tmp_path, monkeypatch):
    service, _ = setup_flow(tmp_path)
    identity = service.list_sales(SOL)[0]["identity"]
    original = service._consolidate
    monkeypatch.setattr(service, "_consolidate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("corte")))
    with pytest.raises(RuntimeError):
        service.mark_complete(SOL, identity)
    assert service.list_sales(SOL)[0]["review_status"] == "UNREVIEWED"
    assert service.daily_movements(SOL) == []
    monkeypatch.setattr(service, "_consolidate", original)
    service.mark_complete(SOL, identity)
    assert len(service.daily_movements(SOL)) == 1


def test_caja_recibe_correccion_una_vez_y_exige_edicion_auditada(tmp_path):
    service, source = setup_flow(tmp_path)
    identity = service.list_sales(SOL)[0]["identity"]
    service.require_correction(SOL, identity, "Corregir CI", "customer_document")
    correction = service.pending_corrections(SOL)[0]
    inbox = CajaCorrectionInbox(SQLiteCashDayRepository(source))
    assert inbox.receive(correction) is True
    assert inbox.receive(correction) is False
    inbox.mark_seen(correction["id"], "operadora")
    with pytest.raises(ValueError):
        inbox.resolve(correction["id"], actor="operadora", reason="Ajuste pedido")
    with SQLiteCashDayRepository(source)._connection() as con:
        con.execute("UPDATE cash_entries SET customer_document='CI-CORREGIDA',revision=revision+1 WHERE id='sale-0'")
        snapshot = con.execute("SELECT * FROM cash_entries WHERE id='sale-0'").fetchone()
        con.execute("INSERT INTO cash_entry_revisions(entry_id,cash_day_id,revision,action,snapshot_json,recorded_at) VALUES(?,?,?,?,?,?)",
                    ("sale-0","day",snapshot["revision"],"UPDATE",'{"audit":{"reason":"Corrección pedida por Sol","user":"operadora"}}',"2099-02-20T12:00:00-03:00"))
        con.commit()
    assert inbox.resolve(correction["id"], actor="operadora", reason="Ajuste pedido") == 2
    assert inbox.pending() == []


def test_migracion_es_aditiva_e_idempotente_sobre_base_existente(tmp_path):
    source = make_snapshot(tmp_path / "legacy.sqlite3", sales=1)
    before = SQLiteCashDayRepository(source).list_entry_revisions("sale-0")
    SQLiteCashDayRepository(source)
    SQLiteCashDayRepository(source)
    after = SQLiteCashDayRepository(source).list_entry_revisions("sale-0")
    assert after == before
