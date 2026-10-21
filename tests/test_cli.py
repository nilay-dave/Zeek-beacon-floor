"""The command line, including what it says about what it cannot tell you."""

from __future__ import annotations

import numpy as np
import pytest

from zbf.cli import main
from zbf.synth import beacon, poisson

HEADER = "\t".join(["#fields", "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "orig_bytes"])


def write_log(tmp_path, series_by_pair):
    rows = [HEADER]
    for index, ((orig, resp, port), timestamps) in enumerate(series_by_pair.items()):
        for ts in timestamps:
            rows.append("\t".join([f"{ts:.3f}", f"C{index}", orig, "40000", resp, str(port), "tcp", "512"]))
    path = tmp_path / "conn.log"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_score_ranks_a_beacon_above_memoryless_traffic(tmp_path, capsys):
    rng = np.random.default_rng(0)
    path = write_log(
        tmp_path,
        {
            ("10.0.0.9", "203.0.113.5", 443): beacon(40, 600.0, 0.1, rng),
            ("10.0.0.9", "198.51.100.7", 80): poisson(40, 6.0, rng),
        },
    )
    assert main(["score", str(path)]) == 0
    out = capsys.readouterr().out
    assert out.index("203.0.113.5") < out.index("198.51.100.7")


def test_score_says_periodic_does_not_mean_malicious(tmp_path, capsys):
    """The sentence that has to survive every edit of this tool."""
    rng = np.random.default_rng(1)
    path = write_log(tmp_path, {("10.0.0.9", "203.0.113.5", 443): beacon(40, 600.0, 0.0, rng)})
    main(["score", str(path)])
    assert "does not mean malicious" in capsys.readouterr().out


def test_score_reports_a_too_short_series_rather_than_scoring_it(tmp_path, capsys):
    rng = np.random.default_rng(2)
    path = write_log(tmp_path, {("10.0.0.9", "203.0.113.5", 443): beacon(5, 600.0, 0.0, rng)})
    main(["score", str(path), "--min-connections", "4"])
    assert "too short" in capsys.readouterr().out


def test_score_exits_non_zero_when_no_pair_is_long_enough(tmp_path):
    rng = np.random.default_rng(3)
    path = write_log(tmp_path, {("10.0.0.9", "203.0.113.5", 443): beacon(1, 600.0, 0.0, rng)})
    assert main(["score", str(path), "--min-connections", "10"]) == 1


def test_a_log_without_a_header_exits_with_a_readable_error(tmp_path, capsys):
    path = tmp_path / "conn.log"
    path.write_text("1700000000.0\tC1\t10.0.0.1\t4000\t8.8.8.8\t53\tudp\t60\n", encoding="utf-8")
    assert main(["score", str(path)]) == 2
    assert "columns cannot be named" in capsys.readouterr().err


def test_fields_prints_the_column_names(tmp_path, capsys):
    rng = np.random.default_rng(4)
    path = write_log(tmp_path, {("10.0.0.9", "203.0.113.5", 443): beacon(5, 600.0, 0.0, rng)})
    assert main(["fields", str(path)]) == 0
    assert "id.resp_p" in capsys.readouterr().out.splitlines()


def test_detectors_prints_what_each_is_blind_to(capsys):
    assert main(["detectors"]) == 0
    out = capsys.readouterr().out
    assert out.count("blind to:") == 5


def test_floor_labels_its_output_as_a_simulation(capsys):
    assert (
        main(
            [
                "floor",
                "--detectors",
                "interval-cv",
                "--intervals",
                "8,16",
                "--jitter",
                "0.2",
                "--seeds",
                "1",
                "--samples",
                "60",
            ]
        )
        == 0
    )
    assert "simulated beacons" in capsys.readouterr().out


def test_hours_converts_the_floor_and_names_the_guidance_it_corrects(capsys):
    assert (
        main(
            [
                "hours",
                "--detectors",
                "interval-cv",
                "--intervals",
                "8,16",
                "--jitter",
                "0.2",
                "--seeds",
                "1",
                "--samples",
                "60",
                "--periods",
                "60,3600",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "twelve hours" in out
    assert "simulated beacons" in out


def test_an_unknown_detector_is_refused_by_name(capsys):
    with pytest.raises(SystemExit, match="unknown detector"):
        main(["floor", "--detectors", "magic"])


def test_chart_writes_a_file(tmp_path):
    destination = tmp_path / "floor.png"
    assert (
        main(
            [
                "chart",
                "--detectors",
                "interval-cv",
                "--intervals",
                "8,16",
                "--jitter",
                "0.2,0.6",
                "--seeds",
                "1",
                "--samples",
                "60",
                "--out",
                str(destination),
            ]
        )
        == 0
    )
    assert destination.stat().st_size > 1000
