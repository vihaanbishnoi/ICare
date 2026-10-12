"""Incident boundaries and event de-duplication, independent of model outputs."""
import unittest

from icare.api.incidents import IncidentTracker


class IncidentTests(unittest.TestCase):
    def test_threshold_is_inclusive_and_overlapping_windows_do_not_duplicate(self):
        tracker = IncidentTracker()
        observed = [tracker.observe(p) for p in [.49, .50, .90, .60]]
        self.assertEqual(observed, [False, True, False, False])

    def test_three_consecutive_clear_windows_allow_a_new_incident(self):
        tracker = IncidentTracker()
        observed = [tracker.observe(p) for p in [.60, .20, .20, .20, .55]]
        self.assertEqual(observed, [True, False, False, False, True])

    def test_clear_threshold_or_intervening_high_score_resets_clear_streak(self):
        for reset_probability in [.35, .40, .90]:
            with self.subTest(reset_probability=reset_probability):
                tracker = IncidentTracker()
                probabilities = [.60, .34, .34, reset_probability, .34, .34, .50,
                                 .34, .34, .34, .50]
                events = [i for i, p in enumerate(probabilities) if tracker.observe(p)]
                self.assertEqual(events, [0, 10])


if __name__ == '__main__':
    unittest.main()
