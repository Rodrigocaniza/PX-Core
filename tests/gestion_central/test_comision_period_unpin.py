"""Boundary de salida: la tasa de un período se suelta cuando ya nada la sostiene (generación 7).

La generación 6 movió el boundary de **entrada** del primer cálculo a `APROBADA`/`PAGADA`, y eso
funcionó. Lo que no tocó fue el de **salida**: la evidencia se creaba con un hecho económico y no se
retiraba cuando ese hecho se retiraba. El Auditor encontró cuatro rutas públicas —revertir la
aprobación, `void_sale`, la reversa de un cobro rechazado, y `observe` seguido de `revert`— que
dejaban el mes fijado para siempre con cero hechos vivos, y midió 9.900.000 Gs de sobrepago por
venta. Es el bloqueante `AB1-g6`.

La regla canónica es ahora:

* el período permanece fijado **mientras exista al menos un hecho económico oficial vivo**
  —`APROBADA` o `PAGADA`— que lo justifique;
* si no queda ninguno, se escribe `UNPINNED` y el período vuelve a ser resoluble;
* una `PAGADA` viva **nunca** deja desfijar: el dinero consolidado está protegido;
* nada se borra: el `PINNED` anterior sigue en el libro, y refijar es un evento más.

Cada prueba nombra el invariante que defiende, no el método que llama.
"""
import sqlite3

import pytest

from modulos.gestion_central.comision_policy import CANONICAL_CODE, CANONICAL_RATE_BP
from modulos.gestion_central.comisiones import (
    POLICY_CANONICAL, CommissionSaleInput, CommissionService,
)
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)


@pytest.fixture
def service(tmp_path):
    return CommissionService(CentralManagementService(CentralRepository(tmp_path / "central.sqlite3")))


def sale(**changes):
    """Venta común ya cancelada de 10.000.000 Gs: el importe del escenario del Auditor."""
    values = dict(branch="Óptica Asunción", source_sale_id="venta-001", saleswoman="Vendedora Uno",
                  sale_date="2099-04-10", kind="COMUN", total_amount=10_000_000,
                  initial_paid=10_000_000, envelope="S-001")
    values.update(changes)
    return CommissionSaleInput(**values)


def partial(**changes):
    """Venta con saldo: hace falta un cobro para volverla comisionable, y ese cobro se puede caer."""
    values = dict(branch="Óptica Asunción", source_sale_id="venta-cheque", saleswoman="Vendedora Uno",
                  sale_date="2099-04-12", kind="COMUN", total_amount=10_000_000,
                  initial_paid=4_000_000, envelope="S-CHQ")
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


def events(service, period="2099-04"):
    with sqlite3.connect(service.repository.database_path) as con:
        return [tuple(row) for row in con.execute(
            "SELECT event,rate_bp,origin FROM commission_period_rate_events WHERE period=? ORDER BY id",
            (period,))]


def audits(service, action):
    return [row for row in service.repository.audit_log(limit=500) if row["action"] == action]


def approve_entry(service, sale_id, responsible="Sol"):
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, responsible)
    return entry_id


def promotional_typo(service):
    """El escenario exacto del Auditor: una tasa promocional con un cero de más, aprobada.

    Devuelve la liquidación aprobada al 100%, con el mes fijado a esa tasa.
    """
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    assert rated_periods(service) == {"2099-04": 10_000}
    return sale_id, entry_id


# --------------------------------------------------- 1 · una APROBADA fija el período
def test_una_aprobada_fija_el_periodo(service):
    sale_id, _ = service.register_sale(SOL, sale())
    approve_entry(service, sale_id)
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert events(service) == [("PINNED", CANONICAL_RATE_BP, "COMMISSION_APPROVED")]


