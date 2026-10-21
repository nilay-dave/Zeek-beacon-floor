# Sources

What this project took from outside itself, and what it made up. Every figure
published here is a simulation, so the distinction matters more than usual.

## The sourced behaviour the project turns on

**Cobalt Strike, `sleep` command.**
<https://hstechdocs.helpsystems.com/manuals/cobaltstrike/current/userguide/content/topics/post-exploitation_asynch-interactive.htm>

`sleep` takes a time in seconds and an optional jitter percentage. The
documentation states that Beacon varies each check in time by that percentage,
and that `sleep 300 20` produces a random sleep between 240 and 300 seconds.
Jitter only ever shortens the sleep: the configured interval is a maximum.

This is the `cobalt-strike` jitter model in `zbf.synth`, and it is the model
the headline floor is measured under. It matters because the symmetric model,
where the interval varies both ways around the nominal value, spreads intervals
over twice the range at the same stated percentage. A floor quoted at "30
percent jitter" means two different things depending on which was meant, and
the benchmark reports both rather than picking one.

Other C2 frameworks implement jitter differently, and the default here follows
the one with documented semantics rather than assuming it generalises.

## The guidance this project is measured against

**Active Countermeasures, beacon analysis guidance.**
<https://www.activecountermeasures.com/threat-hunting-simplifying-the-beacon-analysis-process/>

Recommends capturing at least twelve hours of traffic, with twenty four hours
being more ideal, so that multiple beacon instances are recorded, and describes
beacon scores on a zero to one scale.

Those two numbers are the red lines on the right hand panel of the floor chart.
The guidance is not wrong; it is stated in a unit that hides a dependency on
the beacon period, which is what
[ADR 001](adr/adr-001-measure-in-intervals-not-hours.md) is about.

## The log format

**Zeek, conn.log.** <https://docs.zeek.org/en/lts/logs/conn.html>

Field names and the two on disk formats, tab separated with a `#fields` header
and JSON lines. The relevant detail for this project is that the field set is
not stable across versions: Zeek 8 added `ip_proto`, which shifts the position
of every column after it. That is why `zbf.conn` reads names from the header
and refuses a headerless TSV rather than assuming positions, and why a test
asserts a Zeek 7 record and a Zeek 8 record parse identically.

## Everything else is a declared choice

The following are not sourced from anywhere. They are stated in the benchmark's
`conditions` block and in `docs/metrics.json` so a reader can disagree with
them specifically:

- The composition of the background traffic: half memoryless, half session
  traffic in bursts. Real networks are neither.
- The false positive rate the thresholds are set at, one percent.
- The detection rate the floor is defined at, ninety percent.
- The beacon periods drawn per sample, uniform between thirty seconds and an
  hour. Every detector here is scale free and a test asserts it, so this should
  not affect any result, and drawing it is how that claim is tested rather than
  assumed.
- The share of missed check ins in experiment C.

## Methods

**Bowley skewness.** A quartile based measure of asymmetry,
`(Q3 + Q1 - 2 * Q2) / (Q3 - Q1)`, chosen over the third moment because it is
defined on small samples without the variance of a cubed term. It is the basis
of the `bowley-skew` detector, which does not work, for reasons recorded in
[ADR 003](adr/adr-003-keep-the-detector-that-fails.md).

**Autocorrelation through the frequency domain.** The arrival train is binned,
transformed, multiplied by its own conjugate and transformed back, which is the
Wiener Khinchin route to the same answer `np.correlate` gives by direct
convolution, at O(n log n) instead of O(n squared).
