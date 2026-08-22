"""Huella de la maquina: que hace que esta PC sea esta PC.

Nada de esto es, por si solo, una defensa. Un nombre de equipo se cambia, una
MAC se clona y un serial se falsifica; por eso la mision los descarta como
mecanismo unico y por eso aca no son el mecanismo. La defensa dura es el
sellado del secreto por el sistema operativo (`dpapi.py`), que no depende de
que estos valores sean secretos ni dificiles de escribir.

La huella cumple dos funciones distintas de esa:

1. Entropia secundaria de DPAPI, para que el blob sellado tampoco se abra
   desde un proceso de la misma PC que no sepa reconstruirla.
2. Senal auditable de identidad dentro de la licencia firmada, que detecta el
   caso "la carpeta entera aparecio en otra PC" incluso antes de intentar
   abrir el secreto, y lo deja escrito con nombre propio.

Tolerancia al cambio de hardware: los componentes se dividen en obligatorios y
secundarios. Cambiar un disco no puede dejar a la Optica sin Caja; reinstalar
Windows si es una maquina distinta a estos efectos, y ahi hay re-enrolamiento.

Los valores en crudo no se guardan nunca. Se guarda el hash de cada componente
con el `installation_id` como sal, asi que la licencia no revela el numero de
serie de nadie y dos instalaciones de la misma PC no son correlacionables.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Mapping

from ..crypto.primitives import digest

# Obligatorio: identifica la instalacion de Windows. Cambia al reinstalar el
# sistema operativo, y eso es exactamente cuando queremos re-enrolar.
MANDATORY_COMPONENTS = ("machine_guid",)

# Secundarios: cada uno puede cambiar por mantenimiento legitimo.
SECONDARY_COMPONENTS = ("volume_serial", "windows_install", "computer_name")


@dataclass(frozen=True)
class MachineFingerprint:
    """Componentes en crudo. Vive en memoria; a disco solo van sus hashes."""

    components: Mapping[str, str]

    def available(self) -> tuple[str, ...]:
        return tuple(name for name, value in self.components.items() if value)

    def hashed(self, installation_id: str) -> dict[str, str]:
        """Hash por componente, con el `installation_id` como separador de dominio."""
        return {
            name: digest(
                b"fingerprint-component",
                name.encode("utf-8"),
                installation_id.encode("utf-8"),
                value.encode("utf-8"),
            )
            for name, value in self.components.items()
            if value
        }

    def entropy(self, installation_id: str) -> bytes:
        """Entropia secundaria para DPAPI.

        Usa solo los componentes obligatorios: si entrara un secundario,
        cambiar un disco dejaria el secreto irrecuperable, que es el fallo
        catastrofico que la tolerancia de mas abajo existe para evitar.
        """
        parts: list[bytes] = [b"dpapi-entropy", installation_id.encode("utf-8")]
        for name in MANDATORY_COMPONENTS:
            parts.append(name.encode("utf-8"))
            parts.append(self.components.get(name, "").encode("utf-8"))
        return bytes.fromhex(digest(*parts))


@dataclass(frozen=True)
class BindingMatch:
    """Resultado de comparar la huella de hoy contra la que firmo el emisor."""

    matched: tuple[str, ...]
    mismatched: tuple[str, ...]
    missing: tuple[str, ...]
    mandatory_ok: bool
    secondary_required: int
    secondary_matched: int

    @property
    def ok(self) -> bool:
        return self.mandatory_ok and self.secondary_matched >= self.secondary_required


def compare(
    expected: Mapping[str, str], observed: Mapping[str, str], *, secondary_required: int
) -> BindingMatch:
    """Compara hashes. Nunca ve valores en crudo, ni los necesita."""
    matched: list[str] = []
    mismatched: list[str] = []
    missing: list[str] = []
    for name, expected_hash in expected.items():
        observed_hash = observed.get(name)
        if observed_hash is None:
            missing.append(name)
        elif observed_hash == expected_hash:
            matched.append(name)
        else:
            mismatched.append(name)

    mandatory_ok = all(
        name in matched for name in MANDATORY_COMPONENTS if name in expected
    ) and any(name in expected for name in MANDATORY_COMPONENTS)
    secondary_matched = sum(1 for name in matched if name in SECONDARY_COMPONENTS)
    return BindingMatch(
        matched=tuple(sorted(matched)),
        mismatched=tuple(sorted(mismatched)),
        missing=tuple(sorted(missing)),
        mandatory_ok=mandatory_ok,
        secondary_required=secondary_required,
        secondary_matched=secondary_matched,
    )


def required_secondary(expected: Mapping[str, str]) -> int:
    """Cuantos secundarios tienen que seguir coincidiendo.

    La mitad, redondeando hacia arriba, y al menos uno mientras haya alguno.
    Con tres secundarios eso admite que cambie un disco pero no que cambien
    todos a la vez, que es como se ve una PC distinta.
    """
    total = sum(1 for name in expected if name in SECONDARY_COMPONENTS)
    if total == 0:
        return 0
    return max(1, (total + 1) // 2)


# --------------------------------------------------------------------------
# Recoleccion en Windows
# --------------------------------------------------------------------------
def _registry_value(root: int, path: str, name: str) -> str:
    import winreg

    try:
        # KEY_WOW64_64KEY: un Python de 32 bits veria la vista redirigida y
        # leeria otro MachineGuid, con lo cual la misma PC parecerian dos.
        with winreg.OpenKey(
            root, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ) as key:
            value, _kind = winreg.QueryValueEx(key, name)
            return str(value).strip()
    except OSError:
        return ""


def _system_volume_serial() -> str:
    import ctypes
    import os
    from ctypes import wintypes

    root = os.environ.get("SystemDrive", "C:") + "\\"
    serial = wintypes.DWORD()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), None, 0, ctypes.byref(serial), None, None, None, 0
    )
    return f"{serial.value:08X}" if ok else ""


def collect() -> MachineFingerprint:
    """Huella de la maquina actual. Un componente que no se pueda leer queda vacio."""
    if sys.platform != "win32":
        raise NotImplementedError("la recoleccion de huella de BC Seguridad V1 es de Windows")
    import winreg

    machine_guid = _registry_value(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", "MachineGuid"
    )
    product_id = _registry_value(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductId"
    )
    install_date = _registry_value(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "InstallDate"
    )
    computer_name = _registry_value(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName",
        "ComputerName",
    )
    return MachineFingerprint(
        {
            "machine_guid": machine_guid,
            "volume_serial": _system_volume_serial(),
            # Los dos juntos: el ProductId solo se repite en instalaciones
            # clonadas desde una misma imagen, cosa que en una optica pasa.
            "windows_install": f"{product_id}|{install_date}" if product_id or install_date else "",
            "computer_name": computer_name,
        }
    )
