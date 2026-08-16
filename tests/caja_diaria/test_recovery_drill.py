from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from modulos.caja_diaria.infrastructure.backup import LocalBackupService
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository


MIGRATIONS = Path(__file__).parents[2] / "modulos" / "caja_diaria" / "infrastructure" / "migrations"


def _anonymized_pre_010_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        for migration in sorted(MIGRATIONS.glob("00[1-9]_*.sql")):
            connection.executescript(migration.read_text(encoding="utf-8"))
            version = migration.stem.split("_", 1)[0]
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,CURRENT_TIMESTAMP)",
                (version,),
            )
        connection.execute(
            """INSERT INTO cash_days(
                id,business_date,unit,opening_cash,status,opened_at,closed_at,
                closing_total,closing_cash,closing_card_check,closing_expenses,
                closing_expected_cash,closing_entry_count,version
            ) VALUES ('day-anon','2026-08-12','ANON',100000,'CLOSED',
                '2026-08-12T08:00:00+00:00','2026-08-12T18:00:00+00:00',
                900000,400000,200000,50000,450000,2,2)"""
        )
        entries = [
            ('sale-anon','Venta anonimizada',700000,300000,200000,'999999'),
            ('move-anon','Movimiento anonimizado',200000,100000,0,'100000'),
        ]
        connection.executemany(
            """INSERT INTO cash_entries(
                id,cash_day_id,description,total,cash,card_check,balance_text,
                created_at,updated_at,status,revision,expenses
            ) VALUES (?, 'day-anon', ?, ?, ?, ?, ?,
                '2026-08-12T09:00:00+00:00','2026-08-12T09:00:00+00:00','ACTIVE',1,0)""",
            entries,
        )
        connection.executemany(
            """INSERT INTO sale_items(
                id,cash_entry_id,position,description,code,item_type,frame_price,lens_price
            ) VALUES (?,?,?,?,?,?,?,?)""",
            [
                ('item-a','sale-anon',0,'Producto A','A','MARCO',200000,150000),
                ('item-b','sale-anon',1,'Producto B','B','LENTE',100000,250000),
            ],
        )
        connection.execute(
            """INSERT INTO cash_entry_revisions(
                entry_id,cash_day_id,revision,action,snapshot_json,recorded_at
            ) VALUES ('sale-anon','day-anon',1,'UPDATE',
                '{"description":"Venta anonimizada","total":700000}',
                '2026-08-12T10:00:00+00:00')"""
        )
        connection.execute(
            """INSERT INTO cash_counts(
                id,cash_day_id,expected_total,counted_total,difference,status,quantities_json,recorded_at
            ) VALUES ('count-anon','day-anon',450000,450000,0,'OK','{"100000":4,"50000":1}',
                '2026-08-12T18:00:00+00:00')"""
        )
        connection.commit()
    finally:
        connection.close()


def _rows(path: Path, table: str) -> list[tuple]:
    connection = sqlite3.connect(path)
    try:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        return connection.execute(
            f"SELECT {','.join(columns)} FROM {table} ORDER BY 1"
        ).fetchall()
    finally:
        connection.close()


def test_anonymized_backup_restore_migrations_and_interruption_recovery(tmp_path: Path) -> None:
    source = tmp_path / "anonymous-source.sqlite3"
    _anonymized_pre_010_database(source)
    before = {table: _rows(source, table) for table in (
        "cash_days", "cash_entries", "sale_items", "cash_counts", "cash_entry_revisions"
    )}

    repository = SQLiteCashDayRepository(source)
    backup = LocalBackupService(repository, tmp_path / "backups").create_backup("drill")
    repository.integrity_check()
    repository.close()

    restored = tmp_path / "restored.sqlite3"
    shutil.copy2(backup, restored)
    recovered = SQLiteCashDayRepository(restored)
    recovered.integrity_check()
    recovered.migrate()  # explicit idempotence pass after automatic 010/011 migration
    recovered.close()

    connection = sqlite3.connect(restored)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(f"{version:03d}",) for version in range(1, 20)]
        assert connection.execute(
            "SELECT agreement_amount,balance_text FROM cash_entries WHERE id='sale-anon'"
        ).fetchone() == (0, "999999")
        assert connection.execute("SELECT COUNT(*) FROM agreement_balance_corrections").fetchone() == (0,)
    finally:
        connection.close()

    # 010 adds only a defaulted column and 011 only touches rows with agreements.
    assert _rows(restored, "cash_days") == before["cash_days"]
    assert [row[:-2] for row in _rows(restored, "cash_entries")] == before["cash_entries"]
    restored_items = _rows(restored, "sale_items")
    assert [row[:10] for row in restored_items] == before["sale_items"]
    assert all(row[10:] == (0, 0, row[6] or 0, row[7] or 0, 0) for row in restored_items)
    for table in ("cash_counts", "cash_entry_revisions"):
        assert _rows(restored, table) == before[table]

    # Simulated interrupted copy is rejected, then recovery uses the intact backup.
    interrupted = tmp_path / "interrupted.sqlite3"
    interrupted.write_bytes(backup.read_bytes()[:128])
    with pytest.raises(sqlite3.DatabaseError):
        SQLiteCashDayRepository(interrupted)
    shutil.copy2(backup, interrupted)
    retry = SQLiteCashDayRepository(interrupted)
    retry.integrity_check()
    retry.migrate()
    retry.close()
    interrupted_items = _rows(interrupted, "sale_items")
    assert [row[:10] for row in interrupted_items] == before["sale_items"]
    assert all(row[10:] == (0, 0, row[6] or 0, row[7] or 0, 0) for row in interrupted_items)
