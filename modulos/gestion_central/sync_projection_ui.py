from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .models import Unit
from .sync_projection_view import CATEGORY_LABELS
from .ui import COLORS


ALL_CATEGORIES = "Todas las categorías"
ALL_UNITS = "Todas las sucursales"


class SyncProjectionPanel(tk.Frame):
    """Pantalla de supervisión: lee proyecciones y no ofrece ninguna escritura."""

    def __init__(self, parent, view, principal, *, back, notifier=None):
        super().__init__(parent, bg=COLORS["surface"])
        self.view, self.principal, self.back = view, principal, back
        self.notifier = notifier or messagebox.showinfo
        self.rows = {}
        self._build()
        self.reload()

    def _build(self):
        head = tk.Frame(self, bg=COLORS["card"], height=58); head.pack(fill="x", padx=12, pady=(10, 5)); head.pack_propagate(False)
        self.back_button = tk.Button(head, text="← Volver al panel", command=self.back, bg=COLORS["navy"], fg="white", relief="flat", padx=12)
        self.back_button.pack(side="left", padx=10, pady=10)
        tk.Label(head, text="Recepción BC Sync · proyecciones de las sedes", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 16, "bold")).pack(side="left", padx=10)
        tk.Label(head, text="SOLO LECTURA · NO ESCRIBE EN LAS SEDES", bg="#7D2935", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=6).pack(side="right", padx=10)

        self.kpis = {}
        kpi_frame = tk.Frame(self, bg=COLORS["surface"]); kpi_frame.pack(fill="x", padx=10, pady=4)
        for index, (key, label) in enumerate((("total", "RECIBIDOS"), ("VENTA", "VENTAS"), ("SOBRE", "SOBRES"), ("FACTUFACIL", "FACTUFÁCIL"), ("rejected", "RECHAZOS"), ("duplicated", "DUPLICADOS"))):
            kpi_frame.grid_columnconfigure(index, weight=1, uniform="sync-kpi")
            box = tk.Frame(kpi_frame, bg=COLORS["card"], height=63, highlightthickness=1, highlightbackground="#D7E0E8")
            box.grid(row=0, column=index, padx=3, sticky="ew"); box.grid_propagate(False)
            tk.Label(box, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            value = tk.Label(box, text="0", bg=COLORS["card"], fg=COLORS["navy"], font=("Segoe UI", 15, "bold"))
            value.pack(anchor="w", padx=10); self.kpis[key] = value

        filters = tk.Frame(self, bg=COLORS["surface"]); filters.pack(fill="x", padx=12, pady=4)
        self.category_var = tk.StringVar(value=ALL_CATEGORIES)
        self.category_filter = ttk.Combobox(filters, textvariable=self.category_var, state="readonly", width=22,
                                            values=[ALL_CATEGORIES, *CATEGORY_LABELS.values()])
        self.category_filter.pack(side="left"); self.category_filter.bind("<<ComboboxSelected>>", lambda _e: self.reload())
        self.unit_var = tk.StringVar(value=ALL_UNITS)
        self.unit_filter = ttk.Combobox(filters, textvariable=self.unit_var, state="readonly", width=22,
                                        values=[ALL_UNITS, *(unit.label for unit in Unit)])
        self.unit_filter.pack(side="left", padx=8); self.unit_filter.bind("<<ComboboxSelected>>", lambda _e: self.reload())
        self.state_var, self.text_var = tk.StringVar(), tk.StringVar()
        for label, var, width in (("Estado FactuFácil", self.state_var, 16), ("Buscar", self.text_var, 22)):
            tk.Label(filters, text=label, bg=COLORS["surface"]).pack(side="left", padx=(10, 3))
            entry = tk.Entry(filters, textvariable=var, width=width); entry.pack(side="left")
            entry.bind("<Return>", lambda _e: self.reload())
        self.reload_button = tk.Button(filters, text="Aplicar filtros", command=self.reload); self.reload_button.pack(side="left", padx=8)
        self.last_label = tk.Label(filters, text="Sin recepciones", bg=COLORS["surface"], fg=COLORS["muted"]); self.last_label.pack(side="right")

        panes = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=COLORS["surface"], sashwidth=7); panes.pack(fill="both", expand=True, padx=12, pady=4)
        table_frame = tk.Frame(panes, bg=COLORS["card"]); side = tk.Frame(panes, bg=COLORS["card"], width=420)
        panes.add(table_frame, minsize=760, stretch="always"); panes.add(side, minsize=360, stretch="never")
        columns = ("occurred_at", "unit", "category", "sale", "envelope", "customer", "document", "factufacil", "invoice", "state")
        labels = ("Recibido", "Sucursal", "Categoría", "Venta", "Sobre", "Cliente", "CI/RUC", "FactuFácil", "Factura", "Sync")
        widths = (150, 150, 140, 130, 100, 175, 110, 140, 120, 95)
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", height=18)
        for key, label, width in zip(columns, labels, widths):
            self.tree.heading(key, text=label); self.tree.column(key, width=width, anchor="w")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); vertical.grid(row=0, column=1, sticky="ns"); horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1); table_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        tk.Label(side, text="Detalle del evento recibido", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.detail_label = tk.Label(side, text="Seleccione una recepción", bg=COLORS["card"], fg=COLORS["muted"], wraplength=380, justify="left")
        self.detail_label.pack(anchor="w", padx=12, pady=4)
        tk.Label(side, text="Intentos rechazados o duplicados", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.rejections_tree = ttk.Treeview(side, columns=("audit_at", "outcome", "unit", "reason"), show="headings", height=9)
        for key, label, width in (("audit_at", "Fecha", 140), ("outcome", "Resultado", 95), ("unit", "Sucursal", 140), ("reason", "Motivo", 320)):
            self.rejections_tree.heading(key, text=label); self.rejections_tree.column(key, width=width, anchor="w")
        self.rejections_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.feedback = tk.Label(self, text="Listo", bg=COLORS["navy"], fg="white", anchor="w", padx=10, pady=5)
        self.feedback.pack(fill="x", padx=12, pady=(0, 8))

    def _category(self):
        selection = self.category_var.get()
        return next((key for key, label in CATEGORY_LABELS.items() if label == selection), None)

    def _unit(self):
        selection = self.unit_var.get()
        return next((unit for unit in Unit if unit.label == selection), None)

    def reload(self):
        try:
            rows = self.view.rows(self.principal, category=self._category(), unit=self._unit(),
                                  state=self.state_var.get().strip() or None,
                                  text=self.text_var.get().strip() or None)
            summary = self.view.summary(self.principal)
        except Exception:
            self.feedback.config(text="No se pudo leer la recepción; revise el registro local")
            self.notifier("Recepción BC Sync", "No se pudo leer la recepción de Sync.")
            return None
        self.rows = {row["event_id"]: row for row in rows}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            self.tree.insert("", "end", iid=row["event_id"], values=(
                row["occurred_at"].replace("T", " ")[:19], row["unit_label"], row["category_label"],
                row["sale_id"], row["envelope"], row["customer_name"], row["customer_document"],
                row["factufacil_state"], row["invoice_number"], row["sync_state"]))
        self.kpis["total"].config(text=str(summary["total"]))
        for key in ("VENTA", "SOBRE", "FACTUFACIL"):
            self.kpis[key].config(text=str(summary["categories"].get(key, 0)))
        self.kpis["rejected"].config(text=str(summary["rejected"]))
        self.kpis["duplicated"].config(text=str(summary["duplicated"]))
        last = summary["last_occurred_at"]
        self.last_label.config(text=f"Última recepción: {last.replace('T', ' ')[:19]}" if last else "Sin recepciones")
        self._render_rejections()
        self.feedback.config(text=f"Filtro aplicado · {len(rows)} recepción(es) visibles")
        return rows

    def _render_rejections(self):
        for item in self.rejections_tree.get_children():
            self.rejections_tree.delete(item)
        if not self.principal.allows("audit.read"):
            self.rejections_tree.insert("", "end", values=("—", "—", "—", "Sin permiso de auditoría"))
            return
        for row in self.view.rejections(self.principal):
            self.rejections_tree.insert("", "end", iid=str(row["sequence"]), values=(
                row["audit_at"].replace("T", " ")[:19], row["outcome"], row["unit_label"], row["reason"]))

    def _select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        row = self.rows[selected[-1]]
        detail = " · ".join(f"{key}={value}" for key, value in sorted(row["payload"].items()))
        self.detail_label.config(text=f"{row['category_label']} · {row['unit_label']}\n{row['event_id']}\n{detail}")
        self.feedback.config(text=f"Recepción seleccionada · {row['category_label']}")
