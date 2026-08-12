"""Captura reproducible de BC Caja atravesando el entrypoint real bc_caja.main."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bc_caja


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    original_mainloop = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-entrypoint-") as directory:
        os.environ["BC_CAJA_DATA_DIR"] = directory

        def capture_mainloop(root):
            root.update_idletasks()
            windows = [child for child in root.winfo_children() if isinstance(child, ctk.CTkToplevel)]
            if len(windows) != 1:
                raise RuntimeError(f"entrypoint creó {len(windows)} ventanas de Caja")
            window = windows[0]
            window.attributes("-topmost", True)
            window.update_idletasks()
            window.lift()
            window.focus_force()
            window.update()
            x, y = window.winfo_rootx(), window.winfo_rooty()
            width, height = window.winfo_width(), window.winfo_height()
            ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
            window.attributes("-topmost", False)
            window.destroy()
            root.destroy()

        ctk.CTk.mainloop = capture_mainloop
        try:
            result = bc_caja.main([])
        finally:
            ctk.CTk.mainloop = original_mainloop
            os.environ.pop("BC_CAJA_DATA_DIR", None)
    print(f"BC_CAJA_REAL_ENTRYPOINT_CAPTURE_OK {args.output} 1366x768 result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())