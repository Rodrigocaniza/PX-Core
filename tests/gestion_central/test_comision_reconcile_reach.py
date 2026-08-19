"""Toda ruta que cambia un estado reconcilia su período, y el libro se lee en un solo sitio (gen. 10).

La generación 9 afirmaba que `_set_status` era «por donde pasa toda transición de estado» y que por
eso cualquier ruta futura quedaba cubierta **por construcción**. El Librarian lo instrumentó y
demostró que era falso: `recalculate`, `_apply_source_update` y la promoción a elegible escriben
`status` con un `UPDATE` directo. Hoy no había fuga —esas rutas sólo tocan estados no vivos, salvo
la reparación, que ya reconciliaba por su cuenta— pero la garantía estructural no existía, y con
ella se caía la promesa sobre «cualquier ruta futura».

Aquí se cierra por los dos lados: cada uno de esos sitios reconcilia, y una guarda automática
comprueba que **ninguna función que escriba `status` se olvide de hacerlo**. Es la clase de defecto
que esta misión lleva cinco generaciones persiguiendo: la misma regla en dos sitios, o una garantía
que se afirma y no se sostiene.
"""
import ast
import re
import sqlite3
from pathlib import Path

import pytest

from modulos.gestion_central.comision_policy import CANONICAL_CODE, CANONICAL_RATE_BP, POLICY_CANONICAL
from modulos.gestion_central.comisiones import CommissionSaleInput, CommissionService
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


SOL = Principal("sol", Role.ADMIN_CENTRAL)
MODULO = Path(__file__).resolve().parents[2] / "modulos" / "gestion_central"


@pytest.fixture
def service(tmp_path):
    return CommissionService(CentralManagementService(CentralRepository(tmp_path / "central.sqlite3")))


def sale(**changes):
    values = dict(branch="Óptica Asunción", source_sale_id="venta-001", saleswoman="Vendedora Uno",
                  sale_date="2099-04-10", kind="COMUN", total_amount=1_000_000,
                  initial_paid=1_000_000, envelope="S-001")
    values.update(changes)
    return CommissionSaleInput(**values)


def active(service, sale_id):
    return next(row for row in service.list_entries(SOL) if row["sale_id"] == sale_id
                and row["status"] != "REVERTIDA")


def events(service, period="2099-04"):
    with sqlite3.connect(service.repository.database_path) as con:
        return [tuple(row) for row in con.execute(
            "SELECT event,rate_bp,origin FROM commission_period_rate_events"
            " WHERE period=? ORDER BY id", (period,))]


def audits(service, action):
    return [row for row in service.repository.audit_log(limit=500) if row["action"] == action]


# ------------------------------------------------- la garantía estructural, comprobada
#
# La guarda de la generación 10 era textual y el Librarian la desarmó: buscaba la cadena exacta
# `"UPDATE commission_entries SET"`, de modo que partir el literal en dos la evadía; comprobaba
# `_reconcile_period_pin(` como **subcadena del cuerpo**, de modo que un comentario bastaba; y leía
# un solo fichero. Exhibió una función que escribía estado, no reconciliaba, y la guarda pasaba.
#
# Ésta recorre el **árbol sintáctico** de todos los módulos del paquete. Python une por sí solo los
# literales adyacentes, los comentarios no existen en el árbol, y una llamada es un nodo `Call` y
# no un trozo de texto. Y se autocomprueba: `test_la_guarda_atrapa_una_violacion_sintetica`
# construye los casos que la versión anterior dejaba pasar y verifica que **ésta los detecta**.

# Escritores de `commission_entries` exentos, con su razón. Estar aquí no es una excepción tácita:
# es una afirmación que alguien tuvo que escribir y que el revisor puede discutir.
ESCRITORES_EXENTOS = {
    "_migrate_commission_policy":
        "sólo reemplaza la etiqueta de política retirada, sin tocar tasa ni importe; la "
        "reconciliación de la apertura recorre todos los períodos inmediatamente después",
    "_create_entry":
        "sólo crea liquidaciones en ELEGIBLE o PENDIENTE_SALDO, que no son hechos vivos y por lo "
        "tanto no pueden cambiar la tasa de un período",
}
RECONCILIADORES = {"_reconcile_period_pin", "reconcile_period_rate"}


