"""One owned live session, no frame queue, persistent incident history.

The browser sends at most one frame at a time. Admission rejects extra in-flight
frames rather than accumulating stale camera work. Camera images are not stored
continuously: a few seconds stay in memory, and a ~4 s clip around a detected fall
is saved (see icare.api.clips) and expires after a day.
"""
from datetime import datetime, timedelta, timezone
import math
import secrets
import threading
import time

from icare.api.clips import LiveClipRecorder
from icare.api.incidents import PersonIncidents
from icare.api.schemas import Pose, Prediction
from icare.api.store import utc_now

MAX_FRAME_BYTES = 1024 * 1024


class LiveError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class LiveManager:
    def __init__(self, store, engine, settings, clips=None):
        self.store, self.engine, self.settings, self.clips = store, engine, settings, clips
        self.lock = threading.RLock()
        self.session = None
        self.store.fail_interrupted_live()

    def ensure_video_allowed(self):
        if self.session is not None:
            raise LiveError(409, 'mode_busy', 'Stop Live Detection before analyzing a video.')

    def start(self, owner):
        with self.lock:
            if self.session is not None or self.store.has_video_work():
                raise LiveError(409, 'mode_busy', 'Another source is using inference. Stop it or wait for it to finish.')
            if self.engine is None or not self.engine.ready or not hasattr(self.engine, 'start_stream'):
                raise LiveError(503, 'model_unavailable', 'Live inference is not available.')
            document = {'session_id': secrets.token_urlsafe(16), 'owner': owner, 'state': 'active',
                        'created_at_utc': utc_now(), 'model_version': self.engine.model_version}
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.settings.admission_window_seconds)).isoformat()
            if not self.store.create_live_session(document, cutoff, self.settings.max_jobs_per_visitor_window):
                raise LiveError(429, 'capacity', 'Too many camera sessions. Please try again later.')
            session = {**document, 'cancel': threading.Event(),
                       'incidents': PersonIncidents(confirmations=self.settings.fall_confirmations),
                       'started': time.monotonic(), 'last_activity': time.monotonic(),
                       'last_timestamp': None, 'frames': 0, 'inflight': False, 'closing': False,
                       'idle': threading.Event(),
                       'recorder': (LiveClipRecorder(self.clips, owner, document['session_id'])
                                    if self.clips is not None else None)}
            session['idle'].set()
            self.session = session  # Reserve before loading the model-side session.
        try:
            self.engine.start_stream()
        except Exception as error:
            self.stop(document['session_id'], owner, error=str(error))
            raise LiveError(503, 'model_unavailable', 'Could not start camera inference.') from error
        return {key: document[key] for key in ('session_id','created_at_utc','model_version')}

    def _owned(self, session_id, owner):
        session = self.session
        if session is None or session['session_id'] != session_id or session['owner'] != owner:
            raise LiveError(404, 'not_found', 'No active camera session for this browser.')
        if session['closing']:
            raise LiveError(409, 'session_closed', 'The camera session is stopping.')
        return session

    def claim(self, session_id, owner, timestamp):
        with self.lock:
            session = self._owned(session_id, owner)
            if session['inflight']:
                raise LiveError(409, 'frame_busy', 'A frame is already being processed; send the latest frame after it finishes.')
            elapsed = time.monotonic() - session['started']
            if elapsed > 3600:
                raise LiveError(409, 'session_expired', 'Camera sessions are limited to one hour; stop and start again.')
            if (not math.isfinite(timestamp) or timestamp < 0 or timestamp > elapsed + 2
                    or (session['last_timestamp'] is not None and timestamp <= session['last_timestamp'])):
                raise LiveError(400, 'invalid_timestamp', 'Capture timestamps must increase and match the camera session clock.')
            if session['last_timestamp'] is not None and timestamp - session['last_timestamp'] < 1 / 6 - 0.01:
                raise LiveError(429, 'frame_rate', 'Camera capture is limited to six submitted frames per second.')
            session['inflight'] = True
            session['idle'].clear()
            session['last_activity'] = time.monotonic()
            return session

    def release(self, session):
        with self.lock:
            session['inflight'] = False
            session['idle'].set()

    def process(self, session, data, timestamp):
        started = time.monotonic()
        try:
            # A slow request body may finish after Stop and a new session.
            # Never submit its stale frame to the new model-side session.
            with self.lock:
                if self.session is not session or session['cancel'].is_set():
                    raise LiveError(409, 'session_closed', 'The camera session stopped.')
            record = self.engine.process_frame(data, timestamp, cancel_event=session['cancel'], timeout_seconds=30)
            poses = {pose['track_id']: Pose.model_validate(pose).model_dump() for pose in record['poses']}
            predictions = {item['track_id']: Prediction.model_validate(item).model_dump() for item in record['predictions']}
            with self.lock:
                if self.session is not session or session['cancel'].is_set():
                    raise LiveError(409, 'session_closed', 'The camera session stopped.')
                incidents, people = [], []
                recorder = session['recorder']
                if recorder is not None:
                    recorder.add_frame(timestamp, data)  # includes this frame in any clip it opens
                for person in record['people']:
                    track_id = person['track_id']
                    prediction = predictions.get(track_id)
                    if prediction is not None and session['incidents'].observe(track_id, prediction['fall_probability']):
                        incident = {'incident_id': secrets.token_urlsafe(8), 'session_id': session['session_id'],
                                    'track_id': track_id, 'detected_at_seconds': prediction['timestamp_seconds'],
                                    'confidence': prediction['fall_probability'], 'created_at_utc': utc_now()}
                        if recorder is not None:
                            incident['clip_id'] = recorder.trigger(
                                clip_id=incident['incident_id'], track_id=track_id,
                                detected_at=incident['detected_at_seconds'], confidence=incident['confidence'])
                        self.store.add_live_incident(incident)
                        incidents.append(incident)
                    people.append({**person, 'pose': poses[track_id], 'prediction': prediction,
                                   'incident_latched': session['incidents'].latched(track_id)})
                session['frames'] += 1
                session['last_timestamp'] = timestamp
                session['last_activity'] = time.monotonic()
                wall = max(time.monotonic() - session['started'], 1e-6)
                return {'timestamp_seconds': record['timestamp_seconds'], 'frame_width': record['frame_width'],
                        'frame_height': record['frame_height'], 'status': record['status'],
                        'track_resets': record['track_resets'], 'people': people, 'incidents': incidents,
                        'session_id': session['session_id'], 'model_version': self.engine.model_version,
                        'frames_processed': session['frames'], 'processed_fps': session['frames'] / wall,
                        'processing_ms': (time.monotonic() - started) * 1000,
                        'incident_latched': session['incidents'].any_latched()}
        except LiveError:
            raise
        except Exception as error:
            if getattr(error, 'code', '') == 'invalid_frame':
                raise LiveError(400, 'invalid_frame', str(error)) from error
            # The route releases this frame before stopping the failed session.
            raise LiveError(503, getattr(error, 'code', 'model_error'), 'Camera inference failed. Stop and restart the session.') from error

    def stop(self, session_id, owner, error=None):
        with self.lock:
            session = self.session
            if session is None or session['session_id'] != session_id or session['owner'] != owner:
                return False
            if session['closing']:
                return True
            session['closing'] = True
            session['cancel'].set()
        session['idle'].wait(timeout=6)
        if session['recorder'] is not None:
            session['recorder'].close()  # save any fall clip still waiting for its last second
        try:
            self.engine.stop_stream()
        except Exception:
            # A timed-out/crashed child already starts its own bounded recovery.
            error = error or 'The model session stopped during recovery.'
        finally:
            with self.lock:
                self.store.finish_live_session(session_id, 'failed' if error else 'stopped', session['frames'], error)
                if self.session is session:
                    self.session = None
        return True

    def expire(self):
        with self.lock:
            session = self.session
            expired = session and not session['inflight'] and time.monotonic() - session['last_activity'] > 20
        if expired:
            self.stop(session['session_id'], session['owner'], error='Camera disconnected or stopped sending frames.')

    def close(self):
        with self.lock:
            session = self.session
        if session is not None:
            self.stop(session['session_id'], session['owner'])
