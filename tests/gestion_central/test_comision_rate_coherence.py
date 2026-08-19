"""Una sola regla decide la tasa de un período, y el pin nunca contradice sus hechos (generación 9).

La generación 8 unificó el **predicado de vitalidad** —qué cuenta como hecho vivo— y con eso cerró
`AB1-g7`. Lo que seguía escrito dos veces era la **regla de decisión**: qué tasa tiene el período.

* La siembra exigía coherencia: si los hechos vivos llevaban tasas distintas, no elegía y dejaba el
  mes sin fijar.
* La reconciliación en caliente no miraba la tasa en absoluto: **cualquier** hecho vivo retenía el
  pin, llevara la tasa que llevara.

El Auditor lo explotó con la base que la propia migración produce: una instalación del piloto con
políticas por vendedora y por local —que `_migrate_commission_policy` retira por diseño— deja
liquidaciones del mismo mes con política canónica y tasas distintas. Ese mes nace sin pin teniendo
hechos vivos, y el primer pin que reciba queda clavado para siempre a la tasa equivocada, sostenido
por un hecho que lleva otra. 9.900.000 Gs de sobrepago por venta de 10.000.000 Gs, sin techo, y
otra vez sin ninguna ruta pública de corrección. Es `AB1-g8`.

La regla del propietario dice que el período sigue fijado mientras exista un hecho oficial vivo
**que justifique ese pin**. Un hecho a otra tasa no lo justifica. Aquí hay una sola función de
decisión, `resolve_period_rate`, que usan por igual la reconciliación en caliente y la de la
apertura de la base.
"""
import sqlite3

import pytest

from modulos.gestion_central.comision_policy import (
    CANONICAL_CODE, CANONICAL_RATE_BP, POLICY_CANONICAL, PERIOD_RATE_AMBIGUOUS, resolve_period_rate,
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
            "SELECT event,rate_bp,origin FROM commission_period_rate_events"
            " WHERE period=? ORDER BY id", (period,))]


def audits(service, action):
    return [row for row in service.repository.audit_log(limit=500) if row["action"] == action]


def live_rates(service, period="2099-04"):
    with sqlite3.connect(service.repository.database_path) as con:
        con.row_factory = sqlite3.Row
        return sorted({int(row["rate_bp"])
                       for row in service.repository.live_official_facts(con, period)})


def approve_entry(service, sale_id, responsible="Sol"):
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, responsible)
    return entry_id


def scoped_pilot(tmp_path):
    """La base del Auditor: piloto con políticas por vendedora y por local, que la migración retira.

    Deja dos liquidaciones canónicas del mismo mes a tasas distintas —9% y 7%— que es exactamente
    lo que produce una instalación real del piloto al migrar.
    """
    path = tmp_path / "scoped.sqlite3"
    CommissionService(CentralManagementService(CentralRepository(path)))
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        for key, scope, scope_value, rate in (("V", "VENDEDORA", "Vendedora Vieja", 900),
                                              ("L", "LOCAL", "Óptica Asunción", 700)):
            con.execute(
                "INSERT INTO commission_policies(id,scope,scope_value,rate_bp,approval_status,code,"
                "version,effective_from,created_by,created_at)"
                " VALUES(?,?,?,?,?,?,1,'2026-08-01','PILOTO','2099-01-01T00:00:00')",
                (f"pol-{key}", scope, scope_value, rate, POLICY_CANONICAL, CANONICAL_CODE))
            con.execute(
                "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
                "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,"
                "envelope,content_hash,payload_json,version,created_at,updated_at)"
                " VALUES(?,?,'Óptica Asunción',?,'Vendedora Vieja','COMUN','2099-04-05',1000000,1000000,"
                "0,'2099-04-05',0,NULL,'','h','{}',1,?,?)",
                (f"s-{key}", f"k-{key}", f"src-{key}",
                 f"2099-04-0{1 if key == 'V' else 2}T00:00:00",
                 f"2099-04-0{1 if key == 'V' else 2}T00:00:00"))
        # e-V aprobada al 9%; e-L pagada al 7%. Las dos canónicas, las dos vivas.
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,created_at,updated_at)"
            " VALUES('e-V','s-V',1,'2099-04','Óptica Asunción','Vendedora Vieja','COMUN','APROBADA',"
            "1000000,0,1000000,900,90000,?,?,1,'2026-08-01','GENERAL','2099-04-05',"
            "'2099-04-01T00:00:00','2099-04-01T00:00:00')", (POLICY_CANONICAL, CANONICAL_CODE))
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,paid_at,"
            "payment_reference,created_at,updated_at)"
            " VALUES('e-L','s-L',1,'2099-04','Óptica Asunción','Vendedora Vieja','COMUN','PAGADA',"
            "1000000,0,1000000,700,70000,?,?,1,'2026-08-01','GENERAL','2099-04-05','2099-05-10',"
            "'TRANSF-VIEJA','2099-04-02T00:00:00','2099-04-02T00:00:00')",
            (POLICY_CANONICAL, CANONICAL_CODE))
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(path)))


