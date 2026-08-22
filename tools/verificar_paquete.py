"""Comprobar que el paquete que se va a instalar es el que se verifico.

Existe porque el modo de fallo mas caro de este slice fue un paquete que
arrancaba bien y no llevaba adentro lo que tenia que llevar. Mirar el nombre del
zip no dice nada; el hash si.

    python tools/verificar_paquete.py releases/BC-CAJA-1.0.0-rc.33-win64.zip
    python tools/verificar_paquete.py C:\\ruta\\a\\BC-Caja

Acepta el zip o la carpeta ya descomprimida. Devuelve 0 si todo coincide y 1 si
algo no, con el detalle de que no coincide. No toca nada: solo lee.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESPERADO = RAIZ / "artifacts" / "BC-SECURITY-INSTALLATION-BINDING-V1-001" / "INSTALACIONES" / "HASHES_PAQUETE.txt"

# Ruta dentro del paquete -> sha256 esperado. Se lee de HASHES_PAQUETE.txt para
# que no haya dos listas que puedan discrepar.
INTERNOS = (
    "BC-Caja/BC-Caja.exe",
    "BC-Caja/Seguridad/BC-Seguridad.exe",
    "BC-Caja/_internal/modulos/seguridad/trusted_issuers.json",
    "BC-Caja/Seguridad/_internal/modulos/seguridad/trusted_issuers.json",
)
ZIP_NOMBRE = "BC-CAJA-1.0.0-rc.33-win64.zip"


def esperados() -> dict[str, str]:
    tabla: dict[str, str] = {}
    for linea in ESPERADO.read_text(encoding="utf-8").splitlines():
        partes = linea.split()
        if len(partes) == 2 and len(partes[0]) == 64:
            tabla[partes[1]] = partes[0]
    return tabla


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def verificar(objetivo: Path) -> int:
    tabla = esperados()
    fallos: list[str] = []
    revisados = 0

    if objetivo.is_file() and objetivo.suffix.lower() == ".zip":
        real = sha256(objetivo.read_bytes())
        quiere = tabla.get(ZIP_NOMBRE)
        revisados += 1
        if quiere and real != quiere:
            fallos.append(f"el zip entero: se esperaba {quiere}, es {real}")
        with zipfile.ZipFile(objetivo) as z:
            presentes = set(z.namelist())
            for nombre in INTERNOS:
                if nombre not in presentes:
                    fallos.append(f"FALTA en el paquete: {nombre}")
                    continue
                revisados += 1
                real = sha256(z.read(nombre))
                if real != tabla.get(nombre):
                    fallos.append(f"{nombre}: se esperaba {tabla.get(nombre)}, es {real}")
    elif objetivo.is_dir():
        # carpeta ya descomprimida: se le puede apuntar a BC-Caja o a su padre
        base = objetivo if objetivo.name == "BC-Caja" else objetivo / "BC-Caja"
        for nombre in INTERNOS:
            relativo = nombre.split("/", 1)[1]
            archivo = base / relativo
            if not archivo.is_file():
                fallos.append(f"FALTA en la carpeta: {relativo}")
                continue
            revisados += 1
            real = sha256(archivo.read_bytes())
            if real != tabla.get(nombre):
                fallos.append(f"{relativo}: se esperaba {tabla.get(nombre)}, es {real}")
    else:
        print(f"no se encontro: {objetivo}")
        return 1

    if fallos:
        print("PAQUETE_NO_COINCIDE")
        for f in fallos:
            print("  -", f)
        print("\nEste paquete NO es el que se verifico. No instalarlo.")
        return 1

    print(f"PAQUETE_OK archivos_verificados={revisados}")
    print("Coincide con HASHES_PAQUETE.txt, incluido el almacen de confianza.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    return verificar(Path(argv[1]).expanduser())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
