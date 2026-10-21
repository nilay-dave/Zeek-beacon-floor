"""The zbf command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zbf import __version__
from zbf.conn import ConnLogError, fields, read
from zbf.detect import DETECTORS
from zbf.floor import DEFAULT_FPR, DEFAULT_TARGET_TPR, hours_of_capture, sweep
from zbf.pairs import group, score
from zbf.synth import COBALT_STRIKE, JITTER_MODELS

SIMULATION_NOTE = (
    "note: these are simulated beacons and simulated background traffic. They describe the detectors, not your network."
)


def _detectors(names: str | None):
    if not names:
        return DETECTORS
    chosen = {}
    for name in names.split(","):
        name = name.strip()
        if name not in DETECTORS:
            raise SystemExit(f"unknown detector {name!r}. Available: {', '.join(sorted(DETECTORS))}")
        chosen[name] = DETECTORS[name]
    return chosen


def cmd_fields(args) -> int:
    for name in fields(Path(args.log)):
        print(name)
    return 0


def cmd_detectors(args) -> int:
    for name, detector in sorted(DETECTORS.items()):
        print(f"{name}")
        print(f"  ranks by:  {detector.summary}")
        print(f"  blind to:  {detector.blind_to}")
        print(f"  needs:     {detector.min_intervals} intervals at minimum")
    return 0


def cmd_score(args) -> int:
    path = Path(args.log)
    pairs = group(read(path), minimum=args.min_connections)
    if not pairs:
        print(f"no pair in {path.name} has {args.min_connections} or more connections", file=sys.stderr)
        return 1
    chosen = _detectors(args.detectors)
    results = score(pairs, chosen)[: args.top]

    names = list(chosen)
    header = f"{'pair':<46} {'conns':>6} {'period':>9} {'hours':>7} " + " ".join(f"{n:>9}" for n in names)
    print(header)
    for result in results:
        series = result.series
        period = series.median_period
        shown = f"{period / 60:.1f}m" if period < 7200 else f"{period / 3600:.1f}h"
        cells = []
        for name in names:
            value = result.scores[name]
            cells.append(f"{'too short':>9}" if value is None else f"{value:>9.3f}")
        print(f"{series.label():<46} {series.connections:>6} {shown:>9} {series.span_hours:>7.1f} " + " ".join(cells))
    print()
    print(
        "A high score means periodic. It does not mean malicious: a monitoring agent "
        "is periodic too, and no timing statistic can tell them apart."
    )
    return 0


def cmd_floor(args) -> int:
    chosen = _detectors(args.detectors)
    interval_grid = [int(v) for v in args.intervals.split(",")]
    jitter_grid = [float(v) for v in args.jitter.split(",")]

    print(SIMULATION_NOTE)
    print(
        f"detection rate at {args.fpr:.0%} false positive rate, {args.model} jitter, "
        f"{args.seeds} seeds of {args.samples} samples"
    )
    print()
    for name, detector in chosen.items():
        result = sweep(
            detector,
            interval_grid,
            jitter_grid,
            seeds=args.seeds,
            samples=args.samples,
            fpr=args.fpr,
            model=args.model,
            miss_rate=args.miss_rate,
        )
        print(f"{name}  ({detector.blind_to})")
        print(f"{'intervals':>10} " + " ".join(f"{'j=' + format(j, '.2f'):>8}" for j in jitter_grid))
        for intervals in interval_grid:
            cells = []
            for jitter in jitter_grid:
                point = next(p for p in result.points if p.intervals == intervals and abs(p.jitter - jitter) < 1e-9)
                cells.append(f"{point.tpr:>8.2f}")
            print(f"{intervals:>10} " + " ".join(cells))
        floors = []
        for jitter in jitter_grid:
            needed = result.required_intervals(jitter, args.target)
            floors.append(f"j={jitter:.2f}: " + (f"{needed}" if needed else "never"))
        print(f"  intervals needed for {args.target:.0%} detection  " + ",  ".join(floors))
        print()
    return 0


def cmd_hours(args) -> int:
    """Turn a floor in intervals into the capture window a hunter has to plan."""
    chosen = _detectors(args.detectors)
    periods = [float(v) for v in args.periods.split(",")]
    jitter_grid = [float(v) for v in args.jitter.split(",")]
    interval_grid = [int(v) for v in args.intervals.split(",")]

    print(SIMULATION_NOTE)
    print(f"hours of capture needed for {args.target:.0%} detection at {args.fpr:.0%} false positives")
    print()
    for name, detector in chosen.items():
        result = sweep(
            detector,
            interval_grid,
            jitter_grid,
            seeds=args.seeds,
            samples=args.samples,
            fpr=args.fpr,
            model=args.model,
        )
        print(f"{name}")
        print(f"{'beacon period':>14} " + " ".join(f"{'j=' + format(j, '.2f'):>10}" for j in jitter_grid))
        for period in periods:
            shown = f"{period / 60:.0f}m" if period < 3600 else f"{period / 3600:.0f}h"
            cells = []
            for jitter in jitter_grid:
                needed = result.required_intervals(jitter, args.target)
                if needed is None:
                    cells.append(f"{'never':>10}")
                else:
                    cells.append(f"{hours_of_capture(needed, period):>10.1f}")
            print(f"{shown:>14} " + " ".join(cells))
        print()
    print(
        "Common guidance is to capture for at least twelve hours. A detector does not see "
        "a clock, it sees intervals, so that advice is right for a fast beacon and wrong "
        "for a slow one by as much as the table shows."
    )
    return 0


def cmd_chart(args) -> int:
    from zbf.plot import floor_chart

    destination = Path(args.out)
    floor_chart(
        destination,
        detectors=_detectors(args.detectors),
        interval_grid=[int(v) for v in args.intervals.split(",")],
        jitter_grid=[float(v) for v in args.jitter.split(",")],
        seeds=args.seeds,
        samples=args.samples,
        fpr=args.fpr,
        model=args.model,
    )
    print(f"wrote {destination}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zbf",
        description=(
            "Measures where beacon detection stops working, in intervals observed and "
            "jitter rather than hours of capture."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    one = subparsers.add_parser("fields", help="print a conn.log's column names")
    one.add_argument("log")
    one.set_defaults(func=cmd_fields)

    one = subparsers.add_parser("detectors", help="what each detector ranks by and is blind to")
    one.set_defaults(func=cmd_detectors)

    one = subparsers.add_parser("score", help="score the pairs in a conn.log")
    one.add_argument("log")
    one.add_argument("--top", type=int, default=20)
    one.add_argument("--min-connections", type=int, default=4)
    one.add_argument("--detectors", help="comma separated subset")
    one.set_defaults(func=cmd_score)

    def sweep_arguments(sub):
        # The same grid the benchmark uses, so a local run and the published
        # figures top out in the same place and "never" means the same thing.
        sub.add_argument("--intervals", default="4,6,8,12,16,24,32,48,64,96,128")
        sub.add_argument("--jitter", default="0.0,0.2,0.4,0.6,0.8,1.0")
        sub.add_argument("--seeds", type=int, default=8)
        sub.add_argument("--samples", type=int, default=400)
        sub.add_argument("--fpr", type=float, default=DEFAULT_FPR)
        sub.add_argument("--model", choices=JITTER_MODELS, default=COBALT_STRIKE)
        sub.add_argument("--detectors", help="comma separated subset")

    one = subparsers.add_parser("floor", help="measure the detection floor")
    sweep_arguments(one)
    one.add_argument("--target", type=float, default=DEFAULT_TARGET_TPR)
    one.add_argument("--miss-rate", type=float, default=0.0, help="share of check ins that never happen")
    one.set_defaults(func=cmd_floor)

    one = subparsers.add_parser("hours", help="convert the floor into hours of capture")
    sweep_arguments(one)
    one.add_argument("--target", type=float, default=DEFAULT_TARGET_TPR)
    one.add_argument("--periods", default="60,300,3600,86400", help="beacon periods in seconds")
    one.set_defaults(func=cmd_hours)

    one = subparsers.add_parser("chart", help="draw the floor")
    sweep_arguments(one)
    one.add_argument("--out", default="docs/img/floor.png")
    one.set_defaults(func=cmd_chart)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConnLogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
