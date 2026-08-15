"""Captura reproducible Full HD del detalle horizontal con datos sintéticos."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bc_gestion_central import build_service
from modulos.gestion_central.models import Unit
from modulos.gestion_central.ui import CentralPilotWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bc-central-horizontal-") as directory:
        service = build_service(Path(directory))
        service.bootstrap_synthetic_pilot()
        app = CentralPilotWindow(service, notifier=lambda *_: None)
        app.root.overrideredirect(True)
        app.root.geometry("1920x1080+0+0")
        app.root.attributes("-topmost", True)
        app.root.update()
        app.show_detail(Unit.OPTICA_ASUNCION)
        app.root.update_idletasks(); app.root.lift(); app.root.focus_force(); app.root.update()
        x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
        ImageGrab.grab((x, y, x + app.root.winfo_width(), y + app.root.winfo_height())).save(args.output)
        app.root.destroy()
        for handler in list(app.logger.handlers):
            handler.close()
            app.logger.removeHandler(handler)
    print(f"BC_GESTION_CENTRAL_DETAIL_CAPTURE_OK {args.output} 1920x1080")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
