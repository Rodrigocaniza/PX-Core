from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .real_sync import REVIEW_FIELDS
from .ui import COLORS, pyg


FIELD_LABELS = {
    "date":"Fecha", "customer_name":"Nombre", "envelope":"Sobre", "customer_document":"CI/RUC",
    "customer_phone":"Teléfono", "saleswoman":"Vendedora", "items":"Artículos",
    "codes":"Códigos", "laboratory":"Laboratorio", "prescription":"Receta/observaciones",
    "total":"Total", "cash":"Efectivo", "card_transfer":"Tarjeta/transferencia",
    "agreement":"Convenio", "balance":"Saldo", "delivery_date":"Entrega",
    "factufacil_status":"FactuFácil", "recorded_by":"Registró",
}
STATUS_LABELS = {
    "ALL":"Todas", "UNREVIEWED":"Sin revisar", "IN_REVIEW":"En revisión",
    "REVIEWED":"Revisadas", "WITH_OBSERVATION":"Con observaciones",
    "REQUIRES_CORRECTION":"Requiere corrección",
    "CORRECTED_PENDING_REVALIDATION":"Pendiente de revalidar",
    "ANNULLED":"Anulada",
}
STATUS_COLORS = {
    "UNREVIEWED":"#FFF7E6", "IN_REVIEW":"#E8F1F8", "REVIEWED":"#E5F5ED",
    "WITH_OBSERVATION":"#FFF0D6", "REQUIRES_CORRECTION":"#FCE7E9",
    "CORRECTED_PENDING_REVALIDATION":"#F2E9FF",
    "ANNULLED":"#E5E7EB",
}


