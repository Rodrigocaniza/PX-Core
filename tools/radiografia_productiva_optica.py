# -*- coding: utf-8 -*-
"""Radiografia de la base productiva de la Optica: lo que ninguna migracion puede mover.

Se corre antes y despues de aplicar migraciones y se comparan las dos salidas.
Que dos radiografias sean identicas es la prueba de que la linea nueva no toco
plata, stock, historia ni catalogo. No escribe nada: abre la base en solo lectura.

    python tools/radiografia_productiva_optica.py [--base <ruta>] [--salida <json>]
    python tools/radiografia_productiva_optica.py --comparar antes.json despues.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _abrir(base: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{base.as_posix()}?mode=ro", uri=True)


def radiografia(base: Path) -> dict:
    con = _abrir(base)
    try:
        uno = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
        filas = lambda s: [tuple(r) for r in con.execute(s).fetchall()]  # noqa: E731
        tablas = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}

        datos: dict = {}
        datos["archivo"] = {"tamano": base.stat().st_size, "sha256": sha256(base)}
        datos["integridad"] = uno("PRAGMA integrity_check")
        datos["foreign_key_check"] = filas("PRAGMA foreign_key_check")
        datos["migraciones"] = filas(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version")

        # --- Dinero: cada peso escrito en Caja, uno por uno ---
        datos["caja"] = {
            "dias": uno("SELECT COUNT(*) FROM cash_days"),
            "dias_detalle": filas(
                "SELECT id, business_date, unit, opening_cash, status, closing_total,"
                " closing_cash, closing_expenses, closing_entry_count, version"
                " FROM cash_days ORDER BY id"
            ),
            "entradas": uno("SELECT COUNT(*) FROM cash_entries"),
            "entradas_activas": uno("SELECT COUNT(*) FROM cash_entries WHERE status='ACTIVE'"),
            "total": uno("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
            "efectivo": uno("SELECT COALESCE(SUM(cash),0) FROM cash_entries"),
            "tarjeta_cheque": uno("SELECT COALESCE(SUM(card_check),0) FROM cash_entries"),
            "gastos": uno("SELECT COALESCE(SUM(expenses),0) FROM cash_entries"),
            "convenio": uno("SELECT COALESCE(SUM(agreement_amount),0) FROM cash_entries"),
            "entradas_detalle": filas(
                "SELECT id, cash_day_id, envelope, total, cash, card_check, expenses,"
                " status, revision, saleswoman, customer_document, customer_phone,"
                " balance_text, agreement_amount FROM cash_entries ORDER BY id"
            ),
            "revisiones": uno("SELECT COUNT(*) FROM cash_entry_revisions"),
            "max_revision_por_entrada": filas(
                "SELECT entry_id, MAX(revision) FROM cash_entry_revisions"
                " GROUP BY entry_id ORDER BY entry_id"
            ),
            "arqueos": uno("SELECT COUNT(*) FROM cash_counts"),
            "arqueos_snapshots": uno("SELECT COUNT(*) FROM cash_count_snapshots"),
            "correcciones_dia": uno("SELECT COUNT(*) FROM cash_day_corrections"),
            "sucursales": filas(
                "SELECT cash_register, branch FROM cash_register_branches ORDER BY cash_register"),
        }

        datos["venta_lineas"] = {
            "cantidad": uno("SELECT COUNT(*) FROM sale_items"),
            "detalle": filas(
                "SELECT id, cash_entry_id, position, code, item_type, frame_final_price,"
                " lens_final_price, no_cost, article_id, lens_article_id, laboratory"
                " FROM sale_items ORDER BY id"
            ),
        }

        # --- Catalogo y stock ---
        datos["catalogo"] = {
            "articulos": uno("SELECT COUNT(*) FROM articles"),
            "articulos_activos": uno("SELECT COUNT(*) FROM articles WHERE active=1"),
            "por_naturaleza": filas(
                "SELECT nature, COUNT(*) FROM articles GROUP BY nature ORDER BY nature"),
            "con_laboratorio_default": uno(
                "SELECT COUNT(*) FROM articles WHERE default_laboratory_id IS NOT NULL"),
            "categorias": uno("SELECT COUNT(*) FROM article_categories"),
            "marcas": uno("SELECT COUNT(*) FROM brands"),
            "proveedores": uno("SELECT COUNT(*) FROM suppliers"),
            "laboratorios": filas("SELECT id, name, active FROM laboratories ORDER BY id"),
        }
        datos["stock"] = {
            "movimientos": uno("SELECT COUNT(*) FROM stock_movements"),
            "unidades_netas": uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"),
            "por_destino": filas(
                "SELECT destination, COUNT(*), COALESCE(SUM(quantity),0)"
                " FROM stock_movements GROUP BY destination ORDER BY destination"),
            "por_tipo": filas(
                "SELECT kind, COUNT(*), COALESCE(SUM(quantity),0)"
                " FROM stock_movements GROUP BY kind ORDER BY kind"),
            "integraciones_venta": uno("SELECT COUNT(*) FROM sale_stock_integrations"),
            "compensaciones_anulacion": uno("SELECT COUNT(*) FROM sale_void_compensations"),
            "compras": uno("SELECT COUNT(*) FROM purchases"),
            "lineas_compra": uno("SELECT COUNT(*) FROM purchase_lines"),
        }

        # --- Seguimiento / pedidos / laboratorios ---
        datos["pedidos"] = {
            "cantidad": uno("SELECT COUNT(*) FROM orders"),
            "detalle": filas(
                "SELECT id, branch, customer_name, envelope, saleswoman, status,"
                " cash_entry_id, delivery_date FROM orders ORDER BY id"),
            "revisiones_estado": uno("SELECT COUNT(*) FROM order_status_revisions"),
        }
        datos["seguimiento"] = {
            "trabajos": uno("SELECT COUNT(*) FROM tracked_works"),
            "transiciones": uno("SELECT COUNT(*) FROM tracked_work_transitions"),
            "contactos": uno("SELECT COUNT(*) FROM tracked_work_contacts"),
            "envios_pilar": uno("SELECT COUNT(*) FROM pilar_shipments"),
        }

        # --- Personas, auditoria, sincronizacion ---
        datos["personas"] = {
            "admin_users": uno("SELECT COUNT(*) FROM admin_users"),
            "por_rol": filas(
                "SELECT role, active, COUNT(*) FROM admin_users"
                " GROUP BY role, active ORDER BY role"),
            "responsables_autorizados": uno("SELECT COUNT(*) FROM authorized_responsibles"),
        }
        datos["auditoria"] = {
            "eventos": uno("SELECT COUNT(*) FROM admin_audit_log"),
            "por_accion": filas(
                "SELECT action, COUNT(*) FROM admin_audit_log GROUP BY action ORDER BY action"),
            "ultimo": filas(
                "SELECT actor, action, recorded_at FROM admin_audit_log"
                " ORDER BY recorded_at DESC LIMIT 1"),
        }
        datos["sincronizacion"] = {
            "domain_events": uno("SELECT COUNT(*) FROM domain_events"),
            "event_effects": uno("SELECT COUNT(*) FROM event_effects"),
            "mail_outbox": uno("SELECT COUNT(*) FROM mail_outbox"),
            "mail_history": uno("SELECT COUNT(*) FROM mail_history"),
            "import_runs": uno("SELECT COUNT(*) FROM import_runs"),
        }
        datos["ajustes"] = filas("SELECT key, value_json FROM app_settings ORDER BY key")

        # --- Lo que la linea nueva agrega, si ya esta ---
        nuevas = {}
        for tabla in ("factufacil_loads", "factufacil_history", "service_job_types",
                      "service_jobs", "service_job_events", "service_commission_policy",
                      "service_job_commissions", "service_commission_policy_versions"):
            nuevas[tabla] = uno(f"SELECT COUNT(*) FROM {tabla}") if tabla in tablas else None
        datos["linea_nueva"] = nuevas
        datos["tablas"] = sorted(tablas)
        return datos
    finally:
        con.close()


INMUTABLE = ("caja", "venta_lineas", "catalogo", "stock", "pedidos",
             "seguimiento", "auditoria", "sincronizacion", "ajustes")


def comparar(antes: dict, despues: dict) -> list[str]:
    """Devuelve las diferencias en todo lo que una migracion NO puede mover."""
    diferencias: list[str] = []
    for bloque in INMUTABLE:
        a, d = antes.get(bloque), despues.get(bloque)
        if a == d:
            continue
        if isinstance(a, dict) and isinstance(d, dict):
            for clave in sorted(set(a) | set(d)):
                if a.get(clave) != d.get(clave):
                    diferencias.append(f"{bloque}.{clave}: {a.get(clave)!r} -> {d.get(clave)!r}")
        else:
            diferencias.append(f"{bloque}: {a!r} -> {d!r}")
    return diferencias


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=None)
    parser.add_argument("--salida", type=Path, default=None)
    parser.add_argument("--comparar", nargs=2, type=Path, default=None,
                        metavar=("ANTES", "DESPUES"))
    args = parser.parse_args()

    if args.comparar:
        antes = json.loads(args.comparar[0].read_text(encoding="utf-8"))
        despues = json.loads(args.comparar[1].read_text(encoding="utf-8"))
        diffs = comparar(antes, despues)
        print(f"migraciones antes:   {len(antes['migraciones'])}")
        print(f"migraciones despues: {len(despues['migraciones'])}")
        print(f"integridad despues:  {despues['integridad']}")
        print(f"foreign_key_check:   {despues['foreign_key_check'] or 'sin violaciones'}")
        if diffs:
            print(f"\nFALLA: {len(diffs)} invariante(s) productivo(s) se movieron:")
            for d in diffs:
                print(f"  - {d}")
            return 1
        print("\nOK: ningun invariante productivo se movio.")
        return 0

    base = args.base or resolve_data_paths().database
    if not base.exists():
        print(f"No existe la base: {base}")
        return 2
    datos = radiografia(base)
    texto = json.dumps(datos, indent=2, ensure_ascii=False)
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
        print(f"Radiografia escrita en {args.salida}")
        print(f"  base        {base}")
        print(f"  sha256      {datos['archivo']['sha256']}")
        print(f"  tamano      {datos['archivo']['tamano']}")
        print(f"  migraciones {len(datos['migraciones'])} (ultima {datos['migraciones'][-1][0]})")
        print(f"  integridad  {datos['integridad']}")
        print(f"  fk_check    {datos['foreign_key_check'] or 'sin violaciones'}")
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
