"""Captura reproducible 1920x1080 de mensajes y confirmaciones sintéticos."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bc_gestion_central import build_service
from modulos.gestion_central.delivery import DeliveryService
from modulos.gestion_central.models import Unit
from modulos.gestion_central.ui import CentralPilotWindow


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("output", type=Path); args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bc-central-delivery-") as directory:
        core = build_service(Path(directory)); core.bootstrap_synthetic_pilot()
        sol = core.authenticate("sol.piloto", "Piloto-Temporal-2026"); delivery = DeliveryService(core)
        delivery.queue(sol, Unit.OPTICA_ASUNCION, "Confirmar arqueo y PDF del cierre sintético", "CAJA-01")
        delivery.queue(sol, Unit.OPTICA_PILAR, "Revisar sobre S-014 sintético", "OFFLINE-01")
        delivery.queue(sol, Unit.CONSULTORIO_ASUNCION, "Confirmar recepción sintética", "CAJA-02")
        delivery.process_due(sol)
        app = CentralPilotWindow(core, notifier=lambda *_: None); app.root.overrideredirect(True); app.root.geometry("1920x1080+0+0"); app.root.attributes("-topmost", True)
        app.root.update(); app.show_messages(); app.root.update_idletasks()
        first = app.delivery_panel.tree.get_children()[0]
        app.delivery_panel.tree.selection_set(first); app.delivery_panel.tree.event_generate("<<TreeviewSelect>>")
        app.root.lift(); app.root.focus_force(); app.root.update()
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty(); width, height = app.root.winfo_width(), app.root.winfo_height()
        ImageGrab.grab((x, y, x + width, y + height)).save(args.output); app.root.destroy()
        for handler in list(app.logger.handlers): handler.close(); app.logger.removeHandler(handler)
    print(f"BC_GESTION_CENTRAL_DELIVERY_CAPTURE_OK {args.output} 1920x1080")
    return 0


if __name__ == "__main__": raise SystemExit(main())
