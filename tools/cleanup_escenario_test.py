"""Revierte el escenario TEST del circuito de seguimiento.

Borra exclusivamente los identificadores registrados en el manifiesto: la caja
TEST, los tres laboratorios de prueba, los quince pedidos y cualquier trabajo
de seguimiento que la prueba haya generado a partir de ellos. No toca ningun
dato real, porque no borra por patron sino por id exacto.

Por defecto solo informa lo que haria. Para ejecutar hay que pasar --aplicar.

    python tools/cleanup_escenario_test.py                 # simulacion
    python tools/cleanup_escenario_test.py --aplicar       # revierte
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MANIFIESTO = Path("artifacts/BC-CAJA-ESCENARIO-TEST-CIRCUITO-001/TEST_DATA_MANIFEST.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true",
                        help="ejecuta el borrado; sin esta bandera solo simula")
    parser.add_argument("--reset-circuito", action="store_true",
                        help="deja los pedidos TEST como candidatos otra vez: borra "
                             "los trabajos y envios generados, conserva pedidos y "
                             "laboratorios")
    parser.add_argument("--manifiesto", type=Path, default=MANIFIESTO)
    args = parser.parse_args()

    datos = json.loads(args.manifiesto.read_text(encoding="utf-8"))
    os.environ.pop("BC_CAJA_DATA_DIR", None)
    from modulos.caja_diaria.config import resolve_data_paths

    base = resolve_data_paths().database
    order_ids = [o["id"] for o in datos["orders"]]
    lab_ids = [l["id"] for l in datos["laboratories"]]
    cash_day_id = datos["cash_day"]["id"]

    conexion = sqlite3.connect(str(base))
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    try:
        marcas_o = ",".join("?" for _ in order_ids)
        marcas_l = ",".join("?" for _ in lab_ids)
        work_ids = [
            r[0] for r in conexion.execute(
                f"SELECT id FROM tracked_works WHERE order_id IN ({marcas_o})"
                f" OR laboratory_id IN ({marcas_l})", (*order_ids, *lab_ids),
            )
        ]
        # Salvaguarda: la caja TEST debe seguir sin movimientos. Si alguien
        # cargo una venta real sobre ella, no se borra nada.
        movimientos = conexion.execute(
            "SELECT COUNT(*) FROM cash_entries WHERE cash_day_id = ?", (cash_day_id,),
        ).fetchone()[0]

        print(f"base            : {base}")
        print(f"caja TEST       : {cash_day_id} (movimientos: {movimientos})")
        print(f"pedidos TEST    : {len(order_ids)}")
        print(f"laboratorios    : {len(lab_ids)}")
        print(f"trabajos creados: {len(work_ids)} (con sus transiciones y contactos)")

        if args.reset_circuito:
            envios = [
                r[0] for r in conexion.execute(
                    f"SELECT DISTINCT shipment_id FROM tracked_works"
                    f" WHERE shipment_id IS NOT NULL AND order_id IN ({marcas_o})",
                    order_ids,
                )
            ]
            print(f"\nreset: borraria {len(work_ids)} trabajos y {len(envios)} envio(s);"
                  " los 15 pedidos y los laboratorios se conservan")
            if not args.aplicar:
                print("Simulacion. Nada fue borrado. Repetir con --aplicar.")
                return 0
            marcas_w = ",".join("?" for _ in work_ids) or "''"
            marcas_e = ",".join("?" for _ in envios) or "''"
            conexion.execute("BEGIN IMMEDIATE")
            conexion.execute(
                f"DELETE FROM tracked_work_contacts WHERE work_id IN ({marcas_w})", work_ids)
            conexion.execute(
                f"DELETE FROM tracked_work_transitions WHERE work_id IN ({marcas_w})", work_ids)
            conexion.execute(f"DELETE FROM tracked_works WHERE id IN ({marcas_w})", work_ids)
            conexion.execute(f"DELETE FROM pilar_shipments WHERE id IN ({marcas_e})", envios)
            conexion.commit()
            print("Circuito reiniciado. integrity_check:",
                  conexion.execute("PRAGMA integrity_check").fetchone()[0])
            return 0

        if movimientos:
            print("\nABORTADO: la caja TEST tiene movimientos. Revisar a mano "
                  "antes de borrar: podria haber datos reales.")
            return 2
        if not args.aplicar:
            print("\nSimulacion. Nada fue borrado. Repetir con --aplicar.")
            return 0

        conexion.execute("BEGIN IMMEDIATE")
        marcas_w = ",".join("?" for _ in work_ids) or "''"
        conexion.execute(
            f"DELETE FROM tracked_work_contacts WHERE work_id IN ({marcas_w})", work_ids)
        conexion.execute(
            f"DELETE FROM tracked_work_transitions WHERE work_id IN ({marcas_w})", work_ids)
        conexion.execute(f"DELETE FROM tracked_works WHERE id IN ({marcas_w})", work_ids)
        conexion.execute("DELETE FROM pilar_shipments WHERE id IN (SELECT shipment_id"
                         " FROM tracked_works WHERE 1=0)")
        conexion.execute(f"DELETE FROM orders WHERE id IN ({marcas_o})", order_ids)
        conexion.execute(f"DELETE FROM laboratories WHERE id IN ({marcas_l})", lab_ids)
        conexion.execute("DELETE FROM cash_days WHERE id = ?", (cash_day_id,))
        conexion.commit()
        print("\nRevertido. Verificando integridad...")
        print("integrity_check:", conexion.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        conexion.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
