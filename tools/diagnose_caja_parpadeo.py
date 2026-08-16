"""Aisla el parpadeo de BC Caja midiendo el trabajo de layout en reposo.

No busca "verse mal": mide. Con la ventana abierta y **sin tocar nada**, cuenta
cuantas veces se reposicionan widgets, cuantos `<Configure>` se disparan y
cuantos `after` se programan. En reposo esos numeros tienen que estabilizarse;
si siguen creciendo, hay un ciclo de relayout y eso es exactamente lo que la
operadora ve como parpadeo.

    python tools/diagnose_caja_parpadeo.py [segundos]
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import customtkinter as ctk
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bc_caja


CONTEO = Counter()


def instrumentar():
    """Cuenta place/configure/after sin alterar su comportamiento."""
    original_place = tk.Place.place_configure
    original_after = tk.Misc.after
    original_destroy = tk.BaseWidget.destroy
    original_init = tk.BaseWidget.__init__

    def destroy(self, _o=original_destroy):
        CONTEO["destroy"] += 1
        return _o(self)

    def widget_init(self, *a, _o=original_init, **kw):
        CONTEO["crear_widget"] += 1
        return _o(self, *a, **kw)

    tk.BaseWidget.destroy = destroy
    tk.BaseWidget.__init__ = widget_init

    def place_configure(self, *a, _o=original_place, **kw):
        CONTEO["place"] += 1
        return _o(self, *a, **kw)

    def after(self, ms, *a, _o=original_after, **kw):
        CONTEO["after"] += 1
        if a:
            CONTEO[f"after:{getattr(a[0], '__name__', 'lambda')}"] += 1
        return _o(self, ms, *a, **kw)

    tk.Place.place_configure = place_configure
    tk.Place.place = place_configure
    tk.Misc.after = after


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def medir(root, segundos: float, pestana: str | None = None) -> dict:
    root.update_idletasks()
    root.update()
    if pestana:
        boton = next(
            b for b in descendants(root)
            if isinstance(b, ctk.CTkButton) and pestana in str(b.cget("text")))
        boton.invoke()
        root.update_idletasks()
        root.update()

    # Contar <Configure> por widget, para saber quien se reconfigura solo.
    configures = Counter()

    def marcar(nombre):
        def _handler(_e=None):
            configures[nombre] += 1
        return _handler

    for w in [root, *descendants(root)]:
        try:
            w.bind("<Configure>", marcar(w.winfo_class() + ":" + str(w)[-28:]), add="+")
        except Exception:
            pass

    ventanas = []
    muestras = []
    inicio = time.monotonic()
    CONTEO.clear()
    destruidos0 = creados0 = 0
    while time.monotonic() - inicio < segundos:
        t0 = time.monotonic()
        p0 = CONTEO["place"]
        while time.monotonic() - t0 < 1.0:
            root.update()
            time.sleep(0.005)
        muestras.append(CONTEO["place"] - p0)

    top = sorted(configures.items(), key=lambda kv: -kv[1])[:8]
    return {
        "destroy_total": CONTEO["destroy"],
        "crear_widget_total": CONTEO["crear_widget"],
        "place_por_segundo": muestras,
        "place_total": CONTEO["place"],
        "after_total": CONTEO["after"],
        "after_por_destino": {k.split(":", 1)[1]: v
                              for k, v in CONTEO.items() if k.startswith("after:")},
        "configure_top": top,
        "configure_total": sum(configures.values()),
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    segundos = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    resolucion = sys.argv[2] if len(sys.argv) > 2 else "1920x1080"
    sys.argv = [sys.argv[0]]
    instrumentar()
    original = ctk.CTk.mainloop
    with tempfile.TemporaryDirectory(prefix="bc-caja-flicker-") as carpeta:
        os.environ.update(
            BC_CAJA_DATA_DIR=carpeta, BC_CAJA_WINDOW_SIZE=resolucion,
            BC_CAJA_RESPONSABLE="Operadora", BC_CAJA_AUTOMATED="1",
        )

        def smoke(root):
            datos = medir(root, segundos, os.environ.get("BC_DIAG_TAB") or None)
            print("BC_CAJA_PARPADEO_DIAGNOSTICO")
            print(f"  resolucion            = {resolucion}")
            print(f"  pestana               = {os.environ.get('BC_DIAG_TAB') or 'Caja diaria'}")
            print(f"  widgets destruidos    = {datos['destroy_total']}")
            print(f"  widgets creados       = {datos['crear_widget_total']}")
            print(f"  place()/segundo       = {datos['place_por_segundo']}")
            print(f"  place() total         = {datos['place_total']}")
            print(f"  after() total         = {datos['after_total']}")
            print(f"  after() por destino   = {datos['after_por_destino']}")
            print(f"  <Configure> total     = {datos['configure_total']}")
            for nombre, veces in datos["configure_top"]:
                print(f"    {veces:6d}  {nombre}")
            estable = (all(n == 0 for n in datos["place_por_segundo"][1:])
                       and datos["destroy_total"] == 0
                       and datos["crear_widget_total"] == 0)
            print(f"  VEREDICTO             = "
                  f"{'ESTABLE en reposo' if estable else 'RELAYOUT CONTINUO'}")
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
