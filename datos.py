from pathlib import Path


def leer_datos(ruta):
    archivo = Path(ruta)
    archivo.parent.mkdir(parents=True, exist_ok=True)

    if not archivo.exists():
        archivo.write_text("", encoding="utf-8")
        return []

    try:
        contenido = archivo.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        contenido = archivo.read_text(encoding="cp1252")

    return contenido.splitlines()


def guardar_datos(ruta, lista):
    archivo = Path(ruta)
    archivo.parent.mkdir(parents=True, exist_ok=True)

    contenido = "\n".join(
        elemento.rstrip("\n")
        for elemento in lista
        if elemento.strip() != ""
    )

    if contenido != "":
        contenido += "\n"

    archivo.write_text(contenido, encoding="utf-8")