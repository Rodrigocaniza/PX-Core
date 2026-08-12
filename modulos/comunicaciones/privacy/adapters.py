from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ChatRecord


class UnsupportedExport(ValueError):
    pass


_WA_LINE = re.compile(
    r"^(?P<timestamp>\[?\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?:\s*[ap]\.??\s*m\.?)?\]?)\s*[-–]\s*(?P<sender>[^:]{1,120}):\s*(?P<text>.*)$",
    re.IGNORECASE,
)


class WhatsAppTextAdapter:
    name = "whatsapp-text"

    def parse(self, text: str) -> list[ChatRecord]:
        records: list[ChatRecord] = []
        for line in text.splitlines():
            match = _WA_LINE.match(line)
            if match:
                records.append(ChatRecord(**match.groupdict()))
            elif records and line.strip():
                previous = records[-1]
                records[-1] = ChatRecord(
                    previous.timestamp,
                    previous.sender,
                    previous.text + "\n" + line,
                    previous.metadata,
                )
            elif line.strip():
                raise UnsupportedExport("estructura de exportacion no reconocida")
        if not records:
            raise UnsupportedExport("estructura de exportacion no reconocida")
        return records

    def render(self, records: list[ChatRecord]) -> str:
        return "\n".join(f"{r.timestamp} - {r.sender}: {r.text}" for r in records) + "\n"


class StructuredJsonAdapter:
    name = "structured-json-v1"
    allowed_keys = {"timestamp", "sender", "text", "metadata"}

    def parse(self, text: str) -> list[ChatRecord]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UnsupportedExport("JSON malformado") from exc
        rows = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise UnsupportedExport("JSON sin lista messages")
        records = []
        for row in rows:
            if not isinstance(row, dict) or set(row) - self.allowed_keys:
                raise UnsupportedExport("registro JSON con campos no admitidos")
            if not all(isinstance(row.get(key), str) for key in ("timestamp", "sender", "text")):
                raise UnsupportedExport("registro JSON incompleto")
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()
            ):
                raise UnsupportedExport("metadata JSON invalida")
            records.append(ChatRecord(row["timestamp"], row["sender"], row["text"], metadata))
        return records

    def render(self, records: list[ChatRecord]) -> str:
        payload = {
            "messages": [
                {"timestamp": r.timestamp, "sender": r.sender, "text": r.text, "metadata": r.metadata}
                for r in records
            ]
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def adapter_for(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return WhatsAppTextAdapter()
    if suffix == ".json":
        return StructuredJsonAdapter()
    raise UnsupportedExport("formato no soportado")
