"""Unusual-behaviour events for elderly care, from the tracked poses ICare already computes.

Three events, each defined only by observable movement of one tracked person:

* ``pacing``: repeated back-and-forth walking along the same line (a common sign of
  agitation or restlessness in dementia). Counted from direction reversals of the
  body's horizontal image position, each after a walk of at least
  ``pacing_leg_body_lengths`` body lengths. One turn, a walk across the room, or
  shifting weight in place never counts.
* ``prolonged_inactivity``: a clearly visible person whose joints all stay still
  (robust 10-90 % range under ``stillness_threshold`` body lengths over every
  ``stillness_window_seconds``) for ``inactivity_seconds``.
* ``long_lie``: a person with a recorded fall who has not sat or stood up, and
  was seen lying (torso near horizontal) for at least half of the
  ``long_lie_seconds`` since (the "long lie" after a fall is a recognised risk).

Poor visibility never produces an event: a pose with too few confident joints is
"insufficient evidence", pauses pacing, and resets the stillness clock. All
thresholds are experimental settings until validated on labelled recordings.
No model is loaded here; this module only reads pose records.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from typing import Any, Callable, Mapping

import numpy as np

SHOULDERS, HIPS = (5, 6), (11, 12)
TORSO = SHOULDERS + HIPS

EVENT_TYPES = ("pacing", "prolonged_inactivity", "long_lie")
SEVERITY = {"pacing": "attention", "prolonged_inactivity": "attention", "long_lie": "urgent"}
# Torso angle from vertical (degrees): below UPRIGHT is sitting/standing, above LYING is down.
UPRIGHT_DEGREES, LYING_DEGREES = 35.0, 55.0


@dataclass(frozen=True)
class BehaviourSettings:
    inactivity_seconds: float = 120.0
    long_lie_seconds: float = 60.0
    pacing_reversals: int = 4
    pacing_window_seconds: float = 90.0
    pacing_leg_body_lengths: float = 1.2
    pacing_end_seconds: float = 30.0
    # A turn is confirmed only after walking back this far from the furthest point.
    pacing_turn_body_lengths: float = 0.5
    stillness_window_seconds: float = 3.0
    stillness_threshold: float = 0.05
    # Movement must last this long to end stillness (single-frame pose jitter does not).
    movement_reset_seconds: float = 0.5
    # Poor visibility for this long resets stillness; it is never counted as still.
    insufficient_reset_seconds: float = 2.0
    # Pose gaps longer than this restart pacing and stillness (as the engine's window).
    max_gap_seconds: float = 1.0
    # A person unseen this long is forgotten (the engine tracker's ID lifetime).
    forget_seconds: float = 2.0
    getup_seconds: float = 3.0
    joint_confidence: float = 0.5
    min_joints: int = 8
    min_body_pixels: float = 60.0

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not (math.isfinite(value) and value > 0):
                raise ValueError(f"{name} must be positive and finite")
        if self.pacing_reversals < 2:
            raise ValueError("pacing_reversals must be at least 2")


@dataclass
class _Person:
    last_t: float
    good: bool = False
    # stillness
    recent: deque = field(default_factory=deque)  # (t, keypoints (17, 3), body length px)
    still_since: float | None = None
    moving_since: float | None = None
    poor_since: float | None = None
    # pacing (pixels, converted with the current body length)
    lengths: deque = field(default_factory=lambda: deque(maxlen=60))
    direction: int = 0
    leg_start_x: float | None = None
    leg_start_t: float | None = None
    extreme_x: float | None = None
    extreme_t: float | None = None
    reversals: deque = field(default_factory=deque)  # (turn t, leg start t, leg body lengths)
    # long lie
    fall_t: float | None = None
    down_seconds: float = 0.0
    upright_since: float | None = None
    open: dict = field(default_factory=dict)  # event_type -> event dict
    identity: str | None = None  # enrolled resident's name once matched


class BehaviourMonitor:
    """Per-source behaviour state, one independent record per track ID.

    Feed every pose record (``track_id``, ``timestamp_seconds``, ``bbox_xyxy``,
    ``keypoints``) in time order with :meth:`observe`, report each recorded fall
    with :meth:`note_fall`, and call :meth:`finish` when the source ends. Each call
    returns the events it opened or ended (the same dicts, updated in place).
    """

    def __init__(self, settings: BehaviourSettings | None = None,
                 new_id: Callable[[], str] | None = None) -> None:
        self.settings = settings or BehaviourSettings()
        self._new_id = new_id or _counter()
        self.people: dict[int, _Person] = {}
        self.events: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ inputs

    def observe(self, pose: Mapping[str, Any]) -> list[dict[str, Any]]:
        track_id = int(pose.get("track_id") or 0)
        t = float(pose["timestamp_seconds"])
        changed = self.advance(t, keep=track_id)
        person = self.people.get(track_id)
        if person is None:
            person = self.people[track_id] = _Person(last_t=t)
        elif t - person.last_t > self.settings.max_gap_seconds:
            # Not seen continuously: what happened in the gap is unknown, so motion
            # evidence restarts. A fall stays recorded (lying people are often missed).
            for kind in ("pacing", "prolonged_inactivity"):
                changed += self._close(person, kind, person.last_t, "person_lost")
            self._restart_motion(person)
        dt = min(max(t - person.last_t, 0.0), self.settings.max_gap_seconds)
        person.last_t = t
        identity = pose.get("identity")
        if identity and identity != person.identity:
            person.identity = identity
            for event in person.open.values():  # named after the event opened
                event["identity"] = identity
                changed.append(event)
        keypoints = np.asarray(pose["keypoints"], dtype=np.float64).reshape(17, 3)
        bbox = np.asarray(pose["bbox_xyxy"], dtype=np.float64).reshape(4)
        body = max(bbox[2] - bbox[0], bbox[3] - bbox[1], 1.0)
        person.good = self._good_evidence(keypoints, body)
        changed += self._update_long_lie(track_id, person, t, dt, keypoints)
        if person.good:
            person.poor_since = None
            person.lengths.append(body)
            changed += self._update_stillness(track_id, person, t, keypoints, body)
            changed += self._update_pacing(track_id, person, t, _centre_x(keypoints, bbox, self.settings))
        else:
            person.poor_since = t if person.poor_since is None else person.poor_since
            if t - person.poor_since >= self.settings.insufficient_reset_seconds:
                changed += self._reset_stillness(person, person.poor_since, "resolved")
        changed += self._expire_pacing(person, t)
        return changed

    def note_fall(self, track_id: int | None, t: float) -> None:
        person = self.people.get(int(track_id or 0))
        if person is not None and person.fall_t is None:
            person.fall_t, person.down_seconds, person.upright_since = float(t), 0.0, None

    def advance(self, t: float, keep: int | None = None) -> list[dict[str, Any]]:
        """Forget people unseen for ``forget_seconds`` by source time ``t``."""
        changed = []
        for track_id in [k for k, p in self.people.items()
                         if k != keep and t - p.last_t > self.settings.forget_seconds]:
            person = self.people.pop(track_id)
            changed += self._close_all(person, "person_lost")
        return changed

    def finish(self) -> list[dict[str, Any]]:
        changed = []
        for person in self.people.values():
            changed += self._close_all(person, "source_ended")
        self.people.clear()
        return changed

    def state(self, track_id: int) -> dict[str, Any]:
        """Progress towards each event for one person, for display."""
        person = self.people.get(int(track_id or 0))
        if person is None:
            return {"evidence": "insufficient", "still_seconds": 0.0, "pacing_turns": 0,
                    "down_after_fall_seconds": None, "active_events": []}
        window = self.settings.pacing_window_seconds
        return {
            "evidence": "good" if person.good else "insufficient",
            "still_seconds": round(person.last_t - person.still_since, 3) if person.still_since is not None else 0.0,
            "pacing_turns": sum(1 for turn, _, _ in person.reversals if person.last_t - turn <= window),
            "down_after_fall_seconds": (round(person.last_t - person.fall_t, 3)
                                        if person.fall_t is not None else None),
            "active_events": sorted(person.open),
        }

    # ------------------------------------------------------------------ rules

    def _good_evidence(self, keypoints: np.ndarray, body: float) -> bool:
        visible = keypoints[:, 2] >= self.settings.joint_confidence
        return (int(visible.sum()) >= self.settings.min_joints
                and int(visible[list(TORSO)].sum()) >= 3 and body >= self.settings.min_body_pixels)

    def _update_stillness(self, track_id, person, t, keypoints, body):
        s = self.settings
        person.recent.append((t, keypoints, body))
        while person.recent and t - person.recent[0][0] > s.stillness_window_seconds:
            person.recent.popleft()
        if t - person.recent[0][0] < 0.8 * s.stillness_window_seconds or len(person.recent) < 6:
            return []
        points = np.stack([item[1] for item in person.recent])  # (n, 17, 3)
        shared = (points[:, :, 2] >= s.joint_confidence).all(axis=0)
        if int(shared.sum()) < s.min_joints:
            return []  # cannot judge stillness: neither still nor moving
        xy = points[:, shared, :2]
        spread = np.percentile(xy, 90, axis=0) - np.percentile(xy, 10, axis=0)
        motion = float(np.percentile(np.linalg.norm(spread, axis=1), 90)) / float(np.median(
            [item[2] for item in person.recent]))
        if motion < s.stillness_threshold:
            person.moving_since = None
            if person.still_since is None:
                person.still_since = person.recent[0][0]
            if (t - person.still_since >= s.inactivity_seconds and person.fall_t is None
                    and "prolonged_inactivity" not in person.open):
                return [self._open(person, "prolonged_inactivity", track_id, person.still_since, t,
                                   {"still_seconds": t - person.still_since,
                                    "torso_angle_degrees": _torso_angle(keypoints, s.joint_confidence)})]
            event = person.open.get("prolonged_inactivity")
            if event is not None:
                event["evidence"]["still_seconds"] = round(t - person.still_since, 3)
            return []
        person.moving_since = t if person.moving_since is None else person.moving_since
        if t - person.moving_since >= s.movement_reset_seconds:
            return self._reset_stillness(person, person.moving_since, "resolved")
        return []

    def _reset_stillness(self, person, at, reason):
        person.still_since = person.moving_since = None
        return self._close(person, "prolonged_inactivity", at, reason)

    def _update_pacing(self, track_id, person, t, x):
        s = self.settings
        if x is None:
            return []
        unit = float(np.median(person.lengths))
        turn = s.pacing_turn_body_lengths * unit
        if person.leg_start_x is None:
            person.leg_start_x, person.leg_start_t = x, t
            person.extreme_x, person.extreme_t = x, t
            return []
        if person.direction == 0:
            if abs(x - person.leg_start_x) >= turn:
                person.direction = 1 if x > person.leg_start_x else -1
                person.extreme_x, person.extreme_t = x, t
            return []
        if (x - person.extreme_x) * person.direction > 0:
            person.extreme_x, person.extreme_t = x, t
            return []
        if abs(x - person.extreme_x) < turn:
            return []
        # Walked back far enough: the furthest point was a turn.
        leg = abs(person.extreme_x - person.leg_start_x) / unit
        if leg >= s.pacing_leg_body_lengths:
            person.reversals.append((person.extreme_t, person.leg_start_t, leg))
        person.leg_start_x, person.leg_start_t = person.extreme_x, person.extreme_t
        person.extreme_x, person.extreme_t = x, t
        person.direction = -person.direction
        while person.reversals and t - person.reversals[0][0] > s.pacing_window_seconds:
            person.reversals.popleft()
        turns = len(person.reversals)
        event = person.open.get("pacing")
        if event is not None:
            event["evidence"].update(turns=event["evidence"]["turns"] + (leg >= s.pacing_leg_body_lengths),
                                     duration_seconds=round(t - event["start_seconds"], 3))
            return []
        if turns >= s.pacing_reversals:
            legs = [item[2] for item in person.reversals]
            start = person.reversals[0][1]
            return [self._open(person, "pacing", track_id, start, t, {
                "turns": turns, "mean_leg_body_lengths": float(np.mean(legs)),
                "duration_seconds": t - start})]
        return []

    def _expire_pacing(self, person, t):
        event = person.open.get("pacing")
        last_turn = person.reversals[-1][0] if person.reversals else None
        if event is not None and (last_turn is None or t - last_turn > self.settings.pacing_end_seconds):
            return self._close(person, "pacing", last_turn if last_turn is not None else t, "resolved")
        return []

    def _restart_motion(self, person):
        person.recent.clear()
        person.still_since = person.moving_since = None
        person.direction, person.leg_start_x = 0, None
        person.reversals.clear()

    def _update_long_lie(self, track_id, person, t, dt, keypoints):
        s = self.settings
        if person.fall_t is None or t < person.fall_t:
            return []
        # Sitting or standing upright counts as up; only a clearly horizontal torso
        # counts as down, so a person resting in a chair after a (possibly false)
        # fall alert is never escalated. An unseen torso counts as neither.
        angle = _torso_angle(keypoints, 0.3)
        if angle is not None and angle < UPRIGHT_DEGREES:
            person.upright_since = t if person.upright_since is None else person.upright_since
            if t - person.upright_since >= s.getup_seconds:
                at = person.upright_since
                person.fall_t, person.upright_since = None, None
                return self._close(person, "long_lie", at, "resolved")
            return []
        person.upright_since = None
        if angle is not None and angle > LYING_DEGREES:
            person.down_seconds += dt
        elapsed = t - person.fall_t
        if (elapsed >= s.long_lie_seconds and person.down_seconds >= 0.5 * elapsed
                and "long_lie" not in person.open):
            return [self._open(person, "long_lie", track_id, person.fall_t, t,
                               {"down_seconds": person.down_seconds, "seconds_since_fall": elapsed})]
        event = person.open.get("long_lie")
        if event is not None:
            event["evidence"].update(down_seconds=round(person.down_seconds, 3),
                                     seconds_since_fall=round(elapsed, 3))
        return []

    # ------------------------------------------------------------------ events

    def _open(self, person, kind, track_id, start, t, evidence):
        event = {"event_id": self._new_id(), "event_type": kind, "severity": SEVERITY[kind],
                 "track_id": track_id or None, "identity": person.identity, "start_seconds": _seconds(start),
                 "detected_at_seconds": _seconds(t), "end_seconds": None, "end_reason": None,
                 "evidence": {k: round(float(v), 3) for k, v in evidence.items() if v is not None}}
        person.open[kind] = event
        self.events.append(event)
        return event

    def _close(self, person, kind, at, reason):
        event = person.open.pop(kind, None)
        if event is None:
            return []
        event["end_seconds"] = _seconds(max(float(at), event["detected_at_seconds"]))
        event["end_reason"] = reason
        return [event]

    def _close_all(self, person, reason):
        changed = []
        for kind in list(person.open):
            changed += self._close(person, kind, person.last_t, reason)
        return changed


def settings_from_mapping(values: Mapping[str, Any]) -> BehaviourSettings:
    return BehaviourSettings(**dict(values))


def _counter() -> Callable[[], str]:
    count = iter(range(1, 1 << 62))
    return lambda: f"b{next(count)}"


def _seconds(value: float) -> float:
    return round(float(value), 6)


def _centre_x(keypoints: np.ndarray, bbox: np.ndarray, settings: BehaviourSettings) -> float | None:
    """Mean x of confident hips and shoulders (arm swing moves the box, not these)."""
    joints = keypoints[list(TORSO)]
    visible = joints[:, 2] >= settings.joint_confidence
    if visible.sum() >= 2:
        return float(joints[visible, 0].mean())
    return float((bbox[0] + bbox[2]) / 2)


def _torso_angle(keypoints: np.ndarray, confidence: float) -> float | None:
    """Degrees between the hip→shoulder line and image vertical; None if not visible."""
    points = keypoints[list(TORSO)]
    if not (points[:, 2] >= confidence).all():
        return None
    shoulder = points[:2, :2].mean(axis=0)
    hip = points[2:, :2].mean(axis=0)
    vector = shoulder - hip
    return abs(math.degrees(math.atan2(float(vector[0]), float(-vector[1]))))
