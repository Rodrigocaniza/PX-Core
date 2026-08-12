"""Composition root de BC Comunicaciones."""

from __future__ import annotations

from pathlib import Path

from .application.services import MessageLibraryService, MessagePreparationService
from .config import CommunicationsDataPaths, resolve_data_paths
from .infrastructure.backup import LocalBackupService
from .infrastructure.clipboard import InMemoryClipboard
from .infrastructure.sqlite_repository import SQLiteCommunicationsRepository
from .infrastructure.inbox_repository import SQLiteInboxRepository
from .application.inbox_service import InboxService
from .ui.controller import CommunicationsUIController


def build_repository(database_path: str | Path | None = None) -> SQLiteCommunicationsRepository:
    path = Path(database_path) if database_path is not None else resolve_data_paths().ensure().database
    repository = SQLiteCommunicationsRepository(path)
    repository.integrity_check()
    return repository


def build_inbox(database_path: str | Path | None = None) -> InboxService:
    repository = build_repository(database_path)
    return InboxService(SQLiteInboxRepository(repository))


def build_controller(
    database_path: str | Path | None = None,
    *,
    data_paths: CommunicationsDataPaths | None = None,
    clipboard=None,
    seed: bool = True,
) -> CommunicationsUIController:
    if data_paths is not None:
        paths = data_paths
    elif database_path is not None:
        explicit = Path(database_path)
        paths = CommunicationsDataPaths(
            root=explicit.parent,
            database=explicit,
            backups=explicit.parent / "Backups",
            logs=explicit.parent / "Logs",
        )
    else:
        paths = resolve_data_paths()
    if database_path is None:
        paths.ensure()
        database_path = paths.database

    repository = build_repository(database_path)
    library = MessageLibraryService(repository)
    preparation = MessagePreparationService(
        repository, clipboard=clipboard if clipboard is not None else InMemoryClipboard()
    )
    backup = LocalBackupService(repository, paths.backups)
    controller = CommunicationsUIController(library, preparation, backup_service=backup)
    controller.inbox = InboxService(SQLiteInboxRepository(repository))
    if seed:
        controller.start()
    return controller
