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


def _binned(intervals: np.ndarray) -> np.ndarray | None:
    """Rebuild an arrival train from the intervals and bin it."""
    median = float(np.median(intervals))
    if median <= 0:
        return None
    arrivals = np.concatenate([[0.0], np.cumsum(intervals)])
    width = median / BINS_PER_INTERVAL
    count = int(np.ceil(arrivals[-1] / width)) + 1
    if count < MINIMUM_BINS:
        return None
    if count > SPARSITY_ALLOWANCE * BINS_PER_INTERVAL * arrivals.size:
        return None
    series = np.zeros(count, dtype=float)
    np.add.at(series, np.minimum((arrivals / width).astype(int), count - 1), 1.0)
    return series - series.mean()


def _autocorrelation_peak(intervals: np.ndarray) -> float:
    series = _binned(intervals)
    if series is None:
        return 0.0
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


def _spectral_prominence(intervals: np.ndarray) -> float:
    series = _binned(intervals)
    if series is None:
        return 0.0
    power = np.abs(np.fft.rfft(series)) ** 2
    if power.size < 3:
        return 0.0
    # Index 0 is the mean, already removed, and carries no period.
    power = power[1:]
    total = float(np.sum(power))
    if total <= 0:
        return 0.0
    # The share of spectral energy in the strongest frequency. White noise
    # spreads its energy evenly, so this is near 1/len(power); a clean beacon
    # concentrates it. Rescaled so that the noise floor sits near zero rather
    # than at an arbitrary small number that varies with the series length.
    share = float(np.max(power)) / total
    floor = 1.0 / power.size
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
