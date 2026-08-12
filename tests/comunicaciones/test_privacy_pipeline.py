from __future__ import annotations

import json
from pathlib import Path

import pytest

from modulos.comunicaciones.privacy import AnonymizationPipeline, PrivacyError, inspect_export


SYNTHETIC_CHAT = """12/08/2026, 09:10 - Persona Ficticia Uno: Hola, soy Persona Ficticia Uno y mi email es prueba.uno@example.test
12/08/2026, 09:11 - Agente Ficticio Dos: Su pedido ABC-9876 esta en Sucursal Norte por Gs. 450.000
12/08/2026, 09:12 - Persona Ficticia Uno: Mi telefono es +595 981 123 456, CI 9.999.991 y direccion Calle Imaginaria 123
12/08/2026, 09:13 - Persona Ficticia Uno: fecha de nacimiento 01/02/1990 y diagnostico diabetes controlada
12/08/2026, 09:14 - Persona Ficticia Uno: adjunto receta_Persona_Ficticia_Uno.pdf y usuario @persona_ficticia
"""


def _external_layout(tmp_path: Path):
    repository = tmp_path / "repository"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    repository.mkdir()
    source_dir.mkdir()
    source = source_dir / "synthetic-chat.txt"
    source.write_text(SYNTHETIC_CHAT, encoding="utf-8")
    return repository, source, output_dir


def test_pipeline_redacts_every_supported_class_and_preserves_analytics(tmp_path: Path):
    repository, source, output_dir = _external_layout(tmp_path)
    result = AnonymizationPipeline(repository_root=repository).run(source, output_dir)
    output = result.output.read_text(encoding="utf-8")
    assert "Persona Ficticia" not in output
    assert "example.test" not in output
    assert "+595" not in output and "9.999.991" not in output
    assert "Calle Imaginaria" not in output and "01/02/1990" not in output
    assert "diabetes" not in output and "receta_Persona" not in output
    assert "Gs. 450.000" in output and "Sucursal Norte" in output
    assert "12/08/2026, 09:10" in output
    assert "[CLIENTE_001]" in output and output.count("[CLIENTE_001]") >= 2


def test_report_has_counts_hash_and_no_original_values(tmp_path: Path):
    repository, source, output_dir = _external_layout(tmp_path)
    result = AnonymizationPipeline(repository_root=repository).run(source, output_dir)
    report_text = result.report.read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert report["status"] == "PASS" and report["rules_version"] == "1.0.0"
    assert len(report["input_sha256"]) == 64
    assert report["detected"]["TELEFONO"] == 1
    assert "Persona Ficticia" not in report_text and "example.test" not in report_text


def test_source_is_byte_identical_and_second_run_is_idempotent(tmp_path: Path):
    repository, source, output_dir = _external_layout(tmp_path)
    before = source.read_bytes()
    pipeline = AnonymizationPipeline(repository_root=repository)
    first = pipeline.run(source, output_dir)
    second = pipeline.run(source, output_dir)
    assert source.read_bytes() == before
    assert first.output.read_bytes() == second.output.read_bytes()
    assert first.report.read_bytes() == second.report.read_bytes()


def test_refuses_source_inside_repository(tmp_path: Path):
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "chat.txt"
    source.write_text(SYNTHETIC_CHAT, encoding="utf-8")
    with pytest.raises(PrivacyError, match="no se genero salida"):
        AnonymizationPipeline(repository_root=repository).run(source, tmp_path / "output")


def test_refuses_output_beside_source_or_inside_repository(tmp_path: Path):
    repository, source, _ = _external_layout(tmp_path)
    pipeline = AnonymizationPipeline(repository_root=repository)
    with pytest.raises(PrivacyError, match="separada"):
        pipeline.run(source, source.parent)
    with pytest.raises(PrivacyError, match="separada"):
        pipeline.run(source, repository / "generated")


