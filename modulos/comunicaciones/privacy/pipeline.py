from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .adapters import UnsupportedExport, adapter_for
from .detection import Pseudonymizer, residual_candidates
from .models import ChatRecord, SafeReport
from .preflight import _inside, inspect_export


class PrivacyError(RuntimeError):
    """Error deliberadamente sin datos ni rutas sensibles."""


@dataclass(frozen=True)
class PipelineResult:
    output: Path
    report: Path
    status: str


class AnonymizationPipeline:
    def __init__(self, *, repository_root: str | Path) -> None:
        self.repository_root = Path(repository_root).resolve(strict=True)

    def run(self, source: str | Path, output_directory: str | Path) -> PipelineResult:
        try:
            source_path = Path(source).expanduser().resolve(strict=True)
            destination = Path(output_directory).expanduser().resolve()
            facts = inspect_export(source_path, repository_root=self.repository_root)
            if _inside(destination, self.repository_root) or destination == source_path.parent:
                raise PrivacyError("la salida debe estar separada de la fuente y del repositorio")
            destination.mkdir(parents=True, exist_ok=True)
            adapter = adapter_for(source_path)
            raw = source_path.read_text(encoding="utf-8-sig")
            records = adapter.parse(raw)
            redactor = Pseudonymizer()
            sanitized = [self._sanitize(record, redactor) for record in records]
            rendered = adapter.render(sanitized)
            residual = residual_candidates(rendered)
            if residual:
                raise PrivacyError("la validacion residual rechazo la salida")
            suffix = ".anonymized.json" if source_path.suffix.lower() == ".json" else ".anonymized.txt"
            output = destination / (source_path.stem + suffix)
            report_path = destination / (source_path.stem + ".anonymization-report.json")
            report = SafeReport(
                input_sha256=str(facts["sha256"]),
                format=str(facts["format"]),
                detected=dict(redactor.counts),
                rejected_records=0,
                warnings=[],
            )
            report_content = json.dumps(report.as_dict(), indent=2, ensure_ascii=True) + "\n"
            self._assert_publishable(output, rendered)
            self._assert_publishable(report_path, report_content)
            self._atomic_write(output, rendered)
            self._atomic_write(report_path, report_content)
            return PipelineResult(output, report_path, "PASS")
        except (OSError, UnicodeError, UnsupportedExport, ValueError, PrivacyError) as exc:
            if isinstance(exc, PrivacyError):
                raise
            raise PrivacyError("anonimizacion rechazada; no se genero salida utilizable") from None

    @staticmethod
    def _sanitize(record: ChatRecord, redactor: Pseudonymizer) -> ChatRecord:
        sender = redactor.redact_identity(record.sender)
        text = redactor.redact_text(record.text)
        metadata = {redactor.redact_text(k): redactor.redact_text(v) for k, v in record.metadata.items()}
        return ChatRecord(record.timestamp, sender, text, metadata)

    @staticmethod
    def _assert_publishable(path: Path, content: str) -> None:
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise PrivacyError("la salida ya existe con contenido diferente")

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                return
            raise PrivacyError("la salida ya existe con contenido diferente")
        fd, temporary = tempfile.mkstemp(prefix=".privacy-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
