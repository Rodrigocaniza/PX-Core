"""Demuestra que Pilar y Asuncion ven cosas distintas segun responsabilidad.

Recorre el circuito sobre los 15 registros TEST reales e imprime, en cada
etapa, que ve y que alerta cada local. Al terminar deja el escenario en su
punto de partida.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.pop("BC_CAJA_DATA_DIR", None)
from modulos.caja_diaria.config import resolve_data_paths
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.caja_diaria.application.tracking_service import TrackingService

AYER = date.today() - timedelta(days=1)


def foto(t, etapa):
    linea = [f"{etapa:<34}"]
    for local in ("ASUNCION", "PILAR"):
        p = t.pending_actions_for_branch(local)
        filas = t.board(responsible_branch=local)["rows"]
        alerta = p["alertas"][0]["texto"] if p["alertas"] else "—"
        linea.append(f"{local}: ve {len(filas):>2}  alerta: {alerta}")
    print("   ".join(linea))


def main() -> int:
    repo = SQLiteCashDayRepository(resolve_data_paths().database)
    t = TrackingService(repo)
    t.bind_register_to_branch("PILAR", "PILAR", assigned_by="SMOKE RC22",
                              reason="contexto de prueba de dos locales")
    print("binding caja -> sucursal:",
          [(b["cash_register"], b["branch"]) for b in t.list_register_branches()])
    print()

    cand = t.shipment_candidates()
    works = t.create_pilar_shipment([o.id for o in cand], operator="Nidia (TEST)")["works"]
    foto(t, "1-2) Pilar envia 15")

    for w in works:
        t.receive_in_asuncion(w.id, responsible="Ana (TEST)")
    foto(t, "5) Asuncion recibe los 15")

    labs = t.selectable_laboratories()
    for w, lab in zip(works[:3], labs):
        t.send_to_laboratory(w.id, lab.id, expected_date=AYER, expected_time="15:00",
                             responsible="Ana (TEST)")
    foto(t, "6-7) 3 al laboratorio, vencidos")

    for w in works[:3]:
        t.receive_from_laboratory(w.id, responsible="Ana (TEST)")
    foto(t, "8a) 3 recibidos del laboratorio")

    t.send_batch_to_pilar([w.id for w in works[:3]], responsible="Ana (TEST)")
    foto(t, "8b) encomienda en camino a Pilar")

    for w in works[:3]:
        t.receive_in_pilar(w.id, responsible="Nidia (TEST)")
    foto(t, "10) recibidos en Pilar")
    print()
    print("completados:", len(t.board(scope='COMPLETADOS')['rows']),
          "| activos:", len(t.board()['rows']))
    repo.integrity_check()
    repo.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