def _sql_de(nodo):
    """Todo el SQL literal que aparece dentro de una función, incluidas las f-strings."""
    trozos = []
    for hijo in ast.walk(nodo):
        if isinstance(hijo, ast.Constant) and isinstance(hijo.value, str):
            trozos.append(hijo.value)
        elif isinstance(hijo, ast.JoinedStr):
            trozos += [v.value for v in hijo.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    return " ".join(" ".join(trozos).split())


def _llama_a(nodo, nombres):
    """Si la función contiene una **llamada** real a alguno de esos nombres."""
    for hijo in ast.walk(nodo):
        if not isinstance(hijo, ast.Call):
            continue
        objetivo = hijo.func
        nombre = (objetivo.attr if isinstance(objetivo, ast.Attribute)
                  else objetivo.id if isinstance(objetivo, ast.Name) else None)
        if nombre in nombres:
            return True
    return False


def escritores_de_estado(fuente):
    """Funciones que escriben `commission_entries`, por análisis sintáctico y no por texto."""
    encontrados = {}
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if re.search(r"(UPDATE|INSERT INTO)\s+commission_entries", _sql_de(nodo), re.I):
            encontrados[nodo.name] = nodo
    return encontrados


def test_toda_funcion_que_escribe_commission_entries_reconcilia_su_periodo():
    """`L3-g9` y `L2-g10`: la garantía «por construcción», sostenida por algo que puede fallar.

    Cubre `UPDATE` **y** `INSERT` —la versión anterior sólo miraba `UPDATE`, y una ruta futura que
    insertara una `APROBADA` no la habría detenido— y recorre todos los módulos, no uno.
    """
    for fichero in sorted(MODULO.glob("*.py")):
        for nombre, nodo in escritores_de_estado(fichero.read_text(encoding="utf-8")).items():
            if nombre in ESCRITORES_EXENTOS:
                continue
            assert _llama_a(nodo, RECONCILIADORES), (
                f"{fichero.name}::{nombre} escribe commission_entries y no reconcilia su período")


def test_la_guarda_atrapa_una_violacion_sintetica():
    """La guarda vale lo que valga su capacidad de fallar. Aquí se comprueba que falla.

    Los tres casos son los que el Librarian usó para desarmar la versión textual: el literal SQL
    partido en dos, la mención en un comentario en vez de una llamada, y un `INSERT` en lugar de un
    `UPDATE`. Los tres deben ser detectados como escritores sin reconciliación.
    """
    partido = (
        "class X:\n"
        "    def cierre_masivo(self, con):\n"
        "        con.execute('UPDATE commission_entries'\n"
        "                    \" SET status='APROBADA' WHERE id=?\", (1,))\n")
    comentado = (
        "class X:\n"
        "    def cierre_masivo(self, con):\n"
        "        con.execute(\"UPDATE commission_entries SET status='APROBADA' WHERE id=?\", (1,))\n"
        "        # aqui habria que llamar a self._reconcile_period_pin(con, p, a, b)\n")
    insertado = (
        "class X:\n"
        "    def alta_directa(self, con):\n"
        "        con.execute(\"INSERT INTO commission_entries(id,status) VALUES(?,'APROBADA')\", (1,))\n")

    for fuente in (partido, comentado, insertado):
        escritores = escritores_de_estado(fuente)
        assert escritores, "la guarda no vio un escritor de estado"
        for nodo in escritores.values():
            assert not _llama_a(nodo, RECONCILIADORES)

    # Y el contrapunto: una llamada de verdad sí cuenta.
    correcto = (
        "class X:\n"
        "    def cierre_masivo(self, con):\n"
        "        con.execute('UPDATE commission_entries'\n"
        "                    \" SET status='APROBADA' WHERE id=?\", (1,))\n"
        "        self._reconcile_period_pin(con, '2099-04', 'sol', 'CIERRE')\n")
    assert _llama_a(escritores_de_estado(correcto)["cierre_masivo"], RECONCILIADORES)


def test_los_escritores_exentos_son_los_declarados():
    """Una exención tácita no es una exención: si aparece un escritor nuevo, hay que nombrarlo."""
    encontrados = set()
    for fichero in MODULO.glob("*.py"):
        encontrados |= set(escritores_de_estado(fichero.read_text(encoding="utf-8")))
    assert encontrados == {"_set_status", "recalculate", "_apply_source_update",
                           "_promote_to_eligible", "_create_entry",
                           "_migrate_commission_policy"}, sorted(encontrados)


def test_el_estado_vigente_del_periodo_se_lee_en_un_solo_sitio():
    """Observación 2 del Auditor de la generación 9, y la 3 del Librarian de la 10.

    Lo que se unificó no es «toda lectura del libro» —hay varias, con fines distintos— sino la que
    contesta **cuál es el estado vigente de un período**. Se localiza por sintaxis: funciones cuyo
    SQL lee el libro ordenando por `id` descendente o agregando por `MAX(id)`, que son las dos
    formas de esa pregunta.
    """
    lectores = []
    for fichero in sorted(MODULO.glob("*.py")):
        for nodo in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
            if not isinstance(nodo, ast.FunctionDef):
                continue
            sql = _sql_de(nodo)
            if "commission_period_rate_events" not in sql:
                continue
            if re.search(r"ORDER BY id DESC|MAX\(\s*id\s*\)", sql, re.I):
                lectores.append(f"{fichero.name}::{nodo.name}")
    assert lectores == ["repository.py::last_period_rate_event"], lectores


# ---------------------------------------- las tres rutas que no pasan por `_set_status`
def test_recalcular_reconcilia_aunque_no_repare(service):
    """`recalculate` escribe `status='CALCULADA'` con un `UPDATE` directo."""
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)                       # ELEGIBLE → CALCULADA, sin pasar por _set_status
    assert events(service) == []                   # nada que fijar: sigue siendo provisional
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    assert events(service) == [("PINNED", CANONICAL_RATE_BP, "COMMISSION_APPROVED")]


