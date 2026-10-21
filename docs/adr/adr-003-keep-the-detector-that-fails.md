# ADR 003: the detector that failed, and why the explanation was wrong

Status: accepted, after being rewritten
Date: 2026-10-21

## What this decision was originally

`bowley-skew` scores beacons by one minus the absolute Bowley skewness of
their intervals. In the first sweep it reached the target detection rate
nowhere: not at any number of intervals, not at any jitter, including no
jitter at all.

The decision was to keep it anyway and publish the row of failures, and the
argument was this:

> The failure was predicted and then observed. `blind_to` was written from the
> mathematics before the sweep ran, and the sweep found what it said. That is
> the strongest available evidence that the declaration requirement is doing
> real work rather than generating plausible prose.

That argument was wrong, and the way it was wrong is worth more than the
decision it was defending.

## What was actually happening

Bowley skewness is `(Q3 + Q1 - 2*Q2) / (Q3 - Q1)`. The denominator is zero
when every interval in the middle half is identical, which is what a perfect
beacon looks like, so the code guarded it:

```python
if spread <= 0:
    return 1.0
```

That guard catches only exact floating point equality. A perfect beacon's
intervals are not exactly equal. They are produced by
`np.diff(np.cumsum(sleeps))`, and the running sum accumulates rounding error
whenever the period is not representable in binary, which is almost always.
A perfect beacon with a period of 2047.3771254706232 seconds has an
interquartile spread of 4.5e-13 seconds, which is not zero, so the skewness
was computed as a ratio of two quantities that were both pure rounding noise.

The result was a scale free statistic applied to numerical dust. A perfect
beacon scored 0.0. Across periods drawn the way the benchmark draws them,
39 percent of perfect beacons scored below 0.5 and only 45 percent scored 1.0.
The one percent false positive threshold for this detector sits near 0.99, so
most perfect beacons were misses before any jitter was applied at all.

The fix is a relative guard rather than an exact one: treat a spread that is
negligible against the median as degenerate. After it, every one of 4000
perfect beacons scores 1.0, and the detector reaches the target at low jitter.

## Why the wrong explanation survived

The declared blindness was real. Uniform jitter is nearly skew free in both
models, so `bowley-skew` genuinely does struggle as jitter rises, and it
genuinely is a shape test rather than a regularity test.

So when the sweep produced a row of failures, there was a true statement
available that explained it, and the explanation was flattering: a
declaration written before the measurement had predicted the result. It made
the `blind_to` requirement look like it was doing real work. Nothing about
the output contradicted it.

What it could not explain, and what nobody asked, is why the detector failed
at **zero jitter**, where its declared blindness does not apply at all. That
column was right there in the published table, reading `never`, and the story
had no room for it.

An independent review of the source found the guard. It was not found by
rerunning the benchmark, by adding seeds, or by reading the results, because
all of those were consistent with the wrong explanation.

## Decision

Keep `bowley-skew`, on an argument that no longer depends on the failure:

- It is a different kind of statistic from the other four, a shape test rather
  than a dispersion or spectral one, and the comparison is more informative
  with it than without it.
- Its real blindness, that uniform jitter is nearly skew free, is a measured
  result now rather than an unfalsifiable one, because it can be seen
  degrading from a correct score at zero jitter instead of starting at zero.

And record the methodological consequence, which applies to the whole project:

**A result that confirms a declaration is not evidence that the declaration
was doing work.** It is the case where checking is most needed and least
likely, because the explanation is already there and it is satisfying. The
discipline that caught this was not internal; it was handing the code to a
reader who had not been told what to expect.

## Consequences

- The published floors changed. Every number in `docs/metrics.json` and
  everything generated from it was re-measured after the fix.
- A test pins a perfect beacon at 1.0 across 300 randomly drawn periods, so
  this class of bug cannot return quietly.
- The same review found three other defects of the same shape, where a true
  statement was standing in front of a bug. They are in the commit history
  with the same treatment.
- `docs/limitations.md` gains the general version: the results here have been
  reviewed from the outside once, and the things that survive that are not the
  same as the things that survive rerunning your own benchmark.
