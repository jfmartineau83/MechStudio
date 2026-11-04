from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mechstudio.models import ParameterSpec, ParameterType
from mechstudio.units import ParameterValidationError, convert_parameters


class UnitConversionTests(unittest.TestCase):
    def setUp(self):
        self.specs = [
            ParameterSpec("length", "Length", ParameterType.LENGTH, 1),
            ParameterSpec("angle", "Angle", ParameterType.ANGLE, 20),
            ParameterSpec("count", "Count", ParameterType.INTEGER, 8),
            ParameterSpec("ratio", "Ratio", ParameterType.RATIO, 0.5),
        ]

    def test_sae_converts_only_length(self):
        result = convert_parameters(
            self.specs,
            {"length": "1/8", "angle": "20", "count": "8", "ratio": ".5"},
            "sae",
        )
        self.assertAlmostEqual(result["length"], 3.175)
        self.assertEqual(result["angle"], 20)
        self.assertEqual(result["count"], 8)
        self.assertEqual(result["ratio"], 0.5)

    def test_metric_preserves_numeric_magnitude(self):
        result = convert_parameters(self.specs, {"length": "1/8"}, "metric")
        self.assertEqual(result["length"], 0.125)

    def test_integer_rejects_fraction(self):
        with self.assertRaises(ParameterValidationError):
            convert_parameters(self.specs, {"count": "3/2"}, "metric")


if __name__ == "__main__":
    unittest.main()