# ------------------------------------ 2 · dos APROBADA, revertir una → sigue fijado
def test_revertir_una_de_dos_aprobadas_no_suelta_el_periodo(service):
    """Lo que sostiene el mes es que quede **alguna**, no que la primera siga en pie."""
    first, _ = service.register_sale(SOL, sale())
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    first_entry = approve_entry(service, first)
    service.recalculate(SOL)
    second_entry = active(service, second)["id"]
    service.review(SOL, second_entry)
    service.approve(SOL, second_entry, "Sol")

    service.revert(SOL, first_entry, "se rehace la primera")
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert events(service) == [("PINNED", CANONICAL_RATE_BP, "COMMISSION_APPROVED")]


# ------------------------------------------- 3 · revertir la última APROBADA → unpin
def test_revertir_la_ultima_aprobada_suelta_el_periodo(service):
    sale_id, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "aprobación equivocada: la tasa promocional era un tipeo")
    assert rated_periods(service) == {}
    assert events(service) == [("PINNED", 10_000, "COMMISSION_APPROVED"),
                               ("UNPINNED", 10_000, "COMMISSION_REVERTED")]
    assert service.policy_for_period(SOL, "2099-04")["pinned"] is False


# ------------------------------------------------ 4 · una PAGADA viva nunca desfija
def test_una_pagada_viva_nunca_suelta_el_periodo(service):
    """El dinero que salió de verdad protege el mes, se observe o se anule después."""
    sale_id, entry_id = promotional_typo(service)
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    service.observe(SOL, entry_id, "control posterior al pago")
    assert rated_periods(service) == {"2099-04": 10_000}
    service.void_sale(SOL, sale_id, "la venta se anula después de pagada la comisión")
    assert rated_periods(service) == {"2099-04": 10_000}
    assert events(service) == [("PINNED", 10_000, "COMMISSION_APPROVED")]


def test_una_pagada_no_se_puede_revertir_y_por_lo_tanto_no_suelta(service):
    _, entry_id = promotional_typo(service)
    service.mark_paid(SOL, entry_id, "2099-05-05", "TRANSF-1")
    # `PAGADA` ni siquiera es una transición legal hacia `REVERTIDA`: se rechaza antes de
    # llegar a la guarda de pago, que es la segunda defensa.
    with pytest.raises(ValueError, match="transici"):
        service.revert(SOL, entry_id, "intento de deshacer un pago")
    assert rated_periods(service) == {"2099-04": 10_000}


# ------------------------ 5 · cobro revertido válidamente y cero hechos vivos → unpin
def test_un_cobro_rechazado_despues_de_aprobar_suelta_el_periodo(service):
    """La ruta del cheque que rebota: no hace falta ningún error humano.

    Aprobar es rápido y el rechazo bancario llega días después. En ese momento no salió un
    guaraní de comisión: no hay nada que proteger, y el mes no puede quedar inmovilizado.
    """
    service.set_general_rate(SOL, 10_000, "2099-01-01", "promoción con un cero de más")
    sale_id, _ = service.register_sale(SOL, partial())
    payment_id, _ = service.register_payment(SOL, sale_id, 6_000_000, "2099-04-15", "cheque")
    entry_id = approve_entry(service, sale_id)
    assert rated_periods(service) == {"2099-04": 10_000}

    service.revert_payment(SOL, payment_id, "cheque rechazado por el banco")
    assert active(service, sale_id)["status"] == "PENDIENTE_SALDO"
    assert rated_periods(service) == {}
    assert events(service) == [("PINNED", 10_000, "COMMISSION_APPROVED"),
                               ("UNPINNED", 10_000, "PAYMENT_REVERTED")]


# ------------------------------------------- 6 · void_sale retira el último hecho → unpin
def test_anular_la_venta_del_ultimo_hecho_suelta_el_periodo(service):
    """Regla aprobada 8: una venta anulada no genera comisión — tampoco fija el mes."""
    sale_id, _ = promotional_typo(service)
    service.void_sale(SOL, sale_id, "venta cargada por error")
    assert rated_periods(service) == {}
    assert events(service) == [("PINNED", 10_000, "COMMISSION_APPROVED"),
                               ("UNPINNED", 10_000, "SALE_VOIDED")]


