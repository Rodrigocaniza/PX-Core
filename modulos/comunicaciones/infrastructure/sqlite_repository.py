"""Repositorio SQLite de BC Comunicaciones.

Mismas PRAGMAs y estrategia de migraciones que BC Caja, sobre una base de datos
propia y separada.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping, Sequence
from urllib.parse import quote

from ..domain.errors import DuplicateTemplateError
from ..domain.models import (
    Category,
    DeliveryStatus,
    PreparedMessage,
    Template,
    VariableSpec,
    normalize_search_text,
    utc_now,
)


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
REQUIRED_TABLES = (
    "schema_migrations", "categories", "templates", "prepared_messages",
    "communication_accounts", "conversations", "conversation_messages", "communication_audit",
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteCommunicationsRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._is_memory = str(database_path) == ":memory:"
        if not self._is_memory:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_connection: sqlite3.Connection | None = None
        if self._is_memory:
            self._memory_connection = self._new_connection()
        self.migrate()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = FULL")
        if not self._is_memory:
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._memory_connection or self._new_connection()
        try:
            yield connection
        finally:
            if self._memory_connection is None:
                connection.close()

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None

    def integrity_check(self) -> None:
        with self._connection() as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"SQLite quick_check falló: {result}")

    def backup_to(self, destination: str | Path) -> Path:
        target_path = Path(destination)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as source:
            target = sqlite3.connect(str(target_path))
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
        return target_path

    def restore_from(self, source_path: str | Path) -> None:
        """Sustituye el contenido de la base por el de una copia validada.

        Se usa `Connection.backup()` en lugar de reemplazar el archivo: funciona
        con WAL y con conexiones abiertas, y es atómico desde el punto de vista
        de SQLite.

        El origen se abre **en sólo lectura por URI**: un `sqlite3.connect()`
        común sobre una ruta inexistente crearía una base vacía y la copiaría
        encima de los datos vivos, borrándolos sin que nada fallara.
        """
        resolved = Path(source_path)
        if not resolved.is_file():
            raise sqlite3.OperationalError(f"la copia de origen no existe: {resolved}")
        source = sqlite3.connect(
            f"file:{quote(resolved.as_posix(), safe='/:')}?mode=ro", uri=True
        )
        try:
            with self._connection() as target:
                source.backup(target)
                target.commit()
        finally:
            source.close()
        self.migrate()

    def migrate(self) -> None:
        with self._connection() as connection:
            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = migration.stem.split("_", 1)[0]
                applied = connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                ).fetchone() if self._table_exists(connection, "schema_migrations") else None
                if applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now().astimezone().isoformat()),
                )
                connection.commit()

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() is not None

    def schema_looks_valid(self) -> bool:
        with self._connection() as connection:
            return all(self._table_exists(connection, table) for table in REQUIRED_TABLES)

    # ------------------------------------------------------------------ categorías

    def save_category(self, category: Category) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO categories(slug, name, position, active) VALUES (?,?,?,?)
                   ON CONFLICT(slug) DO UPDATE SET
                       name=excluded.name, position=excluded.position, active=excluded.active""",
                (category.slug, category.name, category.position, int(category.active)),
            )
            connection.commit()

    def list_categories(self, *, include_inactive: bool = False) -> Sequence[Category]:
        query = "SELECT * FROM categories"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY position, name"
        with self._connection() as connection:
            rows = connection.execute(query).fetchall()
        return [
            Category(slug=row["slug"], name=row["name"], position=row["position"], active=bool(row["active"]))
            for row in rows
        ]

    def get_category(self, slug: str) -> Category | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            return None
        return Category(slug=row["slug"], name=row["name"], position=row["position"], active=bool(row["active"]))

    # ------------------------------------------------------------------ plantillas

    def save_template(self, template: Template) -> None:
        values = (
            template.id, template.category_slug, template.title, template.body, template.keywords,
            template.search_blob, int(template.active), int(template.favorite), template.branch,
            template.origin, template.usage_count, _iso(template.created_at), _iso(template.updated_at),
            template.revision,
        )
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """INSERT INTO templates(
                        id,category_slug,title,body,keywords,search_blob,active,favorite,branch,
                        origin,usage_count,created_at,updated_at,revision
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        category_slug=excluded.category_slug, title=excluded.title, body=excluded.body,
                        keywords=excluded.keywords, search_blob=excluded.search_blob,
                        active=excluded.active, favorite=excluded.favorite, branch=excluded.branch,
                        origin=excluded.origin, usage_count=excluded.usage_count,
                        updated_at=excluded.updated_at, revision=excluded.revision""",
                    values,
                )
                connection.execute("DELETE FROM template_variables WHERE template_id = ?", (template.id,))
                connection.executemany(
                    """INSERT INTO template_variables(template_id,name,label,example,position)
                       VALUES (?,?,?,?,?)""",
                    [
                        (template.id, spec.name, spec.label, spec.example, index)
                        for index, spec in enumerate(template.variable_specs)
                    ],
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                if "idx_templates_unique_title" in str(error):
                    raise DuplicateTemplateError(
                        f"Ya existe una plantilla llamada «{template.title}» en esa categoría."
                    ) from error
                raise
            except Exception:
                connection.rollback()
                raise

    def get_template(self, template_id: str) -> Template | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
            if row is None:
                return None
            return self._hydrate_template(connection, row)

    def list_templates(self, *, include_inactive: bool = True) -> Sequence[Template]:
        query = "SELECT * FROM templates"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY title"
        with self._connection() as connection:
            rows = connection.execute(query).fetchall()
            return [self._hydrate_template(connection, row) for row in rows]

    def search_templates(
        self,
        *,
        query: str = "",
        category_slug: str | None = None,
        only_favorites: bool = False,
        include_inactive: bool = False,
    ) -> Sequence[Template]:
        sql = "SELECT * FROM templates WHERE 1 = 1"
        params: list[object] = []
        if not include_inactive:
            sql += " AND active = 1"
        if only_favorites:
            sql += " AND favorite = 1"
        if category_slug:
            sql += " AND category_slug = ?"
            params.append(category_slug)
        needle = normalize_search_text(query)
        if needle:
            sql += " AND search_blob LIKE ? ESCAPE '\\'"
            params.append(f"%{_escape_like(needle)}%")
        sql += " ORDER BY title"
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
            return [self._hydrate_template(connection, row) for row in rows]

    def delete_template(self, template_id: str) -> None:
        """Sólo para mantenimiento; la operación normal desactiva, no borra."""
        with self._connection() as connection:
            connection.execute("DELETE FROM template_variables WHERE template_id = ?", (template_id,))
            connection.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            connection.commit()

    def count_templates(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM templates").fetchone()[0])

    def _hydrate_template(self, connection: sqlite3.Connection, row: sqlite3.Row) -> Template:
        specs = connection.execute(
            "SELECT name,label,example FROM template_variables WHERE template_id = ? ORDER BY position",
            (row["id"],),
        ).fetchall()
        return Template(
            id=row["id"],
            category_slug=row["category_slug"],
            title=row["title"],
            body=row["body"],
            keywords=row["keywords"],
            active=bool(row["active"]),
            favorite=bool(row["favorite"]),
            branch=row["branch"],
            origin=row["origin"],
            usage_count=row["usage_count"],
            created_at=_datetime(row["created_at"]) or utc_now(),
            updated_at=_datetime(row["updated_at"]) or utc_now(),
            revision=row["revision"],
            variable_specs=tuple(
                VariableSpec(name=item["name"], label=item["label"], example=item["example"])
                for item in specs
            ),
        )

    # ------------------------------------------------------------------ historial

    def save_prepared_message(self, message: PreparedMessage) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO prepared_messages(
                    id,template_id,template_title,category_slug,final_text,values_json,operator,
                    channel,status,delivery_reference,subject_kind,subject_reference,
                    manually_edited,prepared_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    message.id, message.template_id, message.template_title, message.category_slug,
                    message.final_text, json.dumps(dict(message.values), ensure_ascii=False, sort_keys=True),
                    message.operator, message.channel, message.status.value, message.delivery_reference,
                    message.subject_kind, message.subject_reference, int(message.manually_edited),
                    _iso(message.prepared_at),
                ),
            )
            connection.commit()

    def list_prepared_messages(self, *, limit: int = 25) -> Sequence[PreparedMessage]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM prepared_messages ORDER BY prepared_at DESC, rowid DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._hydrate_message(row) for row in rows]

    def count_prepared_messages(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM prepared_messages").fetchone()[0])

    @staticmethod
    def _hydrate_message(row: sqlite3.Row) -> PreparedMessage:
        return PreparedMessage(
            id=row["id"],
            template_id=row["template_id"] or "",
            template_title=row["template_title"],
            category_slug=row["category_slug"],
            final_text=row["final_text"],
            values=json.loads(row["values_json"]),
            operator=row["operator"],
            channel=row["channel"],
            status=DeliveryStatus(row["status"]),
            delivery_reference=row["delivery_reference"],
            subject_kind=row["subject_kind"],
            subject_reference=row["subject_reference"],
            manually_edited=bool(row["manually_edited"]),
            prepared_at=_datetime(row["prepared_at"]) or utc_now(),
        )

    # ------------------------------------------------------------------ outbox y settings

    def append_outbox_event(self, event_type: str, payload: Mapping[str, object]) -> str:
        from ..domain.models import new_id

        event_id = new_id()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO outbox_events(id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
                (
                    event_id,
                    str(event_type),
                    json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=str),
                    _iso(utc_now()),
                ),
            )
            connection.commit()
        return event_id

    def list_pending_outbox_events(self, *, limit: int = 100) -> Sequence[Mapping[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id,event_type,payload_json,created_at,attempts,last_error
                   FROM outbox_events WHERE dispatched_at IS NULL
                   ORDER BY created_at LIMIT ?""",
                (int(limit),),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
                "attempts": row["attempts"],
                "last_error": row["last_error"],
            }
            for row in rows
        ]

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connection() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO settings(key,value) VALUES (?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (str(key), str(value or "")),
            )
            connection.commit()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