def test_la_correccion_de_origen_reconcilia(service):
    """`_apply_source_update` es el segundo `UPDATE` directo de estado."""
    sale_id, _ = service.register_sale(SOL, sale())
    service.recalculate(SOL)
    entry_id = active(service, sale_id)["id"]
    service.review(SOL, entry_id)
    service.approve(SOL, entry_id, "Sol")
    assert events(service) == [("PINNED", CANONICAL_RATE_BP, "COMMISSION_APPROVED")]
    # Corregir el origen de una aprobada la manda a OBSERVADA: retira el único hecho vivo.
    service.register_sale(SOL, sale(total_amount=2_000_000, initial_paid=2_000_000))
    assert [event for event, *_ in events(service)] == ["PINNED", "UNPINNED"]


def test_la_promocion_a_elegible_reconcilia(service):
    """Tercer `UPDATE` directo: `PENDIENTE_SALDO → ELEGIBLE` al completarse el cobro."""
    sale_id, _ = service.register_sale(SOL, sale(initial_paid=400_000))
    assert active(service, sale_id)["status"] == "PENDIENTE_SALDO"
    service.register_payment(SOL, sale_id, 600_000, "2099-04-20", "saldo")
    assert active(service, sale_id)["status"] == "ELEGIBLE"
    assert events(service) == []          # elegible no es un hecho vivo: no fija nada