class ReviewPanel(tk.Frame):
    def __init__(self, parent, service, principal, *, back, notifier=None, confirmer=None):
        super().__init__(parent, bg=COLORS["surface"])
        self.service, self.principal, self.back = service, principal, back
        self.notifier = notifier or messagebox.showinfo
        self.confirmer = confirmer or messagebox.askyesno
        self.rows, self.current_identity = {}, None
        self.field_vars = {name: tk.BooleanVar(value=False) for name in REVIEW_FIELDS}
        self._build(); self.reload()

    def _action(self, label, callback):
        try:
            return callback()
        except Exception:
            self.feedback.config(text=f"No se pudo {label}; revise el registro local")
            self.notifier("Revisión", f"No se pudo {label}. La acción no fue aplicada.")
            return None

    def _build(self):
        head=tk.Frame(self,bg=COLORS["card"],height=58); head.pack(fill="x",padx=12,pady=(10,5)); head.pack_propagate(False)
        self.back_button=tk.Button(head,text="← Volver al panel",command=self.back,bg=COLORS["navy"],fg="white",relief="flat",padx=12); self.back_button.pack(side="left",padx=10,pady=10)
        tk.Label(head,text="Revisión fila por fila de Sol",bg=COLORS["card"],fg=COLORS["text"],font=("Segoe UI",16,"bold")).pack(side="left",padx=10)
        tk.Label(head,text="COPIA LOCAL · SOLO LECTURA DE BC CAJA",bg="#7D2935",fg="white",font=("Segoe UI",9,"bold"),padx=10,pady=6).pack(side="right",padx=10)
        self.kpi_frame=tk.Frame(self,bg=COLORS["surface"]); self.kpi_frame.pack(fill="x",padx=10,pady=4)
        self.kpis={}
        for i,key in enumerate(("total","reviewed","pending","observations","percent")):
            self.kpi_frame.grid_columnconfigure(i,weight=1,uniform="review-kpi"); box=tk.Frame(self.kpi_frame,bg=COLORS["card"],height=63,highlightthickness=1,highlightbackground="#D7E0E8"); box.grid(row=0,column=i,padx=3,sticky="ew"); box.grid_propagate(False)
            label={"total":"TOTAL","reviewed":"REVISADAS","pending":"PENDIENTES","observations":"OBSERVACIONES","percent":"PROGRESO"}[key]
            tk.Label(box,text=label,bg=COLORS["card"],fg=COLORS["muted"],font=("Segoe UI",8,"bold")).pack(anchor="w",padx=10,pady=(7,0)); value=tk.Label(box,text="0",bg=COLORS["card"],fg=COLORS["navy"],font=("Segoe UI",15,"bold")); value.pack(anchor="w",padx=10); self.kpis[key]=value
        filters=tk.Frame(self,bg=COLORS["surface"]); filters.pack(fill="x",padx=12,pady=4)
        self.status_var=tk.StringVar(value="ALL"); self.status_filter=ttk.Combobox(filters,textvariable=self.status_var,values=list(STATUS_LABELS),state="readonly",width=28); self.status_filter.pack(side="left"); self.status_filter.bind("<<ComboboxSelected>>",lambda _e:self.reload())
        self.cashbox_var=tk.StringVar(); self.date_var=tk.StringVar(); self.saleswoman_var=tk.StringVar(); self.envelope_var=tk.StringVar()
        for label,var,width in (("Caja",self.cashbox_var,8),("Fecha",self.date_var,11),("Vendedora",self.saleswoman_var,14),("Sobre",self.envelope_var,12)):
            tk.Label(filters,text=label,bg=COLORS["surface"]).pack(side="left",padx=(10,3)); entry=tk.Entry(filters,textvariable=var,width=width); entry.pack(side="left"); entry.bind("<Return>",lambda _e:self.reload())
        tk.Button(filters,text="Aplicar filtros",command=self.reload).pack(side="left",padx=8)
        self.selection_label=tk.Label(filters,text="0 filas seleccionadas",bg=COLORS["surface"],fg=COLORS["muted"]); self.selection_label.pack(side="right")
        panes=tk.PanedWindow(self,orient=tk.HORIZONTAL,bg=COLORS["surface"],sashwidth=7); panes.pack(fill="both",expand=True,padx=12,pady=4)
        table_frame=tk.Frame(panes,bg=COLORS["card"]); detail=tk.Frame(panes,bg=COLORS["card"],width=410); panes.add(table_frame,minsize=900,stretch="always"); panes.add(detail,minsize=390,stretch="never")
        columns=("status","date","envelope","customer","document","phone","saleswoman","items","codes","laboratory","prescription","total","cash","card","agreement","balance","delivery","factufacil","recorded_by")
        self.tree=ttk.Treeview(table_frame,columns=columns,show="headings",selectmode="extended",height=18)
        labels=("Estado","Fecha","Sobre","Cliente","CI/RUC","Teléfono","Vendedora","Artículos","Códigos","Laboratorio","Receta/Obs.","Total","Efectivo","Tarj./Transf.","Convenio","Saldo","Entrega","FactuFácil","Registró")
        widths=(150,90,90,170,100,105,110,170,110,120,190,105,105,115,100,100,95,145,105)
        for key,label,width in zip(columns,labels,widths): self.tree.heading(key,text=label); self.tree.column(key,width=width,anchor="e" if key in {"total","cash","card","agreement"} else "w")
        for status,color in STATUS_COLORS.items(): self.tree.tag_configure(status,background=color)
        y=ttk.Scrollbar(table_frame,orient="vertical",command=self.tree.yview); x=ttk.Scrollbar(table_frame,orient="horizontal",command=self.tree.xview); self.tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.tree.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew"); table_frame.grid_rowconfigure(0,weight=1); table_frame.grid_columnconfigure(0,weight=1)
        self.tree.bind("<<TreeviewSelect>>",self._select); self.tree.bind("<Double-1>",lambda _e:self._select()); self.tree.bind("<Return>",lambda _e:self.mark_complete())
        nav=tk.Frame(table_frame,bg=COLORS["card"]); nav.grid(row=2,column=0,columnspan=2,sticky="ew",pady=5)
        self.previous_button=tk.Button(nav,text="Anterior",command=self.previous); self.previous_button.pack(side="left",padx=3)
        self.next_button=tk.Button(nav,text="Siguiente pendiente",command=self.next_pending); self.next_button.pack(side="left",padx=3)
        self.mark_continue_button=tk.Button(nav,text="Marcar y continuar",command=self.mark_and_continue,bg=COLORS["blue"],fg="white"); self.mark_continue_button.pack(side="left",padx=3)
        self.bulk_button=tk.Button(nav,text="Marcar seleccionadas como revisadas",command=self.mark_many); self.bulk_button.pack(side="right",padx=3)
        tk.Label(detail,text="Detalle y control de campos",bg=COLORS["card"],fg=COLORS["text"],font=("Segoe UI",13,"bold")).pack(anchor="w",padx=12,pady=(10,4))
        self.detail_title=tk.Label(detail,text="Seleccione una fila",bg=COLORS["card"],fg=COLORS["muted"],wraplength=370,justify="left"); self.detail_title.pack(anchor="w",padx=12,pady=4)
        checks=tk.Frame(detail,bg=COLORS["card"]); checks.pack(fill="both",expand=True,padx=8)
        for i,name in enumerate(REVIEW_FIELDS): tk.Checkbutton(checks,text=FIELD_LABELS[name],variable=self.field_vars[name],bg=COLORS["card"],anchor="w").grid(row=i//2,column=i%2,sticky="w",padx=4,pady=1)
        actions=tk.Frame(detail,bg=COLORS["card"]); actions.pack(fill="x",padx=8,pady=6)
        self.fields_button=tk.Button(actions,text="Marcar campos",command=self.mark_fields); self.fields_button.pack(fill="x",pady=2)
        self.complete_button=tk.Button(actions,text="Marcar fila completa como revisada",command=self.mark_complete,bg=COLORS["ok"],fg="white"); self.complete_button.pack(fill="x",pady=2)
        self.note_button=tk.Button(actions,text="Agregar observación",command=self.add_note); self.note_button.pack(fill="x",pady=2)
        self.correction_button=tk.Button(actions,text="Requiere corrección",command=self.require_correction,bg="#F6D6D9"); self.correction_button.pack(fill="x",pady=2)
        self.alert_button=tk.Button(actions,text="Crear alerta para sucursal",command=self.create_alert); self.alert_button.pack(fill="x",pady=2)
        self.feedback=tk.Label(self,text="Listo",bg=COLORS["navy"],fg="white",anchor="w",padx=10,pady=5); self.feedback.pack(fill="x",padx=12,pady=(0,8))

    def reload(self):
        rows=self.service.list_sales(self.principal,status=self.status_var.get(),cashbox=self.cashbox_var.get().strip() or None,date=self.date_var.get().strip() or None,saleswoman=self.saleswoman_var.get().strip() or None,envelope=self.envelope_var.get().strip() or None); self.rows={r["identity"]:r for r in rows}
        for item in self.tree.get_children(): self.tree.delete(item)
        for row in rows:
            p=row["payload"]; values=(STATUS_LABELS[row["review_status"]],p["date"],p["envelope"],p["customer_name"],p["customer_document"],p["customer_phone"],p["saleswoman"],p["items"],p["codes"],p["laboratory"],p["prescription"],pyg(p["total"]),pyg(p["cash"]),pyg(p["card_transfer"]),pyg(p["agreement"]),p["balance"],p["delivery_date"],p["factufacil_status"],p["recorded_by"]); self.tree.insert("","end",iid=row["identity"],values=values,tags=(row["review_status"],))
        progress=self.service.progress(self.principal)
        for key,label in self.kpis.items(): label.config(text=f"{progress[key]}%" if key=="percent" else str(progress[key]))
        self.feedback.config(text=f"Filtro aplicado · {len(rows)} filas")

    def _select(self,_event=None):
        selected=self.tree.selection(); self.selection_label.config(text=f"{len(selected)} filas seleccionadas")
        if not selected:return
        self.current_identity=selected[-1]; row=self.rows[self.current_identity]; p=row["payload"]; self.detail_title.config(text=f"{p['envelope'] or 'Sin sobre'} · {p['customer_name']}\n{STATUS_LABELS[row['review_status']]}")
        reviewed=self.service.reviewed_fields(self.principal,self.current_identity)
        for name,var in self.field_vars.items(): var.set(name in reviewed)
        movement = " · Movimiento diario consolidado" if row.get("movement_id") else ""
        self.feedback.config(text=f"Fila seleccionada · {p['envelope'] or 'sin sobre'}{movement}")

    def _identity(self):
        if not self.current_identity:self.notifier("Revisión","Seleccione una fila."); return None
        return self.current_identity

    def mark_fields(self): return self._action("marcar los campos", self._mark_fields)
    def _mark_fields(self):
        identity=self._identity(); fields=[n for n,v in self.field_vars.items() if v.get()]
        if identity and fields:self.service.mark_fields(self.principal,identity,fields); self.reload(); self.feedback.config(text=f"{len(fields)} campos revisados")
    def mark_complete(self): return self._action("marcar la fila", self._mark_complete)
    def _mark_complete(self):
        identity=self._identity()
        if not identity: return False
        self.service.mark_complete(self.principal,identity); self.reload(); self.feedback.config(text="Fila completa revisada")
        return True
    def mark_many(self): return self._action("marcar el lote", self._mark_many)
    def _mark_many(self):
        ids=self.tree.selection(); count=len(ids)
        if not count:self.notifier("Revisión","Seleccione una o más filas."); return
        if self.confirmer("Confirmar lote",f"Se marcarán {count} filas como revisadas. ¿Continuar?"):
            affected=self.service.mark_many(self.principal,ids); self.reload(); self.feedback.config(text=f"Lote confirmado · {affected} filas")
    def next_pending(self): self._move(pending=True,direction=1)
    def previous(self): self._move(pending=False,direction=-1)
    def _move(self,pending,direction):
        ids=list(self.tree.get_children()); current=ids.index(self.current_identity) if self.current_identity in ids else (-1 if direction>0 else len(ids))
        candidates=ids[current+direction::direction]
        target=next((i for i in candidates if not pending or self.rows[i]["review_status"]!="REVIEWED"),None)
        if target:self.tree.selection_set(target); self.tree.focus(target); self.tree.see(target); self._select()
        else:self.feedback.config(text="No hay otra fila para esa navegación")
    def mark_and_continue(self):
        if self.mark_complete(): self.next_pending()
    def add_note(self): return self._action("agregar la observación", self._add_note)
    def _add_note(self):
        identity=self._identity()
        if identity:
            note=simpledialog.askstring("Observación de Sol","Escriba la observación:",parent=self)
            if note:self.service.add_note(self.principal,identity,note); self.reload(); self.feedback.config(text="Observación agregada al historial")
    def require_correction(self): return self._action("solicitar la corrección", self._require_correction)
    def _require_correction(self):
        identity=self._identity()
        if identity:
            reason=simpledialog.askstring("Requiere corrección","Motivo:",parent=self)
            if reason:self.service.require_correction(self.principal,identity,reason); self.reload(); self.feedback.config(text="Fila reabierta: requiere corrección")
    def create_alert(self): return self._action("crear la alerta", self._create_alert)
    def _create_alert(self):
        identity=self._identity()
        if identity:
            message=simpledialog.askstring("Alerta pendiente","Mensaje para la sucursal:",parent=self)
            if message:self.service.create_branch_alert(self.principal,identity,message); self.feedback.config(text="Alerta pendiente creada; no se envió a BC Caja")