# ------------------------------------------------------ la regla de decisión, en un solo sitio
def test_la_regla_de_decision_es_una_funcion_pura_y_unica():
    """Sin hechos no hay tasa; con tasas distintas no se elige; a igualdad manda el pago."""
    def fact(rate, status="APROBADA", paid=None, created="2099-04-01", ident="a"):
        return {"rate_bp": rate, "status": status, "paid_at": paid, "created_at": created, "id": ident}

    assert resolve_period_rate([]) is None
    assert resolve_period_rate([fact(100), fact(500, ident="b")]) is PERIOD_RATE_AMBIGUOUS
    # Un pago manda sobre una aprobación aunque sea posterior.
    chosen = resolve_period_rate([fact(100, created="2099-04-01", ident="apr"),
                                  fact(100, "PAGADA", "2099-05-01", "2099-04-20", "pag")])
    assert chosen["id"] == "pag"
    # A igualdad de fuerza gana el más antiguo, así el orden de lectura no decide.
    chosen = resolve_period_rate([fact(100, created="2099-04-20", ident="nueva"),
                                  fact(100, created="2099-04-01", ident="vieja")])
    assert chosen["id"] == "vieja"


def test_los_dos_lados_deciden_con_la_misma_funcion():
    """`AB1-g8`: la siembra exigía coherencia de tasa y la reconciliación no la miraba."""
    from pathlib import Path
    modules = Path(__file__).resolve().parents[2] / "modulos" / "gestion_central"
    sources = {source.name: source.read_text(encoding="utf-8") for source in modules.glob("*.py")}
    # Un solo sitio decide, y un solo sitio escribe.
    assert sum(text.count("resolve_period_rate(") for text in sources.values()) == 2  # def + uso
    assert sum(text.count("INSERT INTO commission_period_rate_events") for text in sources.values()) == 1
    # Y la reconciliación es la misma función para la apertura de la base y para las transiciones.
    assert sources["repository.py"].count("def reconcile_period_rate") == 1
    assert "self.reconcile_period_rate(" in sources["repository.py"]
    assert "self.repository.reconcile_period_rate(" in sources["comisiones.py"]


# ------------------------------------------------- el pin nunca contradice sus hechos vivos
def test_el_pin_siempre_lo_lleva_alguno_de_sus_hechos_vivos(tmp_path):
    """El corazón de `AB1-g8`, sobre la base que la propia migración produce.

    El invariante que la generación 8 no sostenía: si un período está fijado, su tasa es una que
    **algún hecho vivo lleva**. Antes, un pin al 100% podía quedar sostenido por un pago al 7%, y
    nada podía retirarlo. Se comprueba en cada paso de la secuencia, no sólo al final.
    """
    service = scoped_pilot(tmp_path)

    def coherente():
        fijado = rated_periods(service).get("2099-04")
        vivos = live_rates(service)
        assert fijado is None or fijado in vivos, (fijado, vivos)
        return fijado

    # Evidencia discrepante recién migrada: no se fija nada, y queda asentado.
    assert coherente() is None and live_rates(service) == [700, 900]
    skipped = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert len(skipped) == 1 and "EVIDENCIA_DISCREPANTE" in skipped[0]["details_json"]

    # Una promoción con un cero de más, sobre el mes discrepante.
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    nueva, _ = service.register_sale(SOL, sale(sale_date="2099-04-18"))
    coherente()
    entry_id = approve_entry(service, nueva)
    coherente()
    service.revert(SOL, entry_id, "aprobación equivocada: la tasa promocional era un tipeo")

    # El mes acaba a la tasa de su hecho vivo —el pago real al 7%—, nunca al 100%.
    assert coherente() == 700
    assert 10_000 not in [rate for _, rate, _ in events(service)]


