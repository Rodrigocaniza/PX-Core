"""Entrypoint autonomo para el piloto local de BC Caja."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
import threading
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
    parser.add_argument("--security-check", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def _dia_sintetico_libre(controller) -> str:
    """Primer dia de 2099 que este sin abrir o abierto.

    El diagnostico escribe una venta y despues cierra el dia. Correrlo dos veces
    sobre la misma fecha fallaba, porque a un dia cerrado no se le puede agregar
    una venta. Se usa 2099 para que sea inconfundiblemente sintetico y no se
    mezcle nunca con la operacion real.
    """
    from datetime import date, timedelta

    from modulos.caja_diaria.domain.models import CashDayStatus

    dia = date(2099, 1, 1)
    for _ in range(365):
        existente = controller.service.repository.get_by_date_and_unit(dia, "PC")
        if existente is None or existente.status is CashDayStatus.OPEN:
            return dia.strftime("%d-%m-%Y")
        dia += timedelta(days=1)
    raise RuntimeError("no queda ningun dia sintetico libre en 2099")


def security_check(data_directory: Path | None = None) -> int:
    """Ciclo real con la seguridad puesta, sin abrir la interfaz.

    Es lo que hay que poder correr **desde el ejecutable congelado**: escribe
    una venta con datos de prueba, la vuelve a leer por el camino de siempre, y
    despues mira la base con SQLite pelado para comprobar que ahi no dice lo
    mismo. Funcionar desde Python no prueba nada sobre funcionar empaquetado, y
    esta es la unica forma de verificarlo antes de llegar a la Optica.

    No toca ninguna base existente mas alla de la que se le indique.
    """
    import sqlite3

    if data_directory is not None:
        os.environ["BC_CAJA_DATA_DIR"] = str(data_directory.resolve())

    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.config import resolve_data_paths
    from modulos.seguridad.application.field_protection import looks_protected

    arranque = security_gate()
    if arranque is None:
        print("BC_CAJA_SECURITY_CHECK_DENY")
        return 2

    from uuid import uuid4

    paths = resolve_data_paths().ensure()
    # La marca lleva un sufijo distinto en cada corrida. Sin eso, buscarla en el
    # archivo no distingue "la venta que acabo de escribir quedo en claro" de
    # "hay datos viejos sin proteger de antes de enrolar", que son dos problemas
    # distintos y solo el primero es una falla del camino de escritura.
    marca = f"PACIENTE DE PRUEBA BC {uuid4().hex[:8]}"
    telefono = "0900-000000"
    controller = build_cash_day_controller(data_paths=paths)
    try:
        fecha = _dia_sintetico_libre(controller)
        day, entrada_guardada = controller.add_manual_entry({
            "fecha": fecha, "unidad": "PC", "caja_inicial": "0",
            "descripcion": marca, "sobre": "PRUEBA-1", "arm_org": "", "cod": "",
            "armazon": "", "cristal": "", "laboratorio": "LAB", "receta_dr": "DR PRUEBA",
            "total": "100000", "efectivo": "100000", "tarjeta_cheque": "",
            "ordenes": "", "cuotas": "", "saldo": "", "gastos": "",
            "vendedora": "PRUEBA", "cliente_telefono": telefono,
            "cliente_documento": "0-PRUEBA", "notas": "OBSERVACION DE PRUEBA",
        })
        # Se busca POR ID la venta que se acaba de escribir. `entries[0]` seria
        # la primera del dia, que en una segunda corrida es la anterior: la
        # comprobacion habria fallado por mirar la fila equivocada y no por un
        # problema del cifrado.
        guardadas = {
            entrada.id: entrada
            for entrada in controller.service.repository.get(day.id).entries
        }
        leido = guardadas.get(entrada_guardada.id)
        if leido is None:
            raise RuntimeError("BC no encontro la venta que acababa de guardar")
        if leido.description != marca or leido.customer_phone != telefono:
            raise RuntimeError(
                "BC no recupero lo que acababa de guardar: "
                f"descripcion={'igual' if leido.description == marca else 'distinta'}, "
                f"telefono={'igual' if leido.customer_phone == telefono else 'distinto'}"
            )
        # Cerrar el dia es lo que genera la planilla, que es el otro archivo con
        # datos del paciente. Sin este paso el diagnostico no lo tocaria, y la
        # planilla es justamente lo que se descubrio en claro al auditar.
        planilla_sellada = None
        if day.status.value == "OPEN":
            from modulos.seguridad.application import file_protection

            cerrado, _cuenta, _correo = controller.admin.close_with_count(
                # La clave idempotente NO lleva la marca: se guarda en claro en
                # `cash_count_snapshots.idempotency_key`, y meter ahi el nombre
                # del cliente habria filtrado por la puerta de atras justo lo
                # que este diagnostico existe para vigilar.
                day.id, {50_000: 2}, "Comprobacion", f"security-check:{day.id}"
            )
            informes = sorted((paths.root / "Reports").glob("*.pdf"))
            if informes:
                planilla_sellada = file_protection.is_sealed(informes[-1])
    finally:
        controller.service.repository.close()

    connection = sqlite3.connect(str(paths.database))
    try:
        crudo = connection.execute(
            "SELECT description, customer_phone FROM cash_entries WHERE id=?",
            (entrada_guardada.id,),
        ).fetchone()
    finally:
        connection.close()

    protegido = arranque.data_protected and all(looks_protected(valor) for valor in crudo)
    filtrado = marca.encode("utf-8") in paths.database.read_bytes()

    # Restos de antes de proteger: no son una falla de este ciclo, pero hay que
    # decirlos, porque significan que falta correr `proteger-datos`.
    from modulos.seguridad.application import data_migration

    restos = sum(data_migration.plaintext_leftovers(paths.database).values())

    print(
        f"BC_CAJA_SECURITY_CHECK_OK outcome={arranque.decision.outcome if arranque.decision else 'SIN_ENROLAR'}"
        f" protegido={'si' if arranque.data_protected else 'no'}"
        f" cifrado_en_disco={'si' if protegido else 'no'}"
        f" filtracion={'SI' if filtrado else 'no'}"
        f" restos_en_claro={restos}"
        f" planilla={'sellada' if planilla_sellada else ('en_claro' if planilla_sellada is False else 'sin_generar')}"
    )
    if not arranque.data_protected:
        return 0
    if not protegido or filtrado:
        return 1
    return 0 if planilla_sellada is not False else 1


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


def security_gate() -> "object | None":
    """Autoriza esta instalacion antes de abrir la ventana, y activa el cifrado.

    Devuelve el resultado del arranque de seguridad, o `None` si la capa no
    esta disponible en este entorno.

    Dos reglas gobiernan esta funcion:

      * Una BC **sin enrolar** pasa de largo y abre como abria siempre. Es lo
        que permite instalar la capa sin cortar la operacion.
      * Un DENY cierra la puerta y **no toca la base**. Los datos quedan
        enteros, que es lo unico que hace posible el rollback.
    """
    from modulos.caja_diaria.config import resolve_data_paths
    from modulos.seguridad import bootstrap as seguridad

    paths = resolve_data_paths()
    arranque = seguridad.arrancar(seguridad.build_context(paths.database))
    if arranque.allowed:
        if arranque.degraded:
            _avisar("BC Caja", arranque.message)
        return arranque
    _avisar("BC Caja", arranque.message, error=True)
    return None


#: Modos que corren sin nadie delante de la pantalla. En cualquiera de ellos BC
#: no puede abrir un dialogo: no hay quien lo cierre y el proceso queda colgado
#: para siempre. Costo aprenderlo dos veces con un smoke que se quedo esperando
#: una ventana que nadie iba a ver.
MODOS_DE_DIAGNOSTICO = ("--self-check", "--first-run-check", "--security-check")


def _sin_pantalla() -> bool:
    return any(bandera in sys.argv for bandera in MODOS_DE_DIAGNOSTICO)


def _avisar(titulo: str, mensaje: str, *, error: bool = False) -> None:
    if not mensaje:
        return
    if _sin_pantalla():
        print(mensaje)
        return
    try:
        from tkinter import messagebox

        (messagebox.showerror if error else messagebox.showwarning)(titulo, mensaje)
    except Exception:
        # Sin entorno grafico —arranque desde consola— el mensaje va a stdout.
        print(mensaje)


def main(argv=None) -> int:
    args = _arguments(argv)
    if args.first_run_check:
        if args.data_dir is None:
            raise SystemExit("--first-run-check requiere --data-dir temporal")
        return first_run_check(args.data_dir)
    if args.self_check:
        return self_check(args.data_dir)
    if args.security_check:
        return security_check(args.data_dir)

    if security_gate() is None:
        return 2

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

    def retry_pending_mail():
        def worker():
            try:
                controller.admin.process_outbox()
            except Exception:
                # La cola durable conserva el trabajo; nunca exponemos secretos ni bloqueamos la UI.
                pass
        threading.Thread(target=worker, name="bc-caja-mail-outbox", daemon=True).start()
        if window.winfo_exists():
            window.after(60_000, retry_pending_mail)

    window.after(2_000, retry_pending_mail)
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
    if not _sin_pantalla():
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
