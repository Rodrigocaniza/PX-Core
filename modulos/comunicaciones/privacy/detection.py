from __future__ import annotations

import re
from collections import Counter, defaultdict


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)),
    ("TELEFONO", re.compile(r"(?<!\w)(?:\+?595\s*)?(?:0?9\d{2})[\s.-]*\d{3}[\s.-]*\d{3}(?!\w)")),
    ("DOCUMENTO", re.compile(r"(?i)\b(?:CI|C[IÍ]DULA|DNI|DOCUMENTO)\s*(?:N[°ºo]?\s*)?[:#-]?\s*\d[\d.]{4,12}\b")),
    ("FECHA_NACIMIENTO", re.compile(r"(?i)\b(?:nac[ií]|nacimiento|fecha\s+de\s+nacimiento)\w*\s*(?:el|:)?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
    ("DIRECCION", re.compile(r"(?i)\b(?:vivo\s+en|direcci[oó]n|domicilio|calle|avenida|av\.)\s*[:#-]?\s*[^,;\n]{3,80}")),
    ("PEDIDO", re.compile(r"(?i)\b(?:pedido|receta|factura)\s*(?:n[°ºo]?\s*)?[:#-]?\s*[A-Z0-9-]{4,30}\b")),
    ("USUARIO", re.compile(r"(?i)(?<!\w)@[a-z0-9_.-]{3,40}\b")),
    ("NOMBRE", re.compile(r"(?i)\b(?:soy|mi nombre es|me llamo)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+){0,3})")),
    ("DATO_SALUD", re.compile(r"(?i)\b(?:diagn[oó]stico|enfermedad|medicaci[oó]n|alergia|cirug[ií]a|embarazo|diabetes|hipertensi[oó]n)\b[^.;\n]{0,100}")),
    ("ADJUNTO", re.compile(r"(?i)\b[\w .()\[\]-]{1,80}\.(?:jpe?g|png|pdf|docx?|xlsx?|heic|mp4|opus)\b")),
)


class Pseudonymizer:
    def __init__(self) -> None:
        self._values: dict[str, dict[str, str]] = defaultdict(dict)
        self.counts: Counter[str] = Counter()

    def token(self, kind: str, value: str) -> str:
        canonical = " ".join(value.casefold().split())
        if canonical not in self._values[kind]:
            self._values[kind][canonical] = f"[{kind}_{len(self._values[kind]) + 1:03d}]"
            self.counts[kind] += 1
        return self._values[kind][canonical]

    def redact_text(self, text: str) -> str:
        result = text
        for kind, pattern in PATTERNS:
            result = pattern.sub(lambda m, k=kind: self.token(k, m.group(0)), result)
        return result

    def redact_identity(self, value: str, kind: str = "CLIENTE") -> str:
        return self.token(kind, value)


def residual_candidates(text: str) -> list[str]:
    # Los pseudonimos tipados contienen palabras como DIRECCION por diseno;
    # se excluyen del segundo escaneo sin excluir texto circundante.
    text = re.sub(r"\[[A-Z_]+_\d{3}\]", "[REDACTED]", text)
    kinds = []
    for kind, pattern in PATTERNS:
        if pattern.search(text):
            kinds.append(kind)
    return sorted(set(kinds))
