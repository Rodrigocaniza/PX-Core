"""Fijación de la tasa del período en el boundary económico oficial (generación 6).

La generación 5 fijaba el mes en el **primer cálculo**. De ahí salieron los dos bloqueantes
económicos que esta suite cubre: una fecha mal tipeada fijaba para siempre un mes lejano
(`AB2-g5`), y la siembra de la migración copiaba la tasa de la liquidación más antigua aunque
estuviera revertida y su venta anulada (`AB1-g5`).

La decisión de propietario es que la tasa del período **no se fija en el cálculo**: se fija
cuando existe un hecho económico oficial —`APROBADA` o `PAGADA`—. Antes de eso todo es
provisional y corregible.

Cada prueba nombra el invariante que defiende, no el método que llama.
"""
import sqlite3

import pytest

from modulos.gestion_central.comision_policy import CANONICAL_CODE, CANONICAL_RATE_BP
from modulos.gestion_central.comisiones import (
    POLICY_CANONICAL, PROVISIONAL_STATES, RATING_BOUNDARY_STATES, CommissionSaleInput,
    CommissionService,
)
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)


@pytest.fixture
def service(tmp_path):
    return CommissionService(CentralManagementService(CentralRepository(tmp_path / "central.sqlite3")))


def sale(**changes):
    values = dict(branch="Óptica Asunción", source_sale_id="venta-001", saleswoman="Vendedora Uno",
                  sale_date="2099-04-10", kind="COMUN", total_amount=400_000,
                  initial_paid=400_000, envelope="S-001")
    values.update(changes)
    return CommissionSaleInput(**values)


def active(service, sale_id):
    return next(row for row in service.list_entries(SOL) if row["sale_id"] == sale_id
                and row["status"] != "REVERTIDA")


def rated_periods(service):
    """Períodos fijados **ahora**: el último evento de cada uno, si es `PINNED`."""
    with sqlite3.connect(service.repository.database_path) as con:
        rows = con.execute(
            "SELECT e.period,e.rate_bp,e.event FROM commission_period_rate_events e"
            " JOIN (SELECT period, MAX(id) AS newest FROM commission_period_rate_events GROUP BY period)"
            "   last ON last.period=e.period AND last.newest=e.id")
        return {row[0]: row[1] for row in rows if row[2] == "PINNED"}


def rate_events(service, period=None):
    """Libro completo, en orden: es la traza que no se borra nunca."""
    with sqlite3.connect(service.repository.database_path) as con:
        query = ("SELECT period,event,rate_bp,origin,reason,actor FROM commission_period_rate_events"
                 + (" WHERE period=?" if period else "") + " ORDER BY id")
        return [tuple(row) for row in con.execute(query, (period,) if period else ())]


def audits(service, action):
    return [row for row in service.repository.audit_log(limit=500) if row["action"] == action]


def approve_entry(service, sale_id, responsible="Sol"):
    """Lleva una venta ya cancelada hasta `APROBADA`, que es el boundary de fijación."""
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, responsible)
    return entry_id


# ------------------------------------------------------- comisión provisional sin tasa fijada
def test_el_primer_calculo_no_fija_la_tasa_del_periodo(service):
    """Calcular es provisional: no compromete dinero, así que no puede fijar el mes."""
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["status"] == "CALCULADA" and entry["rate_bp"] == CANONICAL_RATE_BP
    # El importe se calculó, pero el mes sigue sin fijar.
    assert rated_periods(service) == {}
    assert service.policy_for_period(SOL, "2099-04")["pinned"] is False


def test_revisar_tampoco_fija_porque_todavia_no_hay_hecho_economico(service):
    """`REVISADA` es el último estado provisional: avala el cálculo, no el pago."""
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)
    service.review(SOL, active(service, sale_id)["id"])
    assert active(service, sale_id)["status"] == "REVISADA"
    assert "REVISADA" in PROVISIONAL_STATES
    assert rated_periods(service) == {}


# ------------------------------------------------ corrección de estados provisionales
def test_una_publicacion_posterior_corrige_un_periodo_solo_calculado(service):
    """Mientras nadie aprobó nada, el mes sigue siendo corregible: ése es el punto."""
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)
    assert active(service, sale_id)["rate_bp"] == CANONICAL_RATE_BP

    service.set_general_rate(SOL, 250, "2099-01-01", "corrección de la tasa del período")
    service.recalculate(SOL)
    corrected = active(service, sale_id)
    assert corrected["rate_bp"] == 250
    assert corrected["commission_amount"] == 10_000  # 2,50% de 400.000
    assert rated_periods(service) == {}


