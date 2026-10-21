"""What a detector is, and what every detector has to declare.

A detector takes the start times of the connections between one pair and
returns a score in [0, 1], where 1 means perfectly periodic. Scores are
comparable across detectors by construction, because the floor measurement
sets a threshold per detector at a fixed false positive rate and a detector
whose scores meant something different would be compared at the wrong point.

Two requirements are enforced rather than documented.

``min_intervals`` is a refusal, not a hint. Below it the detector returns None.
Every statistic here is defined on three samples and meaningless on three, and
a score computed from two intervals is a number with no information in it that
a hunter will nonetheless read as evidence. The floor measurement exists
because of exactly that gap, so the library does not paper over it.

``blind_to`` is required and may not be empty. A detector is a decision about
what to ignore, and one that claims to ignore nothing has an assumption nobody
has looked for yet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Detector:
    name: str
    summary: str
    blind_to: str
    min_intervals: int
    _score: object

    def __post_init__(self) -> None:
        if not self.blind_to.strip():
            raise ValueError(
                f"detector {self.name!r} declares no blindness. Every detector ignores something; "
                "if none is obvious the assumption has not been found yet."
            )
        if self.min_intervals < 3:
            raise ValueError(
                f"detector {self.name!r} claims to work on {self.min_intervals} intervals. "
                "Every statistic here needs at least 3."
            )

    def score(self, timestamps: np.ndarray) -> float | None:
        """Score one pair's connection start times, or None if there are too few."""
        ordered = np.sort(np.asarray(timestamps, dtype=float))
        intervals = np.diff(ordered)
        if intervals.size < self.min_intervals:
            return None
        # Simultaneous connections produce zero intervals, which are not evidence
        # of periodicity and break every ratio below. A pair that is nothing but
        # simultaneous connections has no timing signal at all.
        intervals = intervals[intervals > 0]
        if intervals.size < self.min_intervals:
            return None
        # A detector may refuse on its own terms as well: the spectral pair
        # needs a minimum number of bins, which depends on the span and not
        # only on the count. Its refusal propagates rather than becoming a
        # confident zero.
        value = self._score(intervals)
        if value is None:
            return None
        return float(np.clip(value, 0.0, 1.0))


def clamp01(value: float) -> float:
    if not np.isfinite(value):
        return 0.0
    return float(min(1.0, max(0.0, value)))
