from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "MechanicalPartsStudio"


class AppSettings:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or default_data_dir()
        self.modules_dir = self.data_dir / "modules"
        self.cache_dir = self.data_dir / "cache"
        self.presets_dir = self.data_dir / "presets"
        self.path = self.data_dir / "settings.json"
        self.data: dict[str, Any] = {}
        self.load()

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.modules_dir, self.cache_dir, self.presets_dir):
            path.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.data = {}

    def save(self) -> None:
        self.ensure_directories()
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def add_recent(self, path: Path) -> None:
        resolved = str(path.resolve())
        recent = [item for item in self.get("recent_projects", []) if item != resolved]
        self.data["recent_projects"] = [resolved, *recent][:10]
        self.save()

