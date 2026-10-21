# Limitations

Read this before quoting any number from this project.

## It is a simulation, end to end

No conn.log from a real network was used. The beacons are generated and so is
the background traffic, because no real capture was available to the
environment this was built in.

What the project can legitimately claim: under a stated set of assumptions,
these detectors need this many observed intervals, and the conversion from
intervals to hours of capture spans orders of magnitude depending on the beacon
period. The first half is a statement about the detectors. The second half is
arithmetic, and holds regardless of how realistic the traffic was.

What it cannot claim: that a hunter running these detectors on a real network
would see these numbers.

## It measures periodic against not periodic, which is not the question

This is the most important line on the page.

A monitoring agent checking in every sixty seconds is periodic. So is a
software update check, a certificate revocation poll, an NTP client and a
heartbeat to a load balancer. Every detector here scores them exactly as it
scores a beacon, because they are beacons in every respect except intent.

No timing statistic separates malicious from benign. The separation measured
here is periodic from non periodic, and a deployment turns that into alerts by
adding things this tool does not have: knowledge of what the destination is,
whether the software is expected on that host, what the payload sizes look
like, and whether anyone can account for it.

The false positive rate in these results is therefore not a prediction of a
hunter's alert volume. It is computed against non periodic traffic only, for
the reasons in [ADR 002](adr/adr-002-generous-to-the-detectors.md), and a real
network's periodic benign traffic sits entirely above it.

## Every number is a lower bound on the difficulty

Two assumptions are generous to the detectors, both deliberate:

- Thresholds are recalibrated at every point in the sweep. A deployment runs
  one fixed threshold and does worse.
- Beacons are generated with a single stable period. A beacon whose operator
  changes the sleep mid capture defeats the spectral detectors entirely and
  degrades the dispersion ones.

## The background traffic is two distributions, not a network

Half memoryless, half session traffic. Real network traffic is neither, and in
particular it contains:

- Periodic benign traffic, excluded here for the reasons above.
- Traffic whose rate changes with the working day, so a window that spans a
  lunch break has structure that neither model produces.
- Retries and failures, which cluster connections in ways that look regular at
  short timescales.

The second and third both push toward more false positives than reported.

## The jitter models are uniform, and real jitter may not be

Both models draw uniformly, one sided for `cobalt-strike` and two sided for
`symmetric`. A framework that jitters on a different distribution, or that
jitters in a pattern rather than independently per check in, is not covered.
This matters most for `bowley-skew`, which is a shape test: it fails here
because uniform jitter is nearly skew free, and a genuinely skewed jitter
distribution is the one case where it might work.

## The detectors are the obvious five

Dispersion, dispersion robust to outliers, shape, autocorrelation, spectrum.
Not here: anything using payload sizes, which is the strongest signal a real
hunter has after timing; anything using the destination's reputation or
category; anything learning a per host baseline over weeks; anything
correlating several pairs from the same host.

A tool with those would have a different and lower floor, which is a reason to
read these numbers as a floor for timing alone rather than for beacon detection
in general.

## The floor is read off a grid

Intervals are sampled at 4, 6, 8, 12, 16, 24, 32, 48, 64, 96 and 128, so a
floor reported as 24 means "24 was the first grid point to reach the target"
and the true value is somewhere above 16. The grid is coarse at the top on
purpose, because that is the region where the answer is "more than you are
going to get".

## What would make this stronger

In roughly descending order of how much it would change the conclusions:

1. Run it against one real conn.log with a known beacon in it.
2. Add benign periodic traffic as a third class and report the three way
   confusion, rather than excluding it.
3. Add a payload size signal and measure how much of the floor it removes.
4. Model a beacon whose period changes mid capture.
5. More seeds and a finer grid.