def test_una_fecha_mal_tipeada_no_fija_un_mes_lejano(service):
    """`AB2-g5`: el tipeo `2136` en lugar de `2099` fijaba ese mes para siempre."""
    sale_id, _ = service.register_sale(SOL, sale(sale_date="2136-07-03"))
    service.recalculate(SOL)
    assert active(service, sale_id)["period"] == "2136-07"
    # El mes equivocado no queda fijado: nadie aprobó ni pagó nada en él.
    assert rated_periods(service) == {}
    assert service.policy_for_period(SOL, "2136-07")["pinned"] is False


def test_una_venta_anulada_tras_el_calculo_no_deja_el_periodo_fijado(service):
    """Anular es la prueba de que el cálculo era provisional: no puede haber fijado nada."""
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)
    service.void_sale(SOL, sale_id, "venta cargada por error")
    assert rated_periods(service) == {}


# ------------------------------------------------------- fijación en el boundary oficial
def test_aprobar_fija_la_tasa_del_periodo(service):
    """`APROBADA` es el primer hecho económico oficial: ahí se fija el mes."""
    sale_id, _ = service.register_sale(SOL, sale())
    approve_entry(service, sale_id)
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert service.policy_for_period(SOL, "2099-04")["pinned"] is True
    assert "APROBADA" in RATING_BOUNDARY_STATES


def test_pagar_fija_el_periodo_aunque_la_aprobacion_llegara_migrada(service):
    """`PAGADA` también fija: una base migrada puede no traer el asiento de aprobación."""
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    with sqlite3.connect(service.repository.database_path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        con.commit()
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}


def test_un_periodo_fijado_ya_no_se_re_tarifa_por_una_publicacion_posterior(service):
    """Publicar hacia adelante nunca reescribe un mes con dinero avalado."""
    sale_id, _ = service.register_sale(SOL, sale())
    approve_entry(service, sale_id)
    service.set_general_rate(SOL, 900, "2099-01-01", "cambio de tasa")
    service.recalculate(SOL)
    entry = active(service, sale_id)
    assert entry["status"] == "APROBADA"
    assert entry["rate_bp"] == CANONICAL_RATE_BP and entry["commission_amount"] == 4_000
    assert entry["approved_by"] == "Sol"


def test_la_fijacion_no_cuelga_del_estado_mientras_quede_otro_hecho_vivo(service):
    """Dos aprobaciones sostienen el mes: retirar una no lo suelta.

    Es la mitad del contrato que sí es durable. La otra mitad —que retirar la **última** sí
    suelta— vive en `test_comision_period_unpin.py`, que es el alcance de la generación 7.
    """
    first, _ = service.register_sale(SOL, sale())
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    entry_id = approve_entry(service, first)
    service.recalculate(SOL)
    other = active(service, second)["id"]
    service.review(SOL, other)
    service.approve(SOL, other, "Sol")
    service.observe(SOL, entry_id, "consulta de la vendedora")
    service.revert(SOL, entry_id, "se rehace la liquidación")
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}


# ------------------------------- imposibilidad de reinterpretar dinero aprobado o pagado
def test_un_recalculo_no_altera_el_importe_de_una_aprobada_del_periodo_fijado(service):
    """Invariante 6: nada reinterpreta en silencio un importe ya avalado."""
    sale_id, _ = service.register_sale(SOL, sale())
    approve_entry(service, sale_id)
    before = active(service, sale_id)
    service.set_general_rate(SOL, 5_000, "2099-01-01", "tasa nueva")
    result = service.recalculate(SOL)
    after = active(service, sale_id)
    assert result["changed"] == 0
    assert (after["rate_bp"], after["commission_amount"], after["status"], after["approved_by"]) == \
           (before["rate_bp"], before["commission_amount"], "APROBADA", before["approved_by"])


def test_una_pagada_queda_fuera_de_todo_recalculo(service):
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    service.set_general_rate(SOL, 5_000, "2099-01-01", "tasa nueva")
    service.recalculate(SOL)
    paid = active(service, sale_id)
    assert (paid["status"], paid["rate_bp"], paid["commission_amount"]) == ("PAGADA", 100, 4_000)


