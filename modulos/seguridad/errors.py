"""Errores de la capa de seguridad.

Ninguno lleva material criptografico en su mensaje: estos textos terminan en
logs y en pantallas de soporte.
"""

from __future__ import annotations


class SecurityError(Exception):
    """Raiz de la capa. Permite un `except` unico en los bordes."""


class PlatformUnsupportedError(SecurityError):
    """El sistema operativo no ofrece el sellado local requerido."""


class SealedStoreError(SecurityError):
    """El material sellado localmente no pudo abrirse en este contexto."""


class NotEnrolledError(SecurityError):
    """La instalacion todavia no fue enrolada."""


class AlreadyEnrolledError(SecurityError):
    """Ya existe una identidad de instalacion; re-enrolar es una decision explicita."""


class LicenseFormatError(SecurityError):
    """El documento de licencia no tiene la forma esperada."""


class SignatureError(SecurityError):
    """La firma no verifica contra ninguna clave de confianza."""


class TrustStoreError(SecurityError):
    """El almacen de claves publicas de confianza falta o es invalido."""


class KeyringError(SecurityError):
    """La clave de datos no pudo obtenerse ni con la instalacion ni con recuperacion."""


class DataProtectionError(SecurityError):
    """Un valor protegido no pudo abrirse: cifrado ajeno, truncado o manipulado."""


class ReplayError(SecurityError):
    """Una credencial de sincronizacion se presento dos veces."""
