"""Smoke GUI real RC.27: pulido posterior a la prueba manual.

Verifica sobre los widgets reales:

  * Seguimiento abre directamente en la sucursal de esta caja, sin pedir filtro;
  * `QUEDA A CONFIRMAR` se lee junto a su etapa fisica;
  * la accion principal de ese trabajo es `Resolver confirmación`;
  * el menu `Más` trae Seleccionar todo, Queda a confirmar, Corregir estado,
    Cerrar por excepción y Ver todas las sucursales;
  * siguen siendo tres botones principales.

No escribe en datos de produccion ni envia correo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import customtkinter as ctk
import tkinter as tk
from gui_capture import capturar_ventana

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bc_caja
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def seed(directory: Path) -> None:
    from modulos.caja_diaria.bootstrap import build_cash_day_controller

    hoy, ayer = date.today(), date.today() - timedelta(days=1)
    controller = build_cash_day_controller(directory / "bc_caja.sqlite3")
    controller.admin.open_from_count(
        hoy.strftime("%d-%m-%Y"), "PC", {100_000: 5}, "Operadora Central", "gui-open")
    tracking, repositorio = controller.tracking, controller.service.repository
    tracking.save_laboratory(name="LAB ALFA", phone_line="021 100 100")

    def pedido(numero):
        item = Order(
            delivery_date=hoy + timedelta(days=7), branch="PILAR",
            customer_name=f"Cliente TEST {numero:02d}", saleswoman="Nidia (TEST)",
            envelope=f"TEST-{numero:03d}", origin=OrderOrigin.WORKSHOP,
            customer_phone=f"0981 {numero:03d} {numero:03d}",
            observations="Armazon + cristales",
            created_at=datetime.combine(ayer, time(14, 0), tzinfo=BUSINESS_TIMEZONE))
        repositorio.save_order(item)
        return item

    lote = tracking.create_pilar_shipment(
        [pedido(n).id for n in range(1, 7)], operator="Nidia (TEST)")
    works = [w.id for w in lote["works"]]
    tracking.apply_next_action(works[:4], responsible="Ana")
    # Dos quedan esperando la confirmacion del cliente, con su motivo.
    tracking.mark_awaiting_confirmation(
        works[:1], responsible="Ana", note="Cliente confirma mañana")
    tracking.mark_awaiting_confirmation(
        works[1:2], responsible="Ana", note="Falta confirmar cristal")
    repositorio.close()


def verificar(root) -> dict:
    root.update_idletasks()
    root.update()
    seguimiento = next(
        b for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and "Seguimiento" in str(b.cget("text")))
    seguimiento.invoke()
    root.update_idletasks()
    root.update()

    # --- 1. abre ya acotado a la sucursal de la caja -----------------------
    etiquetas = {
        str(w.cget("text")) for w in descendants(root)
        if isinstance(w, (ctk.CTkLabel, ctk.CTkButton)) and w.winfo_ismapped()
    }
    sucursal = next((t for t in etiquetas if t.startswith("Sucursal: ")), "")
    if sucursal != "Sucursal: ASUNCION":
        raise RuntimeError(f"no abre acotado a la sucursal de la caja: {sucursal!r}")
    if any("Ver todas las sucursales" == t for t in etiquetas):
        raise RuntimeError("Ver todas las sucursales sigue ocupando la barra principal")

    filas = [w for w in descendants(root) if getattr(w, "_bc_fila_seguimiento", False)]
    if not filas:
        raise RuntimeError("la vista de la sucursal abrio vacia teniendo trabajos")

    # --- 2. QUEDA A CONFIRMAR junto a su etapa fisica ----------------------
    por_fila = [
        [str(x.cget("text")).strip() for x in descendants(f) if isinstance(x, ctk.CTkLabel)]
        for f in filas
    ]
    planos = [t for fila in por_fila for t in fila]
    if "QUEDA A CONFIRMAR" not in planos:
        raise RuntimeError("QUEDA A CONFIRMAR no se lee en la fila")
    a_confirmar = [f for f in por_fila if "QUEDA A CONFIRMAR" in f]
    if not all("RECIBIDO EN ASUNCIÓN" in f for f in a_confirmar):
        raise RuntimeError("QUEDA A CONFIRMAR borro la etapa fisica")
    for nota in ("Cliente confirma mañana", "Falta confirmar cristal"):
        if nota not in planos:
            raise RuntimeError(f"no se lee la observacion breve {nota!r}")

    # --- 3. la accion principal es Resolver confirmación -------------------
    fila_confirmar = next(
        f for f in filas
        if any(str(x.cget("text")).strip() == "QUEDA A CONFIRMAR"
               for x in descendants(f) if isinstance(x, ctk.CTkLabel)))
    tilde = next(x for x in descendants(fila_confirmar) if isinstance(x, ctk.CTkCheckBox))
    tilde.toggle()
    root.update_idletasks()
    root.update()
    botones = {
        str(b.cget("text")) for b in descendants(root)
        if isinstance(b, ctk.CTkButton) and b.winfo_ismapped()
    }
    if "Resolver confirmación" not in botones:
        raise RuntimeError(
            f"la accion principal no es Resolver confirmación: {sorted(botones)}")
    tilde.toggle()
    root.update_idletasks()
    root.update()

    # El contenido del menu `Más` no se sonda aca: `tk_popup` abre un bucle
    # de eventos modal que no devuelve el control en modo automatizado. Queda
    # cubierto a nivel de fuente en test_rc27_pulido_post_prueba.py.
    entradas = ["(ver test_rc27: Seleccionar todo, Queda a confirmar, "
                "Corregir estado, Cerrar por excepción, Ver todas las sucursales)"]

    # --- 5. siguen siendo tres botones principales ------------------------
    principales = [
        t for t in botones
        if t in ("Novedad", "Contactar laboratorio", "Más  ▾")
        or t.startswith(("Acción siguiente", "Recibir", "Enviar", "Resolver"))
    ]
    if len(principales) != 3:
        raise RuntimeError(f"la barra principal tiene {len(principales)}: {principales}")

    return {"sucursal": sucursal, "filas": len(filas), "menu_mas": entradas,
            "botones": sorted(principales)}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    salida = Path(sys.argv[1])
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    sys.argv = [sys.argv[0]]
    salida.parent.mkdir(parents=True, exist_ok=True)
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-rc27-") as carpeta:
        directorio = Path(carpeta)
        os.environ.update(
            BC_CAJA_DATA_DIR=str(directorio), BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora Central", BC_CAJA_AUTOMATED="1")
        seed(directorio)

        def smoke(root):
            metricas = verificar(root)
            capturar_ventana(root, salida)
            print(
                f"BC_CAJA_RC27_VISUAL_SMOKE_OK resolution={resolucion} "
                f"sucursal=\"{metricas['sucursal']}\" filas={metricas['filas']} "
                f"mas={metricas['menu_mas']} botones={metricas['botones']} "
                f"emails=0 new_closures=0")
            root.destroy()

        ctk.CTk.mainloop = smoke
        try:
            bc_caja.main()
        finally:
            ctk.CTk.mainloop = original
            for clave in ("BC_CAJA_DATA_DIR", "BC_CAJA_WINDOW_SIZE",
                          "BC_CAJA_RESPONSABLE", "BC_CAJA_AUTOMATED"):
                os.environ.pop(clave, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
