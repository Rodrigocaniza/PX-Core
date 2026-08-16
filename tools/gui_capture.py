"""Captura segura de la ventana de BC Caja para evidencia versionada.

Regla operativa vigente: una captura que se commitea solo puede contener la
aplicacion. Recortar una region de pantalla no lo garantiza —la ventana puede
no cubrirla, quedar detras de otra aplicacion o desplazarse por el escalado
DPI— y asi entraron franjas de escritorio en evidencias anteriores.

`PrintWindow` pide a la propia ventana que se dibuje en un contexto en
memoria. No lee el framebuffer, de modo que por construccion no puede capturar
otra aplicacion, ni siquiera si la ventana esta tapada o en segundo plano.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

from PIL import Image

PW_RENDERFULLCONTENT = 2


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def capturar_ventana(ventana, destino: str | Path) -> Path:
    """Guarda la ventana Tk indicada. Falla cerrado si no puede dibujarse."""
    ventana.update_idletasks()
    ventana.update()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    hwnd = int(ventana.winfo_id())
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    # winfo_id devuelve el hijo; PrintWindow necesita la ventana de nivel
    # superior para incluir marco y contenido completo.
    raiz = user32.GetAncestor(hwnd, 2) or hwnd

    rect = wintypes.RECT()
    user32.GetWindowRect(raiz, ctypes.byref(rect))
    ancho, alto = rect.right - rect.left, rect.bottom - rect.top
    if ancho <= 0 or alto <= 0:
        raise RuntimeError(f"la ventana no tiene area visible: {ancho}x{alto}")

    hdc = user32.GetWindowDC(raiz)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, ancho, alto)
    gdi32.SelectObject(mdc, bitmap)
    try:
        if not user32.PrintWindow(raiz, mdc, PW_RENDERFULLCONTENT):
            raise RuntimeError("PrintWindow no pudo dibujar la ventana")
        cabecera = _BITMAPINFOHEADER(
            ctypes.sizeof(_BITMAPINFOHEADER), ancho, -alto, 1, 32, 0, 0, 0, 0, 0, 0,
        )
        buffer = ctypes.create_string_buffer(ancho * alto * 4)
        gdi32.GetDIBits(mdc, bitmap, 0, alto, buffer, ctypes.byref(cabecera), 0)
        Image.frombuffer("RGB", (ancho, alto), buffer, "raw", "BGRX", 0, 1).save(destino)
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(raiz, hdc)
    return destino
