"""Cadena de migraciones esperada, derivada del directorio.

Varios contratos verifican que la cadena se aplique completa y en orden. Antes
repetían la lista a mano, así que cada slice que agrega una migración rompía
cinco pruebas que no tenían nada que ver con él y había que reescribir la misma
enumeración cinco veces.

La fuente de verdad son los `.sql` en disco. Que la prueba los lea de ahí no la
vuelve vacía: lo que verifica es que la base tenga registradas **todas** las
migraciones del directorio, en orden, que es justo lo que falla cuando una
migración se cae a mitad o no se registra en `schema_migrations`.
"""

from __future__ import annotations

from pathlib import Path

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[1]
    / "modulos" / "caja_diaria" / "infrastructure" / "migrations"
)


def versiones_esperadas() -> list[str]:
    """`['001', '002', ...]`, en orden, tal como están en el directorio."""
    return sorted(ruta.name.split("_", 1)[0] for ruta in MIGRATIONS_DIR.glob("*.sql"))


def versiones_esperadas_como_filas() -> list[tuple[str]]:
    """La misma lista con la forma que devuelve `fetchall()` de una sola columna."""
    return [(version,) for version in versiones_esperadas()]


def afirmar_cadena_completa_con(conexion, version: str) -> None:
    """La `version` esta aplicada y la cadena esta entera.

    Existe porque tres slices seguidos escribieron la misma prueba como "la
    ultima migracion es la mia", y las tres se rompieron en cuanto llego la
    siguiente. Lo que cada una queria decir era "la mia se aplico y no falta
    ninguna", que es lo que esto afirma y lo que sigue siendo cierto despues.
    """
    aplicadas = [fila[0] for fila in conexion.execute(
        "SELECT version FROM schema_migrations ORDER BY version")]
    assert version in aplicadas, f"falta la migracion {version}"
    assert aplicadas == versiones_esperadas()
