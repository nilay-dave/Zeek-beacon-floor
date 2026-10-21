"""The three dispersion and shape detectors.

All three ask the same question, how tightly the intervals cluster, and differ
in what they are robust to. The differences matter: a real beacon misses
check ins, and a statistic that a single missed interval can flatten reports
nothing on traffic that a hunter would have found by eye.
"""

from __future__ import annotations

import numpy as np

from zbf.detect.base import Detector, clamp01


def _coefficient_of_variation(intervals: np.ndarray) -> float:
    mean = float(np.mean(intervals))
    if mean <= 0:
        return 0.0
    # Population standard deviation. The sample correction would make the score
    # depend on how long you watched, which is the confusion this whole project
    # is about.
    return clamp01(1.0 - float(np.std(intervals)) / mean)


def _mad_ratio(intervals: np.ndarray) -> float:
    median = float(np.median(intervals))
    if median <= 0:
        return 0.0
    mad = float(np.median(np.abs(intervals - median)))
    return clamp01(1.0 - mad / median)


# A spread this small relative to the median is rounding, not structure.
# np.diff(np.cumsum(...)) does not return exactly equal intervals for a period
# that is not representable in binary: the error accumulates through the sum,
# so a perfect beacon with a period of 2047.3771254706232 has an interquartile
# spread of 4.5e-13. Testing `spread <= 0` caught only exact equality, so the
# skewness was then computed from that rounding noise and a perfect beacon
# scored 0.0. Across periods drawn the way the benchmark draws them, 39 percent
# of perfect beacons scored below 0.5 for this reason alone.
DEGENERATE_SPREAD = 1e-9


def _bowley_skew(intervals: np.ndarray) -> float:
    q1, q2, q3 = (float(v) for v in np.percentile(intervals, [25, 50, 75]))
    spread = q3 - q1
    median = abs(q2)
    if spread <= DEGENERATE_SPREAD * max(median, 1.0):
        # Every interval in the middle half is identical to within rounding,
        # which is as regular as a series gets. Returning 0 here, as an
        # undefined skew, would score a perfect beacon at zero.
        return 1.0
    return clamp01(1.0 - abs((q3 + q1 - 2 * q2) / spread))


INTERVAL_CV = Detector(
    name="interval-cv",
    summary="One minus the coefficient of variation of the intervals.",
    blind_to="a single missed check in, which the standard deviation turns into irregularity, "
    "and two interleaved beacons, which look like one irregular one",
    min_intervals=3,
    _score=_coefficient_of_variation,
)

MAD_RATIO = Detector(
    name="mad-ratio",
    summary="One minus the median absolute deviation over the median, so outliers do not dominate.",
    blind_to="a slow drift in the interval, which stays close to the median throughout; "
    "anything about the order the intervals arrived in; and a bare majority of identical "
    "intervals, which sets the deviation to zero and scores a perfect 1 however wild the rest are",
    min_intervals=3,
    _score=_mad_ratio,
)

BOWLEY_SKEW = Detector(
    name="bowley-skew",
    summary="One minus the absolute Bowley skewness, which catches one sided jitter.",
    blind_to="symmetric jitter of any size, which is skew free and therefore scores like a "
    "perfect beacon, so this is a shape test and not a regularity test",
    min_intervals=4,
    _score=_bowley_skew,
)
