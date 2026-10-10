"""Real spawned-process cancellation/crash/recovery using a labelled adapter."""
from pathlib import Path
import threading
import time
import unittest

from api.process_engine import ProcessEngine, ProcessEngineError


class ProcessEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ProcessEngine({}, startup_timeout=10, factory='process_engine_fixture:create_engine')

    def tearDown(self):
        self.engine.close()

    def run_clip(self, name, cancel=None):
        return self.engine.analyze_video(Path(name), on_pose=lambda p: None,
            on_prediction=lambda p: None, on_progress=lambda p: None,
            cancel_event=cancel or threading.Event())

    def await_recovery(self):
        deadline = time.monotonic() + 10
        while not self.engine.ready and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(self.engine.ready)

    def test_hung_native_call_is_terminated_and_next_clip_works(self):
        cancel = threading.Event()
        timer = threading.Timer(.2, cancel.set)
        timer.start()
        started = time.monotonic()
        with self.assertRaises(ProcessEngineError) as error:
            self.run_clip('hang.mp4', cancel)
        timer.cancel()
        self.assertEqual(error.exception.code, 'cancelled')
        self.assertLess(time.monotonic() - started, 5)
        self.await_recovery()
        self.assertEqual(self.run_clip('normal.mp4')['duration_seconds'], 3)

    def test_crashed_child_recovers_without_restarting_http_service(self):
        with self.assertRaises((ProcessEngineError, EOFError)):
            self.run_clip('crash.mp4')
        self.await_recovery()
        self.assertEqual(self.run_clip('normal.mp4')['frame_width'], 640)

    def test_shutdown_is_bounded_even_when_native_call_hangs(self):
        errors = []
        def run():
            try: self.run_clip('hang.mp4')
            except ProcessEngineError as error: errors.append(error.code)
        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(.1)
        self.engine.close()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, ['cancelled'])
        self.assertFalse(self.engine.ready)


if __name__ == '__main__':
    unittest.main()