# --------------------------------------------- claves de período normalizadas en los dos lados
def legacy_with_full_date(tmp_path):
    """Base de procedencia externa: `period` en fecha completa, tanto en la liquidación como en el libro."""
    path = tmp_path / "externa.sqlite3"
    CommissionService(CentralManagementService(CentralRepository(path)))
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        con.execute(
            "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
            "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,envelope,"
            "content_hash,payload_json,version,created_at,updated_at)"
            " VALUES('s-X','k-X','Óptica Asunción','src-X','Vendedora Uno','COMUN','2099-04-15',"
            "1000000,1000000,0,'2099-04-15',0,NULL,'','h','{}',1,'2099-04-15T00:00:00','2099-04-15T00:00:00')")
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,paid_at,"
            "payment_reference,created_at,updated_at)"
            " VALUES('e-X','s-X',1,'2099-04-15','Óptica Asunción','Vendedora Uno','COMUN','PAGADA',"
            "1000000,0,1000000,700,70000,?,?,1,'2026-08-01','GENERAL','2099-04-15','2099-05-10',"
            "'TRANSF-X','2099-04-15T00:00:00','2099-04-15T00:00:00')",
            (POLICY_CANONICAL, CANONICAL_CODE))
        # Y una fila de libro heredada con la misma clave sin normalizar.
        con.execute(
            "INSERT INTO commission_period_rate_events(period,event,rate_bp,policy_code,policy_version,"
            "policy_effective_from,policy_scope,origin,entry_id,sale_id,reason,actor,recorded_at)"
            " VALUES('2099-04-15','PINNED',700,?,1,'2026-08-01','GENERAL','LEGADO',NULL,NULL,"
            "'fila heredada con fecha completa','externo','2099-05-10T00:00:00')", (CANONICAL_CODE,))
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(path)))


def test_una_clave_de_periodo_sin_normalizar_no_deja_un_periodo_fantasma(tmp_path):
    """Observación 3 del Auditor: la publicación declaraba «protegido» un mes que no existe."""
    service = legacy_with_full_date(tmp_path)
    with sqlite3.connect(service.repository.database_path) as con:
        claves = sorted({row[0] for row in con.execute(
            "SELECT DISTINCT period FROM commission_period_rate_events")})
    # La fila heredada no se borra —el libro es append-only— pero el mes real sí queda reconciliado.
    assert "2099-04" in claves
    service.set_general_rate(SOL, CANONICAL_RATE_BP, "2099-01-01", "publicación posterior")
    publicada = audits(service, "COMMISSION_POLICY_VERSION_PUBLISHED")[0]
    assert '"protected_periods": ["2099-04"]' in publicada["details_json"]
    assert "2099-04-15" not in publicada["details_json"].split('"protected_periods"')[1][:60]


def test_recalcular_por_periodo_alcanza_una_fecha_completa(tmp_path):
    """Observación 7 del Auditor: el filtro literal dejaba esas filas fuera del recálculo."""
    service = legacy_with_full_date(tmp_path)
    with sqlite3.connect(service.repository.database_path) as con:
        con.execute("UPDATE commission_entries SET status='CALCULADA', paid_at=NULL WHERE id='e-X'")
        con.commit()
    service = CommissionService(CentralManagementService(
        CentralRepository(service.repository.database_path)))
    assert service.recalculate(SOL, period="2099-04")["evaluated"] == 1


# ------------------------------------------- el conflicto se asienta con su actor y sin tragarse
def discrepant(tmp_path):
    path = tmp_path / "discrepante.sqlite3"
    CommissionService(CentralManagementService(CentralRepository(path)))
    with sqlite3.connect(path) as con:
        con.execute("DELETE FROM commission_period_rate_events")
        for key, rate, amount in (("A", 700, 70_000), ("B", 500, 50_000)):
            con.execute(
                "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
                "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,"
                "envelope,content_hash,payload_json,version,created_at,updated_at)"
                " VALUES(?,?,'Óptica Asunción',?,'Vendedora Uno','COMUN','2099-04-05',1000000,1000000,"
                "0,'2099-04-05',0,NULL,'','h','{}',1,?,?)",
                (f"s-{key}", f"k-{key}", f"src-{key}", f"2099-04-0{1 if key == 'A' else 2}T00:00:00",
                 f"2099-04-0{1 if key == 'A' else 2}T00:00:00"))
            con.execute(
                "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,"
                "status,gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,"
                "policy_status,policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,"
                "paid_at,payment_reference,created_at,updated_at)"
                " VALUES(?,?,1,'2099-04','Óptica Asunción','Vendedora Uno','COMUN','PAGADA',"
                "1000000,0,1000000,?,?,?,?,1,'2026-08-01','GENERAL','2099-04-05','2099-05-10','T',?,?)",
                (f"e-{key}", f"s-{key}", rate, amount, POLICY_CANONICAL, CANONICAL_CODE,
                 f"2099-04-0{1 if key == 'A' else 2}T00:00:00",
                 f"2099-04-0{1 if key == 'A' else 2}T00:00:00"))
        con.commit()
    return CommissionService(CentralManagementService(CentralRepository(path)))


