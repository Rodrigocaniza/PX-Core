from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


COLORS = {
    "navy": "#10253F", "blue": "#1769AA", "surface": "#F4F7FA",
    "card": "#FFFFFF", "text": "#17212B", "muted": "#617181",
    "ok": "#16855B", "warning": "#C27803", "critical": "#BD2C38",
}


def pyg(value):
    return f"{int(value or 0):,}".replace(",", ".") + " Gs."


class CentralPilotWindow:
    """Responsive Tk console, optimized for a 24-inch 1920x1080 monitor."""

    def __init__(self, service):
        self.service = service
        self.principal = service.authenticate("admin.piloto", "Piloto-Temporal-2026")
        self.root = tk.Tk()
        self.root.title("BC Gestión Central · Piloto aislado")
        self.root.geometry("1600x900")
        self.root.minsize(1180, 680)
        self.root.configure(bg=COLORS["surface"])
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.cards = tk.Frame(self.root, bg=COLORS["surface"])
        self.alerts = ttk.Treeview(self.root, columns=("unidad", "nivel", "mensaje"), show="headings", height=7)
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self.root, bg=COLORS["navy"], height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="BC GESTIÓN CENTRAL", bg=COLORS["navy"], fg="white", font=("Segoe UI", 21, "bold")).pack(side="left", padx=28)
        tk.Label(header, text="PILOTO · DATOS SINTÉTICOS · PRODUCCIÓN DESHABILITADA", bg="#7D2935", fg="white", font=("Segoe UI", 10, "bold"), padx=14, pady=8).pack(side="right", padx=28)
        toolbar = tk.Frame(self.root, bg=COLORS["surface"])
        toolbar.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(toolbar, text="Estado de las cuatro unidades", bg=COLORS["surface"], fg=COLORS["text"], font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Button(toolbar, text="Actualizar", command=self.refresh, bg=COLORS["blue"], fg="white", relief="flat", padx=18, pady=7).pack(side="right")
        self.cards.pack(fill="both", expand=True, padx=18)
        section = tk.Frame(self.root, bg=COLORS["surface"])
        section.pack(fill="x", padx=24, pady=(8, 4))
        tk.Label(section, text="Alertas activas", bg=COLORS["surface"], fg=COLORS["text"], font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Button(section, text="Reconocer seleccionada", command=self.acknowledge, relief="groove", padx=12).pack(side="right")
        for column, label, width in (("unidad", "Unidad", 220), ("nivel", "Nivel", 100), ("mensaje", "Detalle", 700)):
            self.alerts.heading(column, text=label)
            self.alerts.column(column, width=width, anchor="w")
        self.alerts.pack(fill="x", padx=24, pady=(0, 18))

    def refresh(self):
        self.service.refresh_alerts(self.principal)
        data = self.service.dashboard(self.principal)
        for child in self.cards.winfo_children():
            child.destroy()
        width = max(self.root.winfo_width(), 1180)
        columns = 4 if width >= 1500 else 2
        for column in range(columns):
            self.cards.grid_columnconfigure(column, weight=1, uniform="cards")
        for index, card in enumerate(data["cards"]):
            panel = tk.Frame(self.cards, bg=COLORS["card"], highlightthickness=1, highlightbackground="#D7E0E8", padx=18, pady=15)
            panel.grid(row=index // columns, column=index % columns, padx=7, pady=7, sticky="nsew")
            snap = card["snapshot"] or {}
            sync_color = COLORS["ok"] if card["sync"] == "AL DÍA" else COLORS["critical"]
            tk.Label(panel, text=card["label"], bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 14, "bold")).pack(anchor="w")
            tk.Label(panel, text=f"● {card['sync']}  ·  {card['alerts']} alerta(s)", bg=COLORS["card"], fg=sync_color, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 13))
            tk.Label(panel, text=pyg(snap.get("income")), bg=COLORS["card"], fg=COLORS["navy"], font=("Segoe UI", 22, "bold")).pack(anchor="w")
            tk.Label(panel, text=f"Ingresos · {snap.get('entry_count', 0)} movimientos", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 10)).pack(anchor="w")
            tk.Label(panel, text=f"Efectivo {pyg(snap.get('cash'))}   Tarjeta/Cheque {pyg(snap.get('card_check'))}", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10)).pack(anchor="w", pady=(12, 0))
            tk.Label(panel, text=f"Gastos {pyg(snap.get('expenses'))}   Retiros {pyg(snap.get('withdrawals'))}", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10)).pack(anchor="w")
        for item in self.alerts.get_children():
            self.alerts.delete(item)
        for alert in data["alerts"]:
            self.alerts.insert("", "end", iid=alert.id, values=(alert.unit.label, alert.severity, alert.message))

    def acknowledge(self):
        selected = self.alerts.selection()
        if not selected:
            messagebox.showinfo("Alertas", "Seleccione una alerta activa.")
            return
        self.service.acknowledge_alert(self.principal, selected[0])
        self.refresh()

    def run(self):
        self.root.mainloop()
