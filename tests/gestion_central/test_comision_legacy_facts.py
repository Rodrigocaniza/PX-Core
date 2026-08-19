"""Un predicado único de hecho vivo, y una comisión legada que no sostiene ningún mes (generación 8).

La generación 7 puso el boundary de salida en su sitio y cerró `AB1-g6`. Pero dejó el predicado de
vitalidad escrito **dos veces**: el de la siembra exigía política canónica y el del código en
caliente no. `BOUNDARY_SQL_IN` unificó la lista de estados, que era la parte que ya coincidía, y
dejó divergente la que decidía.

La consecuencia la encontró el Auditor. Toda comisión ya pagada del piloto queda, por diseño y para
siempre, con `POLITICA_HISTORICA_PREVIA`: la migración no la repara y `recalculate` no la alcanza
porque ya movió dinero. Esa fila era invisible para la siembra y a la vez un hecho vivo para la
reconciliación, así que **su mes no podía soltarse nunca** y las cuatro rutas de `AB1-g6` volvían a
pagar mal con la misma cifra: 9.900.000 Gs de sobrepago por cada venta de 10.000.000 Gs. Es
`AB1-g7`.

La corrección no elige entre dos reglas: aplica la que el módulo ya tenía. Una liquidación con
`POLITICA_HISTORICA_PREVIA` no es un hecho oficial en ninguna otra parte —el reporte la excluye de
`commission_amount` y la cuenta en `non_official_amount`, el desglose dice «no es pagable con este
importe», la migración jamás siembra desde ella—. Su importe se conserva intacto por auditoría,
pero nunca fue la tasa oficial de su mes y no puede sostenerla.
"""
import sqlite3

import pytest

from modulos.gestion_central.comision_policy import (
    CANONICAL_CODE, CANONICAL_RATE_BP, POLICY_CANONICAL, POLICY_LEGACY,
)
from modulos.gestion_central.comisiones import CommissionSaleInput, CommissionService
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)


def sale(**changes):
    values = dict(branch="Óptica Asunción", source_sale_id="venta-001", saleswoman="Vendedora Uno",
                  sale_date="2099-04-10", kind="COMUN", total_amount=10_000_000,
                  initial_paid=10_000_000, envelope="S-001")
    values.update(changes)
    return CommissionSaleInput(**values)


def active(service, sale_id):
    return next(row for row in service.list_entries(SOL) if row["sale_id"] == sale_id
                and row["status"] != "REVERTIDA")


def rated_periods(service):
    with sqlite3.connect(service.repository.database_path) as con:
        rows = con.execute(
            "SELECT e.period,e.rate_bp,e.event FROM commission_period_rate_events e"
            " JOIN (SELECT period, MAX(id) AS newest FROM commission_period_rate_events GROUP BY period)"
            "   last ON last.period=e.period AND last.newest=e.id")
        return {row[0]: row[1] for row in rows if row[2] == "PINNED"}


def events(service, period="2099-04"):
    with sqlite3.connect(service.repository.database_path) as con:
        return [tuple(row) for row in con.execute(
            "SELECT event,rate_bp,origin,entry_id FROM commission_period_rate_events"
            " WHERE period=? ORDER BY id", (period,))]


def audits(service, action):
    return [row for row in service.repository.audit_log(limit=500) if row["action"] == action]


def approve_entry(service, sale_id, responsible="Sol"):
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, responsible)
    return entry_id


