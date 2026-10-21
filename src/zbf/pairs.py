"""Group a conn.log into the series a detector can score.

A beacon is a property of a pair, not of a connection, so the unit throughout
is (originator, responder, responder port). Port is part of the key because a
host talking to one destination on 443 and on 53 is doing two different things,
and merging them produces an interval series that belongs to neither.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from zbf.conn import Connection
from zbf.detect import DETECTORS, Detector


@dataclass(frozen=True, slots=True)
class PairSeries:
    orig: str
    resp: str
    resp_port: int
    timestamps: np.ndarray
    bytes_sent: int

    @property
    def connections(self) -> int:
        return int(self.timestamps.size)

    @property
    def intervals(self) -> int:
        return max(0, self.connections - 1)

    @property
    def span_hours(self) -> float:
        if self.timestamps.size < 2:
            return 0.0
        return float(self.timestamps[-1] - self.timestamps[0]) / 3600.0

    @property
    def median_period(self) -> float:
        if self.timestamps.size < 2:
            return 0.0
        return float(np.median(np.diff(self.timestamps)))

    def label(self) -> str:
        return f"{self.orig} -> {self.resp}:{self.resp_port}"


def group(connections: Iterable[Connection], minimum: int = 4) -> list[PairSeries]:
    """Collect connections into pairs, dropping pairs below ``minimum``.

    ``minimum`` counts connections, not intervals. The default of 4 is the
    smallest a detector here accepts, and the floor measurement says plainly
    that a result at that size is not worth reading.
    """
    buckets: dict[tuple[str, str, int], list[Connection]] = {}
    for connection in connections:
        buckets.setdefault(connection.pair, []).append(connection)

    series: list[PairSeries] = []
    for (orig, resp, port), group_of in buckets.items():
        if len(group_of) < minimum:
            continue
        timestamps = np.sort(np.array([c.ts for c in group_of], dtype=float))
        series.append(
            PairSeries(
                orig=orig,
                resp=resp,
                resp_port=port,
                timestamps=timestamps,
                bytes_sent=sum(c.orig_bytes for c in group_of),
            )
        )
    return sorted(series, key=lambda s: s.connections, reverse=True)


@dataclass(frozen=True, slots=True)
class Scored:
    series: PairSeries
    scores: dict[str, float | None]

    @property
    def best(self) -> float:
        present = [value for value in self.scores.values() if value is not None]
        return max(present) if present else 0.0


def score(series: Iterable[PairSeries], detectors: dict[str, Detector] | None = None) -> list[Scored]:
    """Score every pair with every detector.

    A None in ``scores`` means the detector declined because the series is too
    short for it, which is reported as such rather than as a zero. The two mean
    different things to a hunter: one is "not a beacon", the other is "ask me
    again when you have watched longer".
    """
    detectors = detectors or DETECTORS
    return sorted(
        (Scored(series=one, scores={name: d.score(one.timestamps) for name, d in detectors.items()}) for one in series),
        key=lambda s: s.best,
        reverse=True,
    )
