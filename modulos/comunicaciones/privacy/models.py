from __future__ import annotations

from dataclasses import dataclass, field


RULES_VERSION = "1.0.0"


@dataclass(frozen=True)
class ChatRecord:
    timestamp: str
    sender: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SafeReport:
    input_sha256: str
    format: str
    detected: dict[str, int]
    rejected_records: int
    warnings: list[str]
    rules_version: str = RULES_VERSION
    status: str = "PASS"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "rules_version": self.rules_version,
            "input_sha256": self.input_sha256,
            "format": self.format,
            "detected": dict(sorted(self.detected.items())),
            "rejected_records": self.rejected_records,
            "warnings": self.warnings,
        }
