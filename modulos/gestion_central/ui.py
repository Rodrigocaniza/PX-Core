from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

COLORS = {"navy": "#10253F", "blue": "#1769AA", "surface": "#F4F7FA", "card": "#FFFFFF", "text": "#17212B", "muted": "#617181", "ok": "#16855B", "critical": "#BD2C38"}


def pyg(value):
    return f"{int(value or 0):,}".replace(",", ".") + " Gs."


def build_ui_logger(data_root: Path) -> logging.Logger:
    log_dir = Path(data_root) / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"bc_gestion_central.ui.{log_dir}")
    if not logger.handlers:
        handler = logging.FileHandler(log_dir / "ui-errors.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class CentralPilotWindow:
    """Consola interactiva adaptable, priorizada para 24 pulgadas Full HD."""

    def __init__(self, service, *, root=None, notifier=None, logger=None, confirmer=None):
        self.service = service
        self.principal = service.authenticate("sol.piloto", "Piloto-Temporal-2026")
        self.root = root or tk.Tk()
        self.notifier = notifier or messagebox.showinfo
        self.confirmer = confirmer or messagebox.askyesno
        self.logger = logger or build_ui_logger(service.repository.database_path.parent)
        self.current_screen, self.selected_unit = "dashboard", None
        self.card_buttons = {}
        self.root.title("BC Gestión Central · Piloto aislado")
        self.root.geometry("1600x900")
        self.root.minsize(1180, 680)
        self.root.configure(bg=COLORS["surface"])
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.status_var = tk.StringVar(value="Piloto listo")
        self.content = tk.Frame(self.root, bg=COLORS["surface"])
        self.content.pack(fill="both", expand=True)
        self._build_shell()
        self.show_dashboard(announce=False)

    def _build_shell(self):
        header = tk.Frame(self.content, bg=COLORS["navy"], height=86)
        header.pack(fill="x"); header.pack_propagate(False)
        tk.Label(header, text="BC GESTIÓN CENTRAL", bg=COLORS["navy"], fg="white", font=("Segoe UI", 21, "bold")).pack(side="left", padx=28)
        tk.Label(header, text="PILOTO · DATOS SINTÉTICOS · NO PRODUCCIÓN", bg="#7D2935", fg="white", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(side="right", padx=28)
        self.body = tk.Frame(self.content, bg=COLORS["surface"])
        self.body.pack(fill="both", expand=True)
        tk.Label(self.content, textvariable=self.status_var, anchor="w", bg=COLORS["navy"], fg="white", padx=18, pady=7).pack(fill="x", side="bottom")

    def _guard(self, action, label):
        try:
            return action()
        except Exception:
            self.logger.exception("UI action failed: %s", label)
            self.status_var.set(f"No se pudo completar: {label}")
            self.notifier("BC Gestión Central", f"No se pudo completar la acción «{label}».\nRevise el registro local de errores.")
            return None

    def _clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()

    def show_dashboard(self, *, announce=True):
        return self._guard(lambda: self._show_dashboard(announce), "mostrar panel principal")

    def _show_dashboard(self, announce):
        self.current_screen, self.selected_unit = "dashboard", None
        self._clear_body()
        self.service.refresh_alerts(self.principal)
        data = self.service.dashboard(self.principal)
        toolbar = tk.Frame(self.body, bg=COLORS["surface"]); toolbar.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(toolbar, text="Estado de las cuatro unidades", bg=COLORS["surface"], fg=COLORS["text"], font=("Segoe UI", 17, "bold")).pack(side="left")
        self.filter_var = tk.StringVar(value="Todas")
        self.filter_box = ttk.Combobox(toolbar, textvariable=self.filter_var, values=["Todas", "Con alertas", "Sin alertas"], state="readonly", width=14)
        self.filter_box.pack(side="right", padx=(8, 0)); self.filter_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_filter())
        self.refresh_button = tk.Button(toolbar, text="Actualizar", command=self.refresh, bg=COLORS["blue"], fg="white", relief="flat", padx=18, pady=7)
        self.refresh_button.pack(side="right")
        self.review_button = tk.Button(toolbar, text="Revisión de ventas", command=self.show_review, bg=COLORS["navy"], fg="white", relief="flat", padx=18, pady=7)
        self.review_button.pack(side="right", padx=8)
        self.pending_button = tk.Button(toolbar, text="Pendientes y bitácora", command=self.show_pending, bg=COLORS["navy"], fg="white", relief="flat", padx=18, pady=7)
        self.pending_button.pack(side="right")
        self.cards = tk.Frame(self.body, bg=COLORS["surface"]); self.cards.pack(fill="both", expand=True, padx=18)
        self._dashboard_data = data; self._render_cards(data["cards"])
        section = tk.Frame(self.body, bg=COLORS["surface"]); section.pack(fill="x", padx=24, pady=(8, 4))
        tk.Label(section, text="Alertas activas", bg=COLORS["surface"], fg=COLORS["text"], font=("Segoe UI", 14, "bold")).pack(side="left")
        self.ack_button = tk.Button(section, text="Reconocer seleccionada", command=self.acknowledge, relief="groove", padx=12); self.ack_button.pack(side="right")
        self.alerts = ttk.Treeview(self.body, columns=("unidad", "nivel", "mensaje"), show="headings", height=7, selectmode="browse")
        for column, label, width in (("unidad", "Unidad", 220), ("nivel", "Nivel", 100), ("mensaje", "Detalle", 700)):
            self.alerts.heading(column, text=label); self.alerts.column(column, width=width, anchor="w")
        self.alerts.bind("<<TreeviewSelect>>", self._alert_selected); self.alerts.bind("<Double-1>", lambda _e: self.acknowledge())
        self.alerts.pack(fill="x", padx=24, pady=(0, 18)); self._render_alerts(data["alerts"])
        if announce:
            self.status_var.set(f"Actualizado {datetime.now().strftime('%H:%M:%S')} · {len(data['alerts'])} alerta(s) activa(s)")

    def _render_cards(self, cards):
        for child in self.cards.winfo_children(): child.destroy()
        self.card_buttons = {}; width = max(self.root.winfo_width(), 1180); columns = 4 if width >= 1500 else 2
        for column in range(columns): self.cards.grid_columnconfigure(column, weight=1, uniform="cards")
        for index, card in enumerate(cards):
            snap = card["snapshot"] or {}
            text = (f"{card['label']}\n\n● {card['sync']} · {card['alerts']} alerta(s)\n\n{pyg(snap.get('income'))}\n"
                    f"Ingresos · {snap.get('entry_count', 0)} movimientos\n\nEfectivo {pyg(snap.get('cash'))}\n"
                    f"Tarjeta/Cheque {pyg(snap.get('card_check'))}\nGastos {pyg(snap.get('expenses'))} · Retiros {pyg(snap.get('withdrawals'))}\n\nVer detalle →")
            button = tk.Button(self.cards, text=text, command=lambda unit=card["unit"]: self.show_detail(unit), bg=COLORS["card"], fg=COLORS["text"], activebackground="#E8F1F8", activeforeground=COLORS["navy"], font=("Segoe UI", 11), justify="left", anchor="nw", relief="solid", borderwidth=1, padx=18, pady=15, cursor="hand2")
            button.grid(row=index // columns, column=index % columns, padx=7, pady=7, sticky="nsew"); self.card_buttons[card["unit"]] = button

    def _render_alerts(self, alerts):
        for item in self.alerts.get_children(): self.alerts.delete(item)
        for alert in alerts: self.alerts.insert("", "end", iid=alert.id, values=(alert.unit.label, alert.severity, alert.message))

    def apply_filter(self): return self._guard(self._apply_filter, "aplicar filtro")

    def _apply_filter(self):
        selection = self.filter_var.get(); cards = self._dashboard_data["cards"]
        if selection == "Con alertas": cards = [card for card in cards if card["alerts"]]
        elif selection == "Sin alertas": cards = [card for card in cards if not card["alerts"]]
        self._render_cards(cards); self.status_var.set(f"Filtro «{selection}»: {len(cards)} unidad(es)")

    def refresh(self): return self.show_dashboard(announce=True)

    def show_review(self):
        return self._guard(self._show_review, "abrir revisión de ventas")

    def _show_review(self):
        from .real_sync import ReviewService
        from .review_ui import ReviewPanel
        self.current_screen = "review"
        self._clear_body()
        self.review_panel = ReviewPanel(
            self.body, ReviewService(self.service.repository), self.principal,
            back=self.show_dashboard, notifier=self.notifier, confirmer=self.confirmer,
        )
        self.review_panel.pack(fill="both", expand=True)
        self.status_var.set("Revisión fila por fila · datos de copia local")

    def show_pending(self):
        return self._guard(self._show_pending, "abrir pendientes y bitácora")

    def _show_pending(self):
        from .pending_ui import PendingPanel
        from .real_sync import ReviewService
        self.current_screen = "pending"
        self._clear_body()
        self.pending_panel = PendingPanel(
            self.body, ReviewService(self.service.repository), self.principal,
            back=self.show_dashboard, notifier=self.notifier,
        )
        self.pending_panel.pack(fill="both", expand=True)
        self.status_var.set("Pendientes y bitácora · sólo lectura, nada se envía")

    def show_detail(self, unit): return self._guard(lambda: self._show_detail(unit), f"abrir detalle de {unit.label}")

    def _show_detail(self, unit):
        data = self.service.dashboard(self.principal)
        card = next(item for item in data["cards"] if item["unit"] == unit)
        snap = card["snapshot"] or {}
        self.current_screen, self.selected_unit = "detail", unit
        self._clear_body()

        # Cabecera horizontal: todos los datos de orientación quedan siempre visibles.
        business, _, branch = unit.label.partition(" ")
        header = tk.Frame(self.body, bg=COLORS["card"], height=66, highlightthickness=1, highlightbackground="#D7E0E8")
        header.pack(fill="x", padx=18, pady=(14, 8)); header.pack_propagate(False)
        self.back_button = tk.Button(header, text="← Volver al panel", command=self.show_dashboard, bg=COLORS["navy"], fg="white", relief="flat", padx=14, pady=7)
        self.back_button.pack(side="left", padx=(12, 14), pady=12)
        tk.Label(header, text=business, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(header, text=f"Sucursal: {branch}", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 11)).pack(side="left", padx=12)
        sync_at = snap.get("source_updated_at", "—")
        if sync_at != "—": sync_at = sync_at.replace("T", " ")[:19]
        for label, value in (("Caja", snap.get("status", "SIN DATOS")), ("Fecha", snap.get("business_date", "—")), ("Última sincronización", sync_at)):
            block = tk.Frame(header, bg=COLORS["card"]); block.pack(side="left", padx=13)
            tk.Label(block, text=label.upper(), bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(block, text=value, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.detail_refresh_button = tk.Button(header, text="Actualizar", command=lambda: self._refresh_detail(unit), bg=COLORS["blue"], fg="white", relief="flat", padx=16, pady=7)
        self.detail_refresh_button.pack(side="right", padx=12, pady=12)

        counted = snap.get("counted_cash")
        difference = None if counted is None else counted - int(snap.get("expected_cash") or 0)
        metrics = [("VENTAS", pyg(snap.get("income"))), ("EFECTIVO", pyg(snap.get("cash"))),
                   ("TARJ./CHEQUE", pyg(snap.get("card_check"))), ("GASTOS", pyg(snap.get("expenses"))),
                   ("RETIROS", pyg(snap.get("withdrawals"))), ("DIF. ARQUEO", "Pendiente" if difference is None else pyg(difference)),
                   ("ALERTAS", str(card["alerts"]))]
        kpis = tk.Frame(self.body, bg=COLORS["surface"]); kpis.pack(fill="x", padx=12, pady=(0, 8))
        self.detail_kpis = {}
        for column, (label, value) in enumerate(metrics):
            kpis.grid_columnconfigure(column, weight=1, uniform="detail-kpi")
            tile = tk.Frame(kpis, bg=COLORS["card"], height=104, highlightthickness=1, highlightbackground="#D7E0E8")
            tile.grid(row=0, column=column, padx=4, sticky="nsew"); tile.grid_propagate(False)
            tk.Label(tile, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(14, 3))
            value_label = tk.Label(tile, text=value, bg=COLORS["card"], fg=COLORS["navy"], font=("Segoe UI", 15, "bold"))
            value_label.pack(anchor="w", padx=12); self.detail_kpis[label] = value_label

        # Zona central en lectura izquierda→derecha: economía amplia + estado/alertas.
        horizontal = max(self.root.winfo_width(), 1180) >= 1400
        panes = tk.PanedWindow(self.body, orient=tk.HORIZONTAL if horizontal else tk.VERTICAL, bg=COLORS["surface"], sashwidth=7, relief="flat")
        panes.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        economy = tk.LabelFrame(panes, text="  Movimientos / detalle económico  ", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        side = tk.LabelFrame(panes, text="  Alertas y sincronización  ", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 11, "bold"), padx=10, pady=10)
        panes.add(economy, minsize=700, stretch="always"); panes.add(side, minsize=330, stretch="never")
        self.economics_tree = ttk.Treeview(economy, columns=("concept", "amount", "reference", "status"), show="headings", height=9)
        for key, label, width, anchor in (("concept", "Concepto", 220, "w"), ("amount", "Monto", 180, "e"), ("reference", "Referencia", 190, "w"), ("status", "Estado", 120, "center")):
            self.economics_tree.heading(key, text=label); self.economics_tree.column(key, width=width, anchor=anchor)
        economic_rows = [("Ventas", snap.get("income"), f"{snap.get('entry_count', 0)} movimientos", snap.get("status", "—")),
                         ("Efectivo", snap.get("cash"), "Cobros", "Registrado"), ("Tarjeta/Cheque", snap.get("card_check"), "Cobros", "Registrado"),
                         ("Gastos", snap.get("expenses"), "Egresos", "Registrado"), ("Retiros", snap.get("withdrawals"), "Egresos", "Registrado"),
                         ("Efectivo esperado", snap.get("expected_cash"), "Arqueo", "Pendiente" if counted is None else "Contado")]
        for row in economic_rows: self.economics_tree.insert("", "end", values=(row[0], pyg(row[1]), row[2], row[3]))
        self.economics_tree.pack(fill="both", expand=True)
        sync_color = COLORS["ok"] if card["sync"] == "AL DÍA" else COLORS["critical"]
        tk.Label(side, text=card["sync"], bg=COLORS["card"], fg=sync_color, font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=6, pady=(4, 2))
        tk.Label(side, text=f"Último dato: {sync_at}", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=6, pady=(0, 10))
        self.detail_alerts = ttk.Treeview(side, columns=("level", "message"), show="headings", height=7)
        self.detail_alerts.heading("level", text="Nivel"); self.detail_alerts.column("level", width=75, anchor="center")
        self.detail_alerts.heading("message", text="Alerta"); self.detail_alerts.column("message", width=280, anchor="w")
        unit_alerts = [alert for alert in data["alerts"] if alert.unit == unit]
        for alert in unit_alerts: self.detail_alerts.insert("", "end", values=(alert.severity, alert.message))
        self.detail_alerts.pack(fill="both", expand=True)
        if not unit_alerts: tk.Label(side, text="Sin alertas activas", bg=COLORS["card"], fg=COLORS["ok"]).pack(anchor="w", padx=6, pady=6)
        self.status_var.set(f"Detalle abierto: {unit.label}")

    def _refresh_detail(self, unit):
        result = self.show_detail(unit)
        self.status_var.set(f"Detalle actualizado {datetime.now().strftime('%H:%M:%S')} · {unit.label}")
        return result

    def _alert_selected(self, _event=None):
        selected = self.alerts.selection()
        if selected:
            values = self.alerts.item(selected[0], "values"); self.status_var.set(f"Alerta seleccionada: {values[0]} · {values[1]}")

    def acknowledge(self): return self._guard(self._acknowledge, "reconocer alerta")

    def _acknowledge(self):
        selected = self.alerts.selection()
        if not selected:
            self.status_var.set("Seleccione una alerta antes de reconocerla"); self.notifier("Alertas", "Seleccione una alerta activa."); return False
        alert_id = selected[0]; self.service.acknowledge_alert(self.principal, alert_id)
        self._dashboard_data = self.service.dashboard(self.principal); self._render_alerts(self._dashboard_data["alerts"])
        self.status_var.set("Alerta reconocida y registrada en el historial auditado"); return True

    def run(self): self.root.mainloop()
