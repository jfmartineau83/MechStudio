from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .models import ParameterOption, ParameterSpec, ParameterType


@dataclass(slots=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


@dataclass(slots=True)
class ModuleCandidate:
    name: str
    parameters: list[str]


@dataclass(slots=True)
class ParseIssue:
    parameter: str
    message: str


@dataclass(slots=True)
class ParseResult:
    metadata: dict[str, str]
    parameters: list[ParameterSpec]
    candidates: list[ModuleCandidate]
    issues: list[ParseIssue] = field(default_factory=list)


class ScadSyntaxError(ValueError):
    pass


class ScadLexer:
    """Tokenizer for the supported Customizer-facing OpenSCAD subset."""

    def tokenize(self, source: str) -> list[Token]:
        result: list[Token] = []
        index, line, column = 0, 1, 1
        length = len(source)
        while index < length:
            char = source[index]
            if char in " \t\r":
                index += 1
                column += 1
                continue
            if char == "\n":
                index += 1
                line += 1
                column = 1
                continue
            if source.startswith("//", index):
                end = source.find("\n", index)
                if end < 0:
                    end = length
                result.append(Token("COMMENT", source[index + 2 : end].strip(), line, column))
                column += end - index
                index = end
                continue
            if source.startswith("/*", index):
                end = source.find("*/", index + 2)
                if end < 0:
                    raise ScadSyntaxError(f"Unterminated block comment at line {line}")
                value = source[index + 2 : end].strip()
                result.append(Token("COMMENT", value, line, column))
                consumed = source[index : end + 2]
                newlines = consumed.count("\n")
                if newlines:
                    line += newlines
                    column = len(consumed.rsplit("\n", 1)[-1]) + 1
                else:
                    column += len(consumed)
                index = end + 2
                continue
            if char == '"':
                start_line, start_column = line, column
                index += 1
                column += 1
                pieces: list[str] = []
                while index < length:
                    current = source[index]
                    if current == '"':
                        index += 1
                        column += 1
                        break
                    if current == "\\" and index + 1 < length:
                        escape = source[index + 1]
                        pieces.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(escape, escape))
                        index += 2
                        column += 2
                        continue
                    if current == "\n":
                        raise ScadSyntaxError(f"Unterminated string at line {start_line}")
                    pieces.append(current)
                    index += 1
                    column += 1
                else:
                    raise ScadSyntaxError(f"Unterminated string at line {start_line}")
                result.append(Token("STRING", "".join(pieces), start_line, start_column))
                continue
            if char.isalpha() or char in "_$":
                start = index
                start_column = column
                while index < length and (source[index].isalnum() or source[index] in "_$"):
                    index += 1
                    column += 1
                result.append(Token("IDENT", source[start:index], line, start_column))
                continue
            if char.isdigit() or (char == "." and index + 1 < length and source[index + 1].isdigit()):
                start = index
                start_column = column
                number = re.match(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", source[index:])
                assert number
                value = number.group(0)
                index += len(value)
                column += len(value)
                result.append(Token("NUMBER", value, line, start_column))
                continue
            result.append(Token("SYMBOL", char, line, column))
            index += 1
            column += 1
        return result


def _annotation_values(text: str, marker: str) -> dict[str, str]:
    position = text.find(marker)
    if position < 0:
        return {}
    try:
        words = shlex.split(text[position + len(marker) :], posix=True)
    except ValueError as exc:
        raise ScadSyntaxError(f"Invalid {marker} annotation: {exc}") from exc
    result: dict[str, str] = {}
    for word in words:
        if "=" in word:
            key, value = word.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def _parse_literal(tokens: list[Token]) -> Any:
    if not tokens:
        raise ScadSyntaxError("Missing default value")
    if len(tokens) == 1:
        token = tokens[0]
        if token.kind == "NUMBER":
            number = float(token.value)
            return int(number) if number.is_integer() and "." not in token.value and "e" not in token.value.lower() else number
        if token.kind == "STRING":
            return token.value
        if token.kind == "IDENT" and token.value in {"true", "false"}:
            return token.value == "true"
    if len(tokens) == 2 and tokens[0].value in {"+", "-"} and tokens[1].kind == "NUMBER":
        value = float(tokens[1].value)
        value = -value if tokens[0].value == "-" else value
        return int(value) if value.is_integer() and "." not in tokens[1].value else value
    if tokens[0].value == "[" and tokens[-1].value == "]":
        values: list[Any] = []
        chunk: list[Token] = []
        for token in tokens[1:-1] + [Token("SYMBOL", ",", tokens[-1].line, 0)]:
            if token.value == ",":
                if chunk:
                    value = _parse_literal(chunk)
                    if not isinstance(value, (int, float)):
                        raise ScadSyntaxError("Only numeric vectors are supported")
                    values.append(value)
                    chunk = []
            else:
                chunk.append(token)
        return values
    raise ScadSyntaxError("Default must be a number, boolean, string, or numeric vector")


def _customizer_suffix(comments: Iterable[str]) -> str | None:
    for comment in comments:
        if "@mps" in comment:
            continue
        match = re.search(r"\[([^\[\]]+)\]", comment)
        if match:
            return match.group(1).strip()
    return None


def _range_and_options(suffix: str | None) -> tuple[float | None, float | None, float | None, list[ParameterOption]]:
    if not suffix:
        return None, None, None, []
    parts = [part.strip() for part in suffix.split(",")]
    if len(parts) == 1:
        range_parts = [part.strip() for part in parts[0].split(":")]
        if len(range_parts) == 3:
            try:
                minimum, step, maximum = map(float, range_parts)
                return minimum, maximum, step, []
            except ValueError:
                pass
    options: list[ParameterOption] = []
    for part in parts:
        if not part:
            continue
        if ":" in part:
            value, label = part.split(":", 1)
        else:
            value, label = part, part
        stripped = value.strip().strip('"')
        try:
            parsed: Any = float(stripped)
            if parsed.is_integer():
                parsed = int(parsed)
        except ValueError:
            parsed = stripped
        options.append(ParameterOption(parsed, label.strip().strip('"')))
    return None, None, None, options


class ScadCustomizerParser:
    def parse_file(self, path: Path) -> ParseResult:
        return self.parse(path.read_text(encoding="utf-8-sig"))

    def parse(self, source: str) -> ParseResult:
        tokens = ScadLexer().tokenize(source)
        metadata: dict[str, str] = {}
        for token in tokens:
            if token.kind == "COMMENT" and "@mps " in token.value and "@mps-param" not in token.value:
                metadata.update(_annotation_values(token.value, "@mps"))

        parameters: list[ParameterSpec] = []
        issues: list[ParseIssue] = []
        candidates: list[ModuleCandidate] = []
        group = "Parameters"
        pending_annotation: dict[str, str] = {}
        depth = 0
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.kind == "COMMENT":
                section = re.fullmatch(r"\[\s*([^\]]+)\s*\]", token.value)
                if section:
                    group = section.group(1).strip()
                if "@mps-param" in token.value:
                    pending_annotation = _annotation_values(token.value, "@mps-param")
                index += 1
                continue
            if token.value in "{(":
                depth += 1
            elif token.value in "})":
                depth = max(0, depth - 1)

            if token.kind == "IDENT" and token.value == "module" and index + 2 < len(tokens):
                name_token = tokens[index + 1]
                open_token = tokens[index + 2]
                if name_token.kind == "IDENT" and open_token.value == "(":
                    args: list[str] = []
                    cursor, local_depth = index + 3, 1
                    while cursor < len(tokens) and local_depth:
                        current = tokens[cursor]
                        if current.value == "(":
                            local_depth += 1
                        elif current.value == ")":
                            local_depth -= 1
                        elif local_depth == 1 and current.kind == "IDENT":
                            previous = tokens[cursor - 1].value if cursor else "("
                            if previous in {"(", ","}:
                                args.append(current.value)
                        cursor += 1
                    candidates.append(ModuleCandidate(name_token.value, args))

            if depth == 0 and token.kind == "IDENT" and index + 1 < len(tokens) and tokens[index + 1].value == "=":
                name = token.value
                cursor = index + 2
                literal_tokens: list[Token] = []
                square_depth = 0
                while cursor < len(tokens):
                    current = tokens[cursor]
                    if current.kind == "COMMENT":
                        cursor += 1
                        continue
                    if current.value == "[":
                        square_depth += 1
                    elif current.value == "]":
                        square_depth -= 1
                    if current.value == ";" and square_depth == 0:
                        break
                    literal_tokens.append(current)
                    cursor += 1
                if cursor >= len(tokens):
                    raise ScadSyntaxError(f"Missing ';' after {name} on line {token.line}")
                assignment_line = token.line
                same_line_comments = [
                    item.value for item in tokens if item.kind == "COMMENT" and item.line == assignment_line
                ]
                annotation = dict(pending_annotation)
                for comment in same_line_comments:
                    if "@mps-param" in comment:
                        annotation.update(_annotation_values(comment, "@mps-param"))
                pending_annotation = {}

                if name.startswith("$") or group.strip().lower() == "hidden":
                    index = cursor + 1
                    continue
                try:
                    default = _parse_literal(literal_tokens)
                except ScadSyntaxError as exc:
                    issues.append(ParseIssue(name, str(exc)))
                    index = cursor + 1
                    continue
                suffix = _customizer_suffix(same_line_comments)
                minimum, maximum, step, options = _range_and_options(suffix)
                type_name = annotation.get("type")
                parameter_type: ParameterType | None = None
                if type_name:
                    try:
                        parameter_type = ParameterType(type_name.lower())
                    except ValueError:
                        issues.append(ParseIssue(name, f"Unsupported parameter type '{type_name}'"))
                elif isinstance(default, bool):
                    parameter_type = ParameterType.BOOLEAN
                elif isinstance(default, str):
                    parameter_type = ParameterType.ENUM if options else ParameterType.TEXT
                elif isinstance(default, list):
                    parameter_type = ParameterType.VECTOR
                elif options:
                    parameter_type = ParameterType.ENUM
                else:
                    issues.append(ParseIssue(name, "Numeric intent is ambiguous; choose length, angle, count, ratio, percentage, or float"))

                if parameter_type:
                    parameters.append(
                        ParameterSpec(
                            name=name,
                            label=annotation.get("label", name.replace("_", " ").title()),
                            parameter_type=parameter_type,
                            default=default,
                            group=group,
                            description=annotation.get("description", ""),
                            minimum=minimum,
                            maximum=maximum,
                            step=step,
                            options=options,
                            visible_if=annotation.get("visible_if"),
                        )
                    )
                index = cursor + 1
                continue
            index += 1
        return ParseResult(metadata, parameters, candidates, issues)

