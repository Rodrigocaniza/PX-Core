"""Proteger los datos existentes, y poder volver atras.

Cifrar una base que ya esta en produccion es la operacion mas peligrosa de este
slice: si sale mal a la mitad, queda mitad legible y mitad no, que es peor que
cualquiera de los dos extremos. Por eso:

  * **Todo en una sola transaccion.** SQLite es atomico tambien para DDL, asi
    que un corte de luz deja la base exactamente como estaba. No hay estado
    intermedio que reparar.
  * **Idempotente.** Un valor ya protegido no se vuelve a proteger. Correr la
    herramienta dos veces no hace dano.
  * **Reversible.** `rollback` hace exactamente lo inverso con la misma clave.
    Es la prueba K de la mision y el seguro de la instalacion en la Optica.
  * **Con respaldo previo obligatorio.** Lo exige el CLI, no la conciencia de
    quien lo corre.

El caso del disparador de `sale_items`
--------------------------------------
`sale_items_de_venta_integrada_sin_update` (migracion 025) prohibe UPDATE sobre
la linea de una venta que ya movio stock. Es una regla del negocio correcta y
no se toca: proteger un campo no puede convertirse en una excusa para relajar
una invariante economica.

Lo que se hace es suspenderlo **dentro de la misma transaccion**: se lee su SQL
de `sqlite_master`, se lo elimina, se cifra, y se lo vuelve a crear con el
mismo texto exacto. Si algo falla en el medio, el rollback de SQLite devuelve
el disparador junto con los datos. Antes de confirmar se verifica que este de
vuelta y que su SQL sea identico al que habia; si no lo es, se aborta.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import SecurityError
from ..infrastructure import security_db
from .field_protection import PROTECTED_COLUMNS, FieldCipher, looks_protected

# Disparadores que impiden reescribir una fila y hay que suspender mientras se
# cifra. Se nombran uno por uno: suspender "todos los que estorben" habria sido
# una puerta abierta a apagar sin querer una regla que si importa.
SUSPENDED_TRIGGERS = ("sale_items_de_venta_integrada_sin_update",)


@dataclass
class MigrationReport:
    protected: dict[str, int] = field(default_factory=dict)
    skipped_empty: int = 0
    already_done: int = 0
    triggers_restored: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return sum(self.protected.values())

    def to_document(self) -> dict[str, Any]:
        return {
            "valores_convertidos": self.total,
            "por_columna": dict(sorted(self.protected.items())),
            "vacios_omitidos": self.skipped_empty,
            "ya_estaban": self.already_done,
            "disparadores_restaurados": list(self.triggers_restored),
        }


def _connect(database_path: str | Path) -> sqlite3.Connection:
    """Conexion cruda a proposito: aca se ve y se escribe el criptograma tal cual.

    Usar la conexion protegida seria descifrar al leer y volver a cifrar al
    escribir — no haria nada, o peor, cifraria dos veces.
    """
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _existing_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def survey(database_path: str | Path) -> dict[str, dict[str, int]]:
    """Cuantos valores hay en claro y cuantos protegidos, por columna.

    Es lo que se mira antes y despues de migrar, y lo que sostiene la prueba de
    que una base robada no dice nada: si `en_claro` no es cero, la afirmacion
    seria falsa.
    """
    resultado: dict[str, dict[str, int]] = {}
    with closing(_connect(database_path)) as connection:
        presentes = _existing_tables(connection)
        for table, columns in PROTECTED_COLUMNS.items():
            if table not in presentes:
                continue
            for column in columns:
                claro = protegidos = 0
                for (value,) in connection.execute(
                    f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} <> ''"
                ):
                    if looks_protected(value):
                        protegidos += 1
                    else:
                        claro += 1
                resultado[f"{table}.{column}"] = {
                    "en_claro": claro, "protegidos": protegidos
                }
    return resultado


def _primary_key(connection: sqlite3.Connection, table: str) -> str:
    for row in connection.execute(f"PRAGMA table_info({table})"):
        if row["pk"]:
            return row["name"]
    raise SecurityError(f"{table} no tiene clave primaria y no se puede migrar fila por fila")


def _suspend_triggers(connection: sqlite3.Connection) -> dict[str, str]:
    guardados: dict[str, str] = {}
    for name in SUSPENDED_TRIGGERS:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
        ).fetchone()
        if row is None or not row["sql"]:
            continue
        guardados[name] = row["sql"]
        connection.execute(f"DROP TRIGGER {name}")
    return guardados


def _restore_triggers(connection: sqlite3.Connection, guardados: dict[str, str]) -> tuple[str, ...]:
    for name, sql in guardados.items():
        connection.execute(sql)
    for name, sql in guardados.items():
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
        ).fetchone()
        if row is None or row["sql"] != sql:
            # Se aborta la transaccion entera. Preferimos una base sin cifrar a
            # una base cifrada con una regla del negocio apagada.
            raise SecurityError(
                f"el disparador {name} no volvio identico; se cancela la migracion de datos"
            )
    return tuple(sorted(guardados))


def _transform(
    database_path: str | Path,
    cipher: FieldCipher,
    *,
    forward: bool,
) -> MigrationReport:
    report = MigrationReport()
    with closing(_connect(database_path)) as connection:
        presentes = _existing_tables(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            guardados = _suspend_triggers(connection)
            for table, columns in sorted(PROTECTED_COLUMNS.items()):
                if table not in presentes:
                    continue
                clave = _primary_key(connection, table)
                for column in columns:
                    convertidos = _transform_column(
                        connection, cipher, table, column, clave, forward, report
                    )
                    if convertidos:
                        report.protected[f"{table}.{column}"] = convertidos
            report.triggers_restored = _restore_triggers(connection, guardados)
        except Exception:
            connection.rollback()
            raise
        connection.commit()
    return report


def _transform_column(
    connection: sqlite3.Connection,
    cipher: FieldCipher,
    table: str,
    column: str,
    key_column: str,
    forward: bool,
    report: MigrationReport,
) -> int:
    filas = connection.execute(
        f"SELECT {key_column} AS clave, {column} AS valor FROM {table}"
        f" WHERE {column} IS NOT NULL AND {column} <> ''"
    ).fetchall()
    cambios: list[tuple[str, Any]] = []
    for fila in filas:
        valor = fila["valor"]
        protegido = looks_protected(valor)
        if forward and protegido:
            report.already_done += 1
            continue
        if not forward and not protegido:
            report.already_done += 1
            continue
        nuevo = (
            cipher.protect(table, column, valor)
            if forward
            else cipher.reveal(table, column, valor)
        )
        if nuevo != valor:
            cambios.append((nuevo, fila["clave"]))
    if cambios:
        connection.executemany(
            f"UPDATE {table} SET {column} = ? WHERE {key_column} = ?", cambios
        )
    return len(cambios)


def protect(database_path: str | Path, cipher: FieldCipher, *, actor: str = "") -> MigrationReport:
    report = _transform(database_path, cipher, forward=True)
    security_db.record_event(
        database_path,
        event=security_db.EVENT_DATA_PROTECTED,
        outcome="OK",
        details={**report.to_document(), "actor": actor, "dek_id": cipher.dek_id},
    )
    return report


def rollback(database_path: str | Path, cipher: FieldCipher, *, actor: str = "") -> MigrationReport:
    """Devuelve los datos a texto plano. Es el camino de vuelta de la instalacion.

    Existe para que aplicar la proteccion en la Optica no sea una puerta de una
    sola direccion. Cifrar sin poder revertir habria sido apostar la base a que
    nada salga mal.
    """
    report = _transform(database_path, cipher, forward=False)
    security_db.record_event(
        database_path,
        event=security_db.EVENT_DATA_ROLLBACK,
        outcome="OK",
        details={**report.to_document(), "actor": actor, "dek_id": cipher.dek_id},
    )
    return report


def plaintext_leftovers(database_path: str | Path) -> dict[str, int]:
    """Columnas protegidas que todavia guardan algo legible. Vacio es lo esperado."""
    return {
        nombre: conteo["en_claro"]
        for nombre, conteo in survey(database_path).items()
        if conteo["en_claro"]
    }