def test_un_conflicto_nuevo_del_mismo_mes_si_se_asienta(tmp_path):
    """Observación 4 del Auditor: la deduplicación por período tragaba la segunda discrepancia."""
    service = discrepant(tmp_path)
    conflictos = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert len(conflictos) == 1 and '"rates_bp": [500, 700]' in conflictos[0]["details_json"]

    # Un tercer pago vivo a otra tasa es un conflicto **distinto**, y debe verse.
    with sqlite3.connect(service.repository.database_path) as con:
        con.execute(
            "INSERT INTO commission_sales(id,identity_key,branch,source_sale_id,saleswoman,sale_kind,"
            "sale_date,total_amount,paid_amount,balance_amount,cancelled_date,voided,void_reason,"
            "envelope,content_hash,payload_json,version,created_at,updated_at)"
            " VALUES('s-C','k-C','Óptica Asunción','src-C','Vendedora Uno','COMUN','2099-04-07',"
            "1000000,1000000,0,'2099-04-07',0,NULL,'','h','{}',1,'2099-04-07T00:00:00','2099-04-07T00:00:00')")
        con.execute(
            "INSERT INTO commission_entries(id,sale_id,sequence,period,branch,saleswoman,sale_kind,status,"
            "gross_amount,agreement_discount,commissionable_base,rate_bp,commission_amount,policy_status,"
            "policy_code,policy_version,policy_effective_from,policy_scope,eligible_date,paid_at,"
            "payment_reference,created_at,updated_at)"
            " VALUES('e-C','s-C',1,'2099-04','Óptica Asunción','Vendedora Uno','COMUN','PAGADA',"
            "1000000,0,1000000,900,90000,?,?,1,'2026-08-01','GENERAL','2099-04-07','2099-05-10','T',"
            "'2099-04-07T00:00:00','2099-04-07T00:00:00')", (POLICY_CANONICAL, CANONICAL_CODE))
        con.commit()
    service = CommissionService(CentralManagementService(
        CentralRepository(service.repository.database_path)))
    conflictos = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert len(conflictos) == 2
    assert '"rates_bp": [500, 700, 900]' in conflictos[0]["details_json"]


def test_un_conflicto_en_caliente_se_asienta_a_nombre_de_quien_lo_provoco(tmp_path):
    """Observación 5 del Auditor: `actor` estaba fijado en duro a `MIGRACION`."""
    service = discrepant(tmp_path)
    # Reabrir no cambia nada; la discrepancia ya está asentada por la migración.
    assert audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")[0]["actor"] == "MIGRACION"
    # Una operación de una usuaria que vuelve a evaluar el mes lo asienta a su nombre.
    with sqlite3.connect(service.repository.database_path) as con:
        con.execute("DELETE FROM central_audit WHERE action='COMMISSION_PERIOD_RATE_SEED_SKIPPED'")
        con.commit()
    nueva, _ = service.register_sale(SOL, sale(source_sale_id="nueva", sale_date="2099-04-25"))
    service.recalculate(SOL)
    conflictos = audits(service, "COMMISSION_PERIOD_RATE_SEED_SKIPPED")
    assert conflictos and conflictos[0]["actor"] == "sol"
