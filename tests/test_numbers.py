from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mechstudio.numbers import NumericInputError, parse_number


class FractionParserTests(unittest.TestCase):
    def test_decimal_and_fraction_equivalence(self):
        self.assertEqual(parse_number("1/8"), parse_number(".125"))
        self.assertEqual(parse_number("0.125"), parse_number(".125"))

    def test_mixed_numbers(self):
        self.assertEqual(float(parse_number("1 1/2")), 1.5)
        self.assertEqual(parse_number("1 1/2"), parse_number("1-1/2"))
        self.assertEqual(float(parse_number("-1 1/2")), -1.5)

    def test_rejects_unsafe_or_malformed_input(self):
        for value in ("1/0", "1//2", "2 3/2", "nan", "1 + 2", "__import__('os')", ""):
            with self.subTest(value=value), self.assertRaises(NumericInputError):
                parse_number(value)


if __name__ == "__main__":
    unittest.main()