# --------------------------------------------------- 7 · observe + revert → unpin correcto
def test_observar_y_luego_revertir_suelta_el_periodo(service):
    _, entry_id = promotional_typo(service)
    service.observe(SOL, entry_id, "la vendedora consulta el importe")
    # Observar ya retira el hecho: una OBSERVADA sin pago no avala nada.
    assert rated_periods(service) == {}
    service.revert(SOL, entry_id, "se rehace la liquidación")
    # Y revertir después no escribe un segundo UNPINNED: ya no había nada que soltar.
    assert events(service) == [("PINNED", 10_000, "COMMISSION_APPROVED"),
                               ("UNPINNED", 10_000, "COMMISSION_OBSERVED")]


# ------------------------------------------------------------ 8 · unpin idempotente
def test_soltar_es_idempotente_por_muchas_transiciones_que_se_encadenen(service):
    sale_id, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "primera reversión")
    service.void_sale(SOL, sale_id, "y además se anula la venta")
    assert [event for event, *_ in events(service)] == ["PINNED", "UNPINNED"]
    assert len(audits(service, "COMMISSION_PERIOD_RATE_UNPINNED")) == 1


# ------------------------------------------------- 9 · reintento no duplica el asiento
def test_un_reintento_de_la_misma_operacion_no_duplica_el_asiento(service):
    """Repetir la anulación es un no-op declarado, y no puede dejar rastro nuevo."""
    sale_id, _ = promotional_typo(service)
    assert service.void_sale(SOL, sale_id, "venta cargada por error") is True
    assert service.void_sale(SOL, sale_id, "venta cargada por error") is False
    assert len(audits(service, "COMMISSION_PERIOD_RATE_UNPINNED")) == 1
    assert len(events(service)) == 2


def test_una_transicion_invalida_no_deja_evento_a_medias(service):
    """Si la transición falla, el libro no se mueve: todo va en la misma transacción."""
    _, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "reversión")
    before = events(service)
    with pytest.raises(ValueError, match="transición inválida"):
        service.revert(SOL, entry_id, "otra vez")
    assert events(service) == before


# ------------------------------- 10 · un hecho oficial posterior vuelve a fijar el período
def test_un_hecho_oficial_posterior_vuelve_a_fijar_el_periodo(service):
    """Refijar no es un caso especial: es el contrato normal aplicado al hecho siguiente."""
    _, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "la tasa promocional era un tipeo")
    # Corrección de la política al 1% oficial, ahora que el mes volvió a ser resoluble.
    service.set_general_rate(SOL, CANONICAL_RATE_BP, "2099-01-01", "corrección al 1% oficial")
    real, _ = service.register_sale(SOL, sale(source_sale_id="venta-real", sale_date="2099-04-22"))
    real_entry = approve_entry(service, real)
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}
    assert events(service) == [("PINNED", 10_000, "COMMISSION_APPROVED"),
                               ("UNPINNED", 10_000, "COMMISSION_REVERTED"),
                               ("PINNED", CANONICAL_RATE_BP, "COMMISSION_APPROVED")]
    assert service.get_entry(SOL, real_entry)["commission_amount"] == 100_000


# ------------------------------------------- 11 · los provisionales siguen sin fijar nada
def test_despues_de_soltar_los_estados_provisionales_siguen_sin_fijar(service):
    _, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "tipeo")
    service.set_general_rate(SOL, CANONICAL_RATE_BP, "2099-01-01", "corrección")
    otra, _ = service.register_sale(SOL, sale(source_sale_id="venta-003", sale_date="2099-04-25"))
    service.recalculate(SOL)
    nueva = active(service, otra)["id"]
    assert rated_periods(service) == {}
    service.review(SOL, nueva)
    assert rated_periods(service) == {}          # REVISADA tampoco fija
    service.approve(SOL, nueva, "Sol")
    assert rated_periods(service) == {"2099-04": CANONICAL_RATE_BP}


