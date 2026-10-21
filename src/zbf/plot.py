"""Draw the floor.

Two panels, because the measurement and the advice are in different units and
the whole argument of this project is that the conversion between them is
where the field guidance goes wrong.

Left: what the detectors actually need, in intervals observed.
Right: the same numbers as hours of capture for one beacon period, against the
twelve and twenty four hour marks that hunting guidance recommends.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from zbf.detect import DETECTORS, Detector  # noqa: E402
from zbf.floor import DEFAULT_FPR, DEFAULT_TARGET_TPR, hours_of_capture, sweep  # noqa: E402
from zbf.synth import COBALT_STRIKE  # noqa: E402

STYLES = [
    ("#1f3b73", "o", "-"),
    ("#a3320b", "s", "--"),
    ("#0b6b3a", "^", "-."),
    ("#7a4fb6", "v", ":"),
    ("#8a6d1f", "D", (0, (3, 1, 1, 1))),
]
# Plotted above the grid to mean "no number of intervals in this sweep reached
# the target". Drawing it as a missing point would read as an easy case.
NEVER = "never reached"


def required_by_jitter(
    detectors: dict[str, Detector],
    interval_grid: list[int],
    jitter_grid: list[float],
    seeds: int,
    samples: int,
    fpr: float,
    model: str,
    target: float,
) -> dict[str, list[int | None]]:
    out: dict[str, list[int | None]] = {}
    for name, detector in detectors.items():
        result = sweep(detector, interval_grid, jitter_grid, seeds=seeds, samples=samples, fpr=fpr, model=model)
        out[name] = [result.required_intervals(jitter, target) for jitter in jitter_grid]
    return out


def floor_chart(
    destination: Path,
    detectors: dict[str, Detector] | None = None,
    interval_grid: list[int] | None = None,
    jitter_grid: list[float] | None = None,
    seeds: int = 8,
    samples: int = 400,
    fpr: float = DEFAULT_FPR,
    model: str = COBALT_STRIKE,
    target: float = DEFAULT_TARGET_TPR,
    period_seconds: float = 3600.0,
    required: dict[str, list[int | None]] | None = None,
) -> Path:
    detectors = detectors or DETECTORS
    interval_grid = interval_grid or [4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128]
    jitter_grid = jitter_grid or [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    if required is None:
        required = required_by_jitter(detectors, interval_grid, jitter_grid, seeds, samples, fpr, model, target)

    ceiling = max(interval_grid)
    off_scale = ceiling * 2

    figure, (left, right) = plt.subplots(1, 2, figsize=(13.5, 5.6))

    for index, (name, needed) in enumerate(required.items()):
        colour, marker, dashes = STYLES[index % len(STYLES)]
        reached = [(j, n) for j, n in zip(jitter_grid, needed, strict=True) if n is not None]
        missed = [j for j, n in zip(jitter_grid, needed, strict=True) if n is None]
        if reached:
            left.plot(
                [j for j, _ in reached],
                [n for _, n in reached],
                color=colour,
                marker=marker,
                linestyle=dashes,
                linewidth=1.8,
                markersize=5.5,
                label=name,
            )
            right.plot(
                [j for j, _ in reached],
                [hours_of_capture(n, period_seconds) for _, n in reached],
                color=colour,
                marker=marker,
                linestyle=dashes,
                linewidth=1.8,
                markersize=5.5,
                label=name,
            )
        if missed:
            left.plot(
                missed,
                [off_scale] * len(missed),
                color=colour,
                marker=marker,
                linestyle="none",
                markersize=6.5,
                markerfacecolor="white",
            )
            right.plot(
                missed,
                [hours_of_capture(off_scale, period_seconds)] * len(missed),
                color=colour,
                marker=marker,
                linestyle="none",
                markersize=6.5,
                markerfacecolor="white",
            )

    left.set_yscale("log")
    left.set_ylabel(f"intervals needed for {target:.0%} detection")
    left.set_xlabel("jitter (fraction of the beacon period)")
    left.set_title("What a detector needs, in intervals", fontsize=11)
    left.axhline(off_scale, color="#999999", linewidth=0.8, linestyle=":")
    left.text(jitter_grid[0], off_scale * 1.08, NEVER, fontsize=8, color="#555555")
    left.grid(alpha=0.25, linewidth=0.6)
    left.legend(fontsize=9, loc="upper left")

    right.set_yscale("log")
    right.set_ylabel("hours of capture")
    right.set_xlabel("jitter (fraction of the beacon period)")
    right.set_title(f"The same floor for a {period_seconds / 3600:.0f} hour beacon", fontsize=11)
    for hours, label in ((12, "12h, common minimum"), (24, "24h, commonly called ideal")):
        right.axhline(hours, color="#b02418", linewidth=1.0, linestyle="--", alpha=0.8)
        right.text(jitter_grid[0], hours * 1.08, label, fontsize=8, color="#b02418")
    right.grid(alpha=0.25, linewidth=0.6)
    right.legend(fontsize=9, loc="upper left")

    figure.suptitle(
        f"Beacon detection floor at a {fpr:.0%} false positive rate, {model} jitter",
        fontsize=12.5,
        y=0.985,
    )
    figure.text(
        0.5,
        0.012,
        "Simulated beacons against simulated non periodic traffic. Open markers: the target was never reached "
        f"within {ceiling} intervals.",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=140)
    plt.close(figure)
    return destination