def test_una_venta_nueva_del_mes_fijado_cobra_la_tasa_fijada(service):
    """Coherencia dentro del mes: lo que se fijó gobierna todo el período."""
    first, _ = service.register_sale(SOL, sale())
    approve_entry(service, first)
    service.set_general_rate(SOL, 900, "2099-01-01", "tasa nueva")
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    service.recalculate(SOL)
    entry = active(service, second)
    assert entry["rate_bp"] == CANONICAL_RATE_BP and entry["commission_amount"] == 4_000


# --------------------------------------------------------------------------- migración
def migrated(tmp_path, entries, *, voided_sales=()):
    """Construye una base con liquidaciones ya existentes y vuelve a abrirla.

    Reabrir es lo que dispara la migración: es exactamente el camino por el que una
    instalación vieja llega a este código.
    """
    path = tmp_path / "legado.sqlite3"
    CommissionService(CentralManagementService(CentralRepository(path)))
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        for index, spec in enumerate(entries):
            sale_id = f"sale-{index}"
            con.execute(
                "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
                "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,envelope,"
                "content_hash,payload_json,version,created_at,updated_at)"
                " VALUES(?,?,'Óptica Asunción',?,'Vendedora Uno','COMUN',?,?,?,0,?,?,NULL,'','h','{}',1,?,?)",
                (sale_id, f"key-{index}", f"src-{index}", f"{spec['period']}-05",
                 spec["total"], spec["total"], f"{spec['period']}-05",
                 1 if sale_id in voided_sales else 0, spec["created_at"], spec["created_at"]),
            )
            con.execute(
                "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
                "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
                "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,created_at,updated_at)"
                " VALUES(?,?,1,?,'Óptica Asunción','Vendedora Uno','COMUN',?,?,0,?,?,?,?,?,1,'2026-08-01','GENERAL',?,?,?)",
                (f"entry-{index}", sale_id, spec["period"], spec["status"], spec["total"], spec["total"],
                 spec["rate_bp"], spec["amount"], spec.get("policy_status", POLICY_CANONICAL),
                 CANONICAL_CODE, f"{spec['period']}-05", spec["created_at"], spec["created_at"]),
            )
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(path)))


def test_la_migracion_no_siembra_desde_una_liquidacion_revertida(tmp_path):
    """`AB1-g5`: la más antigua era `REVERTIDA` y su tasa fijaba el mes igual."""
    service = migrated(tmp_path, [
        dict(period="2099-04", status="REVERTIDA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-04", status="APROBADA", rate_bp=500, amount=20_000,
             total=400_000, created_at="2099-04-20T00:00:00"),
    ])
    assert rated_periods(service) == {"2099-04": 500}


def test_la_migracion_no_siembra_desde_una_venta_anulada(tmp_path):
    service = migrated(tmp_path, [
        dict(period="2099-04", status="APROBADA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-04", status="PAGADA", rate_bp=500, amount=20_000,
             total=400_000, created_at="2099-04-20T00:00:00"),
    ], voided_sales={"sale-0"})
    assert rated_periods(service) == {"2099-04": 500}


def test_la_migracion_nunca_inventa_una_tasa_para_un_mes_solo_provisional(tmp_path):
    """Un mes que nadie aprobó ni pagó queda **sin fijar**, y por lo tanto corregible."""
    service = migrated(tmp_path, [
        dict(period="2099-04", status="CALCULADA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-05", status="REVISADA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-05-01T00:00:00"),
    ])
    assert rated_periods(service) == {}
    assert audits(service, "COMMISSION_PERIOD_RATE_SEEDED") == []


def test_la_migracion_no_desempata_evidencia_discrepante(tmp_path):
    """Dos importes oficiales distintos en el mismo mes: elegir uno sería decidir por el dueño."""
    service = migrated(tmp_path, [
        dict(period="2099-04", status="APROBADA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-04", status="APROBADA", rate_bp=500, amount=20_000,
             total=400_000, created_at="2099-04-20T00:00:00"),
    ])
    assert rated_periods(service) == {}
    skipped = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert len(skipped) == 1 and skipped[0]["target"] == "2099-04"
    assert "EVIDENCIA_DISCREPANTE" in skipped[0]["details_json"]


