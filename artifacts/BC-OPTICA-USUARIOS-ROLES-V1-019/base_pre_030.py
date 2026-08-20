# -*- coding: utf-8 -*-
"""Arma una base local en el estado 029, con ventas y una administradora.

No es la base de la Optica y no puede serlo. Es una base con la misma forma:
migrada hasta la 029, con dias de caja, ventas, gastos y una anulada, para que
aplicar la 030 encima signifique algo.
"""
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(RAIZ))

DESTINO = Path(sys.argv[1])

import modulos.caja_diaria.infrastructure.sqlite_repository as repo_mod  # noqa: E402

# La 030 se esconde: asi la base nace en el estado anterior, que es el que hay
# hoy en la Optica. Se restaura antes de terminar.
MIGR = repo_mod.MIGRATIONS_DIR
falsa = Path(tempfile.mkdtemp()) / "migrations"
falsa.mkdir(parents=True)
for sql in sorted(MIGR.glob("*.sql")):
    if not sql.name.startswith("030"):
        shutil.copy2(sql, falsa / sql.name)
repo_mod.MIGRATIONS_DIR = falsa

from modulos.caja_diaria.domain.models import CashDay, CashEntry  # noqa: E402
from modulos.caja_diaria.application.services import CashDayService  # noqa: E402
from modulos.caja_diaria.application.carry_forward import (  # noqa: E402
    PreviousClosedDayCarryForwardPolicy,
)

DESTINO.unlink(missing_ok=True)
DESTINO.parent.mkdir(parents=True, exist_ok=True)
repositorio = repo_mod.SQLiteCashDayRepository(DESTINO)
try:
    repositorio.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    repositorio.bind_register_to_branch("P2", "PILAR", assigned_by="admin")
    ventas = [
        ("Maria Gonzalez", "1001", 450000, "ana", "1234567", "0981111222",
         "OD esf -2.00 cil -0.75 eje 90 · OI esf -1.75 cil -0.50 eje 85 · adición 2.00"),
        ("Jose Ramirez", "1002", 300000, "rosa", "7654321", "0982222333", "lejos"),
        ("Ana Duarte", "1003", 1250000, "ana", "3456789", "0983333444",
         "multifocal · armazón del cliente · avisar cuando llegue"),
        ("Carlos Benitez", "1004", 180000, "rosa", "4567890", "", ""),
    ]
    entradas = [
        CashEntry(description=d, envelope=s, total=t, cash=t, saleswoman=v,
                  customer_document=doc, customer_phone=tel, observations=obs)
        for d, s, t, v, doc, tel, obs in ventas
    ]
    entradas.append(CashEntry(description="Nafta", expenses=50000))
    dia = CashDay(business_date=date(2026, 8, 18), unit="PC", opening_cash=100000,
                  opened_by="ana", entries=tuple(entradas))
    repositorio.save(dia)
    guardado = repositorio.get_by_date_and_unit(date(2026, 8, 18), "PC")
    servicio = CashDayService(repositorio, PreviousClosedDayCarryForwardPolicy())
    servicio.void_entry(guardado.id, guardado.entries[3].id,
                        "el cliente se arrepintio", user="ana")

    pilar = CashDay(business_date=date(2026, 8, 19), unit="P2", opening_cash=0,
                    opened_by="rosa",
                    entries=(CashEntry(description="Lucia Ayala", envelope="2001",
                                       total=700000, cash=700000, saleswoman="rosa",
                                       customer_document="9876543",
                                       customer_phone="0984444555",
                                       observations="cerca · cristal fotocromatico"),))
    repositorio.save(pilar)
    from modulos.caja_diaria.application.admin_ops import AdminOperations
    import tempfile as _tmp
    AdminOperations(repositorio, Path(_tmp.mkdtemp())).create_initial_admin(
        "sol", "administradora-2026")
finally:
    repositorio.close()
    repo_mod.MIGRATIONS_DIR = MIGR

import sqlite3  # noqa: E402

con = sqlite3.connect(DESTINO)
print("base pre-030:", DESTINO)
print("  migraciones :", con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0])
print("  max version :", con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
print("  dias        :", con.execute("SELECT COUNT(*) FROM cash_days").fetchone()[0])
print("  entradas    :", con.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0])
print("  activas     :", con.execute("SELECT COUNT(*) FROM cash_entries WHERE status='ACTIVE'").fetchone()[0])
print("  usuarios    :", con.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0])
print("  columnas 030:", [r[1] for r in con.execute("PRAGMA table_info(admin_users)")
                          if r[1] in ("display_name","branch","created_by","updated_by")] or "ninguna")
con.close()