def pilot_base(tmp_path, *, period="2099-04", rate_bp=300, amount=30_000, total=1_000_000,
               status="PAGADA", paid_at="2099-05-10", policy_status=None, entry_period=None):
    """Base del piloto con una comisión **ya pagada** antes de la política aprobada.

    Es la forma mínima que produce la migración oficial sobre cualquier instalación que ya haya
    pagado una comisión: etiqueta retirada, que la migración convierte en `POLITICA_HISTORICA_PREVIA`
    conservando el importe intacto.
    """
    path = tmp_path / "piloto.sqlite3"
    CommissionService(CentralManagementService(CentralRepository(path)))
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        con.execute(
            "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
            "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,envelope,"
            "content_hash,payload_json,version,created_at,updated_at)"
            " VALUES('sale-P','key-P','Óptica Asunción','src-P','Vendedora Vieja','COMUN',?,?,?,0,?,0,"
            "NULL,'','h','{}',1,'2099-04-01T00:00:00','2099-04-01T00:00:00')",
            (f"{period}-05", total, total, f"{period}-05"))
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,paid_at,"
            "payment_reference,created_at,updated_at)"
            " VALUES('entry-P','sale-P',1,?,'Óptica Asunción','Vendedora Vieja','COMUN',?,?,0,?,?,?,?,"
            "?,1,'2026-08-01','GENERAL',?,?,'TRANSF-VIEJA','2099-04-01T00:00:00','2099-04-01T00:00:00')",
            (entry_period or period, status, total, total, rate_bp, amount,
             policy_status or "SINTETICA_PENDIENTE_APROBACION", CANONICAL_CODE,
             f"{period}-05", paid_at))
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(path)))


# ------------------------------------------- la comisión legada no es un hecho oficial vivo
def test_una_comision_legada_pagada_no_fija_el_mes_al_migrar(tmp_path):
    """La migración nunca sembró desde ella, y eso sigue siendo correcto."""
    service = pilot_base(tmp_path)
    entry = service.get_entry(SOL, "entry-P")
    assert entry["policy_status"] == POLICY_LEGACY          # la migración sólo cambia la etiqueta
    assert entry["commission_amount"] == 30_000             # el importe queda intacto
    assert rated_periods(service) == {}


def test_una_comision_legada_pagada_tampoco_sostiene_el_mes_en_caliente(tmp_path):
    """`AB1-g7`: el predicado en caliente sí la veía, y por eso el mes no podía soltarse.

    Si la siembra no la considera un hecho y la reconciliación sí, el resultado es un pin que
    ningún hecho justifica y que nada puede retirar.
    """
    service = pilot_base(tmp_path)
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    nueva, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, nueva)
    assert rated_periods(service) == {"2099-04": 10_000}

    service.revert(SOL, entry_id, "aprobación equivocada: la tasa promocional era un tipeo")
    assert rated_periods(service) == {}                      # antes seguía en 10.000
    assert [event for event, *_ in events(service)] == ["PINNED", "UNPINNED"]


def test_el_sobrepago_reaparecido_sobre_una_base_del_piloto_queda_eliminado(tmp_path):
    """El escenario completo del Auditor, medido en guaraníes."""
    service = pilot_base(tmp_path)
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    nueva, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, nueva)
    service.revert(SOL, entry_id, "aprobación equivocada")
    service.set_general_rate(SOL, CANONICAL_RATE_BP, "2099-01-01", "corrección al 1% oficial")

    pagado = 0
    for index in range(3):
        real, _ = service.register_sale(SOL, sale(source_sale_id=f"real-{index}",
                                                  sale_date="2099-04-22", envelope=f"S-R{index}"))
        real_entry = approve_entry(service, real)
        service.mark_paid(SOL, real_entry, "2099-05-20", f"TRANSF-{index}")
        pagado += service.get_entry(SOL, real_entry)["commission_amount"]

    assert pagado == 300_000              # el 1% oficial de 30.000.000 Gs
    assert pagado != 30_000_000           # lo que pagaba la generación 7 sobre una base migrada


def test_el_importe_legado_no_se_toca_nunca(tmp_path):
    """Dejar de contar como hecho vivo no es tocar el dinero: son cosas distintas."""
    service = pilot_base(tmp_path)
    service.set_general_rate(SOL, 10_000, "2099-01-01", "otra tasa")
    nueva, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, nueva)
    service.revert(SOL, entry_id, "se rehace")
    for _ in range(3):
        service.recalculate(SOL)
    legada = service.get_entry(SOL, "entry-P")
    assert (legada["status"], legada["rate_bp"], legada["commission_amount"],
            legada["paid_at"], legada["payment_reference"]) == \
           ("PAGADA", 300, 30_000, "2099-05-10", "TRANSF-VIEJA")


