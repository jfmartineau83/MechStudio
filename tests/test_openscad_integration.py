from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mechstudio.openscad import OpenScadNotFoundError, build_generation_command, discover_openscad
from mechstudio.stl import load_stl


class OpenScadIntegrationTests(unittest.TestCase):
    def test_missing_openscad_is_reported_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(OpenScadNotFoundError):
                build_generation_command(
                    None,
                    ROOT / "examples" / "modules" / "plain_bushing.scad",
                    Path(temporary) / "part.stl",
                    {},
                )

    @unittest.skipUnless(discover_openscad(), "OpenSCAD is not installed on this host")
    def test_sae_bushing_has_millimetre_outer_bounds(self):
        executable = discover_openscad()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bushing.stl"
            command = build_generation_command(
                executable,
                ROOT / "examples" / "modules" / "plain_bushing.scad",
                output,
                {"inner_diameter": 3.175, "outer_diameter": 12.7, "length": 38.1},
            )
            completed = subprocess.run(
                [str(command.executable), *command.arguments],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            mesh = load_stl(output)
            x, y, z = mesh.dimensions
            self.assertAlmostEqual(x, 12.7, places=2)
            self.assertAlmostEqual(y, 12.7, places=2)
            self.assertAlmostEqual(z, 38.1, places=2)


if __name__ == "__main__":
    unittest.main()

