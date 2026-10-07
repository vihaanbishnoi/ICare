from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from icare_app.subject_audit import audit_subject_split


class SubjectAuditTests(unittest.TestCase):
    def write_metadata(self, rows: list[dict]) -> Path:
        directory = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "split.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_detects_subject_overlap(self) -> None:
        path = self.write_metadata(
            [
                {"subject_id": "s1", "split": "train"},
                {"subject_id": "s1", "split": "test"},
                {"subject_id": "s2", "split": "validation"},
            ]
        )
        result = audit_subject_split(path)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.overlaps["test__train"], ["s1"])

    def test_verifies_disjoint_subjects(self) -> None:
        path = self.write_metadata(
            [
                {"subject_id": "s1", "split": "train"},
                {"subject_id": "s2", "split": "test"},
                {"subject_id": "s3", "split": "validation"},
            ]
        )
        result = audit_subject_split(path)
        self.assertEqual(result.status, "verified_subject_disjoint")

    def test_refuses_to_guess_without_subject_coverage(self) -> None:
        path = self.write_metadata(
            [{"video_relative_path": "Fall/video001.mp4", "split": "train"}]
        )
        result = audit_subject_split(path)
        self.assertEqual(result.status, "unverifiable")


if __name__ == "__main__":
    unittest.main()
