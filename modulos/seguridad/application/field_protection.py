"""Proteccion de datos sensibles a nivel de columna, transparente para el dominio.

Que problema resuelve: robar `bc_caja.sqlite3` —o un respaldo, o el ZIP
entero— no puede alcanzar para leer a los pacientes. Abrir esa base con
cualquier visor de SQLite tiene que mostrar criptograma donde antes habia un
nombre, un telefono, una cedula, una receta o una observacion.

Como funciona, en una linea: cada valor protegido se guarda como
`bcx1:<base64url(nonce||ciphertexto||tag)>` en la misma columna TEXT de
siempre. No cambia el esquema, no cambia el tipo, no hay tabla nueva.

Dos mitades:

  * **Lectura** — es agnostica de tabla y de columna. Un `row_factory`
    encadenado descifra cualquier valor que empiece con el prefijo, venga de
    donde venga: `SELECT *`, una columna con alias, un JOIN, una vista. Por
    construccion no se puede olvidar de descifrar un lugar.
  * **Escritura** — es explicita. Un registro dice que columnas se protegen, y
    la conexion mapea los parametros de cada INSERT y UPDATE contra ese
    registro. Lo que el parser no entiende con certeza y toca una tabla
    protegida, lo rechaza; no lo deja pasar en claro.

Dos reglas que parecen menores y no lo son:

  * **La cadena vacia no se cifra.** Varias tablas tienen
    `CHECK(length(trim(columna)) > 0)` y `CHECK(envelope <> '' OR
    customer_name <> '')`. Cifrar `''` produciria un criptograma no vacio y
    esas reglas del negocio pasarian a aceptar filas que hoy rechazan. Ademas
    seria guardar ruido para no proteger nada.
  * **Un valor ya protegido no se vuelve a proteger.** Reaplicar la migracion
    de datos no puede producir cifrado sobre cifrado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from ..canonical import b64u_decode, b64u_encode
from ..crypto.primitives import aead_open, aead_seal
from ..errors import DataProtectionError

PREFIX = "bcx1:"

# ---------------------------------------------------------------------------
# Registro de columnas protegidas
# ---------------------------------------------------------------------------
# Que entra y que no, y por que:
#
#   * Entra la identidad del paciente y todo lo que lo describe: nombre,
#     telefono, documento, receta y observaciones, en las cinco tablas donde la
#     Optica las escribe.
#   * `cash_entries.description` entra porque en esta base es donde la venta
#     guarda de quien es el trabajo. Dejarla afuera habria hecho que la base
#     robada siguiera diciendo el nombre de cada cliente.
#   * `suppliers` queda AFUERA en V1, y es una decision, no un olvido:
#     `idx_suppliers_documento_unico` es un UNIQUE sobre `document`, y el
#     cifrado autenticado usa un nonce por valor, asi que dos proveedores con
#     el mismo RUC dejarian de colisionar y el indice dejaria de cumplir su
#     funcion. Cambiar eso pide un indice ciego con clave, que es otro slice.
#     Queda declarado como riesgo residual.
PROTECTED_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "cash_entries": (
        "description",
        "customer_document",
        "customer_phone",
        "observations",
        "prescription_doctor",
    ),
    # La bitacora de revisiones guarda la entrada ENTERA como JSON. Sin esta
    # linea, proteger las columnas de `cash_entries` seria teatro: el nombre, el
    # telefono y las observaciones de cada venta seguirian legibles en el
    # snapshot, en el mismo archivo. Lo destapo la prueba que busca el nombre
    # del paciente en los bytes crudos de la base.
    "cash_entry_revisions": ("snapshot_json",),
    "orders": ("customer_name", "customer_document", "customer_phone", "observations"),
    "sale_items": ("prescription_doctor",),
    "tracked_works": ("customer_name", "observations", "confirmation_note"),
    "service_jobs": ("customer_name", "customer_phone", "description", "observations"),
}


def protected_tables() -> frozenset[str]:
    return frozenset(PROTECTED_COLUMNS)


def is_protected(table: str, column: str) -> bool:
    return column in PROTECTED_COLUMNS.get(table.lower(), ())


def looks_protected(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


# ---------------------------------------------------------------------------
# El codec
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldCipher:
    """Cifra y descifra valores de columna con la DEK de esta base.

    El dato asociado ata el criptograma a `(dek_id, tabla, columna)`. Mover un
    valor cifrado de `observations` a `customer_phone`, o de una base a otra,
    lo vuelve indescifrable en vez de silenciosamente valido.

    Lo que NO ata es la fila: dos filas de la misma columna son intercambiables
    a nivel criptografico. Es una limitacion asumida — atar la fila obligaria a
    conocer la clave primaria en cada UPDATE, y quien puede reordenar filas de
    un SQLite ya puede reordenarlas sin tocar el cifrado. Ver ADR-0005.
    """

    key: bytes
    dek_id: str

    def _associated_data(self, table: str, column: str) -> bytes:
        return f"bc.field.v1|{self.dek_id}|{table.lower()}|{column.lower()}".encode("utf-8")

    def protect(self, table: str, column: str, value: Any) -> Any:
        if value is None or value == "":
            return value
        if looks_protected(value):
            return value
        if not isinstance(value, str):
            # Una columna protegida que recibe un entero es un error de
            # programa: preferible romper aca que guardar el numero en claro.
            raise DataProtectionError(
                f"{table}.{column} es una columna protegida y recibio {type(value).__name__}"
            )
        sealed = aead_seal(self.key, value.encode("utf-8"), self._associated_data(table, column))
        return PREFIX + b64u_encode(sealed)

    def reveal(self, table: str, column: str, value: Any) -> Any:
        if not looks_protected(value):
            return value
        return self._open(value, self._associated_data(table, column))

    def reveal_unknown_column(self, value: str, *, hint: str = "") -> str:
        """Descifra sin saber con certeza de que columna vino. Es lo que usa la lectura.

        Prueba los datos asociados de las columnas registradas hasta que uno
        verifica. Solo uno puede verificar: AES-GCM autentica, asi que una
        combinacion equivocada falla y no devuelve basura.

        `hint` es el nombre de la columna en el resultado de la consulta. Casi
        siempre es el nombre real, y entonces la primera prueba acierta; cuando
        la consulta usa un alias —FactuFacil llama `cliente` a `description`— no
        acierta y se sigue por la lista completa. Es una optimizacion pura: el
        resultado no depende de que el `hint` sea correcto, solo el costo.
        """
        for table, column in _candidatos(hint):
            try:
                return self._open(value, self._associated_data(table, column))
            except DataProtectionError:
                continue
        raise DataProtectionError(
            "hay un valor protegido que no abre con la clave de datos de esta base"
        )

    def _open(self, value: str, associated_data: bytes) -> str:
        try:
            sealed = b64u_decode(value[len(PREFIX):])
        except ValueError as error:
            raise DataProtectionError("valor protegido con base64 invalido") from error
        return aead_open(self.key, sealed, associated_data).decode("utf-8")


# Todas las combinaciones (tabla, columna), en orden estable. Es la lista que se
# recorre cuando no hay pista o cuando la pista no acerto.
_ALL_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (table, column)
    for table in sorted(PROTECTED_COLUMNS)
    for column in sorted(PROTECTED_COLUMNS[table])
)

# Por nombre de columna: las tablas donde ese nombre existe. Una lectura del
# historial descifra miles de valores, y probar veintipico de combinaciones por
# valor era trabajo desperdiciado en el 95% de los casos.
_BY_COLUMN: Mapping[str, tuple[tuple[str, str], ...]] = {
    column: tuple(pair for pair in _ALL_PAIRS if pair[1] == column)
    for _table, column in _ALL_PAIRS
}


def _candidatos(hint: str) -> tuple[tuple[str, str], ...]:
    preferidos = _BY_COLUMN.get(str(hint).lower(), ())
    if not preferidos:
        return _ALL_PAIRS
    return preferidos + tuple(pair for pair in _ALL_PAIRS if pair not in preferidos)


# ---------------------------------------------------------------------------
# Mapeo de parametros de escritura
# ---------------------------------------------------------------------------
_INSERT_HEAD = re.compile(
    r"^\s*INSERT(?:\s+OR\s+\w+)?\s+INTO\s+(?P<table>[\w\"\[\]`.]+)\s*\((?P<columns>[^()]*)\)\s*"
    r"VALUES\s*\(",
    re.IGNORECASE | re.DOTALL,
)
# Detector suelto: solo para saber a que tabla apunta la sentencia. Si esa tabla
# tiene columnas protegidas y el analisis fino no cierra, se levanta error. Sin
# este paso, cualquier forma de SQL que el parser no reconociera se convertia en
# una escritura en claro silenciosa, que es el peor final posible.
_TARGET = re.compile(
    r"^\s*(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE)\s+(?P<table>[\w\"\[\]`.]+)",
    re.IGNORECASE,
)
_INSERT_SELECT = re.compile(
    r"^\s*INSERT(?:\s+OR\s+\w+)?\s+INTO\s+(?P<table>[\w\"\[\]`.]+)\s*(?:\([^()]*\))?\s*SELECT\b",
    re.IGNORECASE | re.DOTALL,
)
_UPDATE = re.compile(
    r"^\s*UPDATE\s+(?P<table>[\w\"\[\]`.]+)\s+SET\s+(?P<assignments>.*?)"
    r"(?:\bWHERE\b|\bRETURNING\b|$)",
    re.IGNORECASE | re.DOTALL,
)
_ASSIGNMENT = re.compile(r"(?P<column>[\w\"\[\]`.]+)\s*=\s*(?P<expression>.+)", re.DOTALL)


class StatementNotUnderstood(DataProtectionError):
    """La sentencia toca una tabla protegida y el mapeo no es seguro.

    Se levanta a proposito en vez de dejar pasar el valor sin cifrar. Un dato
    sensible guardado en claro por una sentencia que el parser no entendio
    seria una filtracion silenciosa; un error es ruidoso y se arregla.
    """


def _clean_identifier(raw: str) -> str:
    return raw.strip().strip('"').strip("`").strip("[]").split(".")[-1].lower()


def _balanced_slice(text: str, start: int) -> tuple[str, int]:
    """Contenido entre el parentesis que abre en `start-1` y el que lo cierra.

    Hace falta un recorrido y no una expresion regular porque el VALUES puede
    llevar parentesis anidados (`coalesce(?, '')`) y ademas venir seguido de un
    `ON CONFLICT(...)`, que el repositorio usa en casi todos los guardados.
    Cualquiera de las dos formas rompe un patron ingenuo, y romperlo significaba
    quedarse sin plan, es decir, guardar en claro sin avisar.
    """
    depth = 1
    quote = ""
    index = start
    while index < len(text):
        character = text[index]
        if quote:
            if character == quote:
                quote = ""
        elif character in "'\"":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return text[start:index], index + 1
        index += 1
    raise StatementNotUnderstood("parentesis sin cerrar en una sentencia con columnas protegidas")


def _split_top_level(text: str) -> list[str]:
    """Parte por comas que no esten dentro de parentesis ni de comillas."""
    parts: list[str] = []
    depth = 0
    quote = ""
    current: list[str] = []
    for character in text:
        if quote:
            current.append(character)
            if character == quote:
                quote = ""
            continue
        if character in "'\"":
            quote = character
            current.append(character)
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return [part for part in (item.strip() for item in parts) if part]


def plan_parameters(sql: str) -> list[str | None]:
    """Para cada `?` de la sentencia, el nombre de columna protegida, o None.

    Devuelve lista vacia cuando la sentencia no escribe en ninguna tabla
    protegida: ese es el camino de casi todo el repositorio y no cuesta nada.
    """
    objetivo = _TARGET.match(sql)
    if objetivo is None or not PROTECTED_COLUMNS.get(_clean_identifier(objetivo.group("table"))):
        # No escribe sobre ninguna tabla protegida: es el camino de casi todo el
        # repositorio y no cuesta nada.
        return []

    insert_select = _INSERT_SELECT.match(sql)
    if insert_select:
        # Los valores salen de un SELECT sobre la misma base, asi que ya estan
        # protegidos si tenian que estarlo. Los `?` que haya son del WHERE.
        return []

    match = _INSERT_HEAD.match(sql)
    if match:
        table = _clean_identifier(match.group("table"))
        columns = [_clean_identifier(item) for item in _split_top_level(match.group("columns"))]
        cuerpo, fin_de_values = _balanced_slice(sql, match.end())
        values = _split_top_level(cuerpo)
        protected = PROTECTED_COLUMNS.get(table, ())
        if not protected:
            return []
        if len(columns) != len(values):
            raise StatementNotUnderstood(
                f"INSERT sobre {table}: la lista de columnas y la de valores no coinciden"
            )
        plan: list[str | None] = []
        for column, expression in zip(columns, values):
            if expression.strip() != "?":
                if column in protected:
                    raise StatementNotUnderstood(
                        f"INSERT sobre {table}: {column} esta protegida y no recibe un parametro"
                    )
                continue
            plan.append(column if column in protected else None)
        _reject_protected_placeholders_after(sql, fin_de_values, table, plan)
        return plan

    match = _UPDATE.match(sql)
    if match:
        table = _clean_identifier(match.group("table"))
        protected = PROTECTED_COLUMNS.get(table, ())
        if not protected:
            return []
        plan = []
        for assignment in _split_top_level(match.group("assignments")):
            parsed = _ASSIGNMENT.match(assignment)
            if parsed is None:
                raise StatementNotUnderstood(f"UPDATE sobre {table}: asignacion ilegible")
            column = _clean_identifier(parsed.group("column"))
            expression = parsed.group("expression").strip()
            markers = expression.count("?")
            if markers == 0:
                if column in protected:
                    raise StatementNotUnderstood(
                        f"UPDATE sobre {table}: {column} esta protegida y se calcula en SQL"
                    )
                continue
            if column in protected and expression != "?":
                raise StatementNotUnderstood(
                    f"UPDATE sobre {table}: {column} esta protegida y no recibe un parametro simple"
                )
            plan.extend([column if column in protected else None] * markers)
        _reject_protected_placeholders_after(sql, match.end("assignments"), table, plan)
        return plan

    raise StatementNotUnderstood(
        f"sentencia sobre {_clean_identifier(objetivo.group('table'))}, que tiene columnas "
        "protegidas, con una forma que el mapeo no reconoce"
    )


def _reject_protected_placeholders_after(
    sql: str, offset: int, table: str, plan: list[str | None]
) -> None:
    """El resto de la sentencia no puede comparar una columna protegida con un `?`.

    `WHERE customer_phone = ?` sobre datos cifrados no devuelve error: devuelve
    cero filas, en silencio, para siempre. Es la clase de defecto que aparece
    seis meses despues como "a veces no encuentra al cliente".
    """
    tail = sql[offset:]
    if "?" not in tail:
        return
    for column in PROTECTED_COLUMNS.get(table, ()):
        if re.search(rf"\b{re.escape(column)}\b\s*(=|<>|!=|\bLIKE\b|\bIN\b)", tail, re.IGNORECASE):
            raise StatementNotUnderstood(
                f"{table}.{column} esta protegida y no se puede comparar en SQL"
            )
    plan.extend([None] * tail.count("?"))


def apply_plan(
    plan: Sequence[str | None], table_hint: str, parameters: Sequence[Any], cipher: FieldCipher
) -> tuple[Any, ...]:
    protected = list(parameters)
    for index, column in enumerate(plan):
        if column is None or index >= len(protected):
            continue
        protected[index] = cipher.protect(table_hint, column, protected[index])
    return tuple(protected)


def statement_table(sql: str) -> str:
    for pattern in (_INSERT_HEAD, _UPDATE, _INSERT_SELECT):
        match = pattern.match(sql)
        if match:
            return _clean_identifier(match.group("table"))
    return ""


def scan_plaintext(values: Iterable[Any]) -> list[str]:
    """Devuelve los valores que NO estan protegidos. Lo usan las pruebas y el CLI."""
    return [str(value) for value in values if value not in (None, "") and not looks_protected(value)]
