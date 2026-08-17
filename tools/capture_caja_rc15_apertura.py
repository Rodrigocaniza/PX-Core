"""Evidencia visual automatizada de la apertura de Caja (BC-CAJA-APERTURA-CAJA-001).

Siembra la caja de hoy y una caja pasada, abre la caja del día tal como lo hace la
operadora y verifica el contrato antes de capturar:

* la fecha no se puede tipear y arranca en hoy;
* la apertura muestra la hora que puso el sistema;
* consultar otro día carga el histórico en sólo lectura;
* `Caja inicial` está destacada;
* la cabecera no queda cortada (regresión responsive 1366x768).

Con ``--consulta`` captura el modo consulta de otro día.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CajaDiaria import abrir_caja_diaria
from modulos.caja_diaria.bootstrap import build_cash_day_controller
from modulos.caja_diaria.domain.models import CashEntry

FORMATO = "%d-%m-%Y"

# La cabecera usa etiquetas cortas a 1366x768 y largas en Full HD.
ABRIR = ("ABRIR CAJA DE HOY", "ABRIR CAJA")
OTRO_DIA = ("Consultar otro día", "Otro día")

VENTAS = (
    ("Ramona Benítez", "0981 555 101", "S-00410", "Ana", 2700000),
    ("Carlos Duarte", "0982 555 102", "S-00415", "Sol", 1850000),
    ("Lucía Ayala", "0983 555 103", "S-00421", "Ana", 990000),
)


def dia_anterior_con_caja() -> date:
    return date.today() - timedelta(days=1)


def sembrar(controller) -> None:
    hoy = date.today()
    for fecha, inicial in ((dia_anterior_con_caja(), 900000), (hoy, 1190000)):
        day = controller.service.open_day(business_date=fecha, unit="PC", opening_cash=inicial)
        for nombre, telefono, sobre, vendedora, total in VENTAS:
            controller.service.add_entry(day.id, CashEntry(
                description=nombre, customer_phone=telefono, envelope=sobre,
                saleswoman=vendedora, delivery_date=fecha + timedelta(days=3),
                frame_origin="Armazón", frame=total // 2, lens=total - total // 2,
                laboratory="Lab Central", total=total, cash=total, balance="0",
            ))


def descendientes(widget):
    for hijo in widget.winfo_children():
        yield hijo
        yield from descendientes(hijo)


def buscar(raiz, predicado):
    for widget in descendientes(raiz):
        if predicado(widget):
            return widget
    return None


def boton(raiz, *textos):
    encontrado = buscar(
        raiz,
        lambda w: isinstance(w, ctk.CTkButton) and str(w.cget("text")) in textos,
    )
    if encontrado is None:
        raise RuntimeError(f"falta el botón {' / '.join(textos)}")
    return encontrado


def etiqueta_estado(raiz):
    encontrada = buscar(
        raiz,
        lambda w: isinstance(w, ctk.CTkLabel) and str(w.cget("text")).startswith("Estado:"),
    )
    if encontrada is None:
        raise RuntimeError("no se encuentra la etiqueta de estado de caja")
    return encontrada


def verificar_fecha_no_tipeable(window, esperado):
    campo = buscar(
        window,
        lambda w: isinstance(w, ctk.CTkEntry) and str(w.get()).strip() == esperado,
    )
    if campo is None:
        raise RuntimeError(f"la cabecera no arranca en la fecha de hoy ({esperado})")
    campo.focus_set()
    campo.event_generate("<Key>", keysym="9")
    window.update_idletasks()
    window.update()
    if str(campo.get()).strip() != esperado:
        raise RuntimeError(f"la fecha operativa se pudo tipear: {campo.get()!r}")
    return campo


def cerrar_dialogos_ajenos(window, conservar=()):
    """La base temporal no tiene administrador: su diálogo inicial tapa la cabecera."""
    for hijo in list(window.winfo_children()):
        if isinstance(hijo, ctk.CTkToplevel) and hijo.title() not in conservar:
            hijo.destroy()


def elegir_en_calendario(window, objetivo: date):
    selector = next(
        (w for w in window.winfo_children()
         if isinstance(w, ctk.CTkToplevel) and w.title() == "Consultar otro día"),
        None,
    )
    if selector is None:
        raise RuntimeError("consultar otro día no abrió el calendario")
    hoy = date.today()
    if (objetivo.year, objetivo.month) != (hoy.year, hoy.month):
        boton(selector, "‹").invoke()
        window.update_idletasks()
        window.update()
    boton(selector, str(objetivo.day)).invoke()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--consulta", action="store_true",
                        help="captura la consulta de otro día en sólo lectura")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["BC_CAJA_WINDOW_SIZE"] = f"{args.width}x{args.height}"

    hoy = date.today().strftime(FORMATO)
    pasado = dia_anterior_con_caja()

    with tempfile.TemporaryDirectory(prefix="bc-caja-rc15-") as directory:
        controller = build_cash_day_controller(Path(directory) / "bc_caja.sqlite3")
        sembrar(controller)
        root = ctk.CTk()
        root.withdraw()
        window = abrir_caja_diaria(root, controller=controller)
        window.attributes("-topmost", True)

        def settle(ciclos: int = 4) -> None:
            for _ in range(ciclos):
                window.after(120)
                window.update_idletasks()
                window.update()

        settle()
        cerrar_dialogos_ajenos(window)
        verificar_fecha_no_tipeable(window, hoy)
        if buscar(window, lambda w: isinstance(w, ctk.CTkButton)
                  and str(w.cget("text")) == "ABRIR / CONSULTAR") is not None:
            raise RuntimeError("sobrevive el botón ambiguo 'ABRIR / CONSULTAR'")
        boton(window, *OTRO_DIA)

        boton(window, *ABRIR).invoke()
        settle()
        estado = str(etiqueta_estado(window).cget("text"))
        if not re.fullmatch(r"Estado: ABIERTO · \d{2}:\d{2}", estado):
            raise RuntimeError(f"la apertura no muestra la hora automática: {estado!r}")
        if str(boton(window, "Cerrar caja").cget("state")) != "normal":
            raise RuntimeError("la caja de hoy quedó no operable")

        if args.consulta:
            boton(window, *OTRO_DIA).invoke()
            settle()
            elegir_en_calendario(window, pasado)
            settle()
            texto_pasado = pasado.strftime(FORMATO)
            aviso = buscar(
                window,
                lambda w: isinstance(w, ctk.CTkLabel) and str(w.cget("text")) == "SÓLO LECTURA",
            )
            if aviso is None or not aviso.winfo_ismapped():
                raise RuntimeError("consultar otro día no avisa que es sólo lectura")
            if buscar(window, lambda w: isinstance(w, ctk.CTkEntry)
                      and str(w.get()).strip() == texto_pasado) is None:
                raise RuntimeError(f"la cabecera no muestra el día consultado ({texto_pasado})")
            boton(window, "Volver a hoy")
            if boton(window, *ABRIR).winfo_manager():
                raise RuntimeError("se puede abrir caja mientras se consulta otro día")
            for etiqueta in ("Cerrar caja", "Guardar venta  —  F9", "Guardar salida"):
                if str(boton(window, etiqueta).cget("state")) != "disabled":
                    raise RuntimeError(f"'{etiqueta}' sigue habilitado en modo consulta")

        cerrar_dialogos_ajenos(window)
        window.lift()
        window.focus_force()
        settle()
        # Regresión responsive: la cabecera no puede quedar cortada a 1366x768.
        borde = window.winfo_rootx() + window.winfo_width()
        for etiqueta in ("Cerrar caja", "Arqueo"):
            control = boton(window, etiqueta)
            derecha = control.winfo_rootx() + control.winfo_width()
            if derecha > borde:
                raise RuntimeError(f"'{etiqueta}' queda fuera de la ventana: {derecha} > {borde}")

        x, y = window.winfo_rootx(), window.winfo_rooty()
        ancho, alto = window.winfo_width(), window.winfo_height()
        ImageGrab.grab((x, y, x + ancho, y + alto)).save(args.output)
        window.attributes("-topmost", False)
        controller.service.repository.close()
        window.destroy()
        root.destroy()
    modo = "consulta" if args.consulta else "apertura"
    print(f"BC_CAJA_RC15_CAPTURE_OK {args.output} {args.width}x{args.height} modo={modo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
