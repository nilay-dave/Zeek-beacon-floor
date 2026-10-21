"""The generators, and the floor measurement built on them."""

from __future__ import annotations

import numpy as np
import pytest

from zbf.conn import Connection
from zbf.detect import DETECTORS
from zbf.floor import hours_of_capture, measure, sweep
from zbf.pairs import PairSeries, group, score
from zbf.synth import COBALT_STRIKE, SYMMETRIC, Mix, beacon, negatives, positives


def test_cobalt_strike_jitter_only_ever_shortens_the_sleep():
    """The sourced behaviour: sleep 300 20 produces 240 to 300, never 301.

    This is the difference the project turns on. The symmetric model most
    tooling assumes spreads intervals over twice the range at the same stated
    percentage, so the two are not the same experiment.
    """
    rng = np.random.default_rng(0)
    intervals = np.diff(beacon(4000, 300.0, 0.2, rng, model=COBALT_STRIKE))
    assert intervals.max() <= 300.0 + 1e-9
    assert intervals.min() >= 240.0 - 1e-9


def test_symmetric_jitter_spans_twice_the_range_at_the_same_percentage():
    rng = np.random.default_rng(0)
    one_sided = np.diff(beacon(4000, 300.0, 0.2, rng, model=COBALT_STRIKE))
    two_sided = np.diff(beacon(4000, 300.0, 0.2, rng, model=SYMMETRIC))
    assert two_sided.max() > one_sided.max()
    assert (two_sided.max() - two_sided.min()) == pytest.approx(2 * (one_sided.max() - one_sided.min()), rel=0.05)


def test_an_unknown_jitter_model_is_refused():
    with pytest.raises(ValueError, match="unknown jitter model"):
        beacon(10, 60.0, 0.1, np.random.default_rng(0), model="gaussian")


def test_jitter_outside_zero_to_one_is_refused():
    with pytest.raises(ValueError, match="fraction of the period"):
        beacon(10, 60.0, 1.5, np.random.default_rng(0))


def test_missed_check_ins_remove_arrivals_but_keep_the_first():
    rng = np.random.default_rng(1)
    full = beacon(200, 60.0, 0.0, rng, miss_rate=0.0)
    sparse = beacon(200, 60.0, 0.0, rng, miss_rate=0.4)
    assert sparse.size < full.size
    assert sparse[0] == 0.0


def test_the_negative_mix_must_sum_to_one():
    with pytest.raises(ValueError, match="must sum to 1"):
        Mix(poisson_share=0.5, bursty_share=0.9)


def test_negatives_are_a_mix_rather_than_all_poisson():
    """Poisson only negatives would make every false positive rate flattering."""
    rng = np.random.default_rng(2)
    series = negatives(40, 100, rng, Mix(0.5, 0.5))
    assert len(series) == 100
    spans = sorted(float(s[-1] - s[0]) for s in series)
    # Session traffic spans far longer for the same arrival count, so the two
    # populations are visibly different rather than nominally so.
    assert spans[-1] > 10 * spans[0]


def test_detection_improves_with_more_intervals():
    detector = DETECTORS["interval-cv"]
    rng = np.random.default_rng(3)
    few = measure(detector, 4, 0.8, rng, samples=200)
    many = measure(detector, 32, 0.8, rng, samples=200)
    assert many.tpr > few.tpr


def test_detection_degrades_with_more_jitter():
    detector = DETECTORS["interval-cv"]
    rng = np.random.default_rng(4)
    clean = measure(detector, 12, 0.1, rng, samples=200)
    noisy = measure(detector, 12, 1.0, rng, samples=200)
    assert clean.tpr > noisy.tpr


def test_a_detector_that_declines_is_scored_zero_not_excluded():
    """Abstaining must not be a way to look good on the hard cases."""
    detector = DETECTORS["autocorrelation"]
    point = measure(detector, 4, 0.5, np.random.default_rng(5), samples=50)
    assert point.scored_positives == 0
    assert point.tpr == 0.0


