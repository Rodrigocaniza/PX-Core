"""Bandeja unificada compacta para pantallas de 1366x768."""

from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from ..domain.inbox import ConversationFilter, ConversationStatus
from .theme import (
    COLOR_AMBAR, COLOR_FONDO, COLOR_PANEL, COLOR_PANEL_SECUNDARIO, COLOR_PRIMARIO,
    COLOR_TEXTO, COLOR_TEXTO_SUAVE, COLOR_VERDE,
)

STATUS_COLORS = {
    ConversationStatus.NUEVO: COLOR_PRIMARIO,
    ConversationStatus.EN_CURSO: COLOR_AMBAR,
    ConversationStatus.RESUELTO: COLOR_VERDE,
}


class InboxWindow(ctk.CTkToplevel):
    def __init__(self, parent, service, operator_getter) -> None:
        super().__init__(parent)
        self.service, self.operator_getter = service, operator_getter
        self.current = None
        self.title("BC Comunicaciones — Bandeja unificada")
        self.geometry("1366x768")
        self.minsize(1100, 650)
        self.configure(fg_color=COLOR_FONDO)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=2)
        self.grid_rowconfigure(2, weight=1)
        self._header()
        self._filters()
        self._list()
        self._conversation()
        self.refresh()

    def _header(self):
        bar = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0, height=64)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="BANDEJA UNIFICADA", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0,column=0,padx=18,pady=16)
        self.counts_label = ctk.CTkLabel(bar, text="", text_color=COLOR_TEXTO_SUAVE)
        self.counts_label.grid(row=0,column=1,sticky="e",padx=18)

    def _filters(self):
        panel = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0, width=250)
        panel.grid(row=1,column=0,rowspan=2,sticky="nsew")
        panel.grid_propagate(False)
        ctk.CTkLabel(panel,text="FILTROS",font=ctk.CTkFont(weight="bold")).pack(anchor="w",padx=16,pady=(18,6))
        self.text = ctk.CTkEntry(panel, placeholder_text="Cliente o mensaje")
        self.text.pack(fill="x",padx=14,pady=5)
        self.text.bind("<KeyRelease>", lambda _e: self.refresh())
        ctk.CTkLabel(panel,text="Negocio",text_color=COLOR_TEXTO_SUAVE,anchor="w").pack(fill="x",padx=14,pady=(8,0))
        self.business = ctk.CTkComboBox(panel, values=["Todos"], command=lambda _v:self.refresh())
        self.business.pack(fill="x",padx=14,pady=5)
        ctk.CTkLabel(panel,text="Sucursal",text_color=COLOR_TEXTO_SUAVE,anchor="w").pack(fill="x",padx=14,pady=(8,0))
        self.branch = ctk.CTkComboBox(panel, values=["Todas"], command=lambda _v:self.refresh())
        self.branch.pack(fill="x",padx=14,pady=5)
        ctk.CTkLabel(panel,text="Estado",text_color=COLOR_TEXTO_SUAVE,anchor="w").pack(fill="x",padx=14,pady=(8,0))
        self.status = ctk.CTkComboBox(panel, values=["TODOS"]+[s.value for s in ConversationStatus], command=lambda _v:self.refresh())
        self.status.pack(fill="x",padx=14,pady=5)
        self.status.set("TODOS")
        self.accounts = self.service.repository.list_accounts()
        self.business.configure(values=["Todos"]+sorted({a.business for a in self.accounts}))
        self.branch.configure(values=["Todas"]+sorted({a.branch for a in self.accounts}))
        self.business.set("Todos"); self.branch.set("Todas")
        ctk.CTkButton(panel,text="Cargar datos DEMO",command=self.load_demo).pack(fill="x",padx=14,pady=(18,5))
        ctk.CTkLabel(panel,text="Datos demo/proveedor simulado",text_color=COLOR_TEXTO_SUAVE,font=ctk.CTkFont(size=11)).pack(side="bottom",padx=14,pady=18)

    def _list(self):
        frame=ctk.CTkFrame(self,fg_color=COLOR_FONDO,corner_radius=0,width=390)
        frame.grid(row=1,column=1,rowspan=2,sticky="nsew",padx=(10,5),pady=10)
        frame.grid_rowconfigure(1,weight=1); frame.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(frame,text="CONVERSACIONES",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,sticky="w",pady=(2,8))
        self.items=ctk.CTkScrollableFrame(frame,fg_color=COLOR_PANEL)
        self.items.grid(row=1,column=0,sticky="nsew"); self.items.grid_columnconfigure(0,weight=1)

    def _conversation(self):
        frame=ctk.CTkFrame(self,fg_color=COLOR_PANEL,corner_radius=0)
        frame.grid(row=1,column=2,rowspan=2,sticky="nsew",padx=(5,10),pady=10)
        frame.grid_rowconfigure(2,weight=1); frame.grid_columnconfigure(0,weight=1)
        self.title_label=ctk.CTkLabel(frame,text="Elegí una conversación",font=ctk.CTkFont(size=18,weight="bold"),anchor="w")
        self.title_label.grid(row=0,column=0,sticky="ew",padx=18,pady=(16,5))
        actions=ctk.CTkFrame(frame,fg_color="transparent"); actions.grid(row=1,column=0,sticky="ew",padx=14)
        self.operator=ctk.CTkEntry(actions,placeholder_text="Operador",width=150); self.operator.pack(side="left",padx=4)
        ctk.CTkButton(actions,text="Asignar",width=75,command=self.assign).pack(side="left",padx=3)
        for label,status in (("Nuevo",ConversationStatus.NUEVO),("En curso",ConversationStatus.EN_CURSO),("Resolver",ConversationStatus.RESUELTO)):
            ctk.CTkButton(actions,text=label,width=85,command=lambda s=status:self.change_status(s)).pack(side="left",padx=3)
        self.messages=ctk.CTkTextbox(frame,wrap="word",state="disabled")
        self.messages.grid(row=2,column=0,sticky="nsew",padx=18,pady=12)
        reply=ctk.CTkFrame(frame,fg_color="transparent"); reply.grid(row=3,column=0,sticky="ew",padx=14,pady=(0,16)); reply.grid_columnconfigure(0,weight=1)
        self.reply=ctk.CTkEntry(reply,placeholder_text="Escribí una respuesta…")
        self.reply.grid(row=0,column=0,sticky="ew",padx=4)
        self.reply.bind("<Return>",lambda _e:self.send())
        ctk.CTkButton(reply,text="Enviar (simulado)",fg_color=COLOR_VERDE,command=self.send).grid(row=0,column=1,padx=4)

    def refresh(self):
        status=None if self.status.get()=="TODOS" else ConversationStatus(self.status.get())
        filters=ConversationFilter(business="" if self.business.get()=="Todos" else self.business.get(),branch="" if self.branch.get()=="Todas" else self.branch.get(),status=status,text=self.text.get())
        conversations=self.service.search(filters)
        for child in self.items.winfo_children(): child.destroy()
        for conv in conversations:
            ctk.CTkButton(
                self.items, text=f"{conv.contact_name}\n{conv.status.value} · {conv.subject}",
                anchor="w", height=58, fg_color=STATUS_COLORS[conv.status],
                hover_color=COLOR_PANEL_SECUNDARIO[1], command=lambda c=conv:self.open(c),
            ).grid(sticky="ew",padx=5,pady=4)
        counts=self.service.repository.counts()
        self.counts_label.configure(text="  ·  ".join(f"{s.value}: {counts[s]}" for s in ConversationStatus))

    def open(self, conversation):
        self.current=conversation
        self.title_label.configure(text=f"{conversation.contact_name} — {conversation.subject or 'Sin asunto'}")
        self.operator.delete(0,"end"); self.operator.insert(0,conversation.assigned_operator or self.operator_getter())
        lines=[]
        for msg in self.service.repository.list_messages(conversation.id):
            who=msg.operator or conversation.contact_name
            lines.append(f"{msg.occurred_at:%d/%m %H:%M} · {who}\n{msg.body}\n")
        self.messages.configure(state="normal"); self.messages.delete("1.0","end"); self.messages.insert("1.0","\n".join(lines)); self.messages.configure(state="disabled")

    def send(self):
        if not self.current: return
        try:
            self.service.reply(self.current.id,self.reply.get(),self.operator.get())
            self.reply.delete(0,"end"); self.open(self.service.repository.get_conversation(self.current.id)); self.refresh()
        except Exception as error: messagebox.showerror("No se pudo enviar",str(error),parent=self)

    def change_status(self,status):
        if not self.current: return
        try:
            actor=self.operator.get().strip() or self.operator_getter() or "SISTEMA"
            self.current=self.service.transition(self.current.id,status,actor); self.refresh(); self.open(self.current)
        except Exception as error: messagebox.showerror("Estado no actualizado",str(error),parent=self)

    def assign(self):
        if not self.current: return
        try:
            actor=self.operator.get().strip() or self.operator_getter() or "SISTEMA"
            self.current=self.service.assign(self.current.id,self.operator.get(),actor); self.refresh(); self.open(self.current)
        except Exception as error: messagebox.showerror("Asignación no actualizada",str(error),parent=self)

    def load_demo(self):
        self.service.seed_demo()
        self.accounts=self.service.repository.list_accounts()
        self.business.configure(values=["Todos"]+sorted({a.business for a in self.accounts}))
        self.branch.configure(values=["Todas"]+sorted({a.branch for a in self.accounts}))
        self.refresh()
