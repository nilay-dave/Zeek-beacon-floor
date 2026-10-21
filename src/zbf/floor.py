"""Measure where a detector stops working.

The floor is the smallest number of observed intervals at which a detector
still finds a given share of beacons, at a false positive rate fixed against
non periodic traffic. Both halves matter: a detection rate quoted without a
false positive rate is a number any detector can reach by scoring everything
high, and a threshold is only meaningful against the traffic it will run on.

Two choices here are deliberately generous to the detectors, and both are
stated in the results rather than buried.

The threshold is recalibrated at every point in the sweep, from negatives with
the same number of intervals. A detector's scores on random traffic shift as
the series gets longer, so a single fixed threshold would do worse than what is
reported here. A hunter runs a fixed threshold. This measures the detector, not
the deployment, and the deployment is harder.

Negatives are non periodic traffic. Benign periodic traffic, which is most of
what a real false positive is, scores like a beacon under every detector here
because it is a beacon in every respect except intent. Counting it as a
negative would make the false positive rate a measure of how much monitoring
software the simulated network runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from zbf.detect import Detector
from zbf.synth import COBALT_STRIKE, negatives, positives

# One in a hundred pairs flagged. On a network with tens of thousands of pairs
# that is already more than a hunter can read, which is the point of fixing it
# low rather than at a textbook 5 percent.
DEFAULT_FPR = 0.01
DEFAULT_TARGET_TPR = 0.9


@dataclass(frozen=True, slots=True)
class Point:
    intervals: int
    jitter: float
    tpr: float
    threshold: float
    scored_positives: int
    scored_negatives: int


@dataclass(slots=True)
class Sweep:
    detector: str
    jitter_model: str
    fpr: float
    miss_rate: float
    points: list[Point] = field(default_factory=list)

    def at(self, jitter: float) -> list[Point]:
        return sorted(
            (p for p in self.points if abs(p.jitter - jitter) < 1e-9),
            key=lambda p: p.intervals,
        )

    def required_intervals(self, jitter: float, target: float = DEFAULT_TARGET_TPR) -> int | None:
        """The fewest intervals reaching ``target`` detection at this jitter.

        None means the detector never reached it anywhere in the sweep, which
        is a finding and not a missing value.
        """
        for point in self.at(jitter):
            if point.tpr >= target:
                return point.intervals
        return None


def measure(
    detector: Detector,
    intervals: int,
    jitter: float,
    rng: np.random.Generator,
    samples: int = 400,
    fpr: float = DEFAULT_FPR,
    model: str = COBALT_STRIKE,
    miss_rate: float = 0.0,
) -> Point:
    """One point: the detection rate at this many intervals and this jitter."""
    positive_scores = [
        score
        for score in (detector.score(series) for series in positives(intervals, samples, jitter, rng, model, miss_rate))
        if score is not None
    ]
    negative_scores = [
        score
        for score in (detector.score(series) for series in negatives(intervals, samples, rng))
        if score is not None
    ]

    # A detector that refuses this many intervals has a detection rate of zero
    # here, which is the honest reading of "it declined to answer". Reporting
    # it as missing would let a detector look good by abstaining on hard cases.
    if not negative_scores or not positive_scores:
        return Point(intervals, jitter, 0.0, float("nan"), len(positive_scores), len(negative_scores))

    threshold = float(np.quantile(negative_scores, 1.0 - fpr))
    detected = float(np.mean([score >= threshold for score in positive_scores]))
    # Positives the detector refused to score count against it, for the same
    # reason: the beacon was there and nothing was said about it.
    detected *= len(positive_scores) / samples
    return Point(intervals, jitter, detected, threshold, len(positive_scores), len(negative_scores))


def sweep(
    detector: Detector,
    interval_grid: list[int],
    jitter_grid: list[float],
    seeds: int = 8,
    samples: int = 400,
    fpr: float = DEFAULT_FPR,
    model: str = COBALT_STRIKE,
    miss_rate: float = 0.0,
) -> Sweep:
    """The full grid, averaged over seeds.

    Averaged for the same reason every other measurement in this project is:
    a single seed at 400 samples puts a confidence interval of several points
    on every cell, and the floor is read off differences smaller than that.
    """
    result = Sweep(detector=detector.name, jitter_model=model, fpr=fpr, miss_rate=miss_rate)
    for jitter in jitter_grid:
        for intervals in interval_grid:
            runs = [
                measure(detector, intervals, jitter, np.random.default_rng(seed), samples, fpr, model, miss_rate)
                for seed in range(seeds)
            ]
            # Every seed may have declined, at which case there is no
            # threshold rather than a threshold of nan-averaged nothing.
            # np.nanmean over an all-nan slice warns and returns nan, and a
            # warning in a benchmark is a thing people learn to scroll past.
            thresholds = [r.threshold for r in runs if np.isfinite(r.threshold)]
            result.points.append(
                Point(
                    intervals=intervals,
                    jitter=jitter,
                    tpr=float(np.mean([r.tpr for r in runs])),
                    threshold=float(np.mean(thresholds)) if thresholds else float("nan"),
                    scored_positives=int(np.mean([r.scored_positives for r in runs])),
                    scored_negatives=int(np.mean([r.scored_negatives for r in runs])),
                )
            )
    return result


def hours_of_capture(intervals: int, period_seconds: float) -> float:
    """Convert a floor in intervals into the capture window that produces it.

    This is the conversion the field guidance skips. Advice to capture for at
    least twelve hours is advice about a clock, and a detector does not see a
    clock. A beacon sleeping sixty seconds gives 720 intervals in twelve hours;
    one sleeping an hour gives twelve.
    """
    return intervals * period_seconds / 3600.0
