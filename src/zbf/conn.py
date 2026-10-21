"""Read a Zeek conn.log.

Two formats, because both are in the wild: the tab separated format with the
``#fields`` header Zeek writes by default, and the JSON lines format produced
by ``LogAscii::use_json`` and by most log shippers.

The TSV reader takes the column names from the ``#fields`` header rather than
assuming a position. That is not defensiveness, it is required: Zeek 8 added
``ip_proto`` to conn.log, so a reader that hardcodes ``conn_state`` at index 11
reads ``local_orig`` on a Zeek 8 log and reports nothing wrong. A log format
with a schema line in it should be read with the schema line.

Only four fields are needed to look for a beacon: when the connection started,
who opened it, who received it, and on what port. Everything else is carried
through untouched so a caller can filter on it.
"""

from __future__ import annotations

import gzip
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

# Zeek writes these for an unset field. A beacon has a start time and a
# destination, so a record missing one of those is skipped rather than guessed.
UNSET = {"-", "(empty)", ""}

REQUIRED = ("ts", "id.orig_h", "id.resp_h", "id.resp_p")


class ConnLogError(ValueError):
    """The file is not a conn.log this reader can use, and says why."""


@dataclass(frozen=True, slots=True)
class Connection:
    ts: float
    orig: str
    resp: str
    resp_port: int
    proto: str = ""
    service: str = ""
    duration: float = 0.0
    orig_bytes: int = 0
    resp_bytes: int = 0

    @property
    def pair(self) -> tuple[str, str, int]:
        return (self.orig, self.resp, self.resp_port)


def _open(path: Path) -> IO[str]:
    """Open plain or gzipped, because rotated Zeek logs are gzipped."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _number(value: str, cast, default):
    """Cast an optional field, or fall back.

    Rejects the non finite floats that float() accepts. "inf", "nan" and
    "1e400" all parse, and an infinite timestamp reached the spectral
    detectors and raised OverflowError converting a bin count, aborting a
    whole run on one corrupted field.
    """
    if value in UNSET:
        return default
    try:
        parsed = cast(value)
    except ValueError:
        return default
    if isinstance(parsed, float) and not math.isfinite(parsed):
        return default
    return parsed


def _from_mapping(row: dict, source: str, line_number: int) -> Connection | None:
    missing = [field for field in REQUIRED if field not in row]
    if missing:
        raise ConnLogError(
            f"{source} line {line_number}: conn.log is missing {', '.join(missing)}. "
            "This reader needs ts, id.orig_h, id.resp_h and id.resp_p."
        )
    raw_ts = str(row["ts"])
    ts = _number(raw_ts, float, None)
    port = _number(str(row["id.resp_p"]), int, None)
    if ts is None and raw_ts not in UNSET:
        # Present but unusable. Unset is a missing field and is skipped above;
        # a value that is there and cannot be read is corrupt data, and
        # skipping it silently dropped every record in a whole class of real
        # logs while reporting no error at all.
        #
        # The hint is chosen from the value, because the two causes need
        # different fixes and a message that guesses wrong wastes the reader's
        # time. An ISO8601 ts means Zeek was configured with
        # LogAscii::json_timestamps = JSON::TS_ISO8601, the usual setting for
        # shipping into ELK. Anything else is a damaged field.
        looks_like_a_date = any(c in raw_ts for c in "T-:") and any(c.isdigit() for c in raw_ts)
        hint = (
            "A log written with LogAscii::json_timestamps = JSON::TS_ISO8601 has to be "
            "re-exported with the default JSON::TS_EPOCH, or converted before it is read."
            if looks_like_a_date
            else "This reader needs finite epoch seconds."
        )
        raise ConnLogError(f"{source} line {line_number}: ts is {raw_ts!r}, which is not a usable number. {hint}")
    if ts is None or port is None:
        return None
    if str(row["id.orig_h"]) in UNSET or str(row["id.resp_h"]) in UNSET:
        return None
    return Connection(
        ts=ts,
        orig=str(row["id.orig_h"]),
        resp=str(row["id.resp_h"]),
        resp_port=port,
        proto=str(row.get("proto", "")),
        service=str(row.get("service", "")),
        duration=_number(str(row.get("duration", "")), float, 0.0),
        orig_bytes=_number(str(row.get("orig_bytes", "")), int, 0),
        resp_bytes=_number(str(row.get("resp_bytes", "")), int, 0),
    )


def fields(path: Path) -> list[str]:
    """The column names this file carries, from the header or the first record."""
    with _open(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            if not line.strip():
                # read() skips blank lines; this used to call the first one a
                # malformed record and report a missing #fields header, which
                # is a diagnosis of a problem the file does not have.
                continue
            if line.startswith("#fields"):
                return line.split("\t")[1:]
            if line.startswith("#"):
                continue
            if line.strip().startswith("{"):
                try:
                    return list(json.loads(line).keys())
                except json.JSONDecodeError as exc:
                    raise ConnLogError(f"{path.name} line {line_number}: not valid JSON: {exc}") from exc
            raise ConnLogError(
                f"{path.name} line {line_number}: no #fields header and the first record is not JSON. "
                "A tab separated conn.log written without its header cannot be read safely, because "
                "column positions differ between Zeek versions."
            )
    raise ConnLogError(f"{path.name} is empty")


def read(path: Path) -> Iterator[Connection]:
    """Yield every usable connection from a conn.log, TSV or JSON lines."""
    names: list[str] | None = None
    with _open(path) as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                if line.startswith("#fields"):
                    names = line.split("\t")[1:]
                continue
            if line.lstrip().startswith("{"):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                connection = _from_mapping(row, path.name, line_number)
            else:
                if names is None:
                    raise ConnLogError(
                        f"{path.name} line {line_number}: a tab separated record appeared before any "
                        "#fields header, so the columns cannot be named. Keep the header, or export JSON."
                    )
                values = line.split("\t")
                if len(values) != len(names):
                    # A short or long row is a truncated write or a different
                    # schema mid file. Skipping it is right; guessing is not.
                    continue
                connection = _from_mapping(dict(zip(names, values, strict=True)), path.name, line_number)
            if connection is not None:
                yield connection
