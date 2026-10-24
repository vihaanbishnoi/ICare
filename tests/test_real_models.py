"""The real YOLO26n-pose and PoseC3D ONNX files from models/, without video assets."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "onnxruntime is not installed")
class RealModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from icare.inference.engine import load_engine
        cls.engine = load_engine({"model_path": ROOT / "models" / "posec3d_fall.onnx"})

    @classmethod
    def tearDownClass(cls):
        cls.engine.close()

    def test_empty_scenes_produce_no_people_and_no_predictions(self):
        session = self.engine.start_stream()
        try:
            rng = np.random.default_rng(0)
            for index in range(18):
                frame = np.full((360, 640, 3), 114, dtype=np.uint8)
                if index % 2:
                    frame = rng.integers(0, 255, (360, 640, 3), dtype=np.uint8)  # noise
                record = session.process_frame(frame, index / 6)
                self.assertEqual((record["poses"], record["predictions"], record["status"]), ([], [], "no_person"))
        finally:
            session.close()

    def test_posec3d_scores_every_person_independently(self):
        classifier = self.engine._classifier
        rng = np.random.default_rng(1)
        windows = rng.random((3, 1, 17, 48, 64, 64), dtype=np.float32) * 0.2
        separate = [classifier.predict(w) for w in windows]
        repeated = [classifier.predict(w) for w in windows[::-1]][::-1]
        self.assertEqual(separate, repeated)  # no hidden state carried between people

    def test_model_version_names_both_models(self):
        self.assertRegex(self.engine.model_version, r"^posec3d_fall\.onnx@[0-9a-f]{12}\+yolo26n-pose\.onnx@[0-9a-f]{12}$")


if __name__ == "__main__":
    unittest.main()