def test_el_sobrepago_del_mes_discrepante_queda_eliminado(tmp_path):
    """La cifra del Auditor: 30.000.000 Gs pagados donde el mes vale mucho menos.

    El mes no acaba en el 1% general, y es correcto que no lo haga: su único hecho económico vivo
    es un pago real al 7%, y la regla del propietario dice que un pago vivo sostiene su mes. Lo que
    no puede pasar —y era el bloqueante— es que lo sostenga al **100%**, una tasa que ningún hecho
    de ese mes llevó nunca.
    """
    service = scoped_pilot(tmp_path)
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    nueva, _ = service.register_sale(SOL, sale(sale_date="2099-04-18"))
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

    assert pagado == 2_100_000        # 7% de 30.000.000 Gs: la tasa que el mes sí pagó
    assert pagado != 30_000_000       # el 100% que pagaba la generación 8
    assert rated_periods(service) == {"2099-04": 700}


@pytest.mark.parametrize("ruta", ["revert", "void_sale", "observe_revert"])
def test_las_rutas_de_ab1_g6_no_reaparecen_sobre_la_base_discrepante(tmp_path, ruta):
    """Las mismas rutas, sobre la base migrada que las reabría."""
    service = scoped_pilot(tmp_path)
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    nueva, _ = service.register_sale(SOL, sale(sale_date="2099-04-18"))
    entry_id = approve_entry(service, nueva)

    if ruta == "revert":
        service.revert(SOL, entry_id, "aprobación equivocada")
    elif ruta == "void_sale":
        service.void_sale(SOL, nueva, "venta cargada por error")
    else:
        service.observe(SOL, entry_id, "control")
        service.revert(SOL, entry_id, "se rehace")

    # En las tres, el mes queda a la tasa de su hecho vivo, jamás al 100%.
    assert rated_periods(service) == {"2099-04": 700}
    real, _ = service.register_sale(SOL, sale(source_sale_id="real", sale_date="2099-04-25"))
    service.recalculate(SOL)
    assert service.get_entry(SOL, active(service, real)["id"])["commission_amount"] == 700_000


def test_un_pin_a_una_tasa_que_ningun_hecho_lleva_se_corrige_al_abrir(tmp_path):
    """El estado exacto que la generación 8 dejaba clavado, importado tal cual.

    Libro fijado al 100% y un único hecho vivo pagado al 7%: la tasa del período no la lleva
    ninguno de sus hechos. Antes nada podía retirarla; ahora la reconciliación la sustituye por la
    que sus hechos sí sostienen, sin borrar el evento anterior.
    """
    service = scoped_pilot(tmp_path)
    path = service.repository.database_path
    with sqlite3.connect(path) as con:
        # Se retira la aprobación discrepante y se inyecta el pin imposible de la generación 8.
        con.execute("UPDATE commission_entries SET status='REVERTIDA' WHERE id='e-V'")
        con.execute(
            "INSERT INTO commission_period_rate_events(period,event,rate_bp,policy_code,policy_version,"
            "policy_effective_from,policy_scope,origin,entry_id,sale_id,reason,actor,recorded_at)"
            " VALUES('2099-04','PINNED',10000,?,2,'2099-01-01','GENERAL','APROBADA',NULL,NULL,"
            "'pin heredado de la generacion 8','sol','2099-04-30T00:00:00')", (CANONICAL_CODE,))
        con.commit()
    reabierta = CommissionService(CentralManagementService(CentralRepository(path)))
    assert rated_periods(reabierta) == {"2099-04": 700}
    assert [event for event, *_ in events(reabierta)] == ["PINNED", "UNPINNED", "PINNED"]
    # El evento imposible no se borra: queda en el libro con su tasa, y detrás su retirada.
    assert events(reabierta)[0] == ("PINNED", 10_000, "APROBADA")
    assert events(reabierta)[1] == ("UNPINNED", 10_000, "MIGRACION")


