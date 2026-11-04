from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mechstudio.stl import StlError, load_stl


ASCII_TRIANGLE = """solid sample
facet normal 0 0 1
  outer loop
    vertex -1 0 0
    vertex 2 0 0
    vertex 0 3 4
  endloop
endfacet
endsolid sample
"""


class StlTests(unittest.TestCase):
    def test_ascii_mesh_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.stl"
            path.write_text(ASCII_TRIANGLE, encoding="utf-8")
            mesh = load_stl(path)
            self.assertEqual(mesh.bounds, (-1.0, 2.0, 0.0, 3.0, 0.0, 4.0))
            self.assertEqual(mesh.dimensions, (3.0, 3.0, 4.0))

    def test_empty_mesh_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "empty.stl"
            path.write_text("solid empty\nendsolid empty\n", encoding="utf-8")
            with self.assertRaises(StlError):
                load_stl(path)


if __name__ == "__main__":
    unittest.main()

