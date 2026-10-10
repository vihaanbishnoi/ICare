"""Admission limits, streaming upload bounds and restart recovery; labelled adapters."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import unittest

from test_api import ApiTestCase, mp4_bytes


class AdmissionTests(ApiTestCase):
    def test_oversized_result_fails_without_exceeding_its_reserved_disk_budget(self):
        self.app.state.runner.max_result_bytes = 100
        first = self.upload(self.client, mp4_bytes(5)).json()['job_id']
        job = self.wait(self.client, first)
        self.assertEqual(job['error']['code'], 'result_too_large')
        self.assertFalse((self.settings.data_dir / 'jobs' / first / 'result.json').exists())

    def configure(self, **values):
        self.app.state.settings = replace(self.settings, **values)

    def test_visitor_active_limit_is_independent_of_global_queue(self):
        self.configure(max_active_jobs_per_visitor=1)
        self.engine.gate = threading.Event()
        first = self.upload(self.client, mp4_bytes(5)).json()['job_id']
        self.wait(self.client, first, ('running',))
        response = self.upload(self.client, mp4_bytes(5))
        self.assertEqual(response.json()['error']['code'], 'visitor_capacity')
        self.assertEqual(self.upload(self.other_visitor(), mp4_bytes(5)).status_code, 202)

    def test_deleting_result_does_not_reset_rate_limit(self):
        self.configure(max_jobs_per_visitor_window=1)
        first = self.upload(self.client, mp4_bytes(5)).json()['job_id']
        self.wait(self.client, first)
        self.client.delete(f'/api/v1/jobs/{first}')
        response = self.upload(self.client, mp4_bytes(5))
        self.assertEqual(response.json()['error']['code'], 'visitor_rate_limit')

    def test_new_session_cannot_bypass_network_limit(self):
        self.configure(max_jobs_per_ip_window=1)
        first = self.upload(self.client, mp4_bytes(5)).json()['job_id']
        self.wait(self.client, first)
        response = self.upload(self.other_visitor(), mp4_bytes(5))
        self.assertEqual(response.json()['error']['code'], 'network_rate_limit')

    def test_storage_is_reserved_then_released_on_delete(self):
        budget = self.settings.max_upload_bytes + self.settings.result_reserve_bytes
        self.configure(max_storage_bytes=budget)
        first = self.upload(self.client, mp4_bytes(5)).json()['job_id']
        self.wait(self.client, first)
        self.assertEqual(self.upload(self.client, mp4_bytes(5)).json()['error']['code'], 'storage_capacity')
        self.client.delete(f'/api/v1/jobs/{first}')
        self.assertEqual(self.upload(self.client, mp4_bytes(5)).status_code, 202)

    def test_concurrent_reservations_cannot_overfill_visitor_or_storage(self):
        settings = replace(self.settings, max_active_jobs_per_visitor=2)
        store = self.app.state.store
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(lambda n: store.reserve_admission(str(n), 'owner', 'peer', 100, settings, cutoff), range(20)))
        self.assertEqual(codes.count(None), 2)

    def test_chunked_oversized_body_is_rejected_before_extracted_file_write(self):
        body = b'x' * (self.settings.max_upload_bytes + 1024 * 1024 + 1)
        response = self.client.post('/api/v1/jobs/upload', content=iter([body]), headers={
            'Content-Type': 'multipart/form-data; boundary=boundary'})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()['error']['code'], 'file_too_large')
        self.assertEqual(self.app.state.store.count_queued(), 0)

    def test_invalid_body_releases_storage_reservation(self):
        budget = self.settings.max_upload_bytes + self.settings.result_reserve_bytes
        self.configure(max_storage_bytes=budget)
        self.assertEqual(self.upload(self.client, b'bad').status_code, 400)
        self.assertEqual(self.upload(self.client, mp4_bytes(5)).status_code, 202)

    def test_multiple_file_fields_return_contract_error(self):
        response = self.client.post('/api/v1/jobs/upload', files=[
            ('file', ('one.mp4', mp4_bytes(5))), ('file', ('two.mp4', mp4_bytes(5)))])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'invalid_request')


if __name__ == '__main__':
    unittest.main()
