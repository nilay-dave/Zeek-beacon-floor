"""The reader, including the version skew it exists to survive."""

from __future__ import annotations

import gzip
import json

import pytest

from zbf.conn import Connection, ConnLogError, fields, read

ZEEK7_HEADER = "\t".join(
    [
        "#fields",
        "ts",
        "uid",
        "id.orig_h",
        "id.orig_p",
        "id.resp_h",
        "id.resp_p",
        "proto",
        "service",
        "duration",
        "orig_bytes",
        "resp_bytes",
        "conn_state",
        "local_orig",
        "local_resp",
        "missed_bytes",
        "history",
        "orig_pkts",
        "orig_ip_bytes",
        "resp_pkts",
        "resp_ip_bytes",
        "tunnel_parents",
    ]
)
ZEEK7_ROW = "\t".join(
    [
        "1700000000.123",
        "CUid1",
        "10.0.0.5",
        "51514",
        "93.184.216.34",
        "443",
        "tcp",
        "ssl",
        "0.31",
        "517",
        "4096",
        "SF",
        "T",
        "F",
        "0",
        "ShADadFf",
        "7",
        "900",
        "6",
        "4500",
        "-",
    ]
)
# Zeek 8 added ip_proto. Every column after it moves, which is the whole reason
# this reader refuses to work from positions.
ZEEK8_HEADER = ZEEK7_HEADER.replace("\tproto\t", "\tip_proto\tproto\t")
ZEEK8_ROW = ZEEK7_ROW.replace("\ttcp\t", "\t6\ttcp\t")


def write_tsv(tmp_path, header, rows, name="conn.log"):
    path = tmp_path / name
    body = "#separator \\x09\n#path\tconn\n" + header + "\n" + "\n".join(rows) + "\n#close\t2026-01-01-00-00-00\n"
    path.write_text(body, encoding="utf-8")
    return path


def test_reads_a_zeek_7_tsv_log(tmp_path):
    path = write_tsv(tmp_path, ZEEK7_HEADER, [ZEEK7_ROW])
    (one,) = list(read(path))
    assert one == Connection(
        ts=1700000000.123,
        orig="10.0.0.5",
        resp="93.184.216.34",
        resp_port=443,
        proto="tcp",
        service="ssl",
        duration=0.31,
        orig_bytes=517,
        resp_bytes=4096,
    )


def test_a_zeek_8_log_reads_the_same_despite_the_shifted_columns(tmp_path):
    """The regression this reader exists for.

    A reader that hardcodes conn_state at index 11 silently reads local_orig on
    a Zeek 8 log and reports nothing wrong. Taking names from the header makes
    the two versions agree on every field that exists in both.
    """
    seven = next(iter(read(write_tsv(tmp_path, ZEEK7_HEADER, [ZEEK7_ROW], "seven.log"))))
    eight = next(iter(read(write_tsv(tmp_path, ZEEK8_HEADER, [ZEEK8_ROW], "eight.log"))))
    assert seven == eight


def test_reads_json_lines(tmp_path):
    path = tmp_path / "conn.json"
    row = {
        "ts": 1700000000.5,
        "uid": "C2",
        "id.orig_h": "10.0.0.6",
        "id.orig_p": 4000,
        "id.resp_h": "1.1.1.1",
        "id.resp_p": 53,
        "proto": "udp",
        "orig_bytes": 60,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    (one,) = list(read(path))
    assert (one.orig, one.resp, one.resp_port, one.proto) == ("10.0.0.6", "1.1.1.1", 53, "udp")


def test_reads_a_gzipped_log(tmp_path):
    path = tmp_path / "conn.log.gz"
    body = ZEEK7_HEADER + "\n" + ZEEK7_ROW + "\n"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(body)
    assert len(list(read(path))) == 1


def test_a_tsv_without_a_fields_header_is_refused_rather_than_guessed(tmp_path):
    """Both entry points refuse, and each says why in its own terms."""
    path = tmp_path / "headerless.log"
    path.write_text(ZEEK7_ROW + "\n", encoding="utf-8")
    with pytest.raises(ConnLogError, match="columns cannot be named"):
        list(read(path))
    with pytest.raises(ConnLogError, match="differ between Zeek versions"):
        fields(path)


def test_rows_of_the_wrong_width_are_skipped_not_misaligned(tmp_path):
    truncated = "\t".join(ZEEK7_ROW.split("\t")[:9])
    path = write_tsv(tmp_path, ZEEK7_HEADER, [ZEEK7_ROW, truncated, ZEEK7_ROW])
    assert len(list(read(path))) == 2


def test_unset_values_do_not_become_zero(tmp_path):
    row = ZEEK7_ROW.replace("\t517\t", "\t-\t")
    path = write_tsv(tmp_path, ZEEK7_HEADER, [row])
    (one,) = list(read(path))
    assert one.orig_bytes == 0
    assert one.resp_port == 443


def test_a_record_without_a_usable_timestamp_is_dropped(tmp_path):
    path = write_tsv(tmp_path, ZEEK7_HEADER, [ZEEK7_ROW.replace("1700000000.123", "-", 1)])
    assert list(read(path)) == []


def test_fields_reports_the_header_for_tsv_and_the_keys_for_json(tmp_path):
    tsv = write_tsv(tmp_path, ZEEK7_HEADER, [ZEEK7_ROW])
    assert fields(tsv)[:3] == ["ts", "uid", "id.orig_h"]
    assert "ip_proto" in fields(write_tsv(tmp_path, ZEEK8_HEADER, [ZEEK8_ROW], "eight.log"))

    js = tmp_path / "conn.json"
    js.write_text(json.dumps({"ts": 1.0, "id.orig_h": "a", "id.resp_h": "b", "id.resp_p": 1}) + "\n", encoding="utf-8")
    assert fields(js) == ["ts", "id.orig_h", "id.resp_h", "id.resp_p"]


def test_a_log_missing_a_required_field_says_which(tmp_path):
    header = ZEEK7_HEADER.replace("\tid.resp_p", "")
    row = "\t".join(v for i, v in enumerate(ZEEK7_ROW.split("\t")) if i != 5)
    path = write_tsv(tmp_path, header, [row])
    with pytest.raises(ConnLogError, match="id.resp_p"):
        list(read(path))
