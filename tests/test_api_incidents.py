"""The API incident rule must match the retained reference semantics."""
from __future__ import annotations

import unittest

from api.incidents import IncidentTracker
from icare_app.inference import FallDetectionSession, ModelOutput, UnconfiguredBackend


class IncidentParityTests(unittest.TestCase):
    def test_matches_reference_session_rule(self) -> None:
        sequences = [
            [0.1, 0.6, 0.9, 0.2, 0.2, 0.2, 0.55],
            [0.5, 0.34, 0.34, 0.4, 0.34, 0.34, 0.34, 0.5],
            [0.49, 0.2, 0.51, 0.51, 0.1],
            [0.9, 0.2, 0.2, 0.9],
        ]
        for probabilities in sequences:
            reference = FallDetectionSession(UnconfiguredBackend())
            tracker = IncidentTracker()
            ours = []
            for index, probability in enumerate(probabilities):
                reference._consume_output(ModelOutput(float(index), probability))
                if tracker.observe(probability):
                    ours.append(float(index))
            expected = [event.detected_at_seconds for event in reference.events]
            self.assertEqual(ours, expected, probabilities)


if __name__ == "__main__":
    unittest.main()
