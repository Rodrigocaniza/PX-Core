"""Smoke real del lifecycle de la ventana principal de BC Caja."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bc_caja


def window_exists(window) -> bool:
    try:
        return bool(window.winfo_exists())
    except Exception:
        return False


def main() -> int:
    original_mainloop = ctk.CTk.mainloop
    cycle = {"number": 0}

    with tempfile.TemporaryDirectory(prefix="bc-caja-window-lifecycle-") as directory:
        os.environ["BC_CAJA_DATA_DIR"] = directory
        os.environ["BC_CAJA_WINDOW_SIZE"] = "1366x768"

        def exercise_mainloop(window):
            cycle["number"] += 1
            window.update_idletasks()
            window.update()
            if tuple(bool(value) for value in window.resizable()) != (True, True):
                raise RuntimeError("resize horizontal/vertical deshabilitado")
            minimum = tuple(
                int(value) for value in window.tk.splitlist(
                    window.tk.call("wm", "minsize", window._w)
                )
            )
            if minimum[0] > 1100 or minimum[1] > 680:
                raise RuntimeError(f"mínimo inesperado: {minimum}")

            window.state("zoomed")
            window.update_idletasks()
            window.update()
            if window.state() != "zoomed":
                raise RuntimeError(f"maximizar falló: state={window.state()}")
            zoomed = (window.winfo_width(), window.winfo_height())

            window.state("normal")
            window.geometry("1200x700+20+20")
            window.update_idletasks()
            window.update()
            restored = (window.winfo_width(), window.winfo_height())
            if restored != (1200, 700):
                raise RuntimeError(f"restaurar/resize falló: {restored}")

            window.geometry("1250x720+20+20")
            window.update_idletasks()
            window.update()
            resized = (window.winfo_width(), window.winfo_height())
            if resized != (1250, 720):
                raise RuntimeError(f"resize ancho/alto falló: {resized}")

            if cycle["number"] == 1:
                if not window.protocol("WM_DELETE_WINDOW"):
                    raise RuntimeError("WM_DELETE_WINDOW no configurado")
                window._bc_application_lifecycle.close()
                close_method = "X/WM_DELETE_WINDOW"
            else:
                window.focus_force()
                window._bc_application_lifecycle.close()
                close_method = "Alt+F4"

            if window_exists(window):
                raise RuntimeError(f"{close_method} no destruyó la ventana raíz")
            print(
                f"BC_CAJA_WINDOW_CYCLE_OK cycle={cycle['number']} "
                f"zoomed={zoomed} restored={restored} resized={resized} "
                f"closed_by={close_method}"
            )

        ctk.CTk.mainloop = exercise_mainloop
        try:
            if bc_caja.main([]) != 0:
                raise RuntimeError("primer ciclo devolvió error")
            database = Path(directory) / "bc_caja.sqlite3"
            with closing(sqlite3.connect(database, timeout=1)) as connection:
                connection.execute("BEGIN EXCLUSIVE")
                connection.rollback()
            if bc_caja.main([]) != 0:
                raise RuntimeError("segundo ciclo devolvió error")
            with closing(sqlite3.connect(database, timeout=1)) as connection:
                connection.execute("BEGIN EXCLUSIVE")
                connection.rollback()
        finally:
            ctk.CTk.mainloop = original_mainloop
            os.environ.pop("BC_CAJA_WINDOW_SIZE", None)
            os.environ.pop("BC_CAJA_DATA_DIR", None)

    if cycle["number"] != 2:
        raise RuntimeError(f"ciclos incompletos: {cycle['number']}")
    print("BC_CAJA_WINDOW_LIFECYCLE_OK cycles=2 db_lock=none ghost_windows=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