# --------------------------------------------- 12 · el historial previo permanece entero
def test_el_libro_conserva_toda_la_secuencia_sin_borrar_ni_reescribir(service):
    """`PINNED → UNPINNED → PINNED`, con causa, actor y fecha, reconstruible entera."""
    _, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "tipeo")
    service.set_general_rate(SOL, CANONICAL_RATE_BP, "2099-01-01", "corrección")
    real, _ = service.register_sale(SOL, sale(source_sale_id="venta-real", sale_date="2099-04-22"))
    approve_entry(service, real)

    with sqlite3.connect(service.repository.database_path) as con:
        con.row_factory = sqlite3.Row
        rows = [dict(row) for row in con.execute(
            "SELECT * FROM commission_period_rate_events WHERE period='2099-04' ORDER BY id")]
    assert [row["event"] for row in rows] == ["PINNED", "UNPINNED", "PINNED"]
    # El PINNED original no se tocó: conserva su tasa, su causa y la liquidación que lo produjo.
    assert rows[0]["rate_bp"] == 10_000 and rows[0]["origin"] == "COMMISSION_APPROVED"
    assert rows[0]["entry_id"] == entry_id
    # El UNPINNED dice qué tasa se retiró, por qué y quién.
    assert rows[1]["rate_bp"] == 10_000 and rows[1]["origin"] == "COMMISSION_REVERTED"
    assert "ningun hecho economico oficial vivo sostiene esta tasa" in rows[1]["reason"]
    assert all(row["actor"] == "sol" and row["recorded_at"] for row in rows)
    # Y los tres eventos están en `central_audit`, no sólo en el libro.
    assert len(audits(service, "COMMISSION_PERIOD_RATE_PINNED")) == 2
    assert len(audits(service, "COMMISSION_PERIOD_RATE_UNPINNED")) == 1


# ------------------- 13 · ningún importe aprobado o pagado se modifica en silencio
def test_soltar_el_periodo_no_toca_ningun_importe_ni_aval(service):
    """Desfijar cambia cómo se resuelve el mes hacia adelante, no lo que ya se registró."""
    sale_id, entry_id = promotional_typo(service)
    before = service.get_entry(SOL, entry_id)
    service.observe(SOL, entry_id, "consulta")
    after = service.get_entry(SOL, entry_id)
    assert rated_periods(service) == {}
    assert (after["rate_bp"], after["commission_amount"], after["approved_by"]) == \
           (before["rate_bp"], before["commission_amount"], before["approved_by"])


def test_soltar_un_periodo_no_alcanza_a_una_pagada_de_otra_liquidacion(service):
    """Una PAGADA viva impide el unpin, así que este caso no puede darse por construcción."""
    first, first_entry = promotional_typo(service)
    service.mark_paid(SOL, first_entry, "2099-05-05", "TRANSF-1")
    second, _ = service.register_sale(SOL, sale(source_sale_id="venta-002", sale_date="2099-04-20"))
    service.recalculate(SOL)
    second_entry = active(service, second)["id"]
    service.review(SOL, second_entry)
    service.approve(SOL, second_entry, "Sol")
    service.revert(SOL, second_entry, "se rehace la segunda")
    assert rated_periods(service) == {"2099-04": 10_000}
    pagada = service.get_entry(SOL, first_entry)
    assert (pagada["status"], pagada["commission_amount"]) == ("PAGADA", 10_000_000)


