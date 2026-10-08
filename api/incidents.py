"""Incident rule, per job.

Same semantics as FallDetectionSession._consume_output in icare_app/inference.py:
one incident when P(Fall) >= 0.50 while armed, then re-arm only after three
consecutive predictions below 0.35. A lower probability never means "recovered".
"""
from __future__ import annotations

from dataclasses import dataclass


FALL_THRESHOLD = 0.50
CLEAR_THRESHOLD = 0.35
CLEAR_WINDOWS = 3


@dataclass
class IncidentTracker:
    fall_threshold: float = FALL_THRESHOLD
    clear_threshold: float = CLEAR_THRESHOLD
    clear_windows: int = CLEAR_WINDOWS
    armed: bool = True
    clear_count: int = 0

    def observe(self, fall_probability: float) -> bool:
        """Return True when this prediction starts a new incident."""

        if self.armed and fall_probability >= self.fall_threshold:
            self.armed = False
            self.clear_count = 0
            return True
        if not self.armed:
            if fall_probability < self.clear_threshold:
                self.clear_count += 1
                if self.clear_count >= self.clear_windows:
                    self.armed = True
                    self.clear_count = 0
            else:
                self.clear_count = 0
        return False
