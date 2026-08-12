from __future__ import annotations

import hashlib
from pathlib import Path

from .adapters import adapter_for


MAX_INPUT_BYTES = 100 * 1024 * 1024


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_export(source: str | Path, *, repository_root: str | Path) -> dict[str, object]:
    path = Path(source).expanduser().resolve(strict=True)
    root = Path(repository_root).resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError("la fuente debe ser un archivo regular")
    if _inside(path, root):
        raise ValueError("la fuente real no puede estar dentro del repositorio")
    size = path.stat().st_size
    if not size or size > MAX_INPUT_BYTES:
        raise ValueError("tamano de fuente no admitido")
    adapter = adapter_for(path)
    return {"format": adapter.name, "size_bytes": size, "sha256": sha256_file(path), "eligible": True}
