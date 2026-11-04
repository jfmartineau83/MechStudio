from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mechstudio.models import ParameterType
from mechstudio.scad_parser import ScadCustomizerParser


class ScadParserTests(unittest.TestCase):
    def test_bushing_contract(self):
        result = ScadCustomizerParser().parse_file(ROOT / "examples" / "modules" / "plain_bushing.scad")
        self.assertEqual(result.metadata["id"], "org.mechstudio.sample.plain-bushing")
        self.assertEqual([item.name for item in result.parameters], ["inner_diameter", "outer_diameter", "length"])
        self.assertTrue(all(item.parameter_type == ParameterType.LENGTH for item in result.parameters))
        self.assertFalse(result.issues)

    def test_structurally_different_module_types(self):
        result = ScadCustomizerParser().parse_file(ROOT / "examples" / "modules" / "spur_gear.scad")
        types = {item.name: item.parameter_type for item in result.parameters}
        self.assertEqual(types["tooth_count"], ParameterType.INTEGER)
        self.assertEqual(types["pressure_angle"], ParameterType.ANGLE)
        self.assertEqual(types["hub_style"], ParameterType.ENUM)
        self.assertEqual(types["lightening_holes"], ParameterType.BOOLEAN)
        self.assertFalse(result.issues)

    def test_ambiguous_numeric_is_reported(self):
        result = ScadCustomizerParser().parse("value = 10; // [0:1:20]\n")
        self.assertFalse(result.parameters)
        self.assertEqual(result.issues[0].parameter, "value")


if __name__ == "__main__":
    unittest.main()

