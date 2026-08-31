"""Contrato y catálogo local de capturas experimentales."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
VALID_KINDS = {"baseline", "human", "vehicle", "unknown"}
VALID_STATUSES = {
    "created", "capturing", "captured", "processing", "completed", "failed"
}


@dataclass(frozen=True)
class Capture:
    """Una captura y todas las rutas definidas por su contrato."""

    capture_id: str
    root: Path
    metadata: dict[str, Any]

    @property
    def display_name(self) -> str:
        return str(self.metadata["name"])

    @property
    def kind(self) -> str:
        return str(self.metadata.get("kind", "unknown"))

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.root / "processed"

    def file(self, section: str, filename: str) -> Path:
        directories = {
            "config": self.config_dir,
            "raw": self.raw_dir,
            "processed": self.processed_dir,
        }
        try:
            return directories[section] / filename
        except KeyError as error:
            raise ValueError(f"Sección de captura desconocida: {section}") from error


class CaptureRepository:
    """Crea y descubre capturas almacenadas bajo un único directorio."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def discover(self) -> list[Capture]:
        if not self.root.exists():
            return []

        captures = []
        for metadata_path in self.root.glob("*/metadata.json"):
            metadata = self._read_metadata(metadata_path)
            capture = Capture(metadata_path.parent.name, metadata_path.parent, metadata)
            self.validate(capture)
            captures.append(capture)

        return sorted(
            captures,
            key=lambda item: str(item.metadata.get("created_at", "")),
            reverse=True,
        )

    def get(self, capture_id: str) -> Capture:
        capture_dir = self.root / capture_id
        metadata_path = capture_dir / "metadata.json"
        if not metadata_path.is_file():
            raise FileNotFoundError(f"No existe la captura: {capture_id}")
        capture = Capture(capture_id, capture_dir, self._read_metadata(metadata_path))
        self.validate(capture)
        return capture

    def create(self, name: str, kind: str = "unknown", notes: str = "") -> Capture:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("La captura debe tener un nombre.")
        if kind not in VALID_KINDS:
            raise ValueError(f"Tipo de captura inválido: {kind}")

        now = datetime.now().astimezone()
        base_id = f"{now:%Y-%m-%d_%H%M%S}_{_slugify(clean_name)}"
        capture_id = base_id
        suffix = 2
        while (self.root / capture_id).exists():
            capture_id = f"{base_id}-{suffix}"
            suffix += 1

        capture_dir = self.root / capture_id
        for section in ("config", "raw", "processed"):
            (capture_dir / section).mkdir(parents=True, exist_ok=False)

        metadata = {
            "schema_version": SCHEMA_VERSION,
            "capture_id": capture_id,
            "name": clean_name,
            "kind": kind,
            "status": "created",
            "created_at": now.isoformat(timespec="seconds"),
            "notes": notes.strip(),
            "expected_movement": kind in {"human", "vehicle"} if kind != "unknown" else None,
        }
        _write_json(capture_dir / "metadata.json", metadata)
        return Capture(capture_id, capture_dir, metadata)

    def update_status(self, capture_id: str, status: str, error: str | None = None) -> Capture:
        if status not in VALID_STATUSES:
            raise ValueError(f"Estado de captura inválido: {status}")

        capture = self.get(capture_id)
        metadata = dict(capture.metadata)
        metadata["status"] = status
        metadata["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if error:
            metadata["error"] = error
        else:
            metadata.pop("error", None)
        _write_json(capture.root / "metadata.json", metadata)
        return Capture(capture_id, capture.root, metadata)

    def update_metadata(self, capture_id: str, **changes: Any) -> Capture:
        protected = {"schema_version", "capture_id"}
        if protected.intersection(changes):
            raise ValueError("No se pueden modificar los identificadores del contrato.")
        capture = self.get(capture_id)
        metadata = dict(capture.metadata)
        metadata.update(changes)
        metadata["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        _write_json(capture.root / "metadata.json", metadata)
        updated = Capture(capture_id, capture.root, metadata)
        self.validate(updated)
        return updated

    @staticmethod
    def validate(capture: Capture) -> None:
        metadata = capture.metadata
        required = {"schema_version", "capture_id", "name", "kind", "status", "created_at"}
        missing = required - metadata.keys()
        if missing:
            raise ValueError(f"{capture.root}: faltan metadatos {sorted(missing)}")
        if metadata["capture_id"] != capture.capture_id:
            raise ValueError(f"{capture.root}: capture_id no coincide con la carpeta")
        if metadata["kind"] not in VALID_KINDS:
            raise ValueError(f"{capture.root}: tipo de captura inválido")
        if metadata["status"] not in VALID_STATUSES:
            raise ValueError(f"{capture.root}: estado de captura inválido")
        for section in (capture.config_dir, capture.raw_dir, capture.processed_dir):
            if not section.is_dir():
                raise ValueError(f"{capture.root}: falta la carpeta {section.name}")

    @staticmethod
    def _read_metadata(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8-sig") as file:
            return json.load(file)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or "captura"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