# ---------------------------------------- 14 · la migración no inventa pins ni unpins
def migrated(tmp_path, entries, *, voided_sales=(), legacy_pins=()):
    """Base legada construida a mano y reabierta: es como llega una instalación anterior."""
    path = tmp_path / "legado.sqlite3"
    CommissionService(CentralManagementService(CentralRepository(path)))
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        for period, rate_bp in legacy_pins:
            # Fijación tal como la escribía la generación 5, en la tabla que quedó congelada.
            con.execute(
                "INSERT OR REPLACE INTO commission_rated_periods(period,rate_bp,policy_code,policy_version,"
                "policy_effective_from,policy_scope,first_rated_by,first_rated_at,origin)"
                " VALUES(?,?,?,1,'2026-08-01','GENERAL','MIGRACION','2099-01-01T00:00:00','RATED')",
                (period, rate_bp, CANONICAL_CODE))
        for index, spec in enumerate(entries):
            sale_id = f"sale-{index}"
            con.execute(
                "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
                "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,envelope,"
                "content_hash,payload_json,version,created_at,updated_at)"
                " VALUES(?,?,'Óptica Asunción',?,'Vendedora Uno','COMUN',?,?,?,0,?,?,NULL,'','h','{}',1,?,?)",
                (sale_id, f"key-{index}", f"src-{index}", f"{spec['period']}-05",
                 spec["total"], spec["total"], f"{spec['period']}-05",
                 1 if sale_id in voided_sales else 0, spec["created_at"], spec["created_at"]))
            con.execute(
                "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
                "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
                "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,paid_at,"
                "created_at,updated_at)"
                " VALUES(?,?,1,?,'Óptica Asunción','Vendedora Uno','COMUN',?,?,0,?,?,?,?,?,1,'2026-08-01',"
                "'GENERAL',?,?,?,?)",
                (f"entry-{index}", sale_id, spec["period"], spec["status"], spec["total"], spec["total"],
                 spec["rate_bp"], spec["amount"], spec.get("policy_status", POLICY_CANONICAL),
                 CANONICAL_CODE, f"{spec['period']}-05", spec.get("paid_at"),
                 spec["created_at"], spec["created_at"]))
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(path)))


def test_la_migracion_no_escribe_ningun_unpin(tmp_path):
    """Retirar una fijación es un hecho: si nadie lo produjo, la migración no lo inventa."""
    service = migrated(tmp_path, [
        dict(period="2099-04", status="REVERTIDA", rate_bp=10_000, amount=10_000_000,
             total=10_000_000, created_at="2099-04-01T00:00:00"),
    ], legacy_pins=[("2099-04", 10_000)])
    assert events(service) == []
    assert audits(service, "COMMISSION_PERIOD_RATE_UNPINNED") == []
    # No se arrastra la fijación heredada, y queda dicho por qué.
    skipped = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert len(skipped) == 1 and skipped[0]["target"] == "2099-04"
    assert "SIN_HECHO_ECONOMICO_VIVO" in skipped[0]["details_json"]
    # Y la fila vieja sigue intacta: nada se borra.
    with sqlite3.connect(service.repository.database_path) as con:
        assert con.execute("SELECT rate_bp FROM commission_rated_periods WHERE period='2099-04'"
                           ).fetchone() == (10_000,)


def test_la_migracion_y_el_codigo_en_caliente_coinciden(tmp_path):
    """Migrar una base y reconstruirla operando deben dar el mismo resultado.

    En la generación 6 no coincidían: la siembra excluía las `REVERTIDA` pero el código en
    caliente conservaba el pin de una aprobación revertida. Esa divergencia era media `AB1-g6`.
    """
    service = migrated(tmp_path, [
        dict(period="2099-04", status="REVERTIDA", rate_bp=10_000, amount=10_000_000,
             total=10_000_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-05", status="APROBADA", rate_bp=500, amount=500_000,
             total=10_000_000, created_at="2099-05-01T00:00:00"),
        dict(period="2099-06", status="OBSERVADA", rate_bp=700, amount=700_000,
             total=10_000_000, created_at="2099-06-01T00:00:00", paid_at="2099-07-01"),
    ])
    # Sólo los meses con un hecho vivo quedan fijados: la REVERTIDA no, la APROBADA sí, y la
    # OBSERVADA que conserva `paid_at` también, porque ese dinero salió.
    assert rated_periods(service) == {"2099-05": 500, "2099-06": 700}


