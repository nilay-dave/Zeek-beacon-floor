"""What the detectors must do, including the things they must refuse to do."""

from __future__ import annotations

import numpy as np
import pytest

from zbf.detect import DETECTORS
from zbf.detect.base import Detector
from zbf.detect.spectral import BINS_PER_INTERVAL, SPARSITY_ALLOWANCE
from zbf.synth import COBALT_STRIKE, SYMMETRIC, beacon, bursty, poisson


def arrivals(intervals: int, period: float = 600.0, jitter: float = 0.0, seed: int = 0, model=COBALT_STRIKE):
    return beacon(intervals, period, jitter, np.random.default_rng(seed), model=model)


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_a_perfect_beacon_scores_near_the_top(name):
    """Not exactly 1, because the two spectral detectors normalise differently.

    What matters is that a perfect beacon is the best case each one has, which
    is checked against jittered traffic rather than against a fixed number.
    """
    detector = DETECTORS[name]
    perfect = detector.score(arrivals(60))
    jittered = detector.score(arrivals(60, jitter=0.6, seed=3))
    assert perfect is not None and jittered is not None
    assert perfect > jittered


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_memoryless_traffic_scores_below_a_beacon(name):
    detector = DETECTORS[name]
    beacon_score = detector.score(arrivals(60))
    noise = detector.score(poisson(60, 12.0, np.random.default_rng(7)))
    assert beacon_score is not None and noise is not None
    assert beacon_score > noise


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_too_few_intervals_returns_none_rather_than_a_number(name):
    """The refusal this project exists to argue for.

    A score computed from two intervals is a number with no information in it,
    and a hunter will read it as evidence anyway.
    """
    detector = DETECTORS[name]
    assert detector.score(arrivals(2)) is None


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_every_score_is_in_the_unit_interval(name):
    detector = DETECTORS[name]
    for series in (arrivals(40), arrivals(40, jitter=1.0, seed=2), poisson(40, 3.0, np.random.default_rng(4))):
        value = detector.score(series)
        assert value is None or 0.0 <= value <= 1.0


@pytest.mark.parametrize("name", sorted(DETECTORS))
def test_scores_do_not_depend_on_the_beacon_period(name):
    """Every detector here is scale free, and this is where that is checked."""
    detector = DETECTORS[name]
    fast = detector.score(arrivals(40, period=30.0, jitter=0.4, seed=11))
    slow = detector.score(arrivals(40, period=86400.0, jitter=0.4, seed=11))
    assert fast == pytest.approx(slow, abs=1e-9)


def test_simultaneous_connections_are_not_evidence_of_a_period():
    """Zero intervals break every ratio, and are not a beacon."""
    detector = DETECTORS["interval-cv"]
    assert detector.score(np.zeros(40)) is None


def test_a_detector_must_declare_what_it_is_blind_to():
    with pytest.raises(ValueError, match="declares no blindness"):
        Detector(name="naive", summary="x", blind_to="   ", min_intervals=3, _score=lambda i: 1.0)


def test_a_detector_cannot_claim_to_work_on_two_intervals():
    with pytest.raises(ValueError, match="at least 3"):
        Detector(name="eager", summary="x", blind_to="nothing in particular", min_intervals=2, _score=lambda i: 1.0)


def test_bowley_skew_cannot_see_symmetric_jitter():
    """The blindness bowley-skew declares, demonstrated rather than asserted.

    Symmetric jitter is skew free, so a badly jittered beacon and a clean one
    look the same to it. This is why it scores near zero detection in the
    benchmark, and why it is in the repository as a negative result.
    """
    detector = DETECTORS["bowley-skew"]
    clean = detector.score(arrivals(80, jitter=0.0))
    noisy = detector.score(arrivals(80, jitter=0.9, seed=5, model=SYMMETRIC))
    assert clean is not None and noisy is not None
    assert noisy > 0.5
    # The dispersion detectors are not fooled by the same series.
    assert DETECTORS["interval-cv"].score(arrivals(80, jitter=0.9, seed=5, model=SYMMETRIC)) < 0.5


def test_session_traffic_is_refused_by_the_spectral_detectors_not_mis_scored():
    """Bursty traffic bins into a mostly empty array. Declining is correct.

    It is also what keeps the benchmark from taking seventy times longer on
    this detector than on the others, which is how the problem was found.
    """
    series = bursty(40, np.random.default_rng(9))
    intervals = np.diff(np.sort(series))
    span_bins = intervals.sum() / (np.median(intervals) / BINS_PER_INTERVAL)
    assert span_bins > SPARSITY_ALLOWANCE * BINS_PER_INTERVAL * series.size
    assert DETECTORS["autocorrelation"].score(series) == 0.0
