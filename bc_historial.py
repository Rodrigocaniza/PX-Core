"""Aplicación visual independiente BC Historial."""
from __future__ import annotations
import argparse
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from modulos.caja_diaria.config import resolve_data_paths
from modulos.historial_externo.history import HistoryQuery
from modulos.historial_externo.sqlite_reader import SQLiteHistoryReader
from modulos.historial_externo.launcher import HistorialNoDisponible
from modulos.historial_externo.global_history import (
    GlobalHistoryService, HistoryAccessDenied, HistoryPrincipal,
    ROLE_ADMIN, ROLE_FEDERATED_VIEWER, ROLE_OPERATOR, VIEW_GLOBAL, VIEW_LOCAL,
)

def _money(value) -> str:
    return "—" if value is None else f"{int(value):,}".replace(",", ".")

def build_parser():
    parser = argparse.ArgumentParser(description="BC Historial (solo lectura)")
    for flag in ("ci", "ruc", "name", "phone", "envelope", "database"):
        parser.add_argument("--" + flag, default="")
    return parser

class HistoryWindow(tk.Toplevel):
    def __init__(self, master, service, principal, initial):
        super().__init__(master); self.service = service; self.principal = principal; self.events = []
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
        try: result = self.service.search(self.principal, query)
        except (OSError, sqlite3.Error, HistoryAccessDenied, ValueError) as error:
            messagebox.showerror("No se pudo consultar", str(error), parent=self); return
        history = result.selected
        if history is None:
            self.events = []; self.grid.delete(*self.grid.get_children())
            self.person.configure(text=(
                f"{len(result.candidates)} coincidencias separadas · "
                "Refina con CI/RUC; no se fusionan por nombre o teléfono"))
            return
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
    raise SystemExit(
        "BC Historial global requiere una sesión autenticada de BC Caja. "
        "No acepta roles ni permisos por línea de comandos.")


def open_for_verified_session(master, database, session, initial, *, verify_session):
    """Abre Historial con una ``CashSession`` ya revalidada por Caja.

    No recibe strings de rol por CLI/entorno. El llamador obtiene ``session``
    de ``AdminOperations.require_operator`` inmediatamente antes de entrar.
    """
    if session is None or not hasattr(session, "token") or not str(session.token or "").strip():
        raise HistorialNoDisponible("BC Historial requiere una sesión verificada de Caja")
    if not callable(verify_session):
        raise HistorialNoDisponible("BC Historial no recibió un verificador de sesión")
    try:
        verified = verify_session(str(session.token))
    except Exception as error:
        raise HistorialNoDisponible("La sesión de Caja no es válida. Volvé a iniciar sesión.") from error
    required = ("user_id", "role", "branch", "token")
    if verified is None or any(not hasattr(verified, name) for name in required):
        raise HistorialNoDisponible("El verificador no devolvió una sesión válida")
    if not str(verified.user_id or "").strip() or not str(verified.token or "").strip():
        raise HistorialNoDisponible("La sesión de Caja no es válida. Volvé a iniciar sesión.")
    role = str(verified.role).upper()
    permissions_by_role = {
        ROLE_OPERATOR: frozenset({VIEW_LOCAL}),
        ROLE_ADMIN: frozenset({VIEW_GLOBAL}),
        ROLE_FEDERATED_VIEWER: frozenset({VIEW_GLOBAL}),
    }
    if role not in permissions_by_role:
        raise HistorialNoDisponible("Tu rol no tiene acceso habilitado a BC Historial.")
    principal = HistoryPrincipal(
        str(verified.user_id), role, str(verified.branch),
        permissions_by_role.get(role, frozenset()), authenticated=True)
    service = GlobalHistoryService([SQLiteHistoryReader(database)])
    return HistoryWindow(master, service, principal, initial)

if __name__ == "__main__": raise SystemExit(main())
