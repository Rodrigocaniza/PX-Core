"""Serializacion canonica y base64url.

Firmar y verificar tienen que ver exactamente los mismos bytes. `json.dumps`
por defecto no lo garantiza: el orden de las claves y los espacios cambian con
como se construyo el diccionario. Todo lo que se firma pasa por aca.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Mapping


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    """Bytes canonicos de un documento: claves ordenadas, sin espacios, UTF-8.

    `ensure_ascii=False` a proposito: el nombre del negocio puede llevar tildes
    y escaparlas produciria bytes distintos segun quien serialice.
    """
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def b64u_encode(raw: bytes) -> str:
    """base64url sin relleno: entra en JSON, en una URL y en un nombre de archivo."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64u_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)
