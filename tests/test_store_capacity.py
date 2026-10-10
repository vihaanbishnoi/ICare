from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from api.store import Store, utc_now


class CapacityTests(unittest.TestCase):
    def test_concurrent_submissions_cannot_overfill_queue(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            store = Store(Path(directory) / "jobs.sqlite3")
            try:
                def submit(index):
                    job = {"job_id": str(index), "owner": "test-owner", "state": "queued",
                           "progress": None, "source_kind": "upload", "example_id": None,
                           "media_path": "fixture.mp4", "created_at_utc": utc_now(),
                           "model_version": None, "error_code": None, "error_message": None}
                    return store.create_job_with_capacity(job, 3)
                with ThreadPoolExecutor(max_workers=12) as executor:
                    accepted = list(executor.map(submit, range(30)))
                self.assertEqual(sum(accepted), 3)
                self.assertEqual(store.count_queued(), 3)
            finally:
                store.close()
