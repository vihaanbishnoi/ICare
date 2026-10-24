"""Person tracking: stable IDs across movement, falls, crossings, occlusion and exits."""
import unittest

from icare.inference.tracking import PersonTracker
from tests.helpers import person, times


def ids_by_label(tracker, frames):
    """frames: list of (t, {label: pose}). Returns {label: [track ids over time]}."""
    seen = {}
    for t, people in frames:
        labels, poses = zip(*people.items()) if people else ((), ())
        assigned = dict((id(pose), tid) for tid, pose in tracker.update(list(poses), t))
        for label, pose in zip(labels, poses):
            seen.setdefault(label, []).append(assigned[id(pose)])
    return seen


class TrackerTests(unittest.TestCase):
    def test_single_person_keeps_one_id_while_walking(self):
        frames = [(t, {"a": person(t, 100 + 40 * t, 300)}) for t in times(10)]
        self.assertEqual(set(ids_by_label(PersonTracker(), frames)["a"]), {1})

    def test_five_people_each_keep_their_own_id_while_one_falls(self):
        def scene(t):
            fall = min(max((t - 3.0) / 0.6, 0.0), 1.0)  # falls between 3.0 and 3.6 s
            return {"faller": person(t, 100, 300, lying=fall),
                    **{f"p{i}": person(t, 320 + 180 * i, 300) for i in range(4)}}
        seen = ids_by_label(PersonTracker(), [(t, scene(t)) for t in times(6)])
        self.assertEqual({label: len(set(ids)) for label, ids in seen.items()}, dict.fromkeys(seen, 1))
        self.assertEqual(len({ids[0] for ids in seen.values()}), 5)

    def test_people_crossing_paths_do_not_swap_ids(self):
        # Opposite directions, overlapping boxes while they pass each other.
        frames = [(t, {"left": person(t, 100 + 120 * t, 300), "right": person(t, 700 - 120 * t, 310)})
                  for t in times(5)]
        seen = ids_by_label(PersonTracker(), frames)
        self.assertEqual(len(set(seen["left"])), 1)
        self.assertEqual(len(set(seen["right"])), 1)
        self.assertNotEqual(seen["left"][0], seen["right"][0])

    def test_short_occlusion_keeps_the_id_long_absence_starts_a_new_one(self):
        tracker = PersonTracker(max_age_seconds=2.0)
        visible = [t for t in times(8) if not (2.0 <= t < 3.0 or 4.0 <= t < 7.0)]
        seen = ids_by_label(tracker, [(t, {"a": person(t, 200 + 10 * t, 300)}) for t in visible])
        before, after_short, after_long = seen["a"][0], seen["a"][visible.index(3.0)], seen["a"][-1]
        self.assertEqual(before, after_short)       # hidden 1 s: same person
        self.assertNotEqual(before, after_long)     # hidden 3 s: new ID (no appearance model)

    def test_person_entering_gets_a_new_id_and_leaving_expires(self):
        tracker = PersonTracker(max_age_seconds=1.0)
        frames = []
        for t in times(6):
            people = {"a": person(t, 100, 300)}
            if t >= 2.0:
                people["b"] = person(t, 600, 300)
            frames.append((t, people))
        seen = ids_by_label(tracker, frames)
        self.assertEqual((set(seen["a"]), set(seen["b"])), ({1}, {2}))
        tracker.update([person(6.0, 100, 300)], 6.0)   # b left after 5.83 s
        tracker.update([person(6.5, 100, 300)], 6.5)
        tracker.update([person(7.0, 100, 300)], 7.0)   # b unseen for > 1 s
        self.assertEqual(tracker.expired, [2])
        self.assertEqual(tracker.active_ids, [1])

    def test_side_by_side_overlapping_people_stay_distinct(self):
        frames = [(t, {"a": person(t, 300, 300), "b": person(t, 335, 305, h=170)}) for t in times(4)]
        seen = ids_by_label(PersonTracker(), frames)
        self.assertEqual((len(set(seen["a"])), len(set(seen["b"]))), (1, 1))
        self.assertNotEqual(seen["a"][0], seen["b"][0])

    def test_a_person_lying_from_the_start_is_tracked(self):
        frames = [(t, {"a": person(t, 300, 300, lying=1.0)}) for t in times(5)]
        self.assertEqual(set(ids_by_label(PersonTracker(), frames)["a"]), {1})

    def test_ids_are_never_reused(self):
        tracker = PersonTracker(max_age_seconds=0.5)
        tracker.update([person(0, 100, 300)], 0)
        tracker.update([], 1.0)
        assigned = tracker.update([person(1.1, 100, 300)], 1.1)
        self.assertEqual(assigned[0][0], 2)
        self.assertEqual(tracker.ids_issued, 2)


if __name__ == "__main__":
    unittest.main()
