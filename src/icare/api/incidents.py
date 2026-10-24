"""Incident rule, applied independently to every tracked person.

Per person: record one incident when P(Fall) >= 0.50 has been reached on
``confirmations`` consecutive predictions while armed, then re-arm only after
three consecutive predictions below 0.35. A lower probability never means
"recovered"; it only allows that person's next distinct fall to be recorded.
One person's incident never suppresses, clears or delays another person's.
"""
from __future__ import annotations

from dataclasses import dataclass, field


FALL_THRESHOLD = 0.50
CLEAR_THRESHOLD = 0.35
CLEAR_WINDOWS = 3


@dataclass
class IncidentTracker:
    fall_threshold: float = FALL_THRESHOLD
    clear_threshold: float = CLEAR_THRESHOLD
    clear_windows: int = CLEAR_WINDOWS
    # Consecutive high predictions needed; 1 is the baseline rule.
    confirmations: int = 1
    armed: bool = True
    clear_count: int = 0
    high_count: int = 0

    def __post_init__(self) -> None:
        if self.confirmations < 1:
            raise ValueError("confirmations must be at least 1")

    def observe(self, fall_probability: float) -> bool:
        """Return True when this prediction starts a new incident."""

        if self.armed:
            self.high_count = self.high_count + 1 if fall_probability >= self.fall_threshold else 0
            if self.high_count >= self.confirmations:
                self.armed = False
                self.clear_count = self.high_count = 0
                return True
            return False
        if fall_probability < self.clear_threshold:
            self.clear_count += 1
            if self.clear_count >= self.clear_windows:
                self.armed = True
                self.clear_count = 0
        else:
            self.clear_count = 0
        return False


@dataclass
class PersonIncidents:
    """One IncidentTracker per track ID, created on that person's first prediction."""

    confirmations: int = 1
    _trackers: dict[int, IncidentTracker] = field(default_factory=dict)

    def observe(self, track_id: int, fall_probability: float) -> bool:
        tracker = self._trackers.setdefault(track_id, IncidentTracker(confirmations=self.confirmations))
        return tracker.observe(fall_probability)

    def latched(self, track_id: int) -> bool:
        """True while this person's last incident has not re-armed."""
        tracker = self._trackers.get(track_id)
        return tracker is not None and not tracker.armed

    def any_latched(self) -> bool:
        """True while any person's incident has not re-armed, visible or not."""
        return any(not tracker.armed for tracker in self._trackers.values())
