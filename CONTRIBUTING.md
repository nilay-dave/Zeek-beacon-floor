# Contributing

## Running the checks

```bash
make install
make check
```

`make check` runs everything CI runs except the benchmark: house style, the
published number check, the dependency check, the generated results page,
format, lint and the tests. Run it before opening a pull request.

## The rules that are not negotiable

**A detector declares what it is blind to, and a test demonstrates it.** The
`blind_to` field is required and an empty one raises at construction. It is not
documentation: `bowley-skew` declares that symmetric jitter is skew free, and
the benchmark measures it degrading as jitter rises. A new detector needs the
same treatment, including the test that makes the blindness visible rather
than asserted.

Be careful with the inverse. A measurement that agrees with a declaration is
not evidence the declaration was doing work: `bowley-skew` failed everywhere
for a while, the declaration explained it, and the real cause was a floating
point bug. [ADR 003](docs/adr/adr-003-keep-the-detector-that-fails.md) is
about that. If a detector fails where its declared blindness does not apply,
that is the case to chase.

**A detector refuses rather than guesses.** Below `min_intervals` it returns
None, and the scoring output prints that as "too short" rather than as a low
score. The two mean different things to a hunter, and the whole project exists
because that difference gets lost.

**Every published number is tagged and checked.** A figure in the README or
under `docs/` carries the metrics path it came from:

```markdown
<!--number:headline.interval-cv.intervals_at_zero_jitter-->4<!--/number-->
```

`tools/check_numbers.py` compares each against `docs/metrics.json` and fails
the build on drift. Change something that moves a number, run `make bench` then
`make report`, and commit the regenerated files with the change that caused
them.

**Every published figure is labelled a simulation.** There is no real traffic
in this repository. CI fails if `docs/metrics.json` stops saying so.

**Nothing under `src/` opens a socket.** This is an offline tool a responder
should be able to run on an isolated host. CI enforces it.

**No em dashes or en dashes** anywhere: code, comments, commit messages, docs.

## Adding a detector

1. Implement it as a `Detector` with a `summary`, a `blind_to` and an honest
   `min_intervals`.
2. Register it in `zbf.detect.DETECTORS`.
3. Add it to the shared parametrised tests, which every detector must pass:
   scale freedom, scores inside [0, 1], refusal below the minimum, and a
   beacon scoring above memoryless traffic.
4. Add the test that demonstrates its declared blindness.
5. Rerun the benchmark. A detector that loses is worth keeping if its failure
   is informative; one that is merely worse than `interval-cv` everywhere is
   not.

## Changing the floor measurement

The two generous assumptions are deliberate and documented in `zbf/floor.py`:
thresholds are recalibrated at each grid point, and benign periodic traffic is
not counted as a negative. Changing either changes what every published number
means, so it belongs in an ADR and in `docs/limitations.md`, not only in code.

## Commit messages

Conventional Commits, subject under 72 characters, body explaining why rather
than what. A `fix` commit says what was wrong and how it was found.