@pytest.mark.parametrize(
    "name,content",
    [("unknown.csv", "a,b"), ("broken.json", "{bad"), ("unknown.txt", "texto sin estructura")],
)
def test_unknown_or_malformed_formats_fail_closed(tmp_path: Path, name: str, content: str):
    repository = tmp_path / "repository"
    source_dir = tmp_path / "source"
    repository.mkdir()
    source_dir.mkdir()
    source = source_dir / name
    source.write_text(content, encoding="utf-8")
    output = tmp_path / "output"
    with pytest.raises(PrivacyError):
        AnonymizationPipeline(repository_root=repository).run(source, output)
    assert not output.exists() or not any(output.iterdir())


def test_existing_different_output_is_never_overwritten(tmp_path: Path):
    repository, source, output_dir = _external_layout(tmp_path)
    output_dir.mkdir()
    protected = output_dir / "synthetic-chat.anonymized.txt"
    protected.write_text("protected", encoding="utf-8")
    with pytest.raises(PrivacyError, match="contenido diferente"):
        AnonymizationPipeline(repository_root=repository).run(source, output_dir)
    assert protected.read_text(encoding="utf-8") == "protected"


def test_structured_json_redacts_metadata_and_rejects_unknown_fields(tmp_path: Path):
    repository = tmp_path / "repository"
    source_dir = tmp_path / "source"
    repository.mkdir()
    source_dir.mkdir()
    source = source_dir / "synthetic.json"
    source.write_text(json.dumps({"messages": [{
        "timestamp": "2026-08-12T10:00:00-03:00",
        "sender": "Persona Sintetica Tres",
        "text": "escribime a sintetic@example.test",
        "metadata": {"account": "+595 982 222 333"},
    }]}), encoding="utf-8")
    result = AnonymizationPipeline(repository_root=repository).run(source, tmp_path / "output")
    assert "example.test" not in result.output.read_text(encoding="utf-8")
    source.write_text(json.dumps({"messages": [{"timestamp": "x", "sender": "y", "text": "z", "secret": "x"}]}), encoding="utf-8")
    with pytest.raises(PrivacyError):
        AnonymizationPipeline(repository_root=repository).run(source, tmp_path / "other")


def test_preflight_returns_only_safe_metadata(tmp_path: Path):
    repository, source, _ = _external_layout(tmp_path)
    result = inspect_export(source, repository_root=repository)
    assert result["eligible"] is True and result["format"] == "whatsapp-text"
    assert set(result) == {"format", "size_bytes", "sha256", "eligible"}


def test_false_positives_keep_products_amounts_branches_and_unrelated_dates(tmp_path: Path):
    repository = tmp_path / "repository"
    source_dir = tmp_path / "source"
    repository.mkdir()
    source_dir.mkdir()
    source = source_dir / "analytics.txt"
    source.write_text(
        "12/08/2026, 10:00 - Cliente Sintetico: Quiero Cristal Azul en Sucursal Centro por Gs. 1.250.000 para el 20/08/2026\n",
        encoding="utf-8",
    )
    result = AnonymizationPipeline(repository_root=repository).run(source, tmp_path / "output")
    output = result.output.read_text(encoding="utf-8")
    assert "Cristal Azul" in output
    assert "Sucursal Centro" in output
    assert "Gs. 1.250.000" in output
    assert "20/08/2026" in output


def test_repeatable_pseudonyms_reset_between_imports(tmp_path: Path):
    repository, source, output_dir = _external_layout(tmp_path)
    first = AnonymizationPipeline(repository_root=repository).run(source, output_dir)
    other_output = tmp_path / "other-output"
    second = AnonymizationPipeline(repository_root=repository).run(source, other_output)
    assert first.output.read_text(encoding="utf-8") == second.output.read_text(encoding="utf-8")
    assert not list(output_dir.glob("*identity*"))
    assert not list(other_output.glob("*identity*"))
