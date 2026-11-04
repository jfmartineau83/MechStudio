from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ParameterType(str, Enum):
    LENGTH = "length"
    ANGLE = "angle"
    INTEGER = "integer"
    FLOAT = "float"
    RATIO = "ratio"
    PERCENTAGE = "percentage"
    BOOLEAN = "boolean"
    ENUM = "enum"
    TEXT = "text"
    VECTOR = "vector"

    @property
    def numeric(self) -> bool:
        return self in {
            self.LENGTH,
            self.ANGLE,
            self.INTEGER,
            self.FLOAT,
            self.RATIO,
            self.PERCENTAGE,
        }


@dataclass(slots=True)
class ParameterOption:
    value: Any
    label: str


@dataclass(slots=True)
class ParameterSpec:
    name: str
    label: str
    parameter_type: ParameterType
    default: Any
    group: str = "Parameters"
    description: str = ""
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: list[ParameterOption] = field(default_factory=list)
    visible_if: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["parameter_type"] = self.parameter_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParameterSpec":
        copy = dict(data)
        copy["parameter_type"] = ParameterType(copy["parameter_type"])
        copy["options"] = [ParameterOption(**item) for item in copy.get("options", [])]
        return cls(**copy)


@dataclass(slots=True)
class FeatureModule:
    module_id: str
    version: str
    name: str
    description: str
    source_path: Path
    parameters: list[ParameterSpec]
    enabled: bool = True
    original_source: str = ""
    generator: str | None = None

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        source = self.source_path
        if root:
            try:
                source_text = str(source.relative_to(root))
            except ValueError:
                source_text = str(source)
        else:
            source_text = str(source)
        return {
            "schema": 1,
            "module_id": self.module_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "source_path": source_text,
            "parameters": [item.to_dict() for item in self.parameters],
            "enabled": self.enabled,
            "original_source": self.original_source,
            "generator": self.generator,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], root: Path | None = None) -> "FeatureModule":
        source = Path(data["source_path"])
        if root and not source.is_absolute():
            source = root / source
        return cls(
            module_id=data["module_id"],
            version=data.get("version", "0.1.0"),
            name=data.get("name", data["module_id"]),
            description=data.get("description", ""),
            source_path=source,
            parameters=[ParameterSpec.from_dict(item) for item in data.get("parameters", [])],
            enabled=bool(data.get("enabled", True)),
            original_source=data.get("original_source", ""),
            generator=data.get("generator"),
        )


@dataclass(slots=True)
class ParameterValue:
    text: str


@dataclass(slots=True)
class FeatureInstance:
    instance_id: str
    module_id: str
    module_version: str
    name: str
    parameters: dict[str, ParameterValue] = field(default_factory=dict)
    enabled: bool = True
    children: list["FeatureInstance"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "module_id": self.module_id,
            "module_version": self.module_version,
            "name": self.name,
            "parameters": {name: value.text for name, value in self.parameters.items()},
            "enabled": self.enabled,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureInstance":
        return cls(
            instance_id=data["instance_id"],
            module_id=data["module_id"],
            module_version=data.get("module_version", "0.1.0"),
            name=data.get("name", "Part"),
            parameters={k: ParameterValue(str(v)) for k, v in data.get("parameters", {}).items()},
            enabled=bool(data.get("enabled", True)),
            children=[cls.from_dict(item) for item in data.get("children", [])],
        )


@dataclass(slots=True)
class ProjectDocument:
    name: str = "Untitled"
    description: str = ""
    drawing_number: str = ""
    revision_label: str = "A"
    generation_mode: str = "metric"
    components: list[FeatureInstance] = field(default_factory=list)
    active_component: int = 0
    drawing_metadata: dict[str, Any] = field(default_factory=dict)
    document_state: dict[str, Any] = field(default_factory=dict)
    modified: bool = False
    revision: int = 0
    path: Path | None = None

    @property
    def active_feature(self) -> FeatureInstance | None:
        if 0 <= self.active_component < len(self.components):
            return self.components[self.active_component]
        return None

    def touch(self) -> None:
        self.modified = True
        self.revision += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "mechanical-parts-studio-project",
            "schema": 1,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "name": self.name,
            "description": self.description,
            "drawing_number": self.drawing_number,
            "revision_label": self.revision_label,
            "generation_mode": self.generation_mode,
            "components": [item.to_dict() for item in self.components],
            "active_component": self.active_component,
            "drawing_metadata": self.drawing_metadata,
            "document_state": self.document_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path | None = None) -> "ProjectDocument":
        if data.get("format") != "mechanical-parts-studio-project":
            raise ValueError("This is not a Mechanical Parts Studio project")
        if int(data.get("schema", 0)) != 1:
            raise ValueError(f"Unsupported project schema: {data.get('schema')}")
        return cls(
            name=data.get("name", "Untitled"),
            description=data.get("description", ""),
            drawing_number=data.get("drawing_number", ""),
            revision_label=data.get("revision_label", "A"),
            generation_mode=data.get("generation_mode", "metric"),
            components=[FeatureInstance.from_dict(item) for item in data.get("components", [])],
            active_component=int(data.get("active_component", 0)),
            drawing_metadata=dict(data.get("drawing_metadata", {})),
            document_state=dict(data.get("document_state", {})),
            modified=False,
            revision=0,
            path=path,
        )


@dataclass(slots=True)
class GenerationSnapshot:
    document_revision: int
    mode: str
    stl_path: Path
    parameters_mm: dict[str, Any]
    bounds: tuple[float, float, float, float, float, float]

    def current_for(self, document: ProjectDocument) -> bool:
        return self.document_revision == document.revision and self.mode == document.generation_mode

