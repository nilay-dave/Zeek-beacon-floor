"""Measure the floor, and write docs/metrics.json.

**Every number here is a simulation.** The beacons are generated and so is the
background traffic. No conn.log from a real network was used, because none was
available to the environment this was built in, and a floor measured on
synthetic traffic is a statement about the detectors rather than about any
network. What that still buys is the shape of the problem and the units the
answer belongs in, which is the part the field guidance gets wrong.

Five experiments.

**A. The headline floor.** Every detector, across intervals observed and
jitter, at a fixed false positive rate against non periodic traffic. The
output is, for each detector and each jitter, the fewest intervals that reach
90 percent detection.

**B. The jitter model matters.** The same sweep under the sourced Cobalt
Strike model, where jitter only shortens the sleep, and under the symmetric
model most tooling assumes. At the same stated percentage these are not the
same experiment, and the difference is reported rather than averaged away.

**C. Missed check ins.** A real beacon misses. This repeats the headline with
a share of check ins removed, which is the case dispersion statistics handle
worst and spectral ones handle best.

**D. The conversion.** The floor in intervals, turned into hours of capture
for four beacon periods, against the twelve and twenty four hour guidance.

**E. Runtime**, so nobody has to guess whether this runs on a real log.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from zbf.detect import DETECTORS
from zbf.floor import DEFAULT_FPR, DEFAULT_TARGET_TPR, hours_of_capture, sweep
from zbf.pairs import group, score
from zbf.synth import COBALT_STRIKE, SYMMETRIC, negatives, positives

ROOT = Path(__file__).resolve().parents[1]
INTERVAL_GRID = [4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128]
JITTER_GRID = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
PERIODS = [60.0, 300.0, 3600.0, 86400.0]
# The two numbers the field guidance names, which experiment D is measured
# against. Both come from beacon hunting guidance that states a capture window
# in hours and does not state a beacon period, which is the gap this measures.
GUIDANCE_MINIMUM_HOURS = 12.0
GUIDANCE_IDEAL_HOURS = 24.0


def floors_for(detector, seeds, samples, model=COBALT_STRIKE, miss_rate=0.0, target=DEFAULT_TARGET_TPR):
    result = sweep(detector, INTERVAL_GRID, JITTER_GRID, seeds=seeds, samples=samples, model=model, miss_rate=miss_rate)
    return result, {f"{jitter:.1f}": result.required_intervals(jitter, target) for jitter in JITTER_GRID}


def experiment_a(seeds, samples):
    print("A. the headline floor")
    out = {}
    for name, detector in DETECTORS.items():
        started = time.perf_counter()
        result, floors = floors_for(detector, seeds, samples)
        reached = [v for v in floors.values() if v is not None]
        out[name] = {
            "blind_to": detector.blind_to,
            "min_intervals": detector.min_intervals,
            "intervals_needed_by_jitter": floors,
            "worst_jitter_handled": max((float(j) for j, v in floors.items() if v is not None), default=None),
            "intervals_at_zero_jitter": floors["0.0"],
            "tpr_grid": {
                f"{p.jitter:.1f}": {str(q.intervals): round(q.tpr, 4) for q in result.at(p.jitter)}
                for p in result.points
            },
        }
        if len(reached) < len(JITTER_GRID):
            worst = out[name]["worst_jitter_handled"]
            verdict = "never reaches the target" if worst is None else f"gives up above {worst:.1f} jitter"
        else:
            verdict = "reaches the target at every jitter"
        clean = floors["0.0"]
        needs = f"needs {clean} intervals with no jitter" if clean else "never reaches the target at all"
        print(f"   {name:16} {needs}, {verdict}  [{time.perf_counter() - started:.1f}s]")
    return out


def experiment_b(seeds, samples):
    print("B. the jitter model is not a detail")
    out = {}
    for name in ("interval-cv", "mad-ratio"):
        detector = DETECTORS[name]
        _, cobalt = floors_for(detector, seeds, samples, model=COBALT_STRIKE)
        _, symmetric = floors_for(detector, seeds, samples, model=SYMMETRIC)
        out[name] = {"cobalt-strike": cobalt, "symmetric": symmetric}
        for jitter in ("0.4", "0.8"):
            print(f"   {name:16} j={jitter}  cobalt-strike {cobalt[jitter]}  symmetric {symmetric[jitter]}")
    return out


def experiment_c(seeds, samples, miss_rate):
    print(f"C. missed check ins at {miss_rate:.0%}")
    out = {}
    for name, detector in DETECTORS.items():
        _, clean = floors_for(detector, seeds, samples)
        _, missing = floors_for(detector, seeds, samples, miss_rate=miss_rate)
        out[name] = {"no_misses": clean, "with_misses": missing}
        print(f"   {name:16} j=0.4  {clean['0.4']} -> {missing['0.4']}")
    return out


def experiment_d(headline):
    print("D. the floor in hours of capture")
    out = {}
    for name, entry in headline.items():
        rows = {}
        for jitter, needed in entry["intervals_needed_by_jitter"].items():
            if needed is None:
                rows[jitter] = None
                continue
            rows[jitter] = {f"{int(p)}": round(hours_of_capture(needed, p), 3) for p in PERIODS}
        out[name] = rows
    best = out["interval-cv"]
    for jitter in ("0.0", "0.6", "1.0"):
        if best[jitter]:
            print(f"   interval-cv j={jitter}  1h beacon needs {best[jitter]['3600']:.1f} hours of capture")
    return out


def experiment_e():
    print("E. runtime")
    rows = []
    rng = np.random.default_rng(0)
    for pairs in (1_000, 10_000):
        series = positives(24, pairs // 2, 0.3, rng) + negatives(24, pairs - pairs // 2, rng)
        from zbf.conn import Connection

        connections = [
            Connection(ts=float(ts), orig=f"10.0.{index // 254}.{index % 254}", resp="203.0.113.9", resp_port=443)
            for index, one in enumerate(series)
            for ts in one
        ]
        started = time.perf_counter()
        grouped = group(connections, minimum=4)
        scored = score(grouped)
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "pairs": pairs,
                "connections": len(connections),
                "seconds": round(elapsed, 3),
                "scored": len(scored),
            }
        )
        print(f"   {pairs:,} pairs, {len(connections):,} connections, all five detectors: {elapsed:.2f}s")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--samples", type=int, default=400)
    parser.add_argument("--miss-rate", type=float, default=0.2)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "metrics.json")
    args = parser.parse_args()

    started = time.perf_counter()
    headline = experiment_a(args.seeds, args.samples)
    models = experiment_b(args.seeds, args.samples)
    misses = experiment_c(args.seeds, args.samples, args.miss_rate)
    hours = experiment_d(headline)
    runtime = experiment_e()

    payload = {
        "note": (
            "Every figure in this file is a simulation. The beacons are generated and so is the "
            "background traffic; no conn.log from a real network was used. Jitter semantics are "
            "sourced from Cobalt Strike's sleep command, where the jitter percentage only shortens "
            "the sleep. Everything else, including the composition of the background traffic, is a "
            "declared choice."
        ),
        "conditions": {
            "false_positive_rate": DEFAULT_FPR,
            "target_detection_rate": DEFAULT_TARGET_TPR,
            "seeds": args.seeds,
            "samples_per_class": args.samples,
            "interval_grid": INTERVAL_GRID,
            "jitter_grid": JITTER_GRID,
            "jitter_model": COBALT_STRIKE,
            "negatives": "half memoryless, half session traffic; benign periodic traffic is not a negative",
            "threshold": "recalibrated at every point, which is more generous than a deployed fixed threshold",
        },
        "guidance": {
            "minimum_hours": GUIDANCE_MINIMUM_HOURS,
            "ideal_hours": GUIDANCE_IDEAL_HOURS,
            "source": "Active Countermeasures beacon analysis guidance, stated in hours of capture",
        },
        "headline": headline,
        "jitter_models": models,
        "missed_check_ins": {"miss_rate": args.miss_rate, "detectors": misses},
        "hours_of_capture": hours,
        "runtime": runtime,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out} in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
