from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .factufacil import FACTUFACIL_STATES, FIELD_ORDER, FactuFacilService
from .ui import COLORS, pyg


LABELS={"customer":"Cliente","document":"CI/RUC","receipt_number":"N.º boleta","date":"Fecha","cashbox":"N.º caja","envelope":"N.º sobre","prescription":"Observaciones / receta","items":"Artículos y precios","total":"Total","payment_method":"Forma de cobro","paid":"Pagado","balance":"Saldo","branch":"Sucursal","saleswoman":"Vendedora"}


class FactuFacilPanel(tk.Frame):
    def __init__(self,parent,core,principal,*,back,notifier=None):
        super().__init__(parent,bg=COLORS["surface"]); self.service=FactuFacilService(core); self.principal=principal; self.back=back; self.notifier=notifier or messagebox.showinfo; self.rows={}; self.current=None; self._build(); self.reload()

    def _build(self):
        head=tk.Frame(self,bg=COLORS["card"],height=62);head.pack(fill="x",padx=14,pady=(10,5));head.pack_propagate(False)
        tk.Button(head,text="← Volver al panel",command=self.back,bg=COLORS["navy"],fg="white",relief="flat").pack(side="left",padx=10,pady=12)
        tk.Label(head,text="Bandeja FactuFácil",bg=COLORS["card"],fg=COLORS["text"],font=("Segoe UI",17,"bold")).pack(side="left",padx=12)
        tk.Label(head,text="CARGA MANUAL · SIN CONEXIÓN EXTERNA",bg="#7D2935",fg="white",font=("Segoe UI",9,"bold"),padx=10,pady=6).pack(side="right",padx=10)
        filters=tk.Frame(self,bg=COLORS["surface"]);filters.pack(fill="x",padx=16,pady=4)
        self.start_var,self.end_var,self.branch_var,self.envelope_var,self.customer_var,self.status_var=(tk.StringVar() for _ in range(6));self.status_var.set("TODOS")
        for label,var,width in (("Desde",self.start_var,10),("Hasta",self.end_var,10),("Sucursal",self.branch_var,13),("Sobre",self.envelope_var,10),("Cliente",self.customer_var,16)):
            tk.Label(filters,text=label,bg=COLORS["surface"]).pack(side="left",padx=(7,2));tk.Entry(filters,textvariable=var,width=width).pack(side="left")
        self.status_box=ttk.Combobox(filters,textvariable=self.status_var,values=["TODOS"]+list(FACTUFACIL_STATES),state="readonly",width=13);self.status_box.pack(side="left",padx=7)
        tk.Button(filters,text="Aplicar filtros",command=self.reload,bg=COLORS["blue"],fg="white").pack(side="left")
        kpis=tk.Frame(self,bg=COLORS["surface"]);kpis.pack(fill="x",padx=14,pady=4);self.kpis={}
        for i,state in enumerate(("PARA_CARGAR","EN_PROCESO","CARGADO","OBSERVADO")):
            kpis.grid_columnconfigure(i,weight=1,uniform="ff-kpi");box=tk.Frame(kpis,bg=COLORS["card"],height=60,highlightthickness=1,highlightbackground="#D7E0E8");box.grid(row=0,column=i,padx=3,sticky="ew");box.grid_propagate(False);tk.Label(box,text=state.replace("_"," "),bg=COLORS["card"],fg=COLORS["muted"],font=("Segoe UI",8,"bold")).pack(anchor="w",padx=10,pady=(6,0));value=tk.Label(box,text="0",bg=COLORS["card"],fg=COLORS["navy"],font=("Segoe UI",15,"bold"));value.pack(anchor="w",padx=10);self.kpis[state]=value
        panes=tk.PanedWindow(self,orient=tk.HORIZONTAL,bg=COLORS["surface"],sashwidth=7);panes.pack(fill="both",expand=True,padx=14,pady=5)
        left=tk.Frame(panes,bg=COLORS["card"]);right=tk.Frame(panes,bg=COLORS["card"],width=580);panes.add(left,minsize=850,stretch="always");panes.add(right,minsize=540,stretch="never")
        cols=("status","date","branch","envelope","customer","document","total","saleswoman"); labels=("Estado","Fecha","Sucursal","Sobre","Cliente","CI/RUC","Total","Vendedora"); widths=(110,90,150,80,200,110,110,120)
        self.tree=ttk.Treeview(left,columns=cols,show="headings",height=24,selectmode="browse")
        for key,label,width in zip(cols,labels,widths):self.tree.heading(key,text=label);self.tree.column(key,width=width,anchor="center" if key in {"status","date","envelope","total"} else "w")
        y=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview);self.tree.configure(yscrollcommand=y.set);self.tree.pack(side="left",fill="both",expand=True);y.pack(side="right",fill="y");self.tree.bind("<<TreeviewSelect>>",self.select)
        top=tk.Frame(right,bg=COLORS["card"]);top.pack(fill="x",padx=10,pady=(8,3));tk.Label(top,text="Detalle para copiar",bg=COLORS["card"],fg=COLORS["text"],font=("Segoe UI",13,"bold")).pack(side="left");tk.Button(top,text="Copiar todos los datos",command=self.copy_all,bg=COLORS["blue"],fg="white").pack(side="right")
        self.detail_canvas=tk.Canvas(right,bg=COLORS["card"],highlightthickness=0);scroll=ttk.Scrollbar(right,orient="vertical",command=self.detail_canvas.yview);self.detail_canvas.configure(yscrollcommand=scroll.set);scroll.pack(side="right",fill="y");self.detail_canvas.pack(fill="both",expand=True,padx=(10,0));self.detail=tk.Frame(self.detail_canvas,bg=COLORS["card"]);self.detail_canvas.create_window((0,0),window=self.detail,anchor="nw");self.detail.bind("<Configure>",lambda _e:self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all")))
        actions=tk.Frame(right,bg=COLORS["card"]);actions.pack(fill="x",padx=10,pady=7);self.start_button=tk.Button(actions,text="Iniciar carga",command=self.start);self.start_button.pack(side="left",padx=2);self.loaded_button=tk.Button(actions,text="Marcar como cargada",command=self.loaded,bg=COLORS["ok"],fg="white");self.loaded_button.pack(side="left",padx=2);self.revert_button=tk.Button(actions,text="Revertir con motivo",command=self.revert,bg="#F6D6D9");self.revert_button.pack(side="left",padx=2);self.prepare_button=tk.Button(actions,text="Preparar nuevamente",command=self.prepare);self.prepare_button.pack(side="left",padx=2)
        self.feedback=tk.Label(self,text="Listo",bg=COLORS["navy"],fg="white",anchor="w",padx=10,pady=6);self.feedback.pack(fill="x",padx=14,pady=(0,9))

    def reload(self):
        status=None if self.status_var.get() in {"","TODOS"} else self.status_var.get();rows=self.service.list_sales(self.principal,start=self.start_var.get() or None,end=self.end_var.get() or None,branch=self.branch_var.get() or None,envelope=self.envelope_var.get() or None,customer=self.customer_var.get() or None,status=status);self.rows={r["id"]:r for r in rows}
        for item in self.tree.get_children():self.tree.delete(item)
        for row in rows:
            p=row["payload"];self.tree.insert("","end",iid=row["id"],values=(row["status"],p["date"],p["branch"],p["envelope"],p["customer"],p["document"],pyg(p["total"]),p["saleswoman"]))
        counts={s:0 for s in self.kpis}
        for row in rows:
            if row["status"] in counts:counts[row["status"]]+=1
        for state,label in self.kpis.items():label.config(text=str(counts[state]))
        self.feedback.config(text=f"{len(rows)} venta(s) · filtros aplicados")

    def _id(self):
        selected=self.tree.selection()
        if not selected:self.notifier("FactuFácil","Seleccione una venta.");return None
        return selected[0]

    def select(self,_event=None):
        sale_id=self._id()
        if not sale_id:return
        self.current=sale_id
        for child in self.detail.winfo_children():child.destroy()
        export=self.service.ordered_export(self.principal,sale_id)
        for entry in export["fields"]:
            name,value=entry["name"],entry["value"]
            block=tk.Frame(self.detail,bg=COLORS["card"]);block.pack(fill="x",pady=2)
            tk.Label(block,text=LABELS[name],bg=COLORS["card"],fg=COLORS["muted"],font=("Segoe UI",8,"bold"),width=20,anchor="w").pack(side="left")
            rendered=json.dumps(value,ensure_ascii=False,indent=2) if name=="items" else str(value)
            if name in {"prescription","items"}:widget=tk.Text(block,height=max(4,min(9,rendered.count("\n")+3)),wrap="word",width=34);widget.insert("1.0",rendered);widget.config(state="disabled")
            else:widget=tk.Entry(block,width=36);widget.insert(0,rendered);widget.config(state="readonly")
            widget.pack(side="left",fill="x",expand=True);tk.Button(block,text="Copiar",command=lambda v=rendered:self.copy(v)).pack(side="right",padx=3)
        history=self.service.history(self.principal,sale_id);tk.Label(self.detail,text="Historial: "+" · ".join(f"{h['action']} ({h['actor']})" for h in history),bg=COLORS["card"],fg=COLORS["muted"],wraplength=520,justify="left").pack(fill="x",pady=5)

    def copy(self,value):self.clipboard_clear();self.clipboard_append(value);self.update();self.feedback.config(text="Dato copiado al portapapeles local")
    def copy_all(self):
        sale_id=self._id()
        if sale_id:
            export=self.service.ordered_export(self.principal,sale_id);self.copy("\n".join(f"{LABELS[e['name']]}: {json.dumps(e['value'],ensure_ascii=False) if isinstance(e['value'],list) else e['value']}" for e in export["fields"]))
    def start(self):
        sale_id=self._id()
        if sale_id:self.service.start(self.principal,sale_id);self.reload();self.feedback.config(text="Carga marcada en proceso")
    def loaded(self):
        sale_id=self._id()
        if not sale_id:return
        responsible=simpledialog.askstring("Responsable","Nombre de responsable:",parent=self);receipt=simpledialog.askstring("Comprobante","Número de comprobante:",parent=self)
        if responsible and receipt:self.service.mark_loaded(self.principal,sale_id,responsible,receipt);self.reload();self.feedback.config(text="Venta marcada como cargada")
    def revert(self):
        sale_id=self._id();reason=simpledialog.askstring("Revertir","Motivo obligatorio:",parent=self) if sale_id else None
        if reason:self.service.revert(self.principal,sale_id,reason);self.reload();self.feedback.config(text="Marcación revertida y auditada")
    def prepare(self):
        sale_id=self._id()
        if sale_id:self.service.prepare_again(self.principal,sale_id);self.reload();self.feedback.config(text="Venta preparada nuevamente")