def test_la_migracion_sigue_sin_inventar_ni_desempatar(tmp_path):
    service = migrated(tmp_path, [
        dict(period="2099-04", status="CALCULADA", rate_bp=100, amount=100_000,
             total=10_000_000, created_at="2099-04-01T00:00:00"),
        dict(period="2099-05", status="APROBADA", rate_bp=100, amount=100_000,
             total=10_000_000, created_at="2099-05-01T00:00:00"),
        dict(period="2099-05", status="APROBADA", rate_bp=500, amount=500_000,
             total=10_000_000, created_at="2099-05-02T00:00:00"),
    ])
    assert rated_periods(service) == {}
    skipped = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert {row["target"] for row in skipped} == {"2099-05"}
    assert "EVIDENCIA_DISCREPANTE" in skipped[0]["details_json"]


def test_reabrir_la_base_migrada_es_idempotente(tmp_path):
    service = migrated(tmp_path, [
        dict(period="2099-05", status="APROBADA", rate_bp=500, amount=500_000,
             total=10_000_000, created_at="2099-05-01T00:00:00"),
    ])
    path = service.repository.database_path
    for _ in range(5):
        service = CommissionService(CentralManagementService(CentralRepository(path)))
    assert rated_periods(service) == {"2099-05": 500}
    assert len(events(service, "2099-05")) == 1
    assert len(audits(service, "COMMISSION_PERIOD_RATE_PINNED")) == 1


# ---------------------------- 15 · el sobrepago de 9.900.000 Gs queda eliminado
def test_el_sobrepago_de_la_aprobacion_revertida_queda_eliminado(service):
    """El escenario exacto de `AB1-g6`, medido en guaraníes.

    Antes: el mes quedaba fijado al 100% por una aprobación que el propio sistema anuló, y cada
    venta real de 10.000.000 Gs pagaba 10.000.000 Gs en vez de 100.000. Sobrepago 9.900.000 Gs
    por venta, sin techo.
    """
    _, entry_id = promotional_typo(service)
    service.revert(SOL, entry_id, "aprobación equivocada: la tasa promocional era un tipeo")
    service.set_general_rate(SOL, CANONICAL_RATE_BP, "2099-01-01", "corrección al 1% oficial")

    pagado = 0
    for index in range(3):
        real, _ = service.register_sale(SOL, sale(source_sale_id=f"real-{index}",
                                                  sale_date="2099-04-22", envelope=f"S-R{index}"))
        real_entry = approve_entry(service, real)
        service.mark_paid(SOL, real_entry, "2099-05-10", f"TRANSF-{index}")
        pagado += service.get_entry(SOL, real_entry)["commission_amount"]

    assert pagado == 300_000          # el 1% oficial de 30.000.000 Gs
    assert pagado != 30_000_000       # lo que pagaba la generación 6


def test_el_subpago_de_la_direccion_contraria_tambien_queda_eliminado(service):
    """La misma fuga al revés: pin al 1% y política corregida al 10%."""
    sale_id, _ = service.register_sale(SOL, sale())
    entry_id = approve_entry(service, sale_id)
    service.revert(SOL, entry_id, "aprobación equivocada")
    service.set_general_rate(SOL, 1_000, "2099-01-01", "la tasa real del mes era 10%")
    real, _ = service.register_sale(SOL, sale(source_sale_id="real", sale_date="2099-04-22"))
    service.recalculate(SOL)
    assert service.get_entry(SOL, active(service, real)["id"])["commission_amount"] == 1_000_000


# ------------- extra · la regla aprobada 8 defendida también donde sale el dinero
def test_una_venta_anulada_de_una_base_legada_no_llega_al_pago(tmp_path):
    """Observación 1 del Auditor de la generación 6.

    Por ruta pública no se llega aquí: `void_sale` mueve la liquidación. Una base de procedencia
    externa sí puede traer la fila, y hasta la generación 7 el sistema la revisaba, la aprobaba y
    la pagaba, y además fijaba el mes con ella.
    """
    service = migrated(tmp_path, [
        dict(period="2099-04", status="CALCULADA", rate_bp=100, amount=100_000,
             total=10_000_000, created_at="2099-04-01T00:00:00"),
    ], voided_sales={"sale-0"})
    with pytest.raises(ValueError, match="anulada"):
        service.review(SOL, "entry-0")
    assert rated_periods(service) == {}
