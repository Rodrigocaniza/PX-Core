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

    def __init__(self, service, *, root=None, notifier=None, logger=None):
        self.service = service
        self.principal = service.authenticate("admin.piloto", "Piloto-Temporal-2026")
        self.root = root or tk.Tk()
        self.notifier = notifier or messagebox.showinfo
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

    def show_detail(self, unit): return self._guard(lambda: self._show_detail(unit), f"abrir detalle de {unit.label}")

    def _show_detail(self, unit):
        data = self.service.dashboard(self.principal); card = next(item for item in data["cards"] if item["unit"] == unit); snap = card["snapshot"] or {}
        self.current_screen, self.selected_unit = "detail", unit; self._clear_body()
        bar = tk.Frame(self.body, bg=COLORS["surface"]); bar.pack(fill="x", padx=24, pady=18)
        self.back_button = tk.Button(bar, text="← Volver al panel", command=self.show_dashboard, bg=COLORS["navy"], fg="white", relief="flat", padx=16, pady=8); self.back_button.pack(side="left")
        tk.Label(bar, text=unit.label, bg=COLORS["surface"], fg=COLORS["text"], font=("Segoe UI", 20, "bold")).pack(side="left", padx=20)
        detail = tk.Frame(self.body, bg=COLORS["card"], padx=28, pady=24, highlightthickness=1, highlightbackground="#D7E0E8"); detail.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        rows = [("Estado de sincronización", card["sync"]), ("Estado de caja", snap.get("status", "SIN DATOS")), ("Fecha operativa", snap.get("business_date", "—")), ("Ingresos", pyg(snap.get("income"))), ("Efectivo", pyg(snap.get("cash"))), ("Tarjeta/Cheque", pyg(snap.get("card_check"))), ("Gastos", pyg(snap.get("expenses"))), ("Retiros", pyg(snap.get("withdrawals"))), ("Efectivo esperado", pyg(snap.get("expected_cash"))), ("Movimientos", str(snap.get("entry_count", 0))), ("Alertas activas", str(card["alerts"]))]
        for row, (label, value) in enumerate(rows):
            tk.Label(detail, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 11)).grid(row=row, column=0, sticky="w", padx=(0, 40), pady=7)
            tk.Label(detail, text=value, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 12, "bold")).grid(row=row, column=1, sticky="w", pady=7)
        self.status_var.set(f"Detalle abierto: {unit.label}")

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
