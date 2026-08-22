from modulos.comunicaciones.application.services import MessageLibraryService
from modulos.comunicaciones.domain.models import Category, Template, has_unsaved_changes
from modulos.comunicaciones.infrastructure.sqlite_repository import SQLiteCommunicationsRepository
from modulos.comunicaciones.ui.controller import CommunicationsUIController


def _library(tmp_path):
    repository = SQLiteCommunicationsRepository(tmp_path / "communications.sqlite3")
    repository.migrate()
    repository.save_category(Category("general", "General"))
    library = MessageLibraryService(repository)
    return repository, library


def test_branch_filter_includes_shared_and_selected_branch_only(tmp_path):
    repository, library = _library(tmp_path)
    shared = Template("Compartida", "Hola", "general")
    north = Template("Norte", "Hola", "general", branch="Sucursal Norte")
    south = Template("Sur", "Hola", "general", branch="Sucursal Sur")
    for template in (shared, north, south):
        repository.save_template(template)

    assert {item.title for item in library.search(branch="sucursal norte")} == {"Compartida", "Norte"}
    assert {item.title for item in library.search()} == {"Compartida", "Norte", "Sur"}
    assert library.list_branches() == ("Sucursal Norte", "Sucursal Sur")


def test_controller_round_trips_branch_in_create_and_edit_drafts(tmp_path):
    _, library = _library(tmp_path)
    controller = CommunicationsUIController(library, preparation=None)
    created = controller.save_template({
        "title": "Retiro", "body": "Listo", "category_slug": "general",
        "keywords": "pedido", "branch": " Casa Central ", "active": True,
    })
    assert created.branch == "Casa Central"
    draft = controller.draft_from(created)
    assert draft["branch"] == "Casa Central"
    draft["branch"] = "Sucursal Norte"
    updated = controller.save_template(draft, template_id=created.id)
    assert updated.branch == "Sucursal Norte"
    assert has_unsaved_changes(created, draft)
