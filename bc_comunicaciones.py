"""Entrypoint autónomo de BC Comunicaciones.

El operador abre esta aplicación y trabaja: no configura rutas, ni bases de
datos, ni variables de entorno.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description="BC Comunicaciones - biblioteca de mensajes")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="verifica el almacenamiento local sin abrir la interfaz",
    )
    parser.add_argument("--data-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--first-run-check", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def self_check(data_directory: Path | None = None) -> int:
    if data_directory is not None:
        os.environ["BC_COMUNICACIONES_DATA_DIR"] = str(data_directory.resolve())

    from modulos.comunicaciones.bootstrap import build_controller
    from modulos.comunicaciones.config import resolve_data_paths

    paths = resolve_data_paths().ensure()
    controller = build_controller(data_paths=paths)
    try:
        controller.repository.integrity_check()
        plantillas = len(controller.search("", include_inactive=True))
    finally:
        controller.repository.close()
    print(f"BC_COMUNICACIONES_SELF_CHECK_OK data={paths.root} templates={plantillas}")
    return 0


def first_run_check(data_directory: Path) -> int:
    """Ciclo E2E sintético sobre un directorio temporal vacío.

    Recorre el flujo real completo: precarga, búsqueda, preparación con
    variables, copiado, favorito, alta de plantilla, respaldo, reinicio y
    restauración.
    """
    data_directory = data_directory.resolve()
    if data_directory.exists() and any(data_directory.iterdir()):
        raise RuntimeError("first-run-check requiere un directorio temporal vacio")
    os.environ["BC_COMUNICACIONES_DATA_DIR"] = str(data_directory)

    from modulos.comunicaciones.bootstrap import build_controller
    from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard

    clipboard = InMemoryClipboard()
    controller = build_controller(clipboard=clipboard)
    try:
        precargadas = len(controller.search("", include_inactive=True))
        if precargadas == 0:
            raise RuntimeError("la precarga inicial de plantillas no se aplico")

        encontradas = controller.search("retirar")
        if not encontradas:
            raise RuntimeError("la busqueda no encontro la plantilla de retiro")
        plantilla = encontradas[0]

        formulario = controller.open_template(plantilla.id)
        valores = {spec.name: f"VALOR {spec.name.upper()}" for spec in formulario.specs}
        vista = controller.preview(plantilla, valores)
        if not vista.is_complete:
            raise RuntimeError("la vista previa quedo incompleta con todas las variables cargadas")

        mensaje = controller.copy_message(plantilla.id, valores, operator="PILOTO")
        if clipboard.text != mensaje.final_text:
            raise RuntimeError("el mensaje no llego al portapapeles")
        if "{{" in mensaje.final_text:
            raise RuntimeError("quedaron variables sin reemplazar en el mensaje final")

        controller.toggle_favorite(plantilla.id)
        nueva = controller.save_template({
            "title": "PLANTILLA PILOTO",
            "body": "Hola {{cliente}}, mensaje de verificacion.",
            "category_slug": "generales",
            "keywords": "piloto verificacion",
            "active": True,
        })
        respaldo = controller.create_backup("verificacion")
        if not respaldo.is_file():
            raise RuntimeError("el respaldo sintetico no fue creado")
        total_antes = len(controller.search("", include_inactive=True))
    finally:
        controller.repository.close()

    reiniciado = build_controller(clipboard=InMemoryClipboard())
    try:
        if len(reiniciado.search("", include_inactive=True)) != total_antes:
            raise RuntimeError("el reinicio no recupero las plantillas")
        recuperada = reiniciado.library.get(nueva.id)
        if recuperada.title != "PLANTILLA PILOTO":
            raise RuntimeError("el reinicio no recupero la plantilla creada")
        if not reiniciado.library.get(plantilla.id).favorite:
            raise RuntimeError("el reinicio no recupero el favorito")
        if not reiniciado.recent(5):
            raise RuntimeError("el reinicio no recupero el historial")

        reiniciado.set_active(nueva.id, False)
        resultado = reiniciado.restore_backup(respaldo)
        if not reiniciado.library.get(nueva.id).active:
            raise RuntimeError("la restauracion no devolvio el estado previo")
        if resultado.templates != total_antes:
            raise RuntimeError("la restauracion no recupero todas las plantillas")
    finally:
        reiniciado.repository.close()

    print(
        "BC_COMUNICACIONES_FIRST_RUN_OK "
        f"seed={precargadas} copiado=OK favorito=OK alta=OK backup=OK restart=OK restore=OK"
    )
    return 0


def main(argv=None) -> int:
    args = _arguments(argv)
    if args.first_run_check:
        if args.data_dir is None:
            raise SystemExit("--first-run-check requiere --data-dir temporal")
        return first_run_check(args.data_dir)
    if args.self_check:
        return self_check(args.data_dir)

    import customtkinter as ctk

    from modulos.comunicaciones.bootstrap import build_controller
    from modulos.comunicaciones.infrastructure.clipboard import TkClipboard
    from modulos.comunicaciones.ui.app import abrir_comunicaciones

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.withdraw()
    controller = build_controller(clipboard=TkClipboard(root))
    ventana = abrir_comunicaciones(root, controller)

    def cerrar_aplicacion():
        controller.repository.close()
        root.destroy()

    ventana.protocol("WM_DELETE_WINDOW", cerrar_aplicacion)
    root.mainloop()
    return 0


def report_fatal_error(error: BaseException) -> None:
    """Deja el fallo de arranque donde soporte pueda encontrarlo, incluso sin consola."""
    try:
        from modulos.comunicaciones.config import resolve_data_paths

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

            detalle = f"No se pudo abrir BC Comunicaciones.\n\n{error}"
            if log is not None:
                detalle += f"\n\nDetalle técnico: {log}"
            messagebox.showerror("BC Comunicaciones", detalle)
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
