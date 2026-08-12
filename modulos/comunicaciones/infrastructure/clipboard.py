"""Adaptadores de portapapeles.

`TkClipboard` es el real. `InMemoryClipboard` permite probar el flujo completo de
copiado sin abrir una ventana.
"""

from __future__ import annotations


class InMemoryClipboard:
    def __init__(self) -> None:
        self.text: str = ""
        self.copies: int = 0

    def copy(self, text: str) -> None:
        self.text = str(text)
        self.copies += 1


class TkClipboard:
    """Portapapeles de Tk.

    `update()` es necesario en Windows para que el contenido sobreviva al cierre
    de la aplicación.
    """

    def __init__(self, widget) -> None:
        self.widget = widget

    def copy(self, text: str) -> None:
        self.widget.clipboard_clear()
        self.widget.clipboard_append(str(text))
        self.widget.update()
