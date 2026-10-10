"""One reusable spawned model process, isolated from HTTP and SQLite.

The parent polls cancellation even when a native ONNX/OpenCV call is stuck.
No test adapter is selected by production environment variables.
"""
from __future__ import annotations

import importlib
import logging
import multiprocessing
from pathlib import Path
import threading
import time

log = logging.getLogger(__name__)


class ProcessEngineError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _model_process(connection, config, factory):
    engine = None
    try:
        module, name = factory.split(':')
        engine = getattr(importlib.import_module(module), name)(config)
        connection.send(('ready', engine.model_version))
        while True:
            command, path = connection.recv()
            if command == 'close':
                return
            try:
                summary = engine.analyze_video(
                    Path(path), on_pose=lambda value: connection.send(('pose', value)),
                    on_prediction=lambda value: connection.send(('prediction', value)),
                    on_progress=lambda value: connection.send(('progress', value)),
                    cancel_event=threading.Event(),
                )
                connection.send(('done', summary))
            except Exception as error:
                connection.send(('error', (getattr(error, 'code', 'engine_error'), str(error))))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as error:
        try:
            connection.send(('error', (getattr(error, 'code', 'model_unavailable'), str(error))))
        except (BrokenPipeError, OSError):
            pass
    finally:
        if engine is not None:
            engine.close()
        connection.close()


class ProcessEngine:
    def __init__(self, config, *, startup_timeout=180.0, factory='icare_app.engine:load_engine'):
        self.config = config
        self.startup_timeout = startup_timeout
        self.factory = factory
        self.model_version = None
        self._context = multiprocessing.get_context('spawn')
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._calls = threading.Lock()
        self._process = None
        self._connection = None
        self._ready = False
        self._reloader = None
        self._launch()

    @property
    def ready(self):
        with self._lock:
            return self._ready and not self._closed.is_set() and self._process is not None and self._process.is_alive()

    def _launch(self):
        parent, child = self._context.Pipe()
        process = self._context.Process(target=_model_process, args=(child, self.config, self.factory), daemon=True)
        with self._lock:
            if self._closed.is_set():
                parent.close(); child.close()
                return
            self._process, self._connection = process, parent
            process.start()
        child.close()
        deadline = time.monotonic() + self.startup_timeout
        try:
            while time.monotonic() < deadline and not self._closed.is_set():
                if parent.poll(0.05):
                    kind, value = parent.recv()
                    if kind == 'ready':
                        with self._lock:
                            if self._process is process and not self._closed.is_set():
                                self.model_version, self._ready = value, True
                        return
                    raise ProcessEngineError(*value)
                if not process.is_alive():
                    raise ProcessEngineError('model_unavailable', 'Model process exited during startup.')
            raise ProcessEngineError('model_unavailable', 'Model startup timed out or was stopped.')
        except BaseException:
            self._terminate()
            raise

    def _terminate(self):
        with self._lock:
            process, connection = self._process, self._connection
            self._process = self._connection = None
            self._ready = False
        if process is not None:
            if process.is_alive():
                process.terminate()
            process.join(2)
            if process.is_alive():
                process.kill(); process.join(2)
            process.close()
        if connection is not None:
            connection.close()

    def _recover(self):
        self._terminate()
        if self._closed.is_set():
            return
        def reload():
            try:
                self._launch()
            except Exception:
                log.exception('Model process could not recover; restart the API after diagnosis')
        self._reloader = threading.Thread(target=reload, name='icare-model-reload', daemon=True)
        self._reloader.start()

    def analyze_video(self, video_path, *, on_pose, on_prediction, on_progress, cancel_event):
        with self._calls:
            if not self.ready:
                raise ProcessEngineError('model_unavailable', 'The isolated model process is not ready.')
            with self._lock:
                connection, process = self._connection, self._process
            try:
                connection.send(('analyze', str(video_path)))
                while True:
                    if cancel_event.is_set() or self._closed.is_set():
                        raise ProcessEngineError('cancelled', 'Analysis cancelled.')
                    if connection.poll(0.05):
                        kind, value = connection.recv()
                        if kind == 'done':
                            return value
                        if kind == 'error':
                            # A valid model-domain error leaves the child reusable.
                            raise ProcessEngineError(*value)
                        {'pose': on_pose, 'prediction': on_prediction, 'progress': on_progress}[kind](value)
                    elif not process.is_alive():
                        raise ProcessEngineError('worker_crashed', 'Model process exited during analysis.')
            except BaseException as error:
                if not isinstance(error, ProcessEngineError) or error.code in ('cancelled', 'worker_crashed'):
                    self._recover()
                raise

    def wait_ready(self, cancel_event):
        while not self.ready:
            if cancel_event.is_set() or self._closed.is_set():
                raise ProcessEngineError('cancelled', 'Analysis cancelled while model restarted.')
            if self._reloader is None or not self._reloader.is_alive():
                raise ProcessEngineError('model_unavailable', 'The model process could not recover.')
            time.sleep(.05)

    def close(self):
        self._closed.set()
        # Signal the active call to release its pipe before closing the process.
        with self._calls:
            self._terminate()
        if self._reloader is not None:
            self._reloader.join(timeout=3)