def test_required_intervals_reports_never_rather_than_a_missing_value():
    result = sweep(DETECTORS["bowley-skew"], [4, 6], [1.0], seeds=1, samples=100)
    assert result.required_intervals(1.0, target=0.99) is None


def test_required_intervals_finds_the_smallest_grid_point_that_reaches_the_target():
    result = sweep(DETECTORS["interval-cv"], [4, 8, 16, 32], [0.4], seeds=2, samples=200)
    needed = result.required_intervals(0.4, target=0.9)
    assert needed in (4, 8, 16, 32)
    reached = {p.intervals: p.tpr for p in result.at(0.4)}
    assert reached[needed] >= 0.9
    for smaller in [n for n in (4, 8, 16, 32) if n < needed]:
        assert reached[smaller] < 0.9


def test_hours_of_capture_converts_intervals_into_a_capture_window():
    """The conversion the field guidance skips."""
    assert hours_of_capture(12, 3600.0) == pytest.approx(12.0)
    assert hours_of_capture(12, 60.0) == pytest.approx(0.2)
    assert hours_of_capture(12, 86400.0) == pytest.approx(288.0)


def test_the_sweep_is_reproducible_from_its_seeds():
    one = sweep(DETECTORS["mad-ratio"], [8, 16], [0.5], seeds=2, samples=150)
    two = sweep(DETECTORS["mad-ratio"], [8, 16], [0.5], seeds=2, samples=150)
    assert [p.tpr for p in one.points] == [p.tpr for p in two.points]


def connections(pairs):
    return [Connection(ts=ts, orig=o, resp=r, resp_port=p) for o, r, p, ts in pairs]


def test_pairs_are_split_by_destination_port():
    """443 and 53 to the same host are two behaviours, not one series."""
    rows = [("10.0.0.1", "8.8.8.8", 443, t) for t in range(0, 600, 60)]
    rows += [("10.0.0.1", "8.8.8.8", 53, t) for t in range(0, 600, 60)]
    series = group(connections(rows), minimum=4)
    assert {s.resp_port for s in series} == {443, 53}
    assert all(s.connections == 10 for s in series)


def test_pairs_below_the_minimum_are_dropped():
    rows = [("10.0.0.1", "8.8.8.8", 443, t) for t in range(0, 180, 60)]
    assert group(connections(rows), minimum=4) == []


def test_scoring_reports_a_declining_detector_as_none_not_zero():
    series = PairSeries(
        orig="10.0.0.1",
        resp="8.8.8.8",
        resp_port=443,
        timestamps=np.array([0.0, 60.0, 120.0, 180.0]),
        bytes_sent=0,
    )
    (scored,) = score([series])
    assert scored.scores["autocorrelation"] is None
    assert scored.scores["interval-cv"] is not None


def test_positives_draw_a_period_per_beacon():
    rng = np.random.default_rng(6)
    series = positives(20, 40, 0.1, rng)
    periods = {round(float(np.median(np.diff(s))), 3) for s in series}
    assert len(periods) > 30


def test_positives_and_negatives_agree_on_what_an_interval_is():
    """The mismatch that made the published floors wrong.

    beacon() built N sleeps and prepended t=0, giving N intervals. poisson()
    and bursty() returned N arrivals, giving N-1. So every comparison scored
    positives at one series length while calibrating the threshold at another.
    """
    rng = np.random.default_rng(0)
    wanted = 6
    for series in positives(wanted, 3, 0.0, rng) + negatives(wanted, 4, rng):
        assert series.size - 1 == wanted


def test_the_shortest_grid_point_is_measured_rather_than_forced_to_zero():
    """At intervals == min_intervals every negative used to be refused.

    With no negative scored there was no threshold, and the early return
    reported a detection rate of zero for a detector that had scored every
    positive correctly. docs/metrics.json carried "6": 0.0 for both spectral
    detectors followed by "8": 1.0.
    """
    for name in ("autocorrelation", "spectral"):
        detector = DETECTORS[name]
        point = measure(detector, detector.min_intervals, 0.0, np.random.default_rng(1), samples=200)
        assert point.scored_negatives == 200
        assert point.tpr > 0.5
