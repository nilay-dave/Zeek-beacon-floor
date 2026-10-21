# ADR 003: keep the detector that fails

Status: accepted
Date: 2026-10-21

## Context

`bowley-skew` scores beacons by one minus the absolute Bowley skewness of their
intervals. The reasoning is sound in outline: jitter that is applied in one
direction makes the interval distribution asymmetric, and skewness measures
asymmetry.

It does not work. At a one percent false positive rate it detects almost
nothing at any number of intervals or any jitter, which makes it the only
detector here that never reaches the target anywhere in the sweep.

The reason is the one it declares in its own `blind_to` field, written before
the measurement: jitter drawn uniformly, whether one sided like Cobalt Strike's
or symmetric, is symmetric within its own range and therefore nearly skew free.
A badly jittered beacon and a clean one look alike to a skewness statistic.
Session traffic in the background has near zero skew too, which pushes the
threshold to the top of the range and leaves nothing above it.

The obvious response is to delete it.

## Decision

Keep it, in the registry, in the benchmark, and in the published results table.

## Why

**A negative result is a result, and this one is reusable.** Skewness looks
like a reasonable beacon statistic, and anyone building one of these tools will
consider it. The repository answers that question with a measurement instead of
an opinion, which is worth more than one fewer row in a table.

**It makes the other numbers legible.** A table in which every detector works
is a table a reader has no way to calibrate. One in which a plausible detector
fails completely shows that the measurement can tell the difference.

**The failure was predicted and then observed.** `blind_to` was written from
the mathematics before the sweep ran, and the sweep found what it said. That is
the strongest available evidence that the declaration requirement in
`Detector.__post_init__` is doing real work rather than generating plausible
prose.

**Deleting it would be selective reporting.** It was built in good faith as one
of five candidates. Removing the one that lost, and publishing the four that
won, would describe a project that never happened.

## Consequences

- The results table carries a row of near zeros, which needs a sentence of
  explanation every time it is shown.
- `bowley-skew` stays available on the command line, where someone could use it
  by mistake. Its `summary` and `blind_to` are printed by `zbf detectors`, and
  the documentation says plainly that it does not work as a beacon detector on
  its own.
- The same standard applies to any future detector: a candidate that fails is
  kept and reported if its failure is informative, and dropped only if it is
  merely a worse version of something already present.
