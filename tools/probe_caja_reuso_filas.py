"""Sonda de reuso de filas en Seguimiento (regresion del parpadeo).

Mide cuantos widgets se destruyen y se crean al refrescar la tabla con la
misma lista de trabajos. Con reuso tiene que ser cero: si vuelve a crecer,
volvio el parpadeo. Imprime BC_CAJA_REUSO_FILAS_OK / _FAIL.
"""
import os, sys, tempfile, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, "tools"); sys.path.insert(0, ".")
import customtkinter as ctk, tkinter as tk
import bc_caja
C=Counter()
od=tk.BaseWidget.destroy; oi=tk.BaseWidget.__init__
def d(self,_o=od): C["destroy"]+=1; return _o(self)
def i(self,*a,_o=oi,**k): C["crear"]+=1; return _o(self,*a,**k)
tk.BaseWidget.destroy=d; tk.BaseWidget.__init__=i

def desc(w):
    for c in w.winfo_children():
        yield c; yield from desc(c)

def seed(directory):
    from modulos.caja_diaria.bootstrap import build_cash_day_controller
    from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE, Order, OrderOrigin
    from datetime import date, datetime, time as t, timedelta
    hoy=date.today(); ayer=hoy-timedelta(days=1)
    ctl=build_cash_day_controller(Path(directory)/"bc_caja.sqlite3")
    ctl.admin.open_from_count(hoy.strftime("%d-%m-%Y"),"PC",{100_000:5},"Op","o")
    tr=ctl.tracking; repo=ctl.service.repository
    lab=tr.save_laboratory(name="LAB ALFA", phone_line="021 1")
    ids=[]
    for n in range(1,16):
        o=Order(delivery_date=hoy+timedelta(days=7),branch="PILAR",customer_name=f"Cliente {n:02d}",
                saleswoman="Nidia",envelope=f"TEST-{n:03d}",origin=OrderOrigin.WORKSHOP,
                customer_phone="0981 555 111",observations="Cristal",
                created_at=datetime.combine(ayer,t(14,0),tzinfo=BUSINESS_TIMEZONE))
        repo.save_order(o); ids.append(o.id)
    tr.create_pilar_shipment(ids, operator="Nidia")
    repo.close()

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    res="1920x1080"
    with tempfile.TemporaryDirectory(prefix="bc-flick-") as carp:
        os.environ.update(BC_CAJA_DATA_DIR=carp,BC_CAJA_WINDOW_SIZE=res,
                          BC_CAJA_RESPONSABLE="Op",BC_CAJA_AUTOMATED="1")
        seed(carp)
        orig=ctk.CTk.mainloop
        def smoke(root):
            root.update_idletasks(); root.update()
            next(b for b in desc(root) if isinstance(b,ctk.CTkButton) and "Seguimiento" in str(b.cget("text"))).invoke()
            root.update_idletasks(); root.update()
            filas=[w for w in desc(root) if getattr(w,"_bc_fila_seguimiento",False)]
            print(f"filas={len(filas)}")
            # 1. refresco completo por clic en filtro
            act=next(b for b in desc(root) if isinstance(b,ctk.CTkButton) and str(b.cget("text"))=="Activos")
            C.clear(); t0=time.monotonic(); act.invoke(); root.update_idletasks(); root.update()
            churn = (C["destroy"], C["crear"])
            print(f"REFRESCO_FILTRO   destruidos={C['destroy']:4d} creados={C['crear']:4d} ms={1000*(time.monotonic()-t0):.0f}")
            # 2. marcar un checkbox (no deberia reconstruir)
            chk=next(w for w in desc(root) if isinstance(w,ctk.CTkCheckBox))
            C.clear(); t0=time.monotonic(); chk.toggle(); root.update_idletasks(); root.update()
            print(f"MARCAR_CHECKBOX   destruidos={C['destroy']:4d} creados={C['crear']:4d} ms={1000*(time.monotonic()-t0):.0f}")
            # 3. desmarcar
            C.clear(); t0=time.monotonic(); chk.toggle(); root.update_idletasks(); root.update()
            print(f"DESMARCAR         destruidos={C['destroy']:4d} creados={C['crear']:4d} ms={1000*(time.monotonic()-t0):.0f}")
            veredicto = "OK" if churn == (0, 0) else "FAIL"
            print(f"BC_CAJA_REUSO_FILAS_{veredicto} destruidos={churn[0]} creados={churn[1]}")
            root.destroy()
        ctk.CTk.mainloop=smoke
        try: bc_caja.main()
        finally: ctk.CTk.mainloop=orig
main()
