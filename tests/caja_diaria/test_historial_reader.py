from __future__ import annotations

import sqlite3

import pytest

from modulos.historial_externo.history import HistoryQuery
from modulos.historial_externo.sqlite_reader import SQLiteHistoryReader


@pytest.fixture
def history_db(tmp_path):
    path = tmp_path / "bc_caja.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE cash_days(id TEXT PRIMARY KEY, business_date TEXT, unit TEXT);
        CREATE TABLE cash_entries(
          id TEXT PRIMARY KEY, cash_day_id TEXT, description TEXT, envelope TEXT,
          customer_document TEXT, customer_phone TEXT, saleswoman TEXT, performed_by TEXT,
          status TEXT, total INTEGER, cash INTEGER, card_check INTEGER,
          agreement_amount INTEGER, balance_text TEXT, observations TEXT,
          prescription_doctor TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE sale_items(id TEXT, cash_entry_id TEXT, position INTEGER,
          description TEXT, code TEXT, laboratory TEXT, prescription_doctor TEXT);
        CREATE TABLE cash_entry_revisions(entry_id TEXT, action TEXT, revision INTEGER,
          recorded_at TEXT, snapshot_json TEXT);
        CREATE TABLE service_jobs(id TEXT, reference TEXT, received_at TEXT, branch TEXT,
          customer_name TEXT, customer_phone TEXT, job_type TEXT, description TEXT,
          observations TEXT, received_by TEXT, responsible TEXT, status TEXT,
          charged_amount INTEGER, cash_entry_id TEXT, updated_at TEXT);
        CREATE TABLE service_job_events(job_id TEXT, sequence INTEGER, occurred_at TEXT,
          event_type TEXT, actor TEXT, reason TEXT);
        INSERT INTO cash_days VALUES('d1','2026-08-20','ASUNCION');
        INSERT INTO cash_days VALUES('d2','2026-08-21','PILAR');
        INSERT INTO cash_entries VALUES(
          'v1','d1','Ana López','S-10','1234567','0981 111','Marta','',
          'ACTIVE',900000,400000,300000,100000,'100000','Primera compra','Dra. Sol',
          '2026-08-20T10:00:00','2026-08-20T10:00:00');
        INSERT INTO cash_entries VALUES(
          'v2','d2','Ana López','S-11','1234567','0981 111','Luz','',
          'VOIDED',500000,500000,0,0,'0','Se corrigió medida','',
          '2026-08-21T10:00:00','2026-08-21T11:00:00');
        INSERT INTO sale_items VALUES('i1','v1',0,'Armazón','A-1','','');
        INSERT INTO sale_items VALUES('i2','v1',1,'Cristal progresivo','C-9','Lab Uno','Dra. Sol');
        INSERT INTO cash_entry_revisions VALUES(
          'v2','VOID',2,'2026-08-21T11:00:00','{"void_reason":"error de graduación"}');
        INSERT INTO service_jobs VALUES(
          'j1','C-77','2026-08-21T12:00:00','ASUNCION','Ana López','0981 111',
          'COMPOSTURA','Cambiar patilla','Urgente','Mario','Carlos','LISTO',50000,'v2',
          '2026-08-21T13:00:00');
        INSERT INTO service_job_events VALUES(
          'j1',1,'2026-08-21T13:00:00','MARCADO_LISTO','Carlos','');
    """)
    connection.commit(); connection.close()
    return path


@pytest.mark.parametrize("query", [
    HistoryQuery(document="1234567"), HistoryQuery(name="ana"),
    HistoryQuery(phone="0981"), HistoryQuery(envelope="S-10")])
def test_busca_por_los_cuatro_identificadores(history_db, query):
    assert SQLiteHistoryReader(history_db).search(query).events


def test_ficha_consolida_y_ordena_mas_reciente_primero(history_db):
    history = SQLiteHistoryReader(history_db).search(HistoryQuery(document="1234567"))
    assert history.display_name == "Ana López"
    assert history.documents == ("1234567",)
    assert history.phones == ("0981 111",)
    assert [event.kind for event in history.events] == ["TRABAJO", "VENTA", "VENTA"]
    assert history.events[1].status == "VOIDED"
    assert "error de graduación" in history.events[1].trace[0]
    assert "Cristal progresivo" in history.events[2].items[1]
    assert history.events[2].prescription == ("Dra. Sol",)


def test_conexion_es_query_only(history_db):
    connection = SQLiteHistoryReader(history_db)._connect()
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM cash_entries")
    finally:
        connection.close()


def test_filtro_de_sucursal_se_aplica_en_sqlite_antes_de_retornar(history_db):
    reader = SQLiteHistoryReader(history_db)
    asuncion = reader.search(HistoryQuery(name="Ana"), branch="ASUNCION")
    pilar = reader.search(HistoryQuery(name="Ana"), branch="PILAR")
    assert {event.branch for event in asuncion.events} == {"ASUNCION"}
    assert {event.branch for event in pilar.events} == {"PILAR"}
    assert {event.envelope for event in asuncion.events} == {"S-10", "C-77"}
    assert {event.envelope for event in pilar.events} == {"S-11"}


def test_documento_fuerte_no_trae_homonimo_aunque_coincida_el_nombre(history_db):
    connection = sqlite3.connect(history_db)
    connection.execute("""INSERT INTO cash_entries VALUES(
      'v3','d1','Ana López','S-99','9999999','0972 999','Otra','',
      'ACTIVE',100000,100000,0,0,'0','Homónima','',
      '2026-08-19T10:00:00','2026-08-19T10:00:00')""")
    connection.commit(); connection.close()
    history = SQLiteHistoryReader(history_db).search(
        HistoryQuery(document="1.234.567", name="Ana López"))
    assert history.documents == ("1234567",)
    assert {item.envelope for item in history.events if item.kind == "VENTA"} == {"S-10", "S-11"}
