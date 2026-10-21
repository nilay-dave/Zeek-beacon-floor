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

### Known limitations

- Every published figure is a simulation. No real conn.log was used.
- The separation measured is periodic against not periodic. No timing statistic
  separates a beacon from a monitoring agent. See `docs/limitations.md`.
