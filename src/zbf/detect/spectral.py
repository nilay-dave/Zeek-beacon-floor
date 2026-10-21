"""The two detectors that look at the arrival train rather than the intervals.

A dispersion statistic treats the intervals as a bag of numbers and cannot see
order. These two bin the arrivals into a regular time series and look for
periodic structure in it, which is a different question and fails differently:
they survive missed check ins, which only remove energy from the peak, and they
need more samples than a dispersion statistic does.

Both bin at a quarter of the median interval. Finer bins put every arrival in
its own bin and the series becomes impulses with no structure to find; coarser
bins smear adjacent arrivals together and destroy the period.
"""

from __future__ import annotations

import numpy as np

from zbf.detect.base import Detector, clamp01

BINS_PER_INTERVAL = 4
# Below this many bins an FFT has too few frequency cells for a peak to mean
# anything, and the normalisation below starts producing high scores on noise.
MINIMUM_BINS = 16
# A beacon observed for n intervals bins to about 4n cells by construction, so
# anything beyond this multiple of that is a series whose intervals differ by
# orders of magnitude. Session traffic is the usual case: a burst of
# connections four seconds apart, then an hour of silence, which sets the bin
# width from the burst and the length from the silence. Thirty two arrivals
# that way produced an 11,868 cell array that was 99.7 percent empty.
#
# Refusing is the right answer twice over. The autocorrelation of a mostly
# empty array is a measure of its own sparseness rather than of any period, and
# computing it made this detector seventy times slower than every other one in
# the project, which is how the problem was found.
SPARSITY_ALLOWANCE = 8


TOO_SHORT = "too short"
TOO_SPARSE = "too sparse"


def _binned(intervals: np.ndarray) -> tuple[np.ndarray | None, str | None]:
    """Rebuild an arrival train from the intervals and bin it.

    Returns the reason when it cannot, because the two reasons mean opposite
    things to a caller and both used to collapse to a score of zero.

    TOO_SHORT is a refusal: there is not enough series to judge, and the
    caller must report that rather than "not a beacon".

    TOO_SPARSE is a judgement: the intervals differ by orders of magnitude, so
    the arrival train is mostly empty. That is strong evidence against a
    beacon and scores zero, which also keeps session traffic in the negative
    class where the false positive rate needs it.
    """
    median = float(np.median(intervals))
    if median <= 0 or not np.isfinite(median):
        return None, TOO_SHORT
    arrivals = np.concatenate([[0.0], np.cumsum(intervals)])
    span = float(arrivals[-1])
    width = median / BINS_PER_INTERVAL
    if not np.isfinite(span) or width <= 0 or span / width > 1e9:
        return None, TOO_SPARSE
    count = int(np.ceil(span / width)) + 1
    if count < MINIMUM_BINS:
        return None, TOO_SHORT
    if count > SPARSITY_ALLOWANCE * BINS_PER_INTERVAL * arrivals.size:
        return None, TOO_SPARSE
    series = np.zeros(count, dtype=float)
    np.add.at(series, np.minimum((arrivals / width).astype(int), count - 1), 1.0)
    return series - series.mean(), None


def _autocorrelation_peak(intervals: np.ndarray) -> float | None:
    series, reason = _binned(intervals)
    if series is None:
        return None if reason == TOO_SHORT else 0.0
    energy = float(np.dot(series, series))
    if energy <= 0:
        return 0.0
    # Through the frequency domain rather than np.correlate, which is a direct
    # O(n squared) convolution. The series is already being FFTed by the other
    # detector in this module, and at a few thousand cells the difference is
    # the difference between a benchmark that finishes and one that is
    # abandoned.
    padded = int(2 ** np.ceil(np.log2(2 * series.size)))
    spectrum = np.fft.rfft(series, n=padded)
    correlation = np.fft.irfft(spectrum * np.conjugate(spectrum), n=padded)[: series.size] / energy
    # Lag zero is always 1. The first lags are the width of one arrival spike,
    # so the search starts past them or every series peaks at its own impulse.
    start = BINS_PER_INTERVAL // 2 + 1
    if correlation.size <= start:
        return 0.0
    return clamp01(float(np.max(correlation[start:])))


def _spectral_prominence(intervals: np.ndarray) -> float | None:
    series, reason = _binned(intervals)
    if series is None:
        return None if reason == TOO_SHORT else 0.0
    power = np.abs(np.fft.rfft(series)) ** 2
    if power.size < 3:
        return 0.0
    # Index 0 is the mean, already removed, and carries no period.
    power = power[1:]
    total = float(np.sum(power))
    if total <= 0:
        return 0.0
    # The share of spectral energy in the strongest frequency, measured against
    # what white noise would give.
    #
    # The floor is NOT 1/k, the mean share per bin. The statistic is a maximum,
    # and for k independent exponential bin powers the expected maximum share
    # is the harmonic number over k, which is ln(k) times larger. Subtracting
    # the mean left a noise floor that still fell with series length: pure
    # noise scored 0.16 at 16 bins and 0.006 at 1024, so on a real log a short
    # pair scored higher than a long one at the same degree of irregularity.
    share = float(np.max(power)) / total
    k = power.size
    floor = float(np.sum(1.0 / np.arange(1, k + 1))) / k
    if floor >= 1.0:
        return 0.0
    return clamp01((share - floor) / (1.0 - floor))


AUTOCORRELATION = Detector(
    name="autocorrelation",
    summary="The strongest repeat in the binned arrival train at a non zero lag.",
    blind_to="a beacon whose interval changes during the capture, which has no single lag, "
    "and anything shorter than sixteen bins",
    min_intervals=6,
    _score=_autocorrelation_peak,
)

SPECTRAL = Detector(
    name="spectral",
    summary="The share of spectral energy in the strongest frequency, above the noise floor.",
    blind_to="the same drift autocorrelation misses, and a beacon running at a period close "
    "to the capture length, which has too few cycles to form a peak",
    min_intervals=6,
    _score=_spectral_prominence,
)