def test_una_base_migrada_no_nace_violando_el_invariante(tmp_path):
    """Segunda cara de `AB1-g7`: el mes tenía un hecho vivo y ningún evento en el libro.

    El invariante declarado es `fijado ⟺ existe un hecho oficial vivo`. Una base recién migrada
    lo violaba en el paso cero, antes de que nadie hiciera nada.
    """
    service = pilot_base(tmp_path)
    with sqlite3.connect(service.repository.database_path) as con:
        con.row_factory = sqlite3.Row
        live = con.execute(
            "SELECT e.id FROM commission_entries e JOIN commission_sales s ON s.id=e.sale_id"
            " WHERE substr(e.period,1,7)='2099-04' AND e.rate_bp IS NOT NULL"
            "   AND e.policy_status=? AND (e.paid_at IS NOT NULL"
            "        OR (e.status IN ('APROBADA','PAGADA') AND COALESCE(s.voided,0)=0))",
            (POLICY_CANONICAL,)).fetchall()
    assert live == [] and rated_periods(service) == {}


def test_una_pagada_canonica_si_sostiene_su_mes(tmp_path):
    """El contrapunto: lo que distingue a la legada es la política, no el hecho de estar pagada."""
    service = pilot_base(tmp_path, policy_status=POLICY_CANONICAL, rate_bp=500, amount=50_000)
    assert rated_periods(service) == {"2099-04": 500}
    assert events(service) == [("PINNED", 500, "BACKFILL", "entry-P")]


# ------------------------------------------------- un solo predicado, un solo escritor
def test_migrar_y_operar_dan_el_mismo_resultado(tmp_path):
    """`I11`: construir operando y reconstruir migrando tienen que coincidir.

    Se opera una secuencia completa, se borra el libro y se reabre la base: la siembra debe
    reproducir exactamente el estado al que llegó el código en caliente.
    """
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    first, _ = service.register_sale(SOL, sale())
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-05-11"))
    approve_entry(service, first)
    entry_two = approve_entry(service, second)
    service.revert(SOL, entry_two, "se rehace la de mayo")
    en_caliente = rated_periods(service)

    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        con.commit()
    migrada = CommissionService(CentralManagementService(CentralRepository(path)))
    assert rated_periods(migrada) == en_caliente == {"2099-04": CANONICAL_RATE_BP}


def test_la_migracion_reevalua_un_periodo_que_habia_quedado_suelto(tmp_path):
    """Observación 2 de QA: era el último punto donde migrar y operar no coincidían.

    Un período cuyo último evento es `UNPINNED` vuelve a mirarse. Si la base trae evidencia viva,
    fijarlo no inventa nada: aplica la misma regla que el código en caliente.
    """
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.revert(SOL, entry_id, "se suelta el mes")
    assert rated_periods(service) == {}

    # Una aprobación viva inyectada por SQL, como llegaría de una instalación externa.
    with sqlite3.connect(path) as con:
        con.execute(
            "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
            "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,envelope,"
            "content_hash,payload_json,version,created_at,updated_at)"
            " VALUES('sale-X','key-X','Óptica Asunción','src-X','Vendedora Uno','COMUN','2099-04-18',"
            "1000000,1000000,0,'2099-04-18',0,NULL,'','h','{}',1,'2099-04-18T00:00:00','2099-04-18T00:00:00')")
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,created_at,updated_at)"
            " VALUES('entry-X','sale-X',1,'2099-04','Óptica Asunción','Vendedora Uno','COMUN','APROBADA',"
            "1000000,0,1000000,100,10000,?,?,1,'2026-08-01','GENERAL','2099-04-18',"
            "'2099-04-18T00:00:00','2099-04-18T00:00:00')",
            (POLICY_CANONICAL, CANONICAL_CODE))
        con.commit()
    migrada = CommissionService(CentralManagementService(CentralRepository(path)))
    assert rated_periods(migrada) == {"2099-04": CANONICAL_RATE_BP}
    # Y el `UNPINNED` anterior sigue ahí: la secuencia se lee entera.
    assert [event for event, *_ in events(migrada)] == ["PINNED", "UNPINNED", "PINNED"]


