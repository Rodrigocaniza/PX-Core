from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .delivery import DELIVERY_STATES, DeliveryService
from .models import Unit
from .ui import COLORS


class DeliveryPanel(tk.Frame):
    def __init__(self, parent, core, principal, *, back, notifier=None):
        super().__init__(parent, bg=COLORS["surface"])
        self.service = DeliveryService(core)
        self.principal, self.back = principal, back
        self.notifier = notifier or messagebox.showinfo
        self.rows = {}
        self._build(); self.reload()

    def _build(self):
        head = tk.Frame(self, bg=COLORS["card"], height=64); head.pack(fill="x", padx=14, pady=(12, 6)); head.pack_propagate(False)
        tk.Button(head, text="← Volver al panel", command=self.back, bg=COLORS["navy"], fg="white", relief="flat", padx=13).pack(side="left", padx=10, pady=12)
        tk.Label(head, text="Mensajes y confirmaciones", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 17, "bold")).pack(side="left", padx=8)
        tk.Label(head, text="TRANSPORTE LOCAL SIMULADO · SIN ENVÍOS REALES", bg="#7D2935", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=6).pack(side="right", padx=10)

        filters = tk.Frame(self, bg=COLORS["surface"]); filters.pack(fill="x", padx=16, pady=5)
        self.start_var, self.end_var = tk.StringVar(), tk.StringVar()
        self.unit_var, self.pc_var, self.state_var = tk.StringVar(), tk.StringVar(), tk.StringVar(value="TODOS")
        for label, variable, width in (("Desde", self.start_var, 11), ("Hasta", self.end_var, 11), ("PC", self.pc_var, 13)):
            tk.Label(filters, text=label, bg=COLORS["surface"]).pack(side="left", padx=(8, 3)); tk.Entry(filters, textvariable=variable, width=width).pack(side="left")
        tk.Label(filters, text="Sucursal", bg=COLORS["surface"]).pack(side="left", padx=(8, 3))
        self.unit_box = ttk.Combobox(filters, textvariable=self.unit_var, values=["TODAS"] + [u.value for u in Unit], state="readonly", width=22); self.unit_box.set("TODAS"); self.unit_box.pack(side="left")
        tk.Label(filters, text="Estado", bg=COLORS["surface"]).pack(side="left", padx=(8, 3))
        self.state_box = ttk.Combobox(filters, textvariable=self.state_var, values=["TODOS"] + list(DELIVERY_STATES), state="readonly", width=12); self.state_box.pack(side="left")
        tk.Button(filters, text="Aplicar filtros", command=self.reload, bg=COLORS["blue"], fg="white").pack(side="left", padx=8)

        kpis = tk.Frame(self, bg=COLORS["surface"]); kpis.pack(fill="x", padx=14, pady=5); self.kpis = {}
        for index, state in enumerate(("PENDIENTE", "ENTREGADO", "CONFIRMADO", "REINTENTO", "FALLIDO")):
            kpis.grid_columnconfigure(index, weight=1, uniform="delivery-kpi")
            box = tk.Frame(kpis, bg=COLORS["card"], height=63, highlightthickness=1, highlightbackground="#D7E0E8"); box.grid(row=0, column=index, padx=3, sticky="ew"); box.grid_propagate(False)
            tk.Label(box, text=state, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(box, text="0", bg=COLORS["card"], fg=COLORS["navy"], font=("Segoe UI", 15, "bold")); value.pack(anchor="w", padx=10); self.kpis[state] = value

        panes = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=COLORS["surface"], sashwidth=7); panes.pack(fill="both", expand=True, padx=14, pady=5)
        table = tk.Frame(panes, bg=COLORS["card"]); detail = tk.Frame(panes, bg=COLORS["card"], width=420); panes.add(table, minsize=1050, stretch="always"); panes.add(detail, minsize=390, stretch="never")
        columns = ("state", "unit", "pc", "author", "body", "created", "attempts", "last", "next", "delivered", "confirmed", "error")
        labels = ("Estado", "Sucursal", "PC", "Autor", "Mensaje", "Creado", "Intentos", "Último intento", "Próxima ejecución", "Entregado", "Confirmado", "Error")
        widths = (100, 160, 100, 90, 250, 135, 70, 135, 135, 135, 135, 180)
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=24, selectmode="browse")
        for key, label, width in zip(columns, labels, widths): self.tree.heading(key, text=label); self.tree.column(key, width=width, anchor="w")
        y = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview); x = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview); self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew"); table.grid_rowconfigure(0, weight=1); table.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.select)

        tk.Label(detail, text="Detalle auditable", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(12, 5))
        self.detail = tk.Text(detail, height=24, wrap="word", bg="#F9FBFD", relief="solid", borderwidth=1); self.detail.pack(fill="both", expand=True, padx=12, pady=5); self.detail.config(state="disabled")
        actions = tk.Frame(detail, bg=COLORS["card"]); actions.pack(fill="x", padx=12, pady=8)
        self.process_button = tk.Button(actions, text="Procesar pendientes", command=self.process, bg=COLORS["blue"], fg="white"); self.process_button.pack(fill="x", pady=2)
        self.retry_button = tk.Button(actions, text="Reintento seguro", command=self.retry); self.retry_button.pack(fill="x", pady=2)
        self.cancel_button = tk.Button(actions, text="Cancelar con motivo", command=self.cancel, bg="#F6D6D9"); self.cancel_button.pack(fill="x", pady=2)
        self.feedback = tk.Label(self, text="Listo", bg=COLORS["navy"], fg="white", anchor="w", padx=10, pady=6); self.feedback.pack(fill="x", padx=14, pady=(0, 10))

    def reload(self):
        unit = None if self.unit_var.get() in {"", "TODAS"} else Unit(self.unit_var.get())
        state = None if self.state_var.get() in {"", "TODOS"} else self.state_var.get()
        rows = self.service.list_messages(self.principal, start=self.start_var.get() or None, end=self.end_var.get() or None, unit=unit, pc=self.pc_var.get() or None, state=state)
        self.rows = {row["id"]: row for row in rows}
        for item in self.tree.get_children(): self.tree.delete(item)
        for row in rows:
            values = (row["state"], Unit(row["target_unit"]).label, row["target_pc"] or "Sucursal", row["created_by"], row["body"], row["created_at"], row["attempts"], row["last_attempt_at"] or "—", row["next_attempt_at"] or "—", row["delivered_at"] or "—", row["confirmed_at"] or "—", row["error_code"] or "—")
            self.tree.insert("", "end", iid=row["id"], values=values)
        counts = {state: 0 for state in self.kpis}
        for row in rows:
            if row["state"] in counts: counts[row["state"]] += 1
        for state, label in self.kpis.items(): label.config(text=str(counts[state]))
        self.feedback.config(text=f"{len(rows)} mensaje(s) · filtros aplicados")

    def _selected(self):
        selected = self.tree.selection()
        if not selected: self.notifier("Mensajes", "Seleccione un mensaje."); return None
        return selected[0]

    def select(self, _event=None):
        message_id = self._selected()
        if not message_id: return
        row = self.rows[message_id]; history = self.service.history(self.principal, message_id)
        lines = [f"ID: {message_id}", f"Idempotencia: {row['idempotency_key']}", f"Estado: {row['state']}", f"Destino: {row['target_unit']} / {row['target_pc'] or 'Sucursal'}", f"Autor: {row['created_by']}", f"Mensaje: {row['body']}", "", "Historial:"]
        lines += [f"{event['recorded_at']} · {event['from_state'] or 'NUEVO'} → {event['to_state']} · {event['actor']}" for event in history]
        self.detail.config(state="normal"); self.detail.delete("1.0", "end"); self.detail.insert("1.0", "\n".join(lines)); self.detail.config(state="disabled")

    def process(self):
        count = len(self.service.process_due(self.principal)); self.reload(); self.feedback.config(text=f"Procesamiento local completado · {count} mensaje(s)")

    def retry(self):
        message_id = self._selected()
        if message_id: self.service.retry(self.principal, message_id); self.reload(); self.feedback.config(text="Reintento manual programado")

    def cancel(self):
        message_id = self._selected()
        if not message_id: return
        reason = simpledialog.askstring("Cancelar mensaje", "Motivo obligatorio:", parent=self)
        if reason: self.service.cancel(self.principal, message_id, reason); self.reload(); self.feedback.config(text="Mensaje cancelado y auditado")
