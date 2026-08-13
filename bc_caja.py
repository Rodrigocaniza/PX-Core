"""Entrypoint autonomo para el piloto local de BC Caja."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


class ApplicationLifecycle:
    """Owns DB and window shutdown; safe when Windows and finally both call it."""

    def __init__(self, controller, window):
        self.controller = controller
        self.window = window
        self.closed = False

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.controller.service.repository.close()
        finally:
            try:
                if self.window.winfo_exists():
                    self.window.quit()
                    self.window.destroy()
            except Exception:
                # Tk may already be torn down by the window manager.
                pass


def enable_windows_dpi_awareness() -> bool:
    """Activa coordenadas físicas antes de crear Tk; no escala la UI dos veces."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return True
        except (AttributeError, OSError):
            return False


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description="BC Caja - piloto local")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="verifica almacenamiento local sin abrir la interfaz",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--first-run-check", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def self_check(data_directory: Path | None = None) -> int:
    if data_directory is not None:
        os.environ["BC_CAJA_DATA_DIR"] = str(data_directory.resolve())

    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.config import resolve_data_paths

    paths = resolve_data_paths().ensure()
    controller = build_cash_day_controller(data_paths=paths)
    try:
        controller.service.repository.integrity_check()
    finally:
        controller.service.repository.close()
    print(f"BC_CAJA_SELF_CHECK_OK data={paths.root}")
    return 0


def first_run_check(data_directory: Path) -> int:
    """Ciclo sintetico E2E; se usa solo sobre un directorio temporal vacio."""
    data_directory = data_directory.resolve()
    if data_directory.exists() and any(data_directory.iterdir()):
        raise RuntimeError("first-run-check requiere un directorio temporal vacio")
    os.environ["BC_CAJA_DATA_DIR"] = str(data_directory)

    from modulos.caja_diaria.bootstrap import build_cash_day_controller

    values = {
        "fecha": "01-01-2099", "unidad": "PC", "caja_inicial": "500000",
        "descripcion": "OPERACION PILOTO", "sobre": "", "arm_org": "",
        "cod": "", "armazon": "", "cristal": "", "laboratorio": "LAB PILOTO",
        "receta_dr": "",
        "total": "300000", "efectivo": "300000", "tarjeta_cheque": "",
        "ordenes": "", "cuotas": "", "saldo": "", "gastos": "",
        "vendedora": "PILOTO",
    }
    controller = build_cash_day_controller()
    try:
        day, _ = controller.add_manual_entry(values)
        closed = controller.close_day("01-01-2099", "PC")
        if closed.closing_totals is None or closed.closing_totals.expected_cash != 800000:
            raise RuntimeError("el cierre sintetico no coincide")
        backup = controller.last_backup_path
        if backup is None or not backup.is_file():
            raise RuntimeError("el backup sintetico no fue creado")
    finally:
        controller.service.repository.close()

    restarted = build_cash_day_controller()
    try:
        recovered = restarted.list_history("01-01-2099", "PC")
        if recovered.closing_totals is None or recovered.closing_totals.expected_cash != 800000:
            raise RuntimeError("el reinicio no recupero el cierre sintetico")
        if recovered.entries[0].laboratory != "LAB PILOTO":
            raise RuntimeError("el reinicio no recupero el laboratorio sintetico")
    finally:
        restarted.service.repository.close()
    print("BC_CAJA_FIRST_RUN_OK opening=500000 cash=300000 final=800000 backup=OK restart=OK")
    return 0


def main(argv=None) -> int:
    args = _arguments(argv)
    if args.first_run_check:
        if args.data_dir is None:
            raise SystemExit("--first-run-check requiere --data-dir temporal")
        return first_run_check(args.data_dir)
    if args.self_check:
        return self_check(args.data_dir)

    enable_windows_dpi_awareness()
    import customtkinter as ctk
    from CajaDiaria import abrir_caja_diaria
    from modulos.caja_diaria.bootstrap import build_cash_day_controller

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    controller = build_cash_day_controller()
    window = abrir_caja_diaria(root, controller=controller, usar_ventana_raiz=True)
    lifecycle = ApplicationLifecycle(controller, window)
    window._bc_application_lifecycle = lifecycle
    window.protocol("WM_DELETE_WINDOW", lifecycle.close)
    window.bind("<Alt-F4>", lambda _event: (lifecycle.close(), "break")[1], add="+")
    try:
        root.mainloop()
    finally:
        lifecycle.close()
    return 0


def report_fatal_error(error: BaseException) -> None:
    """Persist startup failures where support can find them, even in windowed builds."""
    try:
        from modulos.caja_diaria.config import resolve_data_paths

        paths = resolve_data_paths().ensure()
        log = paths.logs / "startup-error.log"
        log.write_text(
            "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            encoding="utf-8",
        )
    except Exception:
        log = None
    if "--self-check" not in sys.argv and "--first-run-check" not in sys.argv:
        try:
            from tkinter import messagebox

            detail = f"No se pudo abrir BC Caja.\n\n{error}"
            if log is not None:
                detail += f"\n\nDetalle técnico: {log}"
            messagebox.showerror("BC Caja", detail)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as error:
        report_fatal_error(error)
        raise SystemExit(1)