def test_un_pin_sostenido_por_un_hecho_de_su_misma_tasa_no_se_mueve(tmp_path):
    """La otra cara: coherencia no significa soltar en cuanto cambie algo."""
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    first, _ = service.register_sale(SOL, sale())
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    first_entry = approve_entry(service, first)
    service.recalculate(SOL)
    second_entry = active(service, second)["id"]
    service.review(SOL, second_entry)
    service.approve(SOL, second_entry, "Sol")

    service.revert(SOL, first_entry, "se rehace la primera")
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert [event for event, *_ in events(service)] == ["PINNED"]


def test_una_pagada_canonica_viva_sigue_sin_soltar_jamas(tmp_path):
    """La regla del propietario sobre el dinero consolidado no se toca."""
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    service.observe(SOL, entry_id, "control posterior al pago")
    service.void_sale(SOL, sale_id, "la venta se anula después de pagada")
    for _ in range(3):
        service.recalculate(SOL)
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert [event for event, *_ in events(service)] == ["PINNED"]


# --------------------------------------------- la apertura de la base aplica la misma regla
def test_una_fijacion_heredada_sin_hecho_vivo_se_retira_al_abrir(tmp_path):
    """Observación 1 de QA sobre la generación 8, y el contrato que la contradecía.

    Un libro producido por una generación anterior podía traer un `PINNED` que hoy nada sostiene.
    Que no exista ningún hecho vivo es **observable**, no fabricado: aplicar la regla no es
    inventar un hecho, y dejarlo sin aplicar hacía que la pantalla declarara fijado un mes que
    ningún hecho justificaba.
    """
    path = tmp_path / "central.sqlite3"
    service = CommissionService(CentralManagementService(CentralRepository(path)))
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.revert(SOL, entry_id, "se rehace")
    # Se reconstruye a mano el estado que dejaba la generación anterior: el `UNPINNED` no existía.
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events WHERE event='UNPINNED'")
        con.commit()
    reabierta = CommissionService(CentralManagementService(CentralRepository(path)))
    assert rated_periods(reabierta) == {}
    assert [event for event, *_ in events(reabierta)] == ["PINNED", "UNPINNED"]
    # `audit_log` viene del más reciente al más antiguo: el último retiro es el de la migración.
    unpinned = audits(reabierta, "COMMISSION_PERIOD_RATE_UNPINNED")
    assert '"origin": "MIGRACION"' in unpinned[0]["details_json"]


def test_abrir_la_base_muchas_veces_no_escribe_nada_nuevo(tmp_path):
    service = scoped_pilot(tmp_path)
    path = service.repository.database_path
    for _ in range(5):
        service = CommissionService(CentralManagementService(CentralRepository(path)))
    assert events(service) == []
    assert len(audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")) == 1


def test_la_migracion_no_toca_los_importes_de_la_base_discrepante(tmp_path):
    service = scoped_pilot(tmp_path)
    aprobada = service.get_entry(SOL, "e-V")
    pagada = service.get_entry(SOL, "e-L")
    assert (aprobada["status"], aprobada["rate_bp"], aprobada["commission_amount"]) == \
           ("APROBADA", 900, 90_000)
    assert (pagada["status"], pagada["rate_bp"], pagada["commission_amount"], pagada["paid_at"]) == \
           ("PAGADA", 700, 70_000, "2099-05-10")
