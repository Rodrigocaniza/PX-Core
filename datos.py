def leer_datos(ruta):
    archivo = open(ruta, "r")
    contenido = archivo.read()
    archivo.close()
    return contenido.split("\n")

def guardar_datos(ruta, lista):
    with open(ruta, "w") as archivo:
        archivo.write("\n".join(lista))