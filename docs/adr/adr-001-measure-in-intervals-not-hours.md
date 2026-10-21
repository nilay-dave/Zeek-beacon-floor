# ADR 001: measure the floor in intervals observed, not hours of capture

Status: accepted
Date: 2026-10-21

## Context

Beacon hunting guidance is stated in hours. Active Countermeasures recommends
capturing at least twelve hours of traffic, with twenty four being more ideal,
so that multiple beacon instances are recorded. That advice is widely repeated
and it is the operational knob a hunter actually turns.

No detector in this project, and none in any beacon analysis tool, can see a
clock. What every one of them consumes is a sequence of inter arrival times.
How many of those a capture window yields depends entirely on the beacon's
period, which is the one thing a hunter does not know before they look.

A twelve hour capture yields 720 intervals from a sixty second beacon and
twelve from an hourly one. Those are not the same measurement, and no amount of
care about the capture window changes that.

## Decision

Measure and publish the floor in intervals observed and jitter, which are the
units the detectors operate in, and provide the conversion to hours as a
derived table rather than as the primary result.

`zbf hours` performs the conversion, taking the floor in intervals and a beacon
period and returning the capture window a hunter has to plan for. That command
is the point of the project; `zbf floor` is the measurement behind it.

## Consequences

- The headline result is a grid over intervals and jitter, which is less
  immediately actionable than a number of hours and is the honest shape of the
  answer.
- The conversion makes the guidance checkable instead of contradicting it. For
  a fast beacon the twelve hour advice is generous. For a slow one it is short
  by more than an order of magnitude, and the table says by how much.
- A hunter using this has to assume a beacon period to get an answer in hours,
  which is uncomfortable and correct: they were always assuming one, and the
  conversion makes the assumption visible rather than removing it.
- Everything scale free in the codebase stays that way, and a test asserts it:
  the same series scaled from thirty seconds to a day must score identically
  under every detector. Without that property the conversion would not be
  sound.

## What this does not claim

That the twelve hour guidance is wrong. It is advice about a capture window
given without knowledge of the beacon period, which is the only advice anyone
can give in that unit. The claim is narrower: the unit hides a dependency, the
dependency spans orders of magnitude, and a hunter who knows the period they
are hunting can do better than a fixed window.
