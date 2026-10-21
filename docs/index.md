# zeek-beacon-floor

Beacon hunting guidance says to capture at least
<!--number:guidance.minimum_hours-->12<!--/number--> hours of traffic,
<!--number:guidance.ideal_hours-->24<!--/number--> ideally.

No detector sees a clock. What they consume is inter arrival times, and how
many of those a capture window yields depends entirely on the beacon's period,
which is the one thing a hunter does not know before they look.

This measures the detection floor in the units detectors actually work in,
intervals observed and jitter, and converts it back into hours so the guidance
becomes checkable.

## Read this first

Every number here is a simulation. No conn.log from a real network was used.
One behaviour is sourced, Cobalt Strike's jitter semantics; everything else is
a declared choice.

- [Sources](sources.md) separates what was sourced from what was chosen.
- [Limitations](limitations.md) leads with something more important than the
  simulation: this measures periodic against not periodic, and nothing here
  separates malicious from benign.

## The result

![the beacon detection floor](img/floor.png)

`interval-cv` needs
<!--number:headline.interval-cv.intervals_needed_by_jitter.100-->32<!--/number-->
intervals at full jitter. That single floor converts into
<!--number:hours_of_capture.interval-cv.100.60-->0.5<!--/number--> hours of
capture for a one minute beacon and
<!--number:hours_of_capture.interval-cv.100.86400-->768<!--/number--> hours for
a daily one, which is a month.

The plain dispersion statistic beats both spectral detectors, and `bowley-skew`
never reaches the target anywhere in the grid. Both results are on the
[results](results.md) page.

## Install

```bash
pip install zeek-beacon-floor
```

```bash
zbf fields conn.log         # what this Zeek version called things
zbf score conn.log          # rank the pairs
zbf hours --periods 3600    # how long must I watch for an hourly beacon?
zbf detectors               # what each one ranks by, and is blind to
```

## Decisions

- [ADR 001](adr/adr-001-measure-in-intervals-not-hours.md): measure in
  intervals observed, not hours of capture.
- [ADR 002](adr/adr-002-generous-to-the-detectors.md): when in doubt, be
  generous to the detectors, and say so.
- [ADR 003](adr/adr-003-keep-the-detector-that-fails.md): keep the detector
  that fails.
