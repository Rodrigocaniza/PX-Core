from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from .ui import COLORS


ALL_BRANCHES = "Todas las sucursales"
NOTE_KIND = "Observación"
EVENT_KIND = "Evento"


def merge_log(notes, events):
    """Bitácora append-only: observaciones y eventos en una sola línea temporal."""
    entries = [{"recorded_at": note["recorded_at"], "kind": NOTE_KIND, "actor": note["author"],
                "detail": note["note"], "field": note["field_name"] or ""} for note in notes]
    for event in events:
        details = json.loads(event["details_json"]) if event["details_json"] else {}
        reason = str(details.get("reason") or details.get("idempotency_key") or "")
        entries.append({"recorded_at": event["recorded_at"], "kind": EVENT_KIND,
                        "actor": event["actor"], "field": str(details.get("field") or ""),
                        "detail": f"{event['action']}: {event['from_status']} → {event['to_status']}"
                                  + (f" · {reason}" if reason else "")})
    return sorted(entries, key=lambda entry: (entry["recorded_at"], entry["kind"]))


class PendingPanel(tk.Frame):
    """Cola pendiente y bitácora: sólo muestra: no envía, no marca, no despacha."""

    def __init__(self, parent, service, principal, *, back, notifier=None):
        super().__init__(parent, bg=COLORS["surface"])
        self.service, self.principal, self.back = service, principal, back
        self.notifier = notifier or messagebox.showinfo
        self.sales, self.identities, self.current_identity = {}, {}, None
        self._build()
        self.reload()

    def _build(self):
        head = tk.Frame(self, bg=COLORS["card"], height=58); head.pack(fill="x", padx=12, pady=(10, 5)); head.pack_propagate(False)
        self.back_button = tk.Button(head, text="← Volver al panel", command=self.back, bg=COLORS["navy"], fg="white", relief="flat", padx=12)
        self.back_button.pack(side="left", padx=10, pady=10)
        tk.Label(head, text="Pendientes y bitácora de revisión", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 16, "bold")).pack(side="left", padx=10)
        tk.Label(head, text="SOLO LECTURA · NADA SE ENVÍA A LAS SUCURSALES", bg="#7D2935", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=6).pack(side="right", padx=10)

        self.kpis = {}
        kpi_frame = tk.Frame(self, bg=COLORS["surface"]); kpi_frame.pack(fill="x", padx=10, pady=4)
        for index, (key, label) in enumerate((("corrections", "CORRECCIONES"), ("alerts", "ALERTAS"),
                                              ("rows", "FILAS AFECTADAS"), ("branches", "SUCURSALES"))):
            kpi_frame.grid_columnconfigure(index, weight=1, uniform="pending-kpi")
            box = tk.Frame(kpi_frame, bg=COLORS["card"], height=63, highlightthickness=1, highlightbackground="#D7E0E8")
            box.grid(row=0, column=index, padx=3, sticky="ew"); box.grid_propagate(False)
            tk.Label(box, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(box, text="0", bg=COLORS["card"], fg=COLORS["navy"], font=("Segoe UI", 15, "bold"))
            value.pack(anchor="w", padx=10); self.kpis[key] = value

        filters = tk.Frame(self, bg=COLORS["surface"]); filters.pack(fill="x", padx=12, pady=4)
        tk.Label(filters, text="Sucursal", bg=COLORS["surface"]).pack(side="left", padx=(0, 3))
        self.branch_var = tk.StringVar(value=ALL_BRANCHES)
        self.branch_filter = ttk.Combobox(filters, textvariable=self.branch_var, state="readonly", width=24, values=[ALL_BRANCHES])
        self.branch_filter.pack(side="left"); self.branch_filter.bind("<<ComboboxSelected>>", lambda _e: self.reload())
        self.reload_button = tk.Button(filters, text="Actualizar", command=self.reload); self.reload_button.pack(side="left", padx=8)
        self.oldest_label = tk.Label(filters, text="Sin pendientes", bg=COLORS["surface"], fg=COLORS["muted"]); self.oldest_label.pack(side="right")

        queues = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=COLORS["surface"], sashwidth=7); queues.pack(fill="both", expand=True, padx=12, pady=4)
        corrections = tk.LabelFrame(queues, text="  Correcciones solicitadas  ", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 11, "bold"), padx=8, pady=8)
        alerts = tk.LabelFrame(queues, text="  Alertas encoladas  ", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 11, "bold"), padx=8, pady=8)
        queues.add(corrections, minsize=620, stretch="always"); queues.add(alerts, minsize=420, stretch="always")
        self.corrections_tree = ttk.Treeview(corrections, columns=("requested_at", "branch", "date", "envelope", "field", "reason", "requested_by"), show="headings", selectmode="browse", height=8)
        for key, label, width in (("requested_at", "Solicitada", 140), ("branch", "Sucursal", 100), ("date", "Fecha", 95),
                                  ("envelope", "Sobre", 90), ("field", "Campo", 120), ("reason", "Motivo", 240), ("requested_by", "Solicitó", 105)):
            self.corrections_tree.heading(key, text=label); self.corrections_tree.column(key, width=width, anchor="w")
        self.corrections_tree.pack(fill="both", expand=True)
        self.corrections_tree.bind("<<TreeviewSelect>>", lambda _e: self._select(self.corrections_tree))
        self.alerts_tree = ttk.Treeview(alerts, columns=("created_at", "branch", "envelope", "message", "created_by"), show="headings", selectmode="browse", height=8)
        for key, label, width in (("created_at", "Encolada", 140), ("branch", "Sucursal", 100), ("envelope", "Sobre", 90),
                                  ("message", "Mensaje", 260), ("created_by", "Creó", 105)):
            self.alerts_tree.heading(key, text=label); self.alerts_tree.column(key, width=width, anchor="w")
        self.alerts_tree.pack(fill="both", expand=True)
        self.alerts_tree.bind("<<TreeviewSelect>>", lambda _e: self._select(self.alerts_tree))

        log_frame = tk.LabelFrame(self, text="  Bitácora append-only de la fila seleccionada  ", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 11, "bold"), padx=8, pady=8)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.log_title = tk.Label(log_frame, text="Seleccione un pendiente", bg=COLORS["card"], fg=COLORS["muted"], anchor="w")
        self.log_title.pack(fill="x", pady=(0, 4))
        self.log_tree = ttk.Treeview(log_frame, columns=("recorded_at", "kind", "actor", "field", "detail"), show="headings", height=7)
        for key, label, width in (("recorded_at", "Fecha", 140), ("kind", "Tipo", 110), ("actor", "Actor", 110),
                                  ("field", "Campo", 120), ("detail", "Detalle", 520)):
            self.log_tree.heading(key, text=label); self.log_tree.column(key, width=width, anchor="w")
        self.log_tree.pack(fill="both", expand=True)

        self.feedback = tk.Label(self, text="Listo", bg=COLORS["navy"], fg="white", anchor="w", padx=10, pady=5)
        self.feedback.pack(fill="x", padx=12, pady=(0, 8))

    def _branch(self):
        selection = self.branch_var.get()
        return None if selection == ALL_BRANCHES else selection

    def _context(self, identity):
        sale = self.sales.get(identity)
        return sale["payload"] if sale else {}

    def reload(self):
        try:
            self.sales = {sale["identity"]: sale for sale in self.service.list_sales(self.principal)}
            branch = self._branch()
            corrections = self.service.pending_corrections(self.principal, branch=branch)
            alerts = self.service.pending_alerts(self.principal, branch=branch)
        except Exception:
            self.feedback.config(text="No se pudo leer la cola pendiente; revise el registro local")
            self.notifier("Pendientes", "No se pudo leer la cola pendiente.")
            return None
        # El outbox desempata por uuid: se reordena aquí para que la cola no baile
        # entre recargas cuando varias solicitudes comparten el mismo segundo.
        corrections = sorted(corrections, key=lambda row: (row["requested_at"], row["business_date"], row["source_entry_id"]))
        alerts = sorted(alerts, key=lambda row: (row["created_at"], row["branch"], row["identity"]))
        branches = sorted({sale["branch"] for sale in self.sales.values()})
        self.branch_filter.configure(values=[ALL_BRANCHES, *branches])
        for tree in (self.corrections_tree, self.alerts_tree):
            for item in tree.get_children():
                tree.delete(item)
        for row in corrections:
            self.corrections_tree.insert("", "end", iid=row["id"], values=(
                row["requested_at"].replace("T", " ")[:19], row["branch"], row["business_date"],
                self._context(row["identity"]).get("envelope", ""), row["field_name"] or "Fila completa",
                row["reason"], row["requested_by"]))
        for row in alerts:
            self.alerts_tree.insert("", "end", iid=row["id"], values=(
                row["created_at"].replace("T", " ")[:19], row["branch"],
                self._context(row["identity"]).get("envelope", ""), row["message"], row["created_by"]))
        self.identities = {**{row["id"]: row["identity"] for row in corrections},
                           **{row["id"]: row["identity"] for row in alerts}}
        self.kpis["corrections"].config(text=str(len(corrections)))
        self.kpis["alerts"].config(text=str(len(alerts)))
        self.kpis["rows"].config(text=str(len({row["identity"] for row in (*corrections, *alerts)})))
        self.kpis["branches"].config(text=str(len({row["branch"] for row in (*corrections, *alerts)})))
        stamps = sorted([row["requested_at"] for row in corrections] + [row["created_at"] for row in alerts])
        self.oldest_label.config(text=f"Más antiguo: {stamps[0].replace('T', ' ')[:19]}" if stamps else "Sin pendientes")
        self.feedback.config(text=f"{len(corrections)} corrección(es) y {len(alerts)} alerta(s) pendientes")
        return corrections, alerts

    def _select(self, tree):
        selected = tree.selection()
        if not selected:
            return None
        identity = self.identities.get(selected[-1])
        if identity is None:
            return None
        try:
            entries = merge_log(self.service.notes(self.principal, identity),
                                self.service.events(self.principal, identity))
        except Exception:
            self.feedback.config(text="No se pudo leer la bitácora; revise el registro local")
            self.notifier("Bitácora", "No se pudo leer la bitácora de la fila.")
            return None
        self.current_identity = identity
        payload = self._context(identity)
        self.log_title.config(text=f"{payload.get('envelope') or 'Sin sobre'} · {payload.get('customer_name', '')} · {len(entries)} anotación(es)")
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        for entry in entries:
            self.log_tree.insert("", "end", values=(entry["recorded_at"].replace("T", " ")[:19],
                                                    entry["kind"], entry["actor"], entry["field"], entry["detail"]))
        self.feedback.config(text=f"Bitácora de {payload.get('envelope') or identity}")
        return entries
