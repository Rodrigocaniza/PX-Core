"""Una conexion SQLite que cifra al escribir y descifra al leer, sin tocar el SQL.

El repositorio de Caja tiene 1800 lineas de SQL escrito a mano. Meter llamadas
a cifrar y descifrar en cada una habria sido una migracion de codigo enorme y,
peor, una que se puede olvidar en un lugar. Aca la proteccion entra por la
conexion, que es el unico punto por donde pasa todo.

Lectura: `row_factory` encadenado. Cualquier valor con el prefijo se descifra,
sin importar de que consulta salga ni con que alias. No hay forma de leer sin
descifrar.

Escritura: `execute` y `executemany` mapean los parametros contra el registro
de columnas protegidas. Lo que el mapeo no entiende y toca una tabla protegida
levanta error en vez de pasar en claro.

Sin cifrador (`cipher=None`) la clase se comporta exactamente como
`sqlite3.Connection`: mismo camino, mismos objetos, cero diferencias. Esa es la
condicion para que instalar esta capa no cambie nada en una BC sin enrolar.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Iterable, Sequence

from ..application.field_protection import (
    FieldCipher,
    apply_plan,
    looks_protected,
    plan_parameters,
    statement_table,
)

_RAW_ROW_FACTORY = sqlite3.Connection.row_factory


class ProtectedConnection(sqlite3.Connection):
    """`sqlite3.connect(path, factory=ProtectedConnection)` y despues `attach_cipher`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cipher: FieldCipher | None = None
        self._declared_row_factory: Callable | None = None
        self._plan_cache: dict[str, list[str | None]] = {}

    # ------------------------------------------------------------------ cifrador
    def attach_cipher(self, cipher: FieldCipher | None) -> "ProtectedConnection":
        self._cipher = cipher
        # Revalidar la fabrica de filas: puede haberse asignado antes del cifrador.
        self._install_row_factory(self._declared_row_factory)
        return self

    @property
    def cipher(self) -> FieldCipher | None:
        return self._cipher

    # ----------------------------------------------------------------- lectura
    # `row_factory` se intercepta con una property que tapa el descriptor de C.
    # Quien la asigne —el repositorio pone `sqlite3.Row`— sigue viendo lo que
    # asigno; por debajo queda envuelta con el descifrado.
    @property  # type: ignore[override]
    def row_factory(self) -> Callable | None:
        return self._declared_row_factory

    @row_factory.setter
    def row_factory(self, factory: Callable | None) -> None:
        self._install_row_factory(factory)

    def _install_row_factory(self, factory: Callable | None) -> None:
        self._declared_row_factory = factory
        cipher = self._cipher
        if cipher is None:
            _RAW_ROW_FACTORY.__set__(self, factory)
            return

        def revealing(cursor: sqlite3.Cursor, row: tuple) -> Any:
            if any(looks_protected(value) for value in row):
                # `cursor.description` da el nombre de cada columna del
                # resultado. Se usa solo como pista para acertar a la primera;
                # si la consulta puso un alias, el descifrado igual funciona,
                # solo cuesta un poco mas.
                nombres = cursor.description or ()
                row = tuple(
                    cipher.reveal_unknown_column(
                        value,
                        hint=nombres[index][0] if index < len(nombres) else "",
                    )
                    if looks_protected(value)
                    else value
                    for index, value in enumerate(row)
                )
            return factory(cursor, row) if factory is not None else row

        _RAW_ROW_FACTORY.__set__(self, revealing)

    # ---------------------------------------------------------------- escritura
    def _plan(self, sql: str) -> list[str | None]:
        cached = self._plan_cache.get(sql)
        if cached is None:
            cached = plan_parameters(sql)
            self._plan_cache[sql] = cached
        return cached

    def _protect(self, sql: str, parameters: Sequence[Any]) -> Sequence[Any]:
        if self._cipher is None or not parameters:
            return parameters
        plan = self._plan(sql)
        if not any(plan):
            return parameters
        if isinstance(parameters, dict):
            # El repositorio usa parametros posicionales en todo lo que escribe
            # sobre tablas protegidas. Si eso cambiara, es mejor romper que
            # guardar en claro por un camino que nadie penso.
            from ..application.field_protection import StatementNotUnderstood

            raise StatementNotUnderstood(
                "una escritura sobre tabla protegida usa parametros con nombre"
            )
        return apply_plan(plan, statement_table(sql), list(parameters), self._cipher)

    def execute(self, sql: str, parameters: Sequence[Any] = (), /) -> sqlite3.Cursor:  # type: ignore[override]
        return super().execute(sql, self._protect(sql, parameters))

    def executemany(  # type: ignore[override]
        self, sql: str, seq_of_parameters: Iterable[Sequence[Any]], /
    ) -> sqlite3.Cursor:
        if self._cipher is None:
            return super().executemany(sql, seq_of_parameters)
        plan = self._plan(sql)
        if not any(plan):
            return super().executemany(sql, seq_of_parameters)
        table = statement_table(sql)
        protected = [
            apply_plan(plan, table, list(parameters), self._cipher)
            for parameters in seq_of_parameters
        ]
        return super().executemany(sql, protected)


def open_protected(
    database_path: str, cipher: FieldCipher | None, **connect_kwargs: Any
) -> ProtectedConnection:
    connection = sqlite3.connect(database_path, factory=ProtectedConnection, **connect_kwargs)
    return connection.attach_cipher(cipher)