def test_un_periodo_ya_fijado_no_se_resiembra(tmp_path):
    service = pilot_base(tmp_path, policy_status=POLICY_CANONICAL, rate_bp=500, amount=50_000)
    path = service.repository.database_path
    for _ in range(5):
        service = CommissionService(CentralManagementService(CentralRepository(path)))
    assert len(events(service)) == 1
    assert len(audits(service, "COMMISSION_PERIOD_RATE_SEEDED")) == 1


def test_un_periodo_con_fecha_completa_se_empareja_igual(tmp_path):
    """Observación 2 del Auditor: la siembra agrupaba por prefijo y el código comparaba exacto.

    Ninguna ruta pública produce un `period` de diez caracteres —`_month()` sólo devuelve
    `AAAA-MM`— pero una base de procedencia externa sí, y la primera transición cualquiera del mes
    soltaba un período que tenía una aprobación viva.
    """
    service = pilot_base(tmp_path, policy_status=POLICY_CANONICAL, status="APROBADA", paid_at=None,
                         rate_bp=900, amount=90_000, entry_period="2099-04-04")
    assert rated_periods(service) == {"2099-04": 900}
    with sqlite3.connect(service.repository.database_path) as con:
        con.row_factory = sqlite3.Row
        live = CommissionService._live_official_facts(con, "2099-04")
    assert [row["id"] for row in live] == ["entry-P"]


# ------------------------------------------------------ trazabilidad del hecho retirado
def test_el_unpinned_nombra_la_liquidacion_que_dejo_de_sostener_el_mes(tmp_path):
    """Observación 5 de QA. La cadena pedida debe leerse sin cruzar la auditoría por fecha."""
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.revert(SOL, entry_id, "aprobación equivocada")

    assert events(service) == [("PINNED", CANONICAL_RATE_BP, "APROBADA", entry_id),
                               ("UNPINNED", CANONICAL_RATE_BP, "COMMISSION_REVERTED", entry_id)]
    unpinned = audits(service, "COMMISSION_PERIOD_RATE_UNPINNED")
    assert len(unpinned) == 1
    assert f'"entry_id": "{entry_id}"' in unpinned[0]["details_json"]
    assert f'"sale_id": "{sale_id}"' in unpinned[0]["details_json"]


def test_el_libro_tiene_un_solo_escritor(tmp_path):
    """`L1-g7`: había dos rutas de escritura, en dos clases, con dos formatos de asiento."""
    from pathlib import Path
    modules = Path(__file__).resolve().parents[2] / "modulos" / "gestion_central"
    inserts = sum(source.read_text(encoding="utf-8").count(
        "INSERT INTO commission_period_rate_events") for source in modules.glob("*.py"))
    assert inserts == 1
    for forbidden in ("UPDATE commission_period_rate_events",
                      "DELETE FROM commission_period_rate_events"):
        assert all(forbidden not in source.read_text(encoding="utf-8")
                   for source in modules.glob("*.py"))


# ------------------------------------- coherencia del recálculo dentro de una sola pasada
def test_un_solo_recalculo_converge(tmp_path):
    """Observación 1 del Auditor: `decide()` leía el pin fuera de la transacción del llamador.

    Al reparar una liquidación, `recalculate` podía soltar el período; las que evaluaba después en
    el mismo bucle no veían ese `UNPINNED` y se calculaban con la tasa recién retirada. No movía
    dinero mal —la guarda de pago lo impedía— pero exigía dos pasadas y dejaba un rechazo por medio.
    """
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.revert(SOL, entry_id, "se suelta el mes")
    service.set_general_rate(SOL, 200, "2099-01-01", "el mes vale 2%")

    otra, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    service.recalculate(SOL)
    nueva = service.get_entry(SOL, active(service, otra)["id"])
    assert (nueva["rate_bp"], nueva["commission_amount"]) == (200, 200_000)
    # Y la segunda pasada ya no cambia nada: convergió en una.
    assert service.recalculate(SOL)["changed"] == 0
    service.review(SOL, nueva["id"])          # no hay rechazo intermedio que explicar
