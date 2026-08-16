"""Captura 1920x1080 de la bandeja de comisiones sobre datos sintéticos efímeros."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bc_gestion_central import build_service
from modulos.gestion_central.comisiones import CommissionSaleInput, CommissionService
from modulos.gestion_central.ui import CentralPilotWindow


SALES = (
    ("Óptica Asunción", "cap-001", "Ana Piloto", "2099-04-03", "COMUN", 400_000, 200_000, "S-101"),
    ("Óptica Asunción", "cap-002", "Ana Piloto", "2099-04-06", "COMUN", 950_000, 950_000, "S-102"),
    ("Óptica Asunción", "cap-003", "Ana Piloto", "2099-04-09", "CONVENIO", 500_000, 0, "S-103"),
    ("Óptica Pilar", "cap-004", "Rosa Piloto", "2099-04-11", "COMUN", 1_250_000, 400_000, "S-201"),
    ("Óptica Pilar", "cap-005", "Rosa Piloto", "2099-04-14", "COMUN", 780_000, 780_000, "S-202"),
    ("Óptica Pilar", "cap-006", "Rosa Piloto", "2099-04-18", "CONVENIO", 1_600_000, 0, "S-203"),
    ("Consultorio Asunción", "cap-007", "Lucía Piloto", "2099-04-21", "COMUN", 620_000, 620_000, "S-301"),
    ("Consultorio Asunción", "cap-008", "Lucía Piloto", "2099-04-24", "COMUN", 340_000, 100_000, "S-302"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bc-comisiones-") as directory:
        core = build_service(Path(directory))
        core.bootstrap_synthetic_pilot()
        sol = core.authenticate("sol.piloto", "Piloto-Temporal-2026")
        service = CommissionService(core)
        ids = {}
        for row in SALES:
            sale_id, _ = service.register_sale(sol, CommissionSaleInput(*row))
            ids[row[1]] = sale_id
        # El porcentaje ya no se configura para la captura: la política oficial del 1%
        # queda instalada por la migración y el recálculo la aplica sola.
        service.recalculate(sol)
        entries = {row["sale_id"]: row["id"] for row in service.list_entries(sol)}
        # Estados visibles: revisada, aprobada, pagada y observada.
        service.review(sol, entries[ids["cap-002"]])
        service.review(sol, entries[ids["cap-005"]])
        service.approve(sol, entries[ids["cap-005"]], "Sol")
        service.review(sol, entries[ids["cap-007"]])
        service.approve(sol, entries[ids["cap-007"]], "Sol")
        service.mark_paid(sol, entries[ids["cap-007"]], "2099-05-04", "TRANSF-SINTETICA-01")
        service.observe(sol, entries[ids["cap-006"]], "Diferencia sintética con la planilla del local")

        app = CentralPilotWindow(core, notifier=lambda *_: None)
        app.root.overrideredirect(True)
        app.root.geometry("1920x1080+0+0")
        app.root.attributes("-topmost", True)
        app.root.update()
        app.show_commissions()
        panel = app.commissions_panel
        panel.tree.selection_set(entries[ids["cap-003"]])
        panel.tree.event_generate("<<TreeviewSelect>>")
        app.root.update_idletasks()
        app.root.lift()
        app.root.focus_force()
        app.root.update()
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        ImageGrab.grab((x, y, x + app.root.winfo_width(), y + app.root.winfo_height())).save(args.output)
        app.root.destroy()
        for handler in list(app.logger.handlers):
            handler.close()
            app.logger.removeHandler(handler)
    print(f"BC_COMISIONES_CAPTURE_OK {args.output} 1920x1080")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
