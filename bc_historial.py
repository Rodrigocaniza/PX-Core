"""Aplicación visual independiente BC Historial."""
from __future__ import annotations
import argparse
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from modulos.caja_diaria.config import resolve_data_paths
from modulos.historial_externo.history import HistoryQuery
from modulos.historial_externo.sqlite_reader import SQLiteHistoryReader

def _money(value) -> str:
    return "—" if value is None else f"{int(value):,}".replace(",", ".")

def build_parser():
    parser = argparse.ArgumentParser(description="BC Historial (solo lectura)")
    for flag in ("ci", "ruc", "name", "phone", "envelope", "database"):
        parser.add_argument("--" + flag, default="")
    return parser

class HistoryWindow(tk.Tk):
    def __init__(self, reader, initial):
        super().__init__(); self.reader = reader; self.events = []
        self.title("BC Historial · consulta de clientes"); self.geometry("1180x720"); self.minsize(900, 560)
        search = ttk.LabelFrame(self, text="Buscar por cualquier dato"); search.pack(fill="x", padx=12, pady=10)
        self.fields = {}
        for column, (key, label, value) in enumerate((("document", "CI / RUC", initial.document),
                ("name", "Nombre", initial.name), ("phone", "Teléfono", initial.phone),
                ("envelope", "Sobre / trabajo", initial.envelope))):
            ttk.Label(search, text=label).grid(row=0, column=column, sticky="w", padx=6)
            entry = ttk.Entry(search, width=24); entry.insert(0, value)
            entry.grid(row=1, column=column, sticky="ew", padx=6, pady=(0, 8)); search.columnconfigure(column, weight=1)
            entry.bind("<Return>", lambda _event: self.refresh()); self.fields[key] = entry
        ttk.Button(search, text="Buscar", command=self.refresh).grid(row=1, column=4, padx=8)
        self.person = ttk.Label(self, font=("Segoe UI", 12, "bold")); self.person.pack(fill="x", padx=16, pady=(0, 8))
        columns = ("fecha", "tipo", "sucursal", "sobre", "estado", "importe", "detalle")
        self.grid = ttk.Treeview(self, columns=columns, show="headings", height=15)
        for key, label, width in (("fecha", "Fecha", 145), ("tipo", "Movimiento", 85), ("sucursal", "Sucursal", 100),
                                  ("sobre", "Sobre", 95), ("estado", "Estado", 90), ("importe", "Importe", 90),
                                  ("detalle", "Trabajo / cristales", 390)):
            self.grid.heading(key, text=label); self.grid.column(key, width=width, anchor="w")
        self.grid.pack(fill="both", expand=True, padx=12); self.grid.bind("<<TreeviewSelect>>", self.show_detail)
        self.detail = tk.Text(self, height=10, wrap="word", state="disabled"); self.detail.pack(fill="x", padx=12, pady=10)
        if initial.has_terms: self.after_idle(self.refresh)

    def refresh(self):
        query = HistoryQuery(**{key: entry.get() for key, entry in self.fields.items()})
        try: history = self.reader.search(query)
        except (OSError, sqlite3.Error) as error:
            messagebox.showerror("No se pudo consultar", str(error), parent=self); return
        self.events = list(history.events); self.grid.delete(*self.grid.get_children())
        self.person.configure(text=f"{history.display_name or 'Sin coincidencias'}   ·   Documentos: {', '.join(history.documents) or '—'}   ·   Teléfonos: {', '.join(history.phones) or '—'}")
        for index, event in enumerate(self.events):
            self.grid.insert("", "end", iid=str(index), values=(event.occurred_at, event.kind, event.branch,
                             event.envelope, event.status, _money(event.total), event.description))

    def show_detail(self, _event=None):
        selected = self.grid.selection()
        if not selected: return
        event = self.events[int(selected[0])]
        lines = [f"Vendedora / responsable: {event.seller or '—'}", f"Pagos: efectivo {_money(event.cash)} · tarjeta/cheque {_money(event.card_check)} · convenio {_money(event.agreement)} · saldo {event.balance or '—'}"]
        if event.items: lines.append("Ítems / cristales: " + " | ".join(event.items))
        if event.prescription: lines.append("Profesional de receta: " + " | ".join(event.prescription))
        if event.observations: lines.append("Observaciones: " + event.observations)
        if event.trace: lines.append("Trazabilidad:\n- " + "\n- ".join(event.trace))
        self.detail.configure(state="normal"); self.detail.delete("1.0", "end")
        self.detail.insert("1.0", "\n".join(lines)); self.detail.configure(state="disabled")

def main(argv=None):
    args = build_parser().parse_args(argv)
    initial = HistoryQuery(args.ci or args.ruc, args.name, args.phone, args.envelope)
    HistoryWindow(SQLiteHistoryReader(args.database or resolve_data_paths().database), initial).mainloop(); return 0

if __name__ == "__main__": raise SystemExit(main())
