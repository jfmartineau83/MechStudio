from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .models import FeatureModule, ParameterSpec, ParameterType
from .scad_parser import ModuleCandidate, ParseIssue, ParseResult, ScadCustomizerParser


class ModuleImportError(ValueError):
    pass


@dataclass(slots=True)
class ImportInspection:
    source: Path
    scad_files: list[str]


def _safe_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    if not result:
        raise ModuleImportError("Module ID contains no usable characters")
    return result


def _safe_extract(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            relative = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if relative.is_absolute() or ".." in relative.parts:
                raise ModuleImportError(f"Unsafe path in package: {info.filename}")
            if stat.S_ISLNK(mode):
                raise ModuleImportError(f"Symbolic links are not allowed in packages: {info.filename}")
            target = destination.joinpath(*relative.parts)
            resolved = target.resolve()
            if destination.resolve() not in (resolved, *resolved.parents):
                raise ModuleImportError(f"Unsafe path in package: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source_handle, target.open("wb") as target_handle:
                shutil.copyfileobj(source_handle, target_handle)


class ModuleRegistry:
    def __init__(self, modules_dir: Path):
        self.modules_dir = modules_dir
        self.parser = ScadCustomizerParser()
        self._modules: dict[str, FeatureModule] = {}

    @property
    def modules(self) -> list[FeatureModule]:
        return sorted(self._modules.values(), key=lambda item: item.name.casefold())

    @property
    def enabled_modules(self) -> list[FeatureModule]:
        return [item for item in self.modules if item.enabled]

    def get(self, module_id: str) -> FeatureModule | None:
        return self._modules.get(module_id)

    def reload(self) -> list[str]:
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        found: dict[str, FeatureModule] = {}
        errors: list[str] = []
        for metadata_path in self.modules_dir.glob("*/.mps.json"):
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                module = FeatureModule.from_dict(data, metadata_path.parent)
                if not module.source_path.is_file():
                    raise FileNotFoundError(module.source_path)
                found[module.module_id] = module
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                errors.append(f"{metadata_path.parent.name}: {exc}")
        self._modules = found
        return errors

    def inspect(self, source: Path) -> ImportInspection:
        source = source.resolve()
        if not source.is_file():
            raise ModuleImportError(f"File does not exist: {source}")
        if source.suffix.lower() == ".scad":
            return ImportInspection(source, [source.name])
        if source.suffix.lower() != ".zip":
            raise ModuleImportError("Choose an OpenSCAD .scad file or a .zip package")
        with zipfile.ZipFile(source) as bundle:
            files = []
            for info in bundle.infolist():
                relative = PurePosixPath(info.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ModuleImportError(f"Unsafe path in package: {info.filename}")
                if not info.is_dir() and relative.suffix.lower() == ".scad":
                    files.append(info.filename)
        if not files:
            raise ModuleImportError("The package contains no .scad source")
        return ImportInspection(source, sorted(files))

    def preview(self, source: Path, main_relative: str | None = None) -> ParseResult:
        source = source.resolve()
        if source.suffix.lower() == ".scad":
            return self.parser.parse_file(source)
        with tempfile.TemporaryDirectory(prefix="mps-preview-") as temporary:
            root = Path(temporary)
            _safe_extract(source, root)
            candidates = sorted(root.rglob("*.scad"))
            selected = root.joinpath(*PurePosixPath(main_relative).parts) if main_relative else candidates[0]
            if selected not in candidates:
                raise ModuleImportError("Selected source is not part of the package")
            return self.parser.parse_file(selected)

    def install(
        self,
        source: Path,
        *,
        main_relative: str | None = None,
        type_resolutions: dict[str, ParameterType] | None = None,
        generator: str | None = None,
        replace: bool = False,
    ) -> FeatureModule:
        source = source.resolve()
        type_resolutions = type_resolutions or {}
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        stage_parent = Path(tempfile.mkdtemp(prefix="mps-import-", dir=self.modules_dir))
        try:
            content = stage_parent / "content"
            content.mkdir()
            if source.suffix.lower() == ".scad":
                main_source = content / source.name
                shutil.copy2(source, main_source)
                original_source = source.name
            elif source.suffix.lower() == ".zip":
                _safe_extract(source, content)
                scad_files = sorted(content.rglob("*.scad"))
                if not scad_files:
                    raise ModuleImportError("The package contains no .scad source")
                if main_relative:
                    main_source = content.joinpath(*PurePosixPath(main_relative).parts)
                    if main_source not in scad_files:
                        raise ModuleImportError("Selected source is not part of the package")
                else:
                    main_source = scad_files[0]
                original_source = main_source.relative_to(content).as_posix()
            else:
                raise ModuleImportError("Choose an OpenSCAD .scad file or a .zip package")

            parsed = self.parser.parse_file(main_source)
            parameters = list(parsed.parameters)
            unresolved = {issue.parameter: issue for issue in parsed.issues}
            if type_resolutions:
                reparsed_source = main_source.read_text(encoding="utf-8-sig")
                # Resolutions are attached to already parsed literal assignments by a
                # focused second pass; source remains untouched.
                for name, parameter_type in type_resolutions.items():
                    issue = unresolved.get(name)
                    if not issue:
                        continue
                    resolved = self._resolved_parameter(reparsed_source, name, parameter_type)
                    if resolved:
                        parameters.append(resolved)
                        unresolved.pop(name, None)
            if unresolved:
                messages = "; ".join(f"{name}: {issue.message}" for name, issue in unresolved.items())
                raise ModuleImportError(f"Parameter metadata needs clarification: {messages}")
            if not parameters:
                raise ModuleImportError("No exposed Customizer parameters were found")

            metadata = parsed.metadata
            digest = hashlib.sha256(main_source.read_bytes()).hexdigest()[:12]
            module_id = _safe_id(metadata.get("id", f"local.{main_source.stem}.{digest}"))
            module_name = metadata.get("name", main_source.stem.replace("_", " ").title())
            version = metadata.get("version", "0.1.0")
            chosen_generator = generator or metadata.get("generator")
            entry_source = main_source
            if chosen_generator:
                candidate = next((item for item in parsed.candidates if item.name == chosen_generator), None)
                if not candidate:
                    raise ModuleImportError(f"Generator module '{chosen_generator}' was not found")
                entry_source = content / "entrypoint.scad"
                relative = os.path.relpath(main_source, content).replace("\\", "/")
                exposed_names = {parameter.name for parameter in parameters}
                arguments = [name for name in candidate.parameters if name in exposed_names]
                defaults = "\n".join(
                    f"{parameter.name} = {self._literal(parameter.default)};" for parameter in parameters
                )
                calls = ", ".join(f"{name}={name}" for name in arguments)
                entry_source.write_text(
                    f"// Generated compatibility wrapper; original is unchanged.\n{defaults}\n"
                    f"use <{relative}>;\n{chosen_generator}({calls});\n",
                    encoding="utf-8",
                )

            final_dir = self.modules_dir / module_id
            if final_dir.exists() and not replace:
                raise ModuleImportError(f"Module '{module_id}' is already installed")
            module = FeatureModule(
                module_id=module_id,
                version=version,
                name=module_name,
                description=metadata.get("description", ""),
                source_path=final_dir / entry_source.relative_to(content),
                parameters=sorted(parameters, key=lambda item: (item.group, item.name)),
                enabled=True,
                original_source=original_source,
                generator=chosen_generator,
            )
            metadata_data = module.to_dict(final_dir)
            (content / ".mps.json").write_text(json.dumps(metadata_data, indent=2), encoding="utf-8")
            if final_dir.exists():
                shutil.rmtree(final_dir)
            content.replace(final_dir)
            self.reload()
            return self._modules[module_id]
        finally:
            if stage_parent.exists():
                shutil.rmtree(stage_parent, ignore_errors=True)

    def _resolved_parameter(self, source: str, name: str, parameter_type: ParameterType) -> ParameterSpec | None:
        # Reuse the lexer/parser by injecting an in-memory annotation immediately
        # before only the named top-level assignment. This is metadata resolution,
        # never a mutation of the installed source.
        pattern = re.compile(rf"(?m)^(\s*)({re.escape(name)}\s*=)")
        patched, count = pattern.subn(rf"\1// @mps-param type={parameter_type.value}\n\1\2", source, count=1)
        if not count:
            return None
        result = self.parser.parse(patched)
        return next((item for item in result.parameters if item.name == name), None)

    @staticmethod
    def _literal(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, list):
            return "[" + ", ".join(str(item) for item in value) + "]"
        return str(value)

    def set_enabled(self, module_id: str, enabled: bool) -> None:
        module = self._modules[module_id]
        module.enabled = enabled
        directory = module.source_path.parent
        while directory != self.modules_dir and not (directory / ".mps.json").exists():
            directory = directory.parent
        metadata_path = directory / ".mps.json"
        metadata_path.write_text(json.dumps(module.to_dict(directory), indent=2), encoding="utf-8")
        self.reload()

    def remove(self, module_id: str) -> None:
        module = self._modules[module_id]
        directory = module.source_path.parent
        while directory != self.modules_dir and not (directory / ".mps.json").exists():
            directory = directory.parent
        if directory == self.modules_dir or directory.parent != self.modules_dir:
            raise ModuleImportError("Refusing to remove a path outside the module registry")
        shutil.rmtree(directory)
        self.reload()

    def save_preset(self, presets_dir: Path, module: FeatureModule, name: str, values: dict[str, str]) -> Path:
        presets_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_id(name)
        path = presets_dir / f"{_safe_id(module.module_id)}--{safe_name}.json"
        path.write_text(
            json.dumps({"module_id": module.module_id, "name": name, "values": values}, indent=2),
            encoding="utf-8",
        )
        return path

    def list_presets(self, presets_dir: Path, module_id: str) -> list[tuple[str, Path]]:
        result: list[tuple[str, Path]] = []
        if not presets_dir.exists():
            return result
        for path in presets_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("module_id") == module_id:
                    result.append((data.get("name", path.stem), path))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(result, key=lambda item: item[0].casefold())

