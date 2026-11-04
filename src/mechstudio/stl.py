from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path


Vec3 = tuple[float, float, float]
Triangle = tuple[Vec3, Vec3, Vec3]


class StlError(ValueError):
    pass


@dataclass(slots=True)
class Mesh:
    triangles: list[Triangle]
    bounds: tuple[float, float, float, float, float, float]

    @property
    def dimensions(self) -> tuple[float, float, float]:
        xmin, xmax, ymin, ymax, zmin, zmax = self.bounds
        return xmax - xmin, ymax - ymin, zmax - zmin


def _make_mesh(triangles: list[Triangle]) -> Mesh:
    if not triangles:
        raise StlError("The STL contains no triangles")
    coords = [vertex for triangle in triangles for vertex in triangle]
    if any(not math.isfinite(component) for vertex in coords for component in vertex):
        raise StlError("The STL contains nonfinite coordinates")
    xs = [value[0] for value in coords]
    ys = [value[1] for value in coords]
    zs = [value[2] for value in coords]
    return Mesh(triangles, (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))


def _binary_stl(data: bytes) -> Mesh:
    if len(data) < 84:
        raise StlError("Truncated binary STL")
    count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + count * 50
    if len(data) < expected:
        raise StlError("Truncated binary STL triangle data")
    triangles: list[Triangle] = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        triangles.append(
            (
                (values[3], values[4], values[5]),
                (values[6], values[7], values[8]),
                (values[9], values[10], values[11]),
            )
        )
        offset += 50
    return _make_mesh(triangles)


def _ascii_stl(data: bytes) -> Mesh:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StlError("STL is neither valid binary nor UTF-8 ASCII") from exc
    vertices: list[Vec3] = []
    for line in text.splitlines():
        words = line.strip().split()
        if len(words) == 4 and words[0].lower() == "vertex":
            try:
                vertices.append((float(words[1]), float(words[2]), float(words[3])))
            except ValueError as exc:
                raise StlError("Invalid ASCII STL vertex") from exc
    if len(vertices) % 3:
        raise StlError("ASCII STL has an incomplete triangle")
    return _make_mesh([tuple(vertices[i : i + 3]) for i in range(0, len(vertices), 3)])  # type: ignore[list-item]


def load_stl(path: Path) -> Mesh:
    data = path.read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if 84 + count * 50 == len(data):
            return _binary_stl(data)
    return _ascii_stl(data)