def test_la_migracion_no_toca_importes_ni_avales_ya_aprobados(tmp_path):
    """Invariante 6 sobre la migración: es aditiva y nunca reescribe una liquidación."""
    service = migrated(tmp_path, [
        dict(period="2099-04", status="APROBADA", rate_bp=500, amount=20_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
    ])
    entry = service.get_entry(SOL, "entry-0")
    assert (entry["status"], entry["rate_bp"], entry["commission_amount"]) == ("APROBADA", 500, 20_000)


def test_la_migracion_asienta_cada_periodo_sembrado(tmp_path):
    service = migrated(tmp_path, [
        dict(period="2099-04", status="PAGADA", rate_bp=500, amount=20_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
    ])
    seeded = audits(service, "COMMISSION_PERIOD_RATE_SEEDED")
    assert len(seeded) == 1 and seeded[0]["target"] == "2099-04"
    assert '"boundary": "PAGADA"' in seeded[0]["details_json"]
    assert '"rate_bp": 500' in seeded[0]["details_json"]
    assert rate_events(service, "2099-04") == [
        ("2099-04", "PINNED", 500, "BACKFILL",
         "hecho economico vivo PAGADA en la base migrada", "MIGRACION")]


def test_la_migracion_es_idempotente_y_no_duplica_su_auditoria(tmp_path):
    """Reabrir la base mil veces deja lo mismo que abrirla una."""
    service = migrated(tmp_path, [
        dict(period="2099-04", status="APROBADA", rate_bp=500, amount=20_000,
             total=400_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-05", status="APROBADA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-05-01T00:00:00"),
        dict(period="2099-06", status="APROBADA", rate_bp=100, amount=4_000,
             total=400_000, created_at="2099-06-01T00:00:00"),
        dict(period="2099-06", status="APROBADA", rate_bp=700, amount=28_000,
             total=400_000, created_at="2099-06-02T00:00:00"),
    ])
    path = service.repository.database_path
    for _ in range(3):
        service = CommissionService(CentralManagementService(CentralRepository(path)))
    assert rated_periods(service) == {"2099-04": 500, "2099-05": 100}
    assert len(audits(service, "COMMISSION_PERIOD_RATE_SEEDED")) == 2
    assert len(audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")) == 1


# ------------------------------------------------------- reintentos e idempotencia en caliente
def test_fijar_es_idempotente_entre_liquidaciones_del_mismo_mes(service):
    """La segunda aprobación del mes no reescribe la fijación ni duplica el asiento."""
    first, _ = service.register_sale(SOL, sale())
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    approve_entry(service, first)
    service.recalculate(SOL)
    entry_id = active(service, second)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert len(audits(service, "COMMISSION_PERIOD_RATE_PINNED")) == 1


def test_aprobar_y_luego_pagar_deja_un_solo_asiento_de_fijacion(service):
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    assert len(audits(service, "COMMISSION_PERIOD_RATE_PINNED")) == 1


# --------------------------------------------------------------------------- auditoría
def test_la_fijacion_deja_trazabilidad_completa(service):
    """Fijar un mes compromete dinero hacia adelante: tiene que poder reconstruirse."""
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    pinned = audits(service, "COMMISSION_PERIOD_RATE_PINNED")
    assert len(pinned) == 1
    row = pinned[0]
    assert row["target"] == "2099-04" and row["actor"] == "sol"
    for fragment in ('"origin": "APROBADA"', '"rate_bp": 100', f'"entry_id": "{entry_id}"',
                     f'"policy_code": "{CANONICAL_CODE}"'):
        assert fragment in row["details_json"]


# ------------------------------------------------------------------------------ rotulado
def test_un_periodo_sin_tasa_en_vigor_no_se_rotula_con_la_politica_global(service):
    """`QB2-g5`: el export emitía «Comisión oficial None%».

    `2026-07` es anterior a toda vigencia publicada, así que ahí no rige ninguna tasa. La
    política global del 10% existe y es la última publicada, pero rotular con ella este mes
    sería declarar oficial un porcentaje que este mes nunca usó.
    """
    service.set_general_rate(SOL, 1_000, "2099-01-01", "tasa global")
    summary = service.export_summary(SOL, "2026-07")
    assert summary["policy"]["rate_bp"] is None
    assert summary["current_policy"]["rate_bp"] == 1_000
    assert "None" not in summary["policy_disclaimer"]
    assert "10" not in summary["policy_disclaimer"].split("Convenio")[0]
    assert "Sin tasa de comisión en vigor para 2026-07" in summary["policy_disclaimer"]


def test_el_export_distingue_una_tasa_fijada_de_una_todavia_provisional(service):
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)
    assert "todavía no tiene una tasa fijada" in service.export_summary(SOL, "2099-04")["policy_disclaimer"]
    approve_entry(service, sale_id)
    assert "ya fijada" in service.export_summary(SOL, "2099-04")["policy_disclaimer"]
