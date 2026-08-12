"""Smoke real y captura reproducible de la bandeja a 1366x768."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import customtkinter as ctk
from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modulos.comunicaciones.bootstrap import build_controller
from modulos.comunicaciones.domain.inbox import ConversationFilter, ConversationStatus
from modulos.comunicaciones.infrastructure.clipboard import InMemoryClipboard
from modulos.comunicaciones.ui.app import abrir_comunicaciones
from modulos.comunicaciones.ui.inbox_app import InboxWindow


def exercise(controller):
    inbox = controller.inbox
    if inbox.seed_demo() not in (0, 3):
        raise RuntimeError("precarga demo inesperada")
    conversations = inbox.search()
    if len(conversations) != 3:
        raise RuntimeError("la bandeja no cargó tres conversaciones demo")
    selected = inbox.search(ConversationFilter(text="lentes"))[0]
    inbox.assign(selected.id, "SOL", "SOL")
    inbox.transition(selected.id, ConversationStatus.EN_CURSO, "SOL")
    inbox.reply(selected.id, "Hola Ana, tus lentes están listos para retirar.", "SOL")
    inbox.transition(selected.id, ConversationStatus.RESUELTO, "SOL")
    return selected.id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bc-inbox-smoke-") as directory:
        database = Path(directory) / "bc_comunicaciones.sqlite3"
        controller = build_controller(database, clipboard=InMemoryClipboard())
        root = ctk.CTk()
        root.withdraw()
        library = abrir_comunicaciones(root, controller)
        library.update()
        library._primer_dibujado()
        library._abrir_bandeja()
        library.update()
        inbox_window = next(w for w in library.winfo_children() if isinstance(w, InboxWindow))
        inbox_window.update()
        selected_id = exercise(controller)
        controller.repository.close()
        inbox_window.destroy()
        library.destroy()

        # Reabrir la base es parte del smoke: la captura usa exclusivamente lo persistido.
        controller = build_controller(database, clipboard=InMemoryClipboard())
        persisted = controller.inbox.repository.get_conversation(selected_id)
        if persisted is None or persisted.status != ConversationStatus.RESUELTO:
            raise RuntimeError("estado no persistido después de reabrir")
        messages = controller.inbox.repository.list_messages(selected_id)
        if not messages or messages[-1].operator != "SOL":
            raise RuntimeError("respuesta simulada no persistida")

        window = InboxWindow(root, controller.inbox, lambda: "SOL")
        window.update()
        window.open(persisted)
        window.deiconify()
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        for _ in range(5):
            window.update_idletasks(); window.update(); time.sleep(0.2)

        width, height = window.winfo_width(), window.winfo_height()
        if (width, height) != (1366, 768):
            raise RuntimeError(f"resolución inesperada: {width}x{height}")
        x, y = window.winfo_rootx(), window.winfo_rooty()
        ImageGrab.grab((x, y, x + width, y + height)).save(args.output)
        window.attributes("-topmost", False)
        controller.repository.close()
        window.destroy(); root.destroy()

    print(f"BC_COMUNICACIONES_INBOX_SMOKE_OK {args.output} {width}x{height} persistence=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
