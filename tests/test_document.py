from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mechstudio.models import FeatureInstance, GenerationSnapshot, ParameterValue, ProjectDocument


class DocumentTests(unittest.TestCase):
    def test_round_trip_preserves_original_notation(self):
        document = ProjectDocument(
            name="Fractional bushing",
            generation_mode="sae",
            components=[
                FeatureInstance(
                    instance_id="part-1",
                    module_id="sample",
                    module_version="1.0.0",
                    name="Bushing",
                    parameters={"inner": ParameterValue("1/8"), "length": ParameterValue("1 1/2")},
                )
            ],
        )
        restored = ProjectDocument.from_dict(document.to_dict())
        self.assertEqual(restored.active_feature.parameters["inner"].text, "1/8")
        self.assertEqual(restored.active_feature.parameters["length"].text, "1 1/2")
        self.assertEqual(restored.generation_mode, "sae")

    def test_touch_marks_cached_generation_stale(self):
        document = ProjectDocument()
        snapshot = GenerationSnapshot(0, "metric", Path("part.stl"), {}, (0, 1, 0, 1, 0, 1))
        self.assertTrue(snapshot.current_for(document))
        self.assertEqual(document.revision, 0)
        document.touch()
        self.assertTrue(document.modified)
        self.assertEqual(document.revision, 1)
        self.assertFalse(snapshot.current_for(document))


if __name__ == "__main__":
    unittest.main()

