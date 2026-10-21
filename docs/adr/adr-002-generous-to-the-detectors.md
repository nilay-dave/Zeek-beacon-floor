# ADR 002: when in doubt, be generous to the detectors

Status: accepted
Date: 2026-10-21

## Context

A floor measurement has several free choices, and most of them can be set to
make detection look easy or hard. A project whose conclusion is that detection
is harder than the guidance implies has an obvious incentive to set them the
hard way, and would deserve to be disbelieved for it.

Two choices mattered most.

**Where the threshold comes from.** A detector's score distribution on
background traffic shifts as the series gets longer, so a single threshold
calibrated once performs differently at four intervals than at sixty four.

**What counts as a negative.** Real networks are full of periodic traffic that
is not a beacon: monitoring agents, update checks, certificate revocation
polls, NTP.

## Decision

Resolve both in the direction that flatters the detectors, and say so in the
output rather than in a footnote.

**Thresholds are recalibrated at every point in the sweep**, from background
traffic with the same number of intervals. A deployed detector runs one fixed
threshold and does worse than this.

**Negatives are non periodic traffic only.** Benign periodic traffic is
excluded from the negative class entirely.

## Why exclude the traffic that causes real false positives

Because including it would measure the wrong thing twice over.

A monitoring agent checking in every sixty seconds is periodic. It scores like
a beacon under every detector here, and it should, because it is a beacon in
every respect except intent. Counting it as a negative would make the reported
false positive rate a measure of how much monitoring software the simulated
network happens to run, which is a number about the simulation and not about
the detector.

It would also quietly change the question. These detectors separate periodic
from non periodic. Nothing in a timing statistic separates malicious from
benign, and a false positive rate computed against benign beacons would imply
the tool was attempting a separation it cannot make.

So the measurement is of the separation the detectors can do, and the
separation they cannot do is stated plainly in the README and in
`docs/limitations.md` rather than buried in a metric.

## Consequences

- Every floor in this repository is a lower bound on the difficulty. A
  deployment does worse, for reasons that are named.
- The reported false positive rate is not a prediction of a hunter's alert
  volume, and the documentation does not let it be read as one.
- `zbf score` prints, under every result, that a high score means periodic and
  not malicious. A test asserts that sentence is still there, because it is the
  one line in the tool most likely to be lost to an edit.
