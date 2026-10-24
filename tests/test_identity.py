"""Resident naming rules and enrolment storage, with a stand-in face model (no real faces)."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from icare.api.residents import Residents
from icare.inference.identity import FaceError, FaceGallery, SessionIdentities, new_resident, write_gallery
from tests.helpers import person

RNG = np.random.default_rng(0)
ALICE, BOB = RNG.normal(size=128), RNG.normal(size=128)


class ScriptedFaces:
    """faces() returns whatever embedding the test queues, ignoring the image."""

    def __init__(self, embeddings):
        self.embeddings = list(embeddings)

    def faces(self, image, max_side=640):
        e = self.embeddings.pop(0) if self.embeddings else None
        return [] if e is None else [(e / np.linalg.norm(e), 0.9, np.array([0, 0, 40, 40]))]

    def enrolment_embedding(self, image):
        if image.mean() < 1:
            raise FaceError("no_face", "No face was found in one of the photos.")
        return ALICE


def gallery(*people):
    path = Path(tempfile.mkdtemp()) / "faces.json"
    write_gallery(path, [new_resident(name, None, [embedding]) for name, embedding in people])
    return FaceGallery(path)


def run(identities, embeddings_per_frame, track_ids=(1,)):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    for step, _ in enumerate(embeddings_per_frame):
        people = [(tid, person(step * 1.0, 200 + 400 * i, 200)) for i, tid in enumerate(track_ids)]
        identities.update(frame, step * 1.0, people, set(track_ids))
    return identities.names


class NamingTests(unittest.TestCase):
    def test_two_consecutive_matches_name_a_person(self):
        noisy = ALICE + RNG.normal(scale=0.3, size=128)
        names = run(SessionIdentities(ScriptedFaces([noisy, noisy]), gallery(("Alice", ALICE))), [0, 1])
        self.assertEqual(names, {1: "Alice"})

    def test_one_match_is_not_enough(self):
        names = run(SessionIdentities(ScriptedFaces([ALICE, None]), gallery(("Alice", ALICE))), [0, 1])
        self.assertEqual(names, {})

    def test_strangers_stay_anonymous(self):
        names = run(SessionIdentities(ScriptedFaces([BOB] * 5), gallery(("Alice", ALICE))), range(5))
        self.assertEqual(names, {})

    def test_a_name_is_never_given_to_two_people(self):
        faces = ScriptedFaces([ALICE] * 8)
        names = run(SessionIdentities(faces, gallery(("Alice", ALICE))), range(4), track_ids=(1, 2))
        self.assertEqual(list(names.values()), ["Alice"])

    def test_names_are_dropped_when_the_track_ends(self):
        identities = SessionIdentities(ScriptedFaces([ALICE, ALICE]), gallery(("Alice", ALICE)))
        run(identities, [0, 1])
        identities.update(np.zeros((720, 1280, 3), dtype=np.uint8), 5.0, [], set())
        self.assertEqual(identities.names, {})


class EnrolmentTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "faces.json"
        self.residents = Residents(self.path, ScriptedFaces([]))

    def photo(self, value=128):
        import cv2
        return cv2.imencode(".png", np.full((64, 64, 3), value, dtype=np.uint8))[1].tobytes()

    def test_enrol_list_replace_and_delete(self):
        first = self.residents.enrol(" Vihaan ", "204", [self.photo(), self.photo()])
        self.assertEqual((first["name"], first["room"], first["photo_count"]), ("Vihaan", "204", 2))
        self.assertNotIn("embeddings", first)
        self.residents.enrol("vihaan", None, [self.photo()])  # same name re-enrolled replaces
        listed = self.residents.listing()["residents"]
        self.assertEqual([(r["name"], r["photo_count"]) for r in listed], [("vihaan", 1)])
        self.assertTrue(self.residents.delete(listed[0]["resident_id"]))
        self.assertEqual(self.residents.listing()["residents"], [])

    def test_bad_input_is_rejected_with_a_code(self):
        cases = [("", [self.photo()], "invalid_name"), ("A", [], "invalid_photos"),
                 ("A", [b"not an image"], "invalid_image"), ("A", [self.photo(0)], "no_face")]
        for name, photos, code in cases:
            with self.assertRaises(FaceError) as caught:
                self.residents.enrol(name, None, photos)
            self.assertEqual(caught.exception.code, code)
        self.assertFalse(self.path.exists())

    def test_missing_models_are_reported(self):
        residents = Residents(self.path, None)
        self.assertFalse(residents.listing()["face_models_ready"])
        with self.assertRaises(FaceError) as caught:
            residents.enrol("A", None, [self.photo()])
        self.assertEqual(caught.exception.code, "face_models_unavailable")


if __name__ == "__main__":
    unittest.main()
