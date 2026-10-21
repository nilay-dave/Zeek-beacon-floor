# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

First release.

### Added

- A Zeek conn.log reader that takes column names from the `#fields` header
  rather than assuming positions, handling TSV, JSON lines and gzip, and
  refusing a headerless TSV rather than guessing.
- Five timing detectors, each declaring what it ranks by and what it is blind
  to, and each returning nothing rather than a number below its minimum number
  of intervals.
- Two jitter models: Cobalt Strike's, where jitter only shortens the sleep, and
  the symmetric model most tooling assumes.
- A floor measurement: the fewest observed intervals reaching a target
  detection rate at a false positive rate fixed against non periodic traffic.
- `zbf hours`, which converts a floor in intervals into the capture window a
  hunter has to plan for.
- `zbf` command line: `fields`, `detectors`, `score`, `floor`, `hours`,
  `chart`.
- A benchmark of five experiments writing `docs/metrics.json`, and
  `docs/results.md` generated from it with `--check` in CI.

### Fixed before release

Four defects found by an outside review of the source, two of which had
changed published numbers. They are listed here rather than folded silently
into the first release, because the published figures moved and a reader
comparing against anything written earlier deserves to know why.

- `bowley-skew` scored a perfect beacon at 0.0. Its degenerate spread guard
  tested exact floating point equality, and a perfect beacon's intervals are
  not exactly equal once a non representable period has been through a running
  sum. 39 percent of perfect beacons scored below 0.5.
- Generated beacons carried one more interval than the background traffic they
  were calibrated against, so the false positive rate was a rate at a
  different series length than the detection rate beside it, and the shortest
  grid point reported zero detection for detectors that had scored every
  positive correctly.
- The spectral noise floor subtracted the mean share of spectral energy per
  bin where the statistic is a maximum, leaving a floor that fell by more than
  an order of magnitude across the interval grid.
- A `ts` that was present but unreadable was skipped silently, so a log
  written with `LogAscii::json_timestamps = JSON::TS_ISO8601` read as zero
  records and no error.

### Known limitations

- Every published figure is a simulation. No real conn.log was used.
- The separation measured is periodic against not periodic. No timing statistic
  separates a beacon from a monitoring agent. See `docs/limitations.md`.
