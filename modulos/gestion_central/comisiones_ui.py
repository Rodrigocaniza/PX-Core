"""Bandeja visual de comisiones para Sol. Sólo presenta: el cálculo vive en `comisiones.py`."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from .comision_policy import rate_percent_text
from .comisiones import COMMISSION_STATES, CommissionService
from .ui import COLORS, pyg


# Colores de estado legibles sobre tarjeta blanca, con texto siempre contrastado.
STATE_COLORS = {
    "PENDIENTE_SALDO": ("#FFF3D6", "#7A5A10"),
    "ELEGIBLE": ("#E2F0FB", "#12507D"),
    "CALCULADA": ("#DDEBFA", "#123F6B"),
    "REVISADA": ("#E4EEF7", "#1B4E7A"),
    "APROBADA": ("#DFF1E6", "#15653F"),
    "PAGADA": ("#CFE9DA", "#0E4F30"),
    "OBSERVADA": ("#FBE7D2", "#8A4A11"),
    "REVERTIDA": ("#F6D6D9", "#7D2935"),
}
KPI_LAYOUT = (
    ("Ventas del período", "sales_in_period", False),
    ("Ventas canceladas", "cancelled_sales", False),
    ("Cobros parciales", "partial_payments_amount", True),
    ("Convenios", "agreements", False),
    ("Base comisionable", "commissionable_base", True),
    ("Comisión oficial", "commission_amount", True),
    ("Pendiente de aprobación", "pending_approval", False),
    ("Pagado", "paid_amount", True),
)
SUMMARY_COLUMNS = (
    ("branch", "Local", 190, "w"), ("saleswoman", "Vendedora", 175, "w"),
    ("sales", "Ventas", 70, "center"), ("pending_balance", "Con saldo", 85, "center"),
    ("cancelled", "Canceladas", 90, "center"), ("agreements", "Convenios", 85, "center"),
    ("gross_informative", "Total vendido", 145, "e"), ("agreement_discount", "Desc. convenio", 135, "e"),
    ("commissionable_base", "Base comisionable", 165, "e"), ("commission_amount", "Comisión", 135, "e"),
)
ENTRY_COLUMNS = (
    ("status", "Estado", 126, "w"), ("sale_date", "Fecha venta", 88, "center"),
    ("period", "Período", 72, "center"), ("branch", "Local", 145, "w"),
    ("saleswoman", "Vendedora", 135, "w"), ("sale_kind", "Tipo", 74, "center"),
    ("envelope", "Sobre", 64, "center"), ("gross_amount", "Total", 112, "e"),
    ("balance_amount", "Saldo", 108, "e"), ("agreement_discount", "Desc. 5%", 100, "e"),
    ("commissionable_base", "Base comisionable", 135, "e"), ("commission_amount", "Comisión", 112, "e"),
)
HISTORY_COLUMNS = (("when", "Fecha", 125, "w"), ("action", "Acción", 195, "w"),
                   ("state", "Estado", 110, "w"), ("actor", "Responsable", 95, "w"))
AMOUNT_KEYS = {"gross_informative", "agreement_discount", "commissionable_base", "commission_amount",
               "non_official_amount", "balance_amount", "gross_amount", "paid_amount",
               "partial_payments_amount"}


class CommissionsPanel(tk.Frame):
    """Bandeja mensual de comisiones: resumen, detalle, desglose e historial."""

    def __init__(self, parent, core, principal, *, back, notifier=None, asker=None, data_root=None):
        super().__init__(parent, bg=COLORS["surface"])
        self.service = CommissionService(core)
        self.principal = principal
        self.back = back
        self.notifier = notifier or messagebox.showinfo
        self.asker = asker or (lambda title, prompt: simpledialog.askstring(title, prompt, parent=self))
        self.data_root = Path(data_root or core.repository.database_path.parent)
        self.rows, self.current, self.report, self.policy = {}, None, None, None
        self._build()
        self.reload()

    # ------------------------------------------------------------------ diseño
    def _build(self):
        head = tk.Frame(self, bg=COLORS["card"], height=62)
        head.pack(fill="x", padx=14, pady=(10, 5)); head.pack_propagate(False)
        tk.Button(head, text="← Volver al panel", command=self.back, bg=COLORS["navy"], fg="white",
                  relief="flat", padx=12, pady=6).pack(side="left", padx=10, pady=12)
        tk.Label(head, text="Comisiones por vendedora y local", bg=COLORS["card"], fg=COLORS["text"],
                 font=("Segoe UI", 17, "bold")).pack(side="left", padx=12)
        self.policy_label = tk.Label(head, text="", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9))
        self.policy_label.pack(side="left", padx=14)
        tk.Label(head, text="PILOTO · DATOS SINTÉTICOS · SIN NÓMINA NI BANCOS", bg="#7D2935", fg="white",
                 font=("Segoe UI", 9, "bold"), padx=10, pady=6).pack(side="right", padx=10)

        filters = tk.Frame(self, bg=COLORS["surface"]); filters.pack(fill="x", padx=16, pady=4)
        self.period_var, self.branch_var, self.saleswoman_var, self.status_var = (tk.StringVar() for _ in range(4))
        self.branch_var.set("TODOS"); self.saleswoman_var.set("TODAS"); self.status_var.set("TODOS")
        tk.Label(filters, text="Mes (AAAA-MM)", bg=COLORS["surface"]).pack(side="left", padx=(7, 3))
        self.period_entry = tk.Entry(filters, textvariable=self.period_var, width=10)
        self.period_entry.pack(side="left")
        tk.Label(filters, text="Local", bg=COLORS["surface"]).pack(side="left", padx=(12, 3))
        self.branch_box = ttk.Combobox(filters, textvariable=self.branch_var, state="readonly", width=20)
        self.branch_box.pack(side="left"); self.branch_box.bind("<<ComboboxSelected>>", lambda _e: self.reload())
        tk.Label(filters, text="Vendedora", bg=COLORS["surface"]).pack(side="left", padx=(12, 3))
        self.saleswoman_box = ttk.Combobox(filters, textvariable=self.saleswoman_var, state="readonly", width=20)
        self.saleswoman_box.pack(side="left"); self.saleswoman_box.bind("<<ComboboxSelected>>", lambda _e: self.reload())
        tk.Label(filters, text="Estado", bg=COLORS["surface"]).pack(side="left", padx=(12, 3))
        self.status_box = ttk.Combobox(filters, textvariable=self.status_var, state="readonly", width=18,
                                       values=["TODOS", *COMMISSION_STATES])
        self.status_box.pack(side="left"); self.status_box.bind("<<ComboboxSelected>>", lambda _e: self.reload())
        self.apply_button = tk.Button(filters, text="Aplicar", command=self.reload, bg=COLORS["blue"],
                                      fg="white", relief="flat", padx=14, pady=4)
        self.apply_button.pack(side="left", padx=10)
        self.export_button = tk.Button(filters, text="Exportar resumen", command=self.export,
                                       bg=COLORS["navy"], fg="white", relief="flat", padx=12, pady=4)
        self.export_button.pack(side="right", padx=4)
        self.recalculate_button = tk.Button(filters, text="Recalcular", command=self.recalculate,
                                            bg="#2A86C7", fg="white", relief="flat", padx=12, pady=4)
        self.recalculate_button.pack(side="right", padx=4)

        kpis = tk.Frame(self, bg=COLORS["surface"]); kpis.pack(fill="x", padx=14, pady=5)
        self.kpis, self.kpi_captions = {}, {}
        for column, (label, key, _money) in enumerate(KPI_LAYOUT):
            kpis.grid_columnconfigure(column, weight=1, uniform="com-kpi")
            box = tk.Frame(kpis, bg=COLORS["card"], height=68, highlightthickness=1, highlightbackground="#D7E0E8")
            box.grid(row=0, column=column, padx=3, sticky="ew"); box.grid_propagate(False)
            caption = tk.Label(box, text=label.upper(), bg=COLORS["card"], fg=COLORS["muted"],
                               font=("Segoe UI", 8, "bold"))
            caption.pack(anchor="w", padx=10, pady=(9, 0)); self.kpi_captions[key] = caption
            value = tk.Label(box, text="0", bg=COLORS["card"], fg=COLORS["navy"], font=("Segoe UI", 14, "bold"))
            value.pack(anchor="w", padx=10); self.kpis[key] = value

        # Aviso de importes fuera de la política oficial. Sólo aparece cuando los hay.
        self.warning = tk.Label(self, text="", bg="#FBE7D2", fg="#8A4A11", anchor="w",
                                font=("Segoe UI", 9, "bold"), padx=12, pady=5)

        panes = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=COLORS["surface"], sashwidth=7, relief="flat")
        panes.pack(fill="both", expand=True, padx=14, pady=5)
        self.panes = panes
        # Anchos calibrados para 1920x1080: la tabla principal muestra hasta la comisión sin recorte.
        left = tk.Frame(panes, bg=COLORS["surface"]); right = tk.Frame(panes, bg=COLORS["card"], width=540)
        panes.add(left, minsize=1310, stretch="always"); panes.add(right, minsize=500, stretch="never")

        summary = tk.LabelFrame(left, text="  Resumen por vendedora  ", bg=COLORS["card"], fg=COLORS["text"],
                                font=("Segoe UI", 10, "bold"), padx=6, pady=5)
        summary.pack(fill="x", pady=(0, 6))
        self.summary_tree = ttk.Treeview(summary, columns=[key for key, *_ in SUMMARY_COLUMNS],
                                         show="headings", height=5, selectmode="browse")
        for key, label, width, anchor in SUMMARY_COLUMNS:
            self.summary_tree.heading(key, text=label)
            self.summary_tree.column(key, width=width, anchor=anchor, stretch=False)
        self.summary_tree.pack(fill="x")

        detail = tk.LabelFrame(left, text="  Ventas del período  ", bg=COLORS["card"], fg=COLORS["text"],
                               font=("Segoe UI", 10, "bold"), padx=6, pady=5)
        detail.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(detail, columns=[key for key, *_ in ENTRY_COLUMNS], show="headings",
                                 height=17, selectmode="browse")
        for key, label, width, anchor in ENTRY_COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=anchor, stretch=False)
        for state, (background, foreground) in STATE_COLORS.items():
            self.tree.tag_configure(state, background=background, foreground=foreground)
        scroll = ttk.Scrollbar(detail, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.select)

        tk.Label(right, text="Detalle y desglose del cálculo", bg=COLORS["card"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(9, 2))
        self.reason = tk.Label(right, text="Seleccione una venta para ver por qué comisiona o no.",
                               bg="#E2F0FB", fg="#12507D", font=("Segoe UI", 10, "bold"), wraplength=520,
                               justify="left", anchor="w", padx=12, pady=9)
        self.reason.pack(fill="x", padx=12, pady=3)
        self.breakdown = tk.Frame(right, bg=COLORS["card"]); self.breakdown.pack(fill="x", padx=12, pady=5)
        self.policy_note = tk.Label(right, text="", bg=COLORS["card"], fg=COLORS["muted"],
                                    font=("Segoe UI", 9), wraplength=520, justify="left", anchor="w")
        self.policy_note.pack(fill="x", padx=12)

        actions = tk.Frame(right, bg=COLORS["card"]); actions.pack(fill="x", padx=10, pady=8)
        self.review_button = tk.Button(actions, text="Revisar cálculo", command=self.review, padx=8)
        self.approve_button = tk.Button(actions, text="Aprobar", command=self.approve, bg=COLORS["ok"],
                                        fg="white", padx=8)
        self.paid_button = tk.Button(actions, text="Marcar pagada", command=self.mark_paid, bg=COLORS["navy"],
                                     fg="white", padx=8)
        self.observe_button = tk.Button(actions, text="Observar", command=self.observe, bg="#FBE7D2", padx=8)
        self.revert_button = tk.Button(actions, text="Revertir", command=self.revert, bg="#F6D6D9", padx=8)
        for button in (self.review_button, self.approve_button, self.paid_button,
                       self.observe_button, self.revert_button):
            button.pack(side="left", padx=2)

        tk.Label(right, text="Historial auditable", bg=COLORS["card"], fg=COLORS["text"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(4, 2))
        self.history = ttk.Treeview(right, columns=("when", "action", "state", "actor"), show="headings", height=8)
        for key, label, width, anchor in HISTORY_COLUMNS:
            self.history.heading(key, text=label)
            self.history.column(key, width=width, anchor=anchor, stretch=False)
        self.history.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.feedback = tk.Label(self, text="Listo", bg=COLORS["navy"], fg="white", anchor="w", padx=12, pady=6)
        self.feedback.pack(fill="x", padx=14, pady=(0, 9))

    # ------------------------------------------------------------------- datos
    def _default_period(self):
        rows = self.service.list_entries(self.principal)
        periods = sorted({row["period"] for row in rows if row["period"]} |
                         {row["sale_date"][:7] for row in rows})
        return periods[-1] if periods else "2099-04"

    def reload(self):
        if not self.period_var.get().strip():
            self.period_var.set(self._default_period())
        period = self.period_var.get().strip()
        branch = None if self.branch_var.get() in {"", "TODOS"} else self.branch_var.get()
        saleswoman = None if self.saleswoman_var.get() in {"", "TODAS"} else self.saleswoman_var.get()
        status = None if self.status_var.get() in {"", "TODOS"} else self.status_var.get()
        self.report = self.service.report(self.principal, period, branch=branch,
                                          saleswoman=saleswoman, status=status)
        every = self.service.list_entries(self.principal, period=period)
        self.branch_box.configure(values=["TODOS", *sorted({row["branch"] for row in every})])
        self.saleswoman_box.configure(values=["TODAS", *sorted({row["saleswoman"] for row in every})])
        self.rows = {row["id"]: row for row in self.report["entries"]}

        for key, label in self.kpis.items():
            value = self.report["kpi"][key]
            label.config(text=pyg(value) if key in AMOUNT_KEYS else str(value))
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        for bucket in self.report["by_saleswoman"]:
            self.summary_tree.insert("", "end", values=tuple(
                pyg(bucket[key]) if key in AMOUNT_KEYS else bucket[key] for key, *_ in SUMMARY_COLUMNS))
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.report["entries"]:
            self.tree.insert("", "end", iid=row["id"], tags=(row["status"],), values=tuple(
                self._cell(row, key) for key, *_ in ENTRY_COLUMNS))
        self.policy = self._apply_policy_labels()
        self.feedback.config(text=f"{len(self.report['entries'])} venta(s) en {period} · filtros aplicados")
        if self.current in self.rows:
            self.tree.selection_set(self.current)
        else:
            self.current = None

    def _apply_policy_labels(self):
        """La pantalla nombra el porcentaje oficial vigente en vez de darlo por sabido.

        El KPI sí lleva el porcentaje porque suma únicamente lo calculado con la política
        aprobada. Las columnas no: una fila puede arrastrar un importe de una política
        retirada, y encabezarla «Comisión 1,00%» declararía como oficial algo que no lo es.
        """
        policy = self.service.current_policy(self.principal)
        percent = rate_percent_text(policy["rate_bp"])
        self.policy_label.config(
            text=f"Comisión oficial {percent} de la base · {policy['code']} v{policy['version']} · "
                 f"vigente desde {policy['effective_from']} · redondeo {policy['rounding']} a Gs. enteros")
        self.kpi_captions["commission_amount"].config(text=f"COMISIÓN OFICIAL {percent}")
        kpi = self.report["kpi"]
        if kpi["non_official_amount"]:
            self.warning.config(
                text=f"⚠ {kpi['non_official_entries']} liquidación(es) por {pyg(kpi['non_official_amount'])} "
                     f"con política anterior, fuera de la comisión oficial. Recalcule las no pagadas.")
            self.warning.pack(fill="x", padx=16, pady=(0, 4), before=self.panes)
        else:
            self.warning.pack_forget()
        return policy

    @staticmethod
    def _cell(row, key):
        value = row.get(key)
        if key == "status":
            return value.replace("_", " ")
        if key == "sale_kind":
            return "Convenio" if value == "CONVENIO" else "Común"
        if key in AMOUNT_KEYS:
            return "—" if value is None else pyg(value)
        return "—" if value in (None, "") else value

    # ----------------------------------------------------------------- detalle
    def select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        self.current = selected[0]
        detail = self.service.breakdown(self.principal, self.current)
        background, foreground = STATE_COLORS[detail["status"]]
        self.reason.config(text=f"{detail['status'].replace('_', ' ')} · {detail['reason']}",
                           bg=background, fg=foreground)
        for child in self.breakdown.winfo_children():
            child.destroy()
        for line in detail["lines"]:
            row = tk.Frame(self.breakdown, bg=COLORS["card"]); row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{line['sign']} {line['label']}".strip(), bg=COLORS["card"], fg=COLORS["text"],
                     font=("Segoe UI", 10), anchor="w").pack(side="left")
            tk.Label(row, text=pyg(line["amount"]), bg=COLORS["card"], fg=COLORS["navy"],
                     font=("Consolas", 11, "bold"), anchor="e", width=18).pack(side="right")
        self.policy_note.config(text=detail["policy_note"])
        for item in self.history.get_children():
            self.history.delete(item)
        for event in self.service.history(self.principal, self.current):
            self.history.insert("", "end", values=(event["recorded_at"].replace("T", " ")[:19],
                                                   event["action"], event["to_state"], event["actor"]))

    def _selected(self):
        if not self.current:
            self.notifier("Comisiones", "Seleccione una venta de la tabla.")
            return None
        return self.current

    def _run(self, label, action):
        entry_id = self._selected()
        if not entry_id:
            return False
        try:
            result = action(entry_id)
        except ValueError as error:
            self.notifier("Comisiones", str(error))
            self.feedback.config(text=f"No se pudo {label}: {error}")
            return False
        if result is False:
            return False
        self.reload()
        if self.current in self.rows:
            self.select()
        self.feedback.config(text=f"{label.capitalize()} · registrado en el historial auditable")
        return True

    # ----------------------------------------------------------------- acciones
    def review(self):
        return self._run("revisar cálculo", lambda entry_id: self.service.review(self.principal, entry_id))

    def approve(self):
        responsible = self.asker("Aprobar comisión", "Responsable de la aprobación:")
        if not responsible:
            return False
        return self._run("aprobar", lambda entry_id: self.service.approve(self.principal, entry_id, responsible))

    def mark_paid(self):
        payment_date = self.asker("Marcar pagada", "Fecha de pago (AAAA-MM-DD):")
        reference = self.asker("Marcar pagada", "Referencia del pago:") if payment_date else None
        if not payment_date or not reference:
            return False
        return self._run("marcar pagada",
                         lambda entry_id: self.service.mark_paid(self.principal, entry_id, payment_date, reference))

    def observe(self):
        reason = self.asker("Observar", "Motivo de la observación:")
        if not reason:
            return False
        return self._run("observar", lambda entry_id: self.service.observe(self.principal, entry_id, reason))

    def revert(self):
        reason = self.asker("Revertir", "Motivo de la reversión:")
        if not reason:
            return False
        return self._run("revertir", lambda entry_id: self.service.revert(self.principal, entry_id, reason))

    def recalculate(self):
        result = self.service.recalculate(self.principal, period=self.period_var.get().strip() or None)
        self.reload()
        self.feedback.config(text=f"Recálculo idempotente · {result['evaluated']} evaluada(s), "
                                  f"{result['changed']} actualizada(s)")
        return result

    def export(self):
        period = self.period_var.get().strip()
        summary = self.service.export_summary(self.principal, period)
        folder = self.data_root / "Comisiones"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"comisiones-{period}.local.json"
        target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        self.feedback.config(text=f"Resumen exportado localmente: {target.name}")
        return target
