"""Generate the traffic the floor is measured on.

Positives are beacons. Negatives are non periodic traffic. The separation this
project measures is periodic against not periodic, and not malicious against
benign, which is a distinction section "What this cannot tell you" in the
README refuses to blur: a monitoring agent checking in every sixty seconds is
periodic, scores like a beacon under every detector here, and should.

Two jitter models, because the word means two things.

``cobalt-strike`` is the sourced one. Cobalt Strike's ``sleep`` command takes a
jitter percentage that only ever shortens the sleep: ``sleep 300 20`` produces
a random sleep between 240 and 300 seconds. The interval set is a maximum.

``symmetric`` is the one most tooling and most writing assumes, where the
interval varies both ways around the nominal value.

They are not the same experiment. At the same stated percentage the symmetric
model spreads intervals over twice the range, so a floor measured under it is
a floor for a beacon nobody configured. Both are measured, and the sourced one
is the headline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

COBALT_STRIKE = "cobalt-strike"
SYMMETRIC = "symmetric"
JITTER_MODELS = (COBALT_STRIKE, SYMMETRIC)


def beacon(
    intervals: int,
    period: float,
    jitter: float,
    rng: np.random.Generator,
    model: str = COBALT_STRIKE,
    miss_rate: float = 0.0,
) -> np.ndarray:
    """Connection start times for one beacon.

    ``jitter`` is a fraction of the period. ``miss_rate`` is the share of check
    ins that never happen, which is what a laptop closing its lid looks like in
    a conn.log, and which is the thing dispersion statistics handle worst.
    """
    if not 0.0 <= jitter <= 1.0:
        raise ValueError(f"jitter is a fraction of the period, got {jitter}")
    if model == COBALT_STRIKE:
        sleeps = period * (1.0 - rng.uniform(0.0, jitter, intervals))
    elif model == SYMMETRIC:
        sleeps = period * (1.0 + rng.uniform(-jitter, jitter, intervals))
    else:
        raise ValueError(f"unknown jitter model {model!r}, expected one of {JITTER_MODELS}")

    arrivals = np.concatenate([[0.0], np.cumsum(sleeps)])
    if miss_rate > 0:
        kept = rng.random(arrivals.size) >= miss_rate
        kept[0] = True
        arrivals = arrivals[kept]
    return arrivals


def poisson(count: int, rate_per_hour: float, rng: np.random.Generator) -> np.ndarray:
    """Memoryless traffic: a workstation talking to something when a person acts."""
    gaps = rng.exponential(3600.0 / rate_per_hour, count)
    return np.cumsum(gaps)


def bursty(count: int, rng: np.random.Generator, session_mean: int = 8) -> np.ndarray:
    """Traffic in sessions: a burst of connections, then a long quiet gap.

    This is the negative that matters. Inside a burst the intervals are short
    and similar, so a dispersion statistic computed over a window that lands
    inside one burst sees regularity. Poisson traffic alone would make the
    false positive rate look better than any hunter has ever seen it.
    """
    arrivals: list[float] = []
    now = 0.0
    while len(arrivals) < count:
        burst = max(2, int(rng.poisson(session_mean)))
        gaps = rng.exponential(4.0, burst)
        for gap in gaps:
            now += gap
            arrivals.append(now)
        now += rng.exponential(3600.0)
    return np.array(arrivals[:count])


@dataclass(frozen=True, slots=True)
class Mix:
    """The negative class, as proportions that must sum to one."""

    poisson_share: float = 0.5
    bursty_share: float = 0.5

    def __post_init__(self) -> None:
        total = self.poisson_share + self.bursty_share
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"negative class shares must sum to 1, got {total}")


def negatives(count: int, samples: int, rng: np.random.Generator, mix: Mix | None = None) -> list[np.ndarray]:
    """``samples`` series of non periodic traffic, each with ``count`` arrivals."""
    mix = mix or Mix()
    how_many_poisson = int(round(samples * mix.poisson_share))
    series = [poisson(count, rng.uniform(1.0, 60.0), rng) for _ in range(how_many_poisson)]
    series += [bursty(count, rng) for _ in range(samples - how_many_poisson)]
    return series


def positives(
    count: int,
    samples: int,
    jitter: float,
    rng: np.random.Generator,
    model: str = COBALT_STRIKE,
    miss_rate: float = 0.0,
) -> list[np.ndarray]:
    """``samples`` beacons, each observed for ``count`` intervals.

    The period is drawn per beacon rather than fixed, because a floor measured
    at one period would be a floor for that period. Every detector here is
    scale free, so this should not matter, and drawing it is how that claim
    gets tested rather than assumed.
    """
    return [
        beacon(count, float(rng.uniform(30.0, 3600.0)), jitter, rng, model=model, miss_rate=miss_rate)
        for _ in range(samples)
    ]
