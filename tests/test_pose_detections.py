"""Duplicate detections of one person merge; distinct overlapping people do not."""
import unittest

import numpy as np

from icare.inference.pose import _without_duplicates


class DuplicateDetectionTests(unittest.TestCase):
    def order(self, boxes):
        boxes = np.asarray(boxes, dtype=np.float64)
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        return _without_duplicates(boxes, np.argsort(-areas, kind="stable"))

    def test_near_identical_boxes_for_one_person_keep_only_the_larger(self):
        # Observed on real footage: two boxes with IoU ~0.99 for one walker.
        self.assertEqual(self.order([[970, 49, 1182, 581], [969, 48, 1183, 583]]), [1])

    def test_people_standing_close_together_are_both_kept(self):
        self.assertEqual(sorted(self.order([[300, 100, 400, 400], [360, 110, 460, 410]])), [0, 1])

    def test_child_partly_in_front_of_an_adult_is_kept(self):
        self.assertEqual(sorted(self.order([[300, 100, 420, 460], [330, 260, 400, 460]])), [0, 1])


if __name__ == "__main__":
    unittest.main()
