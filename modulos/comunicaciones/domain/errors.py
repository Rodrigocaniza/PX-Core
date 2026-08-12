"""Errores de dominio de BC Comunicaciones.

Todos derivan de `CommunicationsError` para que la UI pueda traducirlos a
mensajes comprensibles sin capturar `Exception`.
"""

from __future__ import annotations

from typing import Sequence


class CommunicationsError(Exception):
    """Raíz de todos los errores previstos del módulo."""


class InvalidTemplateError(CommunicationsError):
    """La plantilla no cumple sus reglas mínimas (título, cuerpo, categoría)."""


class TemplateNotFoundError(CommunicationsError):
    """Se pidió una plantilla que no existe."""


class DuplicateTemplateError(CommunicationsError):
    """Ya existe otra plantilla con el mismo título dentro de la categoría."""


class CategoryNotFoundError(CommunicationsError):
    """Se referenció una categoría inexistente o desactivada."""


class TemplateInactiveError(CommunicationsError):
    """Se intentó preparar un mensaje con una plantilla desactivada."""


class MissingVariablesError(CommunicationsError):
    """Faltan valores obligatorios para completar el mensaje."""

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = tuple(missing)
        legible = ", ".join(self.missing)
        super().__init__(f"Faltan completar estos datos: {legible}")


class BackupError(CommunicationsError):
    """No se pudo crear la copia de seguridad."""


class RestoreError(CommunicationsError):
    """El archivo indicado no es una copia de seguridad válida de BC Comunicaciones."""
