#!/usr/bin/env python3
"""Analyse the AMBici and Bicing realtime GBFS captures (T006).

Throwaway spike code. Implements the Analysis plan in
docs/spikes/s001-ambici-realtime-capture.md › Analysis plan, which is the
source of truth: this script makes no analysis decisions of its own.

Implemented (parts 1–3): common settings (configuration, streamed loading,
analysis window and grid, responses used, UTC conversion), Verification ›
reconciliation (including the gaps.csv check), the 4b, 5d and 6b
hand-checkable examples, metrics 1a, 1b, 1d, 1e, 1f, 2c, 2d, the 2a input
(field_comparison.csv), 3a–3d, 4a–4c, 5a–5d, 6a–6d, 7a–7c, 8a–8j, 9a–9d
(AMBici), 10a–10b (AMBici), and the --only option.

Structure: every response used is streamed once, in request order per feed,
to a list of analysers. Each analyser owns one plan section, observes the
responses it needs and renders its own outputs. Later parts add analysers and
summary sections without changing the existing ones. Metrics computed from
the request log alone (5, 7) are plain functions over the log lines.

Usage, from the repository root, with the venv active:
    python spikes/realtime-capture-analysis/analyse_realtime_capture.py --system both
    python spikes/realtime-capture-analysis/analyse_realtime_capture.py --system both --only 3a,5d
"""

import argparse
import bisect
import csv
import gzip
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jsonschema

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCHEMA_DIR = HERE / "schemas"

# Common settings › Analysis window (both ends are complete ticks, inclusive).
WINDOW_START = datetime(2026, 10, 3, 17, 11, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 5, 14, 26, tzinfo=UTC)
STATIC_GRID_MINUTES = 15

# Numbers from the step 1 inventory, checked (not enforced) by the reconciliation.
INVENTORY = {
    "ticks_in_window": 2716,
    "failed_in_window": {"ambici": 7, "bicing": 5},
    "missing_ticks_total": 3,
}

# Common-model feeds compared in field_comparison.csv and searched for IDs (2a input, 2c).
COMMON_MODEL_FEEDS = ["station_information", "station_status", "vehicle_types"]
ID_FIELDS = ["station_id", "vehicle_type_id"]

# Timestamp fields: the fields typed Timestamp (2.3) or Datetime (3.0) in the official
# schemas of the declared version, restricted to the feeds each system publishes.
SYSTEMS = {
    "ambici": {
        "label": "AMBici",
        "capture_dir": REPO / "spikes/ambici-spike",
        "out_dir": REPO / "spikes/ambici-spike/analysis",
        "gbfs_version": "2.3",
        "language": "en",  # responses used: en only; ca/es copies belong to question 10
        "dynamic_feeds": ["station_status", "free_bike_status"],
        "static_feeds": [
            "gbfs", "system_information", "vehicle_types", "station_information",
            "system_hours", "system_regions", "system_pricing_plans", "geofencing_zones",
        ],
        "timestamp_kind": "posix",
        "timestamp_fields": {
            "*": ["last_updated"],
            "station_status": ["data.stations[].last_reported"],
            "free_bike_status": ["data.bikes[].last_reported"],
            "geofencing_zones": [
                "data.geofencing_zones.features[].properties.start",
                "data.geofencing_zones.features[].properties.end",
            ],
        },
        # Field names of station_status (4a, 8a, 8c); no disabled counts in AMBici.
        "status_fields": {"available": "num_bikes_available", "docks": "num_docks_available",
                          "vehicles_disabled": None, "docks_disabled": None},
        "docks_capacity": False,      # 6c, 8a: no vehicle_docks_capacity
        "known_issues": True,         # 8i
        "system_questions": ["9", "10"],
    },
    "bicing": {
        "label": "Bicing",
        "capture_dir": REPO / "spikes/bicing-spike/realtime",
        "out_dir": REPO / "spikes/bicing-spike/analysis",
        "gbfs_version": "3.0",
        "language": None,  # no language copies; all in-window responses are used
        "dynamic_feeds": ["station_status"],
        "static_feeds": [
            "gbfs", "gbfs_versions", "geofencing_zones", "station_information",
            "system_information", "system_pricing_plans", "system_regions", "vehicle_types",
        ],
        "timestamp_kind": "rfc3339",
        "timestamp_fields": {
            "*": ["last_updated"],
            "station_status": ["data.stations[].last_reported"],
            "geofencing_zones": [
                "data.geofencing_zones.features[].properties.start",
                "data.geofencing_zones.features[].properties.end",
            ],
        },
        "status_fields": {"available": "num_vehicles_available", "docks": "num_docks_available",
                          "vehicles_disabled": "num_vehicles_disabled", "docks_disabled": "num_docks_disabled"},
        "docks_capacity": True,
        "known_issues": False,
        "system_questions": [],
    },
}

# 5d rule 1: the Mac sleep/wake excerpt (local time with its UTC offset on every line).
PMSET_FILE = HERE / "inputs" / "pmset-sleep-wake-2026-10-03-to-2026-10-05.txt"

# 3a: lists of objects carrying one of these keys are compared as sets keyed by it.
ID_KEYS = ["station_id", "bike_id", "vehicle_type_id", "plan_id", "region_id"]

# 7b: the only complete UTC day of the capture.
VOLUME_DAY = datetime(2026, 10, 4, tzinfo=UTC)

# 7c: projection units (approved conventions).
DAYS_PER_MONTH, DAYS_PER_YEAR = 30, 365
GB = 10**9
R2_FREE_BYTES = 10 * GB
SLOW_POLL_MINUTES = 5

# --only: metric ids the script implements, in summary order; the ones needing both systems.
METRICS = ["1a", "1b", "1d", "1e", "1f", "2a", "2c", "2d", "3a", "3b", "3c", "3d", "4a", "4b", "4c",
           "5a", "5b", "5c", "5d", "6a", "6b", "6c", "6d", "7a", "7b", "7c",
           "8a", "8b", "8c", "8d", "8e", "8f", "8g", "8h", "8i", "8j", "9a", "9b", "9c", "9d", "10a", "10b"]
CROSS_SYSTEM_METRICS = {"2a", "2c", "2d", "5d", "7c"}
QUALITY_CHECKS = [m for m in METRICS if m.startswith("8")]


def applies(name, metric):
    """False for a metric of a system-only question (9, 10) on a system it does not cover."""
    question = re.match(r"\d+", metric).group()
    return question not in ("9", "10") or question in SYSTEMS[name]["system_questions"]


def timestamp_paths(cfg, feed):
    """Return the set of timestamp field paths configured for a feed."""
    fields = cfg["timestamp_fields"]
    return set(fields["*"]) | set(fields.get(feed, []))


# ---------------------------------------------------------------------------
# Time helpers (Common settings › Timestamps: UTC, milliseconds kept)
# ---------------------------------------------------------------------------

def parse_iso_utc(text):
    """Parse an ISO 8601 / RFC 3339 string with offset into an aware UTC datetime."""
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise ValueError(f"no UTC offset: {text}")
    return value.astimezone(UTC)


def to_utc(value, kind):
    """Convert a GBFS timestamp value to UTC; return None if it cannot be parsed."""
    try:
        if kind == "posix":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            return datetime.fromtimestamp(value, UTC)
        if not isinstance(value, str):
            return None
        return parse_iso_utc(value)
    except (ValueError, OverflowError, OSError):
        return None


def iso(dt):
    """Format an aware datetime as UTC ISO 8601 with milliseconds and a Z suffix."""
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def minute_grid(start, end, every_minutes=1):
    """Return the expected ticks between start and end inclusive, on the given grid."""
    ticks, tick = [], start
    while tick <= end:
        minutes = int(tick.timestamp()) // 60
        if minutes % every_minutes == 0:
            ticks.append(tick)
        tick += timedelta(minutes=1)
    return ticks


# ---------------------------------------------------------------------------
# Loading: request log and responses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Request:
    """One line of a capture request log, with times parsed to UTC."""

    tick: datetime
    requested_at: datetime
    purpose: str
    feed: str
    language: str | None
    http_status: int | None
    elapsed_ms: int | None
    bytes_raw: int | None
    bytes_gz: int | None
    server_last_updated: datetime | None
    file: str | None
    error: str | None
    log_file: str
    line_no: int

    @property
    def stored(self):
        """True when the request succeeded and a raw response was saved."""
        return self.error is None and self.file is not None


@dataclass
class Response:
    """A stored response being streamed: its log line and its parsed JSON body."""

    request: Request
    doc: object


def load_requests(cfg):
    """Read every request log line of a system (the logs are small; bodies are not loaded)."""
    requests = []
    for log_path in sorted((cfg["capture_dir"] / "log").glob("requests_*.jsonl")):
        with open(log_path, encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                rec = json.loads(line)
                last = rec.get("server_last_updated")
                requests.append(Request(
                    tick=parse_iso_utc(rec["tick_utc"]),
                    requested_at=parse_iso_utc(rec["requested_at_utc"]),
                    purpose=rec["purpose"],
                    feed=rec["feed"],
                    language=rec.get("language"),
                    http_status=rec["http_status"],
                    elapsed_ms=rec["elapsed_ms"],
                    bytes_raw=rec["bytes_raw"],
                    bytes_gz=rec["bytes_gz"],
                    server_last_updated=None if last is None else to_utc(last, cfg["timestamp_kind"]),
                    file=rec["file"],
                    error=rec["error"],
                    log_file=log_path.name,
                    line_no=line_no,
                ))
    return requests


def stream_responses(cfg, requests, load_errors):
    """Yield stored responses one at a time, grouped by feed and ordered by request time.

    Only one parsed body is alive at a time. Files that cannot be read or parsed
    are recorded in load_errors and skipped.
    """
    ordered = sorted((r for r in requests if r.stored), key=lambda r: (r.feed, r.requested_at))
    for req in ordered:
        path = cfg["capture_dir"] / req.file
        try:
            with gzip.open(path, "rb") as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as exc:
            load_errors.append((req.file, f"{type(exc).__name__}: {exc}"))
            continue
        yield Response(req, doc)


def scan_raw_files(cfg):
    """Return the relative paths of raw files on disk with the UTC time in their name."""
    files = {}
    for path in (cfg["capture_dir"] / "raw").glob("*/*/*.json.gz"):
        stamp = datetime.strptime(path.name.removesuffix(".json.gz"), "%Y%m%dT%H%M%SZ")
        files[str(path.relative_to(cfg["capture_dir"]))] = stamp.replace(tzinfo=UTC)
    return files


# ---------------------------------------------------------------------------
# Analysis window and responses used (Common settings)
# ---------------------------------------------------------------------------

def in_window(moment):
    """True when a tick or file time falls inside the analysis window (minute resolution)."""
    return WINDOW_START <= moment < WINDOW_END + timedelta(minutes=1)


def split_requests(cfg, requests):
    """Split log lines into the responses used and the discarded ones, by reason."""
    used, discarded = [], defaultdict(list)
    for req in requests:
        if req.purpose == "language_copy" or (cfg["language"] and req.language != cfg["language"]):
            discarded["language copy (used only by question 10)"].append(req)
        elif not in_window(req.tick):
            discarded["outside the analysis window"].append(req)
        else:
            used.append(req)
    return used, discarded


def is_on_grid(cfg, req):
    """True when a request is an expected tick of its feed (see Common settings › Grid)."""
    if req.purpose != "observation":
        return False
    if req.feed in cfg["dynamic_feeds"]:
        return True
    return (int(req.tick.timestamp()) // 60) % STATIC_GRID_MINUTES == 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def json_type(value):
    """Return the JSON Schema type name of a parsed JSON value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def collapse_path(parts):
    """Turn a JSON path (keys and list indices) into a dotted path with list items collapsed."""
    text = ""
    for part in parts:
        if isinstance(part, int):
            text += "[]"
        else:
            text += f".{part}" if text else str(part)
    return text or "(root)"


def pct(part, whole):
    """Percentage with two decimals, or an empty string when whole is zero."""
    return "" if not whole else f"{100 * part / whole:.2f}"


def write_csv(path, header, rows):
    """Write a CSV file with a header row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def md_table(header, rows):
    """Render a Markdown table."""
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def schema_commit():
    """Read the pinned MobilityData schema commit from schemas/SOURCE.md."""
    text = (SCHEMA_DIR / "SOURCE.md").read_text(encoding="utf-8")
    match = re.search(r"Commit \(pinned\)\s*\|\s*`([0-9a-f]{40})`", text)
    return match.group(1) if match else "unknown"


class Analyser:
    """Base class: one plan section, fed every response used, in request order per feed."""

    feeds = None  # None = every feed; otherwise the feeds this analyser needs

    def wants(self, feed):
        """True when the analyser needs responses of this feed."""
        return self.feeds is None or feed in self.feeds

    def observe(self, response):
        """Process one response."""

    def finish(self):
        """Called once after the last response."""


# ---------------------------------------------------------------------------
# 1. Schema: feeds, versions, field profile, stability, compliance
# ---------------------------------------------------------------------------

class FeedsPublished(Analyser):
    """1a. Feed names listed in each gbfs.json response, with first and last time seen."""

    feeds = {"gbfs"}

    def __init__(self, cfg):
        self.cfg = cfg
        self.responses = 0
        self.first, self.last, self.listed = {}, {}, Counter()
        self.language_blocks = Counter()
        self.language_mismatches = []

    def observe(self, response):
        """Collect the feed names of one index response."""
        self.responses += 1
        data = response.doc.get("data", {})
        when = response.request.requested_at
        if self.cfg["gbfs_version"].startswith("2."):
            # 2.x: one block per language; the en block is the reference.
            blocks = {lang: {f["name"] for f in block.get("feeds", [])} for lang, block in data.items()}
            self.language_blocks[",".join(sorted(blocks))] += 1
            names = blocks.get(self.cfg["language"], set())
            if len({frozenset(v) for v in blocks.values()}) > 1:
                self.language_mismatches.append(response.request.file)
        else:
            names = {f["name"] for f in data.get("feeds", [])}
        for name in names:
            self.listed[name] += 1
            self.first.setdefault(name, when)
            self.last[name] = when

    def feed_names(self):
        """All feed names listed in at least one index response."""
        return set(self.listed)

    def render(self):
        """Summary section for 1a."""
        cfg = self.cfg
        rows = [(f"`{n}`", self.listed[n], iso(self.first[n]), iso(self.last[n])) for n in sorted(self.listed)]
        out = [f"### 1a. Feeds published\n\n{self.responses} `gbfs.json` responses used."]
        if cfg["gbfs_version"].startswith("2."):
            blocks = "; ".join(f"`{k}` in {v} responses" for k, v in self.language_blocks.items())
            out.append(f"Language blocks: {blocks}. Feed names taken from the `{cfg['language']}` block. "
                       f"Responses whose language blocks list different feeds: {len(self.language_mismatches)}"
                       + (f" (first: `{self.language_mismatches[0]}`)." if self.language_mismatches else "."))
        out.append(md_table(["Feed", "Responses listing it", "First seen (UTC)", "Last seen (UTC)"], rows))
        captured = set(cfg["dynamic_feeds"]) | set(cfg["static_feeds"])
        listed = self.feed_names() | {"gbfs"}  # the index does not list itself
        out.append(f"Listed but not captured: {', '.join(sorted(listed - captured)) or 'none'}. "
                   f"Captured but never listed (index excluded): {', '.join(sorted(captured - listed)) or 'none'}.")
        return "\n\n".join(out)


class DeclaredVersion(Analyser):
    """1b. The `version` field of each response used, per feed."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.by_feed = defaultdict(Counter)

    def observe(self, response):
        """Record the declared version of one response."""
        doc = response.doc
        version = doc.get("version", "(absent)") if isinstance(doc, dict) else "(not an object)"
        self.by_feed[response.request.feed][str(version)] += 1

    def render(self):
        """Summary section for 1b."""
        rows = [(f"`{feed}`", "; ".join(f"{v} ({n})" for v, n in sorted(c.items())))
                for feed, c in sorted(self.by_feed.items())]
        overall = sorted({v for c in self.by_feed.values() for v in c})
        return (f"### 1b. Declared version\n\nVersions found across all feeds: {', '.join(overall)} "
                f"(expected one; configured {self.cfg['gbfs_version']}).\n\n"
                + md_table(["Feed", "Version (responses)"], rows))


class FieldStats:
    """Running statistics of one field path in one feed (1d)."""

    __slots__ = ("occurrences", "types", "nulls", "num_min", "num_max",
                 "ts_min", "ts_max", "ts_unparseable", "distinct")

    def __init__(self):
        self.occurrences = 0
        self.types = Counter()
        self.nulls = 0
        self.num_min = self.num_max = None
        self.ts_min = self.ts_max = None
        self.ts_unparseable = 0
        self.distinct = set()


class FieldProfile(Analyser):
    """1d field profile and 1e schema stability, computed in the same walk of each response."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.stats = defaultdict(dict)        # feed -> path -> FieldStats
        self.objects = defaultdict(Counter)   # feed -> object path -> occurrences
        self.responses = Counter()
        self.previous = {}                    # feed -> (paths, request) of the previous response
        self.changes = []                     # 1e rows

    def observe(self, response):
        """Profile every field of one response and compare its paths with the previous one."""
        feed = response.request.feed
        stats, objects = self.stats[feed], self.objects[feed]
        ts_paths = timestamp_paths(self.cfg, feed)
        kind = self.cfg["timestamp_kind"]
        seen = set()
        self.responses[feed] += 1

        def record(path, value):
            seen.add(path)
            st = stats.get(path)
            if st is None:
                st = stats[path] = FieldStats()
            st.occurrences += 1
            vtype = json_type(value)
            st.types[vtype] += 1
            if vtype == "null":
                st.nulls += 1
                return
            if vtype in ("array", "object"):
                return
            # (type, value) so that true/1 and 1/1.0 stay distinct.
            st.distinct.add((vtype, value))
            if path in ts_paths:
                moment = to_utc(value, kind)
                if moment is None:
                    st.ts_unparseable += 1
                else:
                    st.ts_min = moment if st.ts_min is None or moment < st.ts_min else st.ts_min
                    st.ts_max = moment if st.ts_max is None or moment > st.ts_max else st.ts_max
            elif vtype in ("integer", "number"):
                st.num_min = value if st.num_min is None or value < st.num_min else st.num_min
                st.num_max = value if st.num_max is None or value > st.num_max else st.num_max

        def walk(node, path):
            if isinstance(node, dict):
                objects[path] += 1
                for key, value in node.items():
                    child = f"{path}.{key}" if path else key
                    record(child, value)
                    walk(value, child)
            elif isinstance(node, list):
                child = path + "[]"
                for item in node:
                    record(child, item)
                    walk(item, child)

        walk(response.doc, "")

        prev = self.previous.get(feed)
        if prev is not None:
            prev_paths, prev_req = prev
            req = response.request
            for change, paths in (("appeared", seen - prev_paths), ("disappeared", prev_paths - seen)):
                for path in sorted(paths):
                    self.changes.append((feed, path, change, req.file, iso(req.requested_at),
                                         prev_req.file, iso(prev_req.requested_at)))
        self.previous[feed] = (seen, response.request)

    @staticmethod
    def parent_of(path):
        """Parent object path of a field path; for list items, the list itself."""
        if path.endswith("[]"):
            return path[:-2]
        return path.rsplit(".", 1)[0] if "." in path else ""

    def rows(self, feed):
        """Profile rows of one feed, as dicts keyed by CSV column."""
        ts_paths = timestamp_paths(self.cfg, feed)
        rows = []
        for path in sorted(self.stats[feed]):
            st = self.stats[feed][path]
            parent = self.parent_of(path)
            is_item = path.endswith("[]")
            # % present / % null are over occurrences of the parent object; top-level over responses.
            # List items are not keyed fields: no % present; % null is over the items.
            parent_occ = st.occurrences if is_item else (
                self.objects[feed][parent] if parent else self.responses[feed])
            is_ts = path in ts_paths
            if is_ts:
                low = iso(st.ts_min) if st.ts_min else ""
                high = iso(st.ts_max) if st.ts_max else ""
            else:
                low = "" if st.num_min is None else st.num_min
                high = "" if st.num_max is None else st.num_max
            distinct = sorted(st.distinct, key=lambda tv: (tv[0], str(tv[1])))
            values = ""
            if st.distinct and len(distinct) <= 20:
                shown = [iso(to_utc(v, self.cfg["timestamp_kind"])) if is_ts and to_utc(v, self.cfg["timestamp_kind"]) else v
                         for _, v in distinct]
                values = json.dumps(shown, ensure_ascii=False)
            rows.append({
                "feed": feed,
                "path": path,
                "parent_path": "(list items)" if is_item else (parent or "(root)"),
                "parent_occurrences": parent_occ,
                "occurrences": st.occurrences,
                "types": "; ".join(f"{t}:{n}" for t, n in sorted(st.types.items())),
                "present_pct": "" if is_item else pct(st.occurrences, parent_occ),
                "null_pct": pct(st.nulls, parent_occ),
                "min": low,
                "max": high,
                "timestamp": "yes" if is_ts else "",
                "timestamp_unparseable": st.ts_unparseable if is_ts else "",
                "distinct_count": len(st.distinct) if st.distinct else "",
                "distinct_values": values,
            })
        return rows

    def all_rows(self):
        """Profile rows of every feed."""
        return [row for feed in sorted(self.stats) for row in self.rows(feed)]

    def render(self):
        """Summary sections for 1d and 1e."""
        rows, mixed, unparseable = [], [], []
        for feed in sorted(self.stats):
            profile = self.rows(feed)
            nulls = sum(1 for r in profile if r["null_pct"] not in ("", "0.00"))
            rows.append((f"`{feed}`", self.responses[feed], len(profile), nulls))
            for r in profile:
                kinds = [t for t in r["types"].split("; ") if not t.startswith("null:")]
                if len(kinds) > 1:
                    mixed.append((f"`{feed}`", f"`{r['path']}`", r["types"]))
                if r["timestamp_unparseable"] not in ("", 0):
                    unparseable.append((f"`{feed}`", f"`{r['path']}`", r["timestamp_unparseable"]))
        out = ["### 1d. Field profile\n\nFull profile in `field_profile.csv`.",
               md_table(["Feed", "Responses", "Field paths", "Paths with nulls"], rows),
               "Paths with more than one non-null type:",
               md_table(["Feed", "Path", "Types (count)"], mixed) if mixed else "None.",
               "Timestamp values that could not be converted to UTC:",
               md_table(["Feed", "Path", "Values"], unparseable) if unparseable else "None."]
        by_feed = Counter(c[0] for c in self.changes)
        out.append("### 1e. Schema stability\n\n"
                   f"Field paths appearing or disappearing versus the previous response of the same feed: "
                   f"{len(self.changes)} rows in `schema_changes.csv` (expected empty)."
                   + ("\n\n" + md_table(["Feed", "Rows"], [(f"`{f}`", n) for f, n in sorted(by_feed.items())])
                      if by_feed else ""))
        return "\n\n".join(out)


class Compliance(Analyser):
    """1f. Violations of the official GBFS JSON Schema of the declared version."""

    def __init__(self, cfg, commit):
        self.cfg = cfg
        self.commit = commit
        self.validators = {}
        self.missing_schema = set()
        self.groups = {}                       # (feed, keyword, schema path) -> group
        self.by_instance_path = defaultdict(Counter)  # feed -> collapsed instance path -> count
        self.validated = Counter()

    def validator(self, feed):
        """Return the cached validator of a feed, or None if no schema exists for it."""
        if feed not in self.validators:
            path = SCHEMA_DIR / f"v{self.cfg['gbfs_version']}" / f"{feed}.json"
            if not path.exists():
                self.missing_schema.add(feed)
                self.validators[feed] = None
            else:
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.validators[feed] = jsonschema.validators.validator_for(schema)(schema)
        return self.validators[feed]

    def observe(self, response):
        """Validate one response and group its violations."""
        feed = response.request.feed
        validator = self.validator(feed)
        if validator is None:
            return
        self.validated[feed] += 1
        affected = set()
        for error in validator.iter_errors(response.doc):
            schema_path = "/".join(str(p) for p in error.absolute_schema_path)
            instance_path = collapse_path(list(error.absolute_path))
            key = (feed, error.validator, schema_path)
            group = self.groups.get(key)
            if group is None:
                group = self.groups[key] = {
                    "instance_paths": set(), "message": error.message, "occurrences": 0,
                    "responses": 0, "example": response.request.file,
                }
            group["instance_paths"].add(instance_path)
            group["occurrences"] += 1
            if key not in affected:
                group["responses"] += 1
                affected.add(key)
            self.by_instance_path[feed][instance_path] += 1

    def rows(self):
        """Rows of schema_violations.csv."""
        return [(feed, keyword, schema_path, "; ".join(sorted(g["instance_paths"])), g["message"],
                 g["occurrences"], g["responses"], g["example"], self.commit)
                for (feed, keyword, schema_path), g in sorted(self.groups.items())]

    def render(self):
        """Summary section for 1f."""
        out = [f"### 1f. Compliance\n\nSchemas: MobilityData `gbfs-json-schema` v{self.cfg['gbfs_version']} "
               f"at commit `{self.commit}`. Responses validated per feed: "
               + ", ".join(f"`{f}` {n}" for f, n in sorted(self.validated.items())) + "."]
        if self.missing_schema:
            out.append("No official schema for: " + ", ".join(f"`{f}`" for f in sorted(self.missing_schema))
                       + " (not validated).")
        rows = [(f"`{r[0]}`", r[1], f"`{r[2]}`", f"`{r[3]}`", r[5], r[6], r[4][:150]) for r in self.rows()]
        out.append(f"Violation groups (feed + keyword + schema path): {len(rows)}. Full rows in `schema_violations.csv`; "
                   "the message is the first occurrence's.")
        if rows:
            out.append(md_table(["Feed", "Keyword", "Schema path", "Instance path", "Occurrences",
                                 "Responses affected", "Message (first, truncated)"], rows))
        return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 2. Common model: ID collisions, feeds without equivalent, field_comparison.csv
# ---------------------------------------------------------------------------

class IdCollector(Analyser):
    """2c input: every station_id and vehicle_type_id value in the common-model feeds."""

    feeds = set(COMMON_MODEL_FEEDS)

    def __init__(self, cfg):
        self.cfg = cfg
        self.values = {name: set() for name in ID_FIELDS}   # (json type, value)
        self.paths = {name: Counter() for name in ID_FIELDS}
        # vehicle_type_ids arrays are not keys named vehicle_type_id, so they stay outside
        # the 2c set; collected only to report whether they would change it.
        self.array_values = set()

    def observe(self, response):
        """Collect ID values found under keys named station_id or vehicle_type_id."""
        feed = response.request.feed

        def walk(node, path):
            if isinstance(node, dict):
                for key, value in node.items():
                    child = f"{path}.{key}" if path else key
                    if key in self.values:
                        self.values[key].add((json_type(value), value))
                        self.paths[key][f"{feed}: {child}"] += 1
                    elif key == "vehicle_type_ids" and isinstance(value, list):
                        self.array_values.update((json_type(v), v) for v in value)
                    walk(value, child)
            elif isinstance(node, list):
                for item in node:
                    walk(item, path + "[]")

        walk(response.doc, "")


def render_common_model(system, results):
    """Summary section for question 2 (2c, 2d); needs both systems' results."""
    out = ["## 2. Common model",
           "2a (field mapping) and 2b (effort summary) are done by Chat. Their input, "
           "`field_comparison.csv`, is in `spikes/bicing-spike/analysis/`."]
    if set(results) != set(SYSTEMS):
        out.append("### 2c. ID collisions\n\nNot computed: needs both systems (`--system both`).")
        out.append("### 2d. Feeds without equivalent\n\nNot computed: needs both systems (`--system both`).")
        return "\n\n".join(out)

    a, b = (results[name]["ids"] for name in SYSTEMS)
    la, lb = (SYSTEMS[name]["label"] for name in SYSTEMS)
    rows, details = [], []
    for field in ID_FIELDS:
        common = a.values[field] & b.values[field]
        types_a = sorted({t for t, _ in a.values[field]})
        types_b = sorted({t for t, _ in b.values[field]})
        rows.append((f"`{field}`", len(a.values[field]), ", ".join(types_a), len(b.values[field]),
                     ", ".join(types_b), len(common)))
        if common:
            details.append(f"`{field}` values in both systems: "
                           + ", ".join(f"`{v}`" for _, v in sorted(common, key=lambda tv: str(tv[1]))))
    arrays = []
    for name, other in ((n, m) for n in SYSTEMS for m in SYSTEMS if n != m):
        own, theirs = results[name]["ids"], results[other]["ids"]
        if own.array_values:
            arrays.append(f"{SYSTEMS[name]['label']} also has `vehicle_type_ids` arrays (not keys named "
                          f"`vehicle_type_id`, so not in the set above): {len(own.array_values)} distinct values, "
                          f"{len(own.array_values - own.values['vehicle_type_id'])} not in its own `vehicle_type_id` "
                          f"set, {len(own.array_values & theirs.values['vehicle_type_id'])} in "
                          f"{SYSTEMS[other]['label']}'s `vehicle_type_id` set.")
    if not details:
        details.append("No value appears in both systems.")
    details += arrays
    paths = []
    for name in SYSTEMS:
        ids = results[name]["ids"]
        for field in ID_FIELDS:
            for path, n in sorted(ids.paths[field].items()):
                paths.append((SYSTEMS[name]["label"], f"`{field}`", f"`{path}`", n))
    out.append("### 2c. ID collisions\n\nValues compared as JSON values (type and value), from every key named "
               "`station_id` or `vehicle_type_id` in all responses used of "
               + ", ".join(f"`{f}`" for f in COMMON_MODEL_FEEDS) + ".\n\n"
               + md_table(["Field", f"{la} distinct", f"{la} types", f"{lb} distinct", f"{lb} types",
                           "Values in both"], rows)
               + "\n\n" + "\n\n".join(details)
               + "\n\nPaths the values came from (occurrences):\n\n"
               + md_table(["System", "Field", "Feed: path", "Occurrences"], paths))

    feeds = {name: results[name]["feeds"].feed_names() for name in SYSTEMS}
    names = list(SYSTEMS)
    only = [(SYSTEMS[n]["label"], ", ".join(f"`{f}`" for f in sorted(feeds[n] - feeds[m])) or "none")
            for n, m in ((names[0], names[1]), (names[1], names[0]))]
    out.append("### 2d. Feeds without equivalent\n\nFeed names from 1a (all `gbfs.json` responses used), "
               "compared literally by name.\n\n" + md_table(["Published only by", "Feeds"], only))
    return "\n\n".join(out)


def field_comparison_rows(results):
    """Rows of field_comparison.csv: outer join of both profiles on feed + path (2a input)."""
    profiles, violations = {}, {}
    for name in SYSTEMS:
        prof = results[name]["profile"]
        profiles[name] = {(r["feed"], r["path"]): r for feed in COMMON_MODEL_FEEDS for r in prof.rows(feed)}
        violations[name] = results[name]["compliance"].by_instance_path
    keys = sorted(set().union(*(p.keys() for p in profiles.values())))
    rows = []
    for feed, path in keys:
        row = [feed, path]
        for name in SYSTEMS:
            r = profiles[name].get((feed, path))
            if r is None:
                row += ["no"] + [""] * 7
                continue
            distinct = r["distinct_values"] or (f"{r['distinct_count']} distinct" if r["distinct_count"] != "" else "")
            row += ["yes", r["types"], r["present_pct"], r["null_pct"], r["min"], r["max"], distinct,
                    violations[name][feed].get(path, 0)]
        rows.append(row)
    return rows


def field_comparison_header():
    """Header of field_comparison.csv."""
    header = ["feed", "path"]
    for name in SYSTEMS:
        header += [f"{name}_{c}" for c in ("present", "types", "present_pct", "null_pct", "min", "max",
                                           "distinct", "violations_1f")]
    return header


# ---------------------------------------------------------------------------
# Part 2 helpers: distributions and gaps on the grid
# ---------------------------------------------------------------------------

def median(values):
    """Median as statistics.median (mean of the two middle values for an even count)."""
    return statistics.median(values) if values else None


def p95(values):
    """95th percentile by the nearest-rank method."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def fmt(value, digits=3):
    """Format a number for tables: integral values without decimals, others rounded."""
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def distribution(values):
    """Median, p95 and max of a list, formatted; empty cells when the list is empty."""
    return [fmt(median(values)), fmt(p95(values)), fmt(max(values) if values else None)]


def feed_grid(cfg, feed):
    """Expected ticks of a feed in the window (see Common settings › Grid)."""
    every = 1 if feed in cfg["dynamic_feeds"] else STATIC_GRID_MINUTES
    return minute_grid(WINDOW_START, WINDOW_END, every)


def missing_ticks_by_feed(cfg, used):
    """Per feed, the sorted expected ticks without a stored on-grid response."""
    stored = defaultdict(set)
    for req in used:
        if req.stored and is_on_grid(cfg, req):
            stored[req.feed].add(req.tick)
    return {feed: [t for t in feed_grid(cfg, feed) if t not in stored[feed]]
            for feed in cfg["dynamic_feeds"] + cfg["static_feeds"]}


def spans_gap(missing, prev_tick, tick):
    """True when a missing expected tick lies strictly between two response ticks."""
    i = bisect.bisect_right(missing, prev_tick)
    return i < len(missing) and missing[i] < tick


def is_ok(req):
    """A successful request: HTTP 200 and a stored response (5a, 5d)."""
    return req.stored and req.http_status == 200


def feed_order(cfg):
    """Feeds in configuration order: dynamic first, then static."""
    return cfg["dynamic_feeds"] + cfg["static_feeds"]


# ---------------------------------------------------------------------------
# 3. Freshness: content changes, station reporting, last_updated, ttl
# ---------------------------------------------------------------------------

def comparable(value):
    """Normalise a parsed JSON value with the 3a comparison rules, so that == means "same value".

    Numbers compare by value (50 = 50.0) but never equal a boolean; key order is
    ignored; lists of objects that all carry one ID key are compared as sets of
    items (a multiset, so duplicates still count); other lists in order.
    """
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("num", value)
    if isinstance(value, dict):
        return ("obj", frozenset((k, comparable(v)) for k, v in value.items()))
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            for key in ID_KEYS:
                if all(key in item for item in value):
                    return ("set", key, frozenset(Counter(comparable(item) for item in value).items()))
        return ("list", tuple(comparable(item) for item in value))
    return (json_type(value), value)


class ContentChanges(Analyser):
    """3a. Changes of the `data` block between consecutive responses of each feed."""

    def __init__(self, cfg, missing):
        self.cfg = cfg
        self.missing = missing
        self.previous = {}      # feed -> (request, comparable data) of the previous response
        self.last_change = {}   # feed -> request of the last change; None after a gap
        self.stats = defaultdict(Counter)
        self.intervals = defaultdict(list)
        self.rows = []          # content_changes.csv

    def observe(self, response):
        """Compare one response's data block with the previous response of its feed."""
        req = response.request
        feed = req.feed
        doc = response.doc
        data = comparable(doc.get("data") if isinstance(doc, dict) else doc)
        st = self.stats[feed]
        st["responses"] += 1
        prev = self.previous.get(feed)
        self.previous[feed] = (req, data)
        if prev is None:
            return
        prev_req, prev_data = prev
        if spans_gap(self.missing.get(feed, []), prev_req.tick, req.tick):
            # Not compared; and no interval may span the gap, so the next change starts afresh.
            st["excluded"] += 1
            self.last_change[feed] = None
            return
        st["compared"] += 1
        if data == prev_data:
            return
        st["changes"] += 1
        last = self.last_change.get(feed)
        interval = None
        if last is not None:
            interval = (req.requested_at - last.requested_at).total_seconds()
            self.intervals[feed].append(interval)
        self.rows.append((feed, iso(req.requested_at), iso(last.requested_at) if last else "", fmt(interval)))
        self.last_change[feed] = req

    def render(self):
        """Summary section for 3a."""
        rows = []
        for feed in feed_order(self.cfg):
            st = self.stats[feed]
            rows.append([f"`{feed}`", st["responses"], st["compared"], st["excluded"], st["changes"],
                         pct(st["changes"], st["compared"]), len(self.intervals[feed])]
                        + distribution(self.intervals[feed]))
        return ("### 3a. Content change rate\n\n"
                f"One row per change in `content_changes.csv` ({len(self.rows)} rows). Intervals in seconds, "
                "by request time, between consecutive changes with no gap between them.\n\n"
                + md_table(["Feed", "Responses", "Pairs compared", "Pairs excluded (gap)", "Changes",
                            "% changed", "Intervals counted", "Interval median", "p95", "max"], rows))


def station_counts(station):
    """3b "counts": every numeric field of a station except last_reported.

    List items are identified by vehicle_type_id / vehicle_type_ids, not by position.
    """
    out = {}

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                if not path and key == "last_reported":
                    continue
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                label = str(i)
                if isinstance(item, dict) and "vehicle_type_id" in item:
                    label = f"vehicle_type_id={item['vehicle_type_id']}"
                elif isinstance(item, dict) and isinstance(item.get("vehicle_type_ids"), list):
                    label = "vehicle_type_ids=" + ",".join(sorted(str(v) for v in item["vehicle_type_ids"]))
                walk(item, f"{path}[{label}]")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            out[path] = node

    walk(station, "")
    return out


def station_sort_key(station_id):
    """Numeric station IDs in numeric order, others after them as text."""
    text = str(station_id)
    return (not text.isdigit(), int(text) if text.isdigit() else 0, text)


class StationReporting(Analyser):
    """3b. Time between consecutive distinct last_reported values per station."""

    feeds = {"station_status"}

    def __init__(self, cfg):
        self.cfg = cfg
        self.prev = None                 # (tick, {station_id: (last_reported, counts)})
        self.items = self.stamped = self.unparseable = 0
        self.pairs = Counter()
        self.station_pairs = self.station_skipped = self.negative = 0
        self.stations = set()
        self.intervals = defaultdict(list)
        self.heartbeats = Counter()
        self.silent = Counter()

    def observe(self, response):
        """Compare each station with the previous response, if it is exactly 1 tick earlier."""
        kind = self.cfg["timestamp_kind"]
        doc = response.doc
        updated = to_utc(doc.get("last_updated"), kind)
        current = {}
        for station in doc.get("data", {}).get("stations", []):
            self.items += 1
            reported = to_utc(station.get("last_reported"), kind)
            if reported is None:
                self.unparseable += 1
                continue
            if reported == updated:
                self.stamped += 1
            sid = station.get("station_id")
            self.stations.add(sid)
            current[sid] = (reported, station_counts(station))
        tick = response.request.tick
        if self.prev is not None:
            prev_tick, previous = self.prev
            if tick - prev_tick == timedelta(minutes=1):
                self.pairs["compared"] += 1
                self.station_skipped += len(previous.keys() ^ current.keys())
                for sid, (reported, counts) in current.items():
                    old = previous.get(sid)
                    if old is None:
                        continue
                    self.station_pairs += 1
                    moved, changed = reported != old[0], counts != old[1]
                    if moved:
                        interval = (reported - old[0]).total_seconds()
                        self.negative += interval < 0
                        self.intervals[sid].append(interval)
                        if not changed:
                            self.heartbeats[sid] += 1
                    elif changed:
                        self.silent[sid] += 1
            else:
                self.pairs["excluded"] += 1
        self.prev = (tick, current)

    def measurable(self):
        """False when every station item carries the feed time as last_reported."""
        return not (self.items and self.stamped == self.items)

    def rows(self):
        """Rows of station_reporting.csv (empty when 3b is not measurable)."""
        if not self.measurable():
            return []
        return [[sid, len(self.intervals[sid])] + distribution(self.intervals[sid])
                + [self.heartbeats[sid], self.silent[sid]]
                for sid in sorted(self.stations, key=station_sort_key)]

    def render(self):
        """Summary section for 3b."""
        out = ["### 3b. Station reporting interval",
               f"`station_status` station items: {self.items}; with `last_reported` equal to the response's "
               f"`last_updated`: {self.stamped} ({pct(self.stamped, self.items)} %); `last_reported` not "
               f"convertible: {self.unparseable}. Response pairs exactly 1 tick apart: {self.pairs['compared']}; "
               f"pairs excluded (gap): {self.pairs['excluded']}."]
        if not self.measurable():
            out.append("**3b not measurable:** every station item is stamped with the feed time "
                       "(`last_reported` = `last_updated`). `station_reporting.csv` has the header only.")
            return "\n\n".join(out)
        medians = [median(v) for v in self.intervals.values() if v]
        without = sum(1 for sid in self.stations if not self.intervals[sid])
        out.append(f"Station comparisons: {self.station_pairs}; station skipped for a pair (in only one of the "
                   f"two responses): {self.station_skipped}. Negative intervals (`last_reported` going "
                   f"backwards): {self.negative}. One row per station in `station_reporting.csv` "
                   f"({len(self.stations)} stations; {without} with no interval).")
        out.append(md_table(["Across stations, each station's median interval (s)", "median", "p95", "max"],
                            [["Value"] + distribution(medians)]))
        out.append(md_table(["Heartbeats (`last_reported` changed, counts did not)",
                             "Silent changes (counts changed, `last_reported` did not)"],
                            [[sum(self.heartbeats.values()), sum(self.silent.values())]]))
        return "\n\n".join(out)


class LastUpdated(Analyser):
    """3c. Request time minus last_updated per feed; values going backwards; older than ttl."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.lags = defaultdict(list)
        self.ttls = defaultdict(Counter)
        self.previous = {}
        self.backwards = defaultdict(list)
        self.applicable = Counter()
        self.older = Counter()
        self.unparseable = Counter()

    def observe(self, response):
        """Record the lag, the ttl and any backwards step of one response."""
        req, doc = response.request, response.doc
        feed = req.feed
        updated = to_utc(doc.get("last_updated"), self.cfg["timestamp_kind"])
        ttl = doc.get("ttl")
        self.ttls[feed][json.dumps(ttl)] += 1
        if updated is None:
            self.unparseable[feed] += 1
            return
        lag = (req.requested_at - updated).total_seconds()
        self.lags[feed].append(lag)
        prev = self.previous.get(feed)
        if prev is not None and updated < prev[0]:
            self.backwards[feed].append((req, updated, prev[1], prev[0]))
        self.previous[feed] = (updated, req)
        if isinstance(ttl, (int, float)) and not isinstance(ttl, bool) and ttl > 0:
            self.applicable[feed] += 1
            self.older[feed] += lag > ttl

    def declared_ttl(self, feed):
        """Distinct ttl values of a feed with their response counts."""
        return "; ".join(f"{v} ({n})" for v, n in sorted(self.ttls[feed].items()))

    def render(self):
        """Summary section for 3c."""
        rows = []
        for feed in feed_order(self.cfg):
            lags = self.lags[feed]
            older = (f"{self.older[feed]} of {self.applicable[feed]}" if self.applicable[feed]
                     else "n/a (ttl 0)")
            rows.append([f"`{feed}`", len(lags), self.declared_ttl(feed), fmt(min(lags) if lags else None)]
                        + distribution(lags) + [len(self.backwards[feed]), older, self.unparseable[feed]])
        out = ["### 3c. `last_updated` behaviour",
               "Lag = request time (`requested_at_utc`) − `last_updated`, in seconds. Negative = `last_updated` "
               "later than the request time.",
               md_table(["Feed", "Responses", "ttl (responses)", "Lag min", "median", "p95", "max",
                         "Going backwards", "Older than ttl", "`last_updated` not convertible"], rows)]
        examples = [(f"`{feed}`", iso(req.requested_at), iso(value), iso(prev_value), f"`{req.file}`")
                    for feed in feed_order(self.cfg) for req, value, _, prev_value in self.backwards[feed]]
        out.append("Values going backwards:")
        out.append(md_table(["Feed", "Requested at", "`last_updated`", "Previous `last_updated`", "File"],
                            examples) if examples else "None.")
        return "\n\n".join(out)


def render_declared_vs_measured(cfg, content, last_updated):
    """Summary section for 3d."""
    rows = [[f"`{feed}`", last_updated.declared_ttl(feed)] + distribution(content.intervals[feed])
            for feed in feed_order(cfg)]
    return ("### 3d. Declared vs measured\n\nMeasured = the 3a interval between content changes, in seconds.\n\n"
            + md_table(["Feed", "Declared ttl (responses)", "Measured median", "p95", "max"], rows))


# ---------------------------------------------------------------------------
# 5. Reliability: failed requests, latency, stale responses, gaps
# ---------------------------------------------------------------------------

def render_failed_requests(cfg, used):
    """Summary section for 5a."""
    rows = []
    for feed in feed_order(cfg):
        reqs = [r for r in used if r.feed == feed]
        failed = [r for r in reqs if not is_ok(r)]
        errors = Counter(r.error or f"HTTP {r.http_status}" for r in failed)
        rows.append((f"`{feed}`", len(reqs), len(failed), pct(len(failed), len(reqs)),
                     "; ".join(f"{e} ({n})" for e, n in sorted(errors.items())) or "—"))
    total = len(used)
    failed = sum(1 for r in used if not is_ok(r))
    return ("### 5a. Failed requests\n\nAll requests used, off-grid requests included. Failed = HTTP status ≠ 200, "
            "timeout or connection error.\n\n"
            + md_table(["Feed", "Requests", "Failed", "% failed", "Errors (count)"], rows)
            + f"\n\nAll feeds: {failed} of {total} ({pct(failed, total)} %).")


def render_latency(cfg, used):
    """Summary section for 5b."""
    rows, failed_rows = [], []
    for feed in feed_order(cfg):
        reqs = [r for r in used if r.feed == feed]
        ok = [r.elapsed_ms for r in reqs if is_ok(r) and r.elapsed_ms is not None]
        rows.append([f"`{feed}`", len(ok)] + distribution(ok))
        failed_rows += [(f"`{feed}`", iso(r.tick), iso(r.requested_at), r.elapsed_ms, r.error)
                        for r in reqs if not is_ok(r)]
    return ("### 5b. Latency\n\n`elapsed_ms` of successful requests:\n\n"
            + md_table(["Feed", "Successful requests", "Median ms", "p95 ms", "Max ms"], rows)
            + "\n\nFailed requests, with their elapsed time:\n\n"
            + (md_table(["Feed", "Tick", "Requested at", "Elapsed ms", "Error"], failed_rows)
               if failed_rows else "None."))


def render_stale(cfg, used):
    """Summary section for 5c."""
    rows, compared = [], 0
    for feed in feed_order(cfg):
        prev = None
        for req in sorted((r for r in used if r.feed == feed and r.stored), key=lambda r: r.requested_at):
            if req.server_last_updated is None:
                continue
            if prev is not None:
                compared += 1
                if req.server_last_updated < prev.server_last_updated:
                    rows.append((f"`{feed}`", iso(req.requested_at), iso(req.server_last_updated),
                                 iso(prev.server_last_updated), f"`{req.file}`"))
            prev = req
    return ("### 5c. Stale responses\n\nFrom the request log (`server_last_updated`), stored responses of each feed "
            f"ordered by request time; {compared} consecutive pairs compared. Stale responses: {len(rows)}.\n\n"
            + (md_table(["Feed", "Requested at", "`last_updated`", "Previous `last_updated`", "File"], rows)
               if rows else "None (trivially empty result reported as a finding)."))


SLEEP_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4}) (\S+)")


def load_sleep_intervals():
    """5d rule 1: asleep from a Sleep line to the next Wake/DarkWake line; also counts the lines read."""
    intervals, start, counts = [], None, Counter()
    for line in PMSET_FILE.read_text(encoding="utf-8").splitlines():
        match = SLEEP_LINE.match(line)
        if not match:
            continue
        when = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S %z").astimezone(UTC)
        category = match.group(2)
        counts[category] += 1
        if category == "Sleep" and start is None:
            start = when
        elif category in ("Wake", "DarkWake") and start is not None:
            intervals.append((start, when))
            start = None
    if start is not None:
        intervals.append((start, None))
    return intervals, counts


def request_ref(system, req):
    """Short reference of a log line: system, log file and line number."""
    return f"{system} {req.log_file}:{req.line_no}"


def classify_gaps(name, results, sleeps):
    """5d. Classify every missing expected tick of one system and group them into gaps.

    Returns (gap rows, per-tick details). Rules are applied in plan order; systems
    are compared by scheduled tick.
    """
    cfg = SYSTEMS[name]
    other = next(n for n in SYSTEMS if n != name)
    own_by_tick, other_by_tick = defaultdict(list), defaultdict(list)
    for req in results[name]["used"]:
        own_by_tick[req.tick].append(req)
    for req in results[other]["used"]:
        other_by_tick[req.tick].append(req)
    ticks_with_lines = sorted(own_by_tick)

    def asleep(tick):
        return any(start <= tick and (end is None or tick < end) for start, end in sleeps)

    def failure_class(tick):
        # Rules 3 and 4 depend only on the other system's requests on the same tick.
        others = other_by_tick.get(tick, [])
        if others and all(is_ok(r) for r in others):
            return "provider", 3
        return "ours (probable)", 4

    def evidence(tick, own):
        return [(name, r) for r in own] + [(other, r) for r in other_by_tick.get(tick, [])]

    details = {}
    for feed, ticks in missing_ticks_by_feed(cfg, results[name]["used"]).items():
        for tick in ticks:
            note = ""
            failed = [r for r in own_by_tick.get(tick, []) if r.feed == feed and not is_ok(r)]
            if asleep(tick):
                cls, rule, lines = "ours", 1, []
            elif failed:
                (cls, rule), lines = failure_class(tick), evidence(tick, failed)
            elif not own_by_tick.get(tick):
                i = bisect.bisect_left(ticks_with_lines, tick) - 1
                prev = ticks_with_lines[i] if i >= 0 else None
                ends = [r.requested_at + timedelta(milliseconds=r.elapsed_ms or 0)
                        for r in own_by_tick.get(prev, [])]
                if prev is not None and max(ends) >= tick:
                    causes = [r for r in own_by_tick[prev] if not is_ok(r)]
                    classes = {failure_class(prev)[0] for _ in causes}
                    cls = classes.pop() if len(classes) == 1 else "blocked"
                    rule, lines = 2, evidence(prev, causes)
                    note = (f"previous tick with log lines {iso(prev)}; its last request ended {iso(max(ends))}; "
                            f"failed requests on it: {len(causes)}")
                    if cls == "blocked":
                        note += " (no single class to inherit)"
                else:
                    cls, rule, lines = "ours", 5, []
            else:
                cls, rule, lines = "ours", 5, []
            details[(feed, tick)] = {"feed": feed, "tick": tick, "class": cls, "rule": rule,
                                     "lines": lines, "note": note}

    # One row per run of consecutive expected ticks of the same feed and class.
    gaps = []
    for feed in feed_order(cfg):
        grid = feed_grid(cfg, feed)
        index = {t: i for i, t in enumerate(grid)}
        run = []
        for tick in (t for t in grid if (feed, t) in details):
            d = details[(feed, tick)]
            if run and (index[tick] - index[run[-1]["tick"]] != 1 or d["class"] != run[-1]["class"]):
                gaps.append(run)
                run = []
            run.append(d)
        if run:
            gaps.append(run)
    return gaps, details


def gap_row(run):
    """One gaps.csv row from a run of classified ticks."""
    rules = list(dict.fromkeys(str(d["rule"]) for d in run))
    refs = list(dict.fromkeys(request_ref(s, r) for d in run for s, r in d["lines"]))
    return (run[0]["feed"], iso(run[0]["tick"]), iso(run[-1]["tick"]), len(run), run[0]["class"],
            "; ".join(rules), "; ".join(refs))


GAP_CLASSES = ["ours", "provider", "ours (probable)"]


def render_gaps(name, gaps, sleep_counts, sleeps):
    """Summary section for 5d."""
    cfg = SYSTEMS[name]
    in_window_sleeps = [s for s in sleeps if s[0] <= WINDOW_END + timedelta(minutes=1)
                        and (s[1] is None or s[1] >= WINDOW_START)]
    classes = GAP_CLASSES + sorted({run[0]["class"] for run in gaps} - set(GAP_CLASSES))
    totals = {feed: Counter() for feed in feed_order(cfg)}
    for run in gaps:
        totals[run[0]["feed"]][run[0]["class"]] += len(run)
    rows = [[f"`{feed}`"] + [totals[feed][c] for c in classes] + [sum(totals[feed].values())]
            for feed in feed_order(cfg)]
    rows.append(["All feeds"] + [sum(t[c] for t in totals.values()) for c in classes]
                + [sum(sum(t.values()) for t in totals.values())])
    gap_rows = [(f"`{r[0]}`",) + r[1:] for r in map(gap_row, gaps)]
    return ("### 5d. Gaps\n\n"
            f"pmset excerpt: {sum(sleep_counts.values())} dated lines read, by category: "
            f"{', '.join(f'{k} {v}' for k, v in sorted(sleep_counts.items())) or 'none'}; sleep intervals "
            f"overlapping the window: {len(in_window_sleeps)}. Systems compared by scheduled tick.\n\n"
            "Missing expected ticks per class and feed:\n\n"
            + md_table(["Feed"] + classes + ["Total"], rows)
            + f"\n\nGaps (`gaps.csv`, {len(gaps)} rows):\n\n"
            + (md_table(["Feed", "Start", "End", "Duration (ticks)", "Class", "Rule", "Log lines"], gap_rows)
               if gap_rows else "None."))


def render_gaps_check(gaps, recon):
    """Verification › Reconciliation: ticks inside gaps = ticks without a response."""
    in_gaps = Counter()
    for run in gaps:
        in_gaps[run[0]["feed"]] += len(run)
    rows = []
    for p in recon["per_feed"]:
        without = p["failed"] + p["no_line"]
        rows.append((f"`{p['feed']}`", in_gaps[p["feed"]], without,
                     "yes" if in_gaps[p["feed"]] == without else "**no**"))
    return ("### Ticks inside gaps = ticks without a response (`gaps.csv` check)\n\n"
            + md_table(["Feed", "Ticks inside gaps", "Ticks without a response", "Holds"], rows))


def render_gap_examples(name, results, gaps):
    """Verification › Hand-checkable example for 5d: one gap per class, with its log lines and raw files."""
    used = results[name]["used"]
    out = ["### 5d. One gap per class"]
    classes = GAP_CLASSES + sorted({run[0]["class"] for run in gaps} - set(GAP_CLASSES))
    for cls in classes:
        run = next((r for r in gaps if r[0]["class"] == cls), None)
        if run is None:
            out.append(f"**{cls}:** none, class empty.")
            continue
        row = gap_row(run)
        feed, start, end = run[0]["feed"], run[0]["tick"], run[-1]["tick"]
        stored = sorted((r for r in used if r.feed == feed and r.stored and is_on_grid(SYSTEMS[name], r)),
                        key=lambda r: r.tick)
        before = next((r for r in reversed(stored) if r.tick < start), None)
        after = next((r for r in stored if r.tick > end), None)
        lines = list(dict.fromkeys((s, r) for d in run for s, r in d["lines"]))
        line_rows = [(request_ref(s, r), iso(r.tick), iso(r.requested_at), r.purpose, f"`{r.feed}`",
                      r.http_status, r.elapsed_ms, r.error or "", f"`{r.file}`" if r.file else "")
                     for s, r in lines]
        raw = [f"`{r.file}`" for r in (before, after) if r is not None]
        raw += [f"`{r.file}` ({s})" for s, r in lines if r.file]
        notes = [d["note"] for d in run if d["note"]]
        out.append(f"**{cls}:** `{feed}` {iso(start)} to {iso(end)}, {row[3]} tick(s), rule {row[5]}."
                   + (" " + "; ".join(dict.fromkeys(notes)) + "." if notes else ""))
        out.append(md_table(["Log line", "Tick", "Requested at", "Purpose", "Feed", "HTTP", "Elapsed ms",
                             "Error", "File"], line_rows) if line_rows else "No log lines.")
        out.append(f"Raw files involved ({SYSTEMS[name]['label']} files under `{SYSTEMS[name]['capture_dir'].relative_to(REPO)}/`, "
                   f"the other system's under its own capture folder): last stored `{feed}` before the gap, "
                   "first after it, then the stored files of the log lines: " + ", ".join(raw) + ".")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 7. Volume: size per request, per day, projection
# ---------------------------------------------------------------------------

def median_gz(cfg, used):
    """Per feed, the median bytes_gz of stored responses (7a, input to 7c)."""
    return {feed: median([r.bytes_gz for r in used if r.feed == feed and r.stored and r.bytes_gz is not None])
            for feed in feed_order(cfg)}


def render_size_per_request(cfg, used):
    """Summary section for 7a."""
    rows = []
    for feed in feed_order(cfg):
        stored = [r for r in used if r.feed == feed and r.stored]
        raw = [r.bytes_raw for r in stored if r.bytes_raw is not None]
        gz = [r.bytes_gz for r in stored if r.bytes_gz is not None]
        rows.append((f"`{feed}`", len(stored), fmt(median(raw)), fmt(max(raw) if raw else None),
                     fmt(median(gz)), fmt(max(gz) if gz else None)))
    return ("### 7a. Size per request\n\nStored responses used, in bytes. `bytes_gz` is our own gzip size, "
            "which is what storage would hold.\n\n"
            + md_table(["Feed", "Stored responses", "bytes_raw median", "bytes_raw max", "bytes_gz median",
                        "bytes_gz max"], rows))


def render_size_per_day(cfg, used):
    """Summary section for 7b."""
    day_end = VOLUME_DAY + timedelta(days=1)
    rows, total = [], 0
    for feed in feed_order(cfg):
        reqs = [r for r in used if r.feed == feed and r.stored and VOLUME_DAY <= r.tick < day_end]
        on_grid = [r for r in reqs if is_on_grid(cfg, r)]
        off_grid = [r for r in reqs if not is_on_grid(cfg, r)]
        every = 1 if feed in cfg["dynamic_feeds"] else STATIC_GRID_MINUTES
        expected = len(minute_grid(VOLUME_DAY, day_end - timedelta(minutes=1), every))
        size = sum(r.bytes_gz or 0 for r in reqs)
        total += size
        rows.append((f"`{feed}`", f"{len(on_grid)} of {expected}", len(off_grid),
                     sum(r.bytes_gz or 0 for r in off_grid), size, f"{size / 10**6:.2f}"))
    rows.append(("All feeds", "", "", "", total, f"{total / 10**6:.2f}"))
    return (f"### 7b. Size per day\n\n{VOLUME_DAY:%Y-%m-%d} (UTC, by tick), as measured: sum of `bytes_gz` of "
            "every stored response, off-grid ones included.\n\n"
            + md_table(["Feed", "On-grid stored of expected", "Off-grid stored", "Off-grid bytes_gz",
                        "bytes_gz total", "MB (10^6 bytes)"], rows))


def render_projection(results):
    """Summary section for 7c; needs both systems."""
    if set(results) != set(SYSTEMS):
        return "### 7c. Projection\n\nNot computed: needs both systems (`--system both`)."
    medians = {name: median_gz(SYSTEMS[name], results[name]["used"]) for name in SYSTEMS}

    def per_day(name, poll_minutes, with_fbs):
        cfg = SYSTEMS[name]
        total = 0
        for feed, size in medians[name].items():
            if feed == "free_bike_status" and not with_fbs:
                continue
            per = 24 * 60 // poll_minutes if feed in cfg["dynamic_feeds"] else 24 * 60 // STATIC_GRID_MINUTES
            total += (size or 0) * per
        return total

    rows = []
    for with_fbs, label in ((True, "All feeds as captured"), (False, "Without `free_bike_status` (AMBici)")):
        for poll in (1, SLOW_POLL_MINUTES):
            days = {name: per_day(name, poll, with_fbs) for name in SYSTEMS}
            both = sum(days.values())
            month, year = both * DAYS_PER_MONTH, both * DAYS_PER_YEAR
            rows.append((label, f"{poll} min", *(f"{days[n] / 10**6:.2f}" for n in SYSTEMS),
                         f"{both / 10**6:.2f}", f"{month / GB:.2f}", pct(month, R2_FREE_BYTES),
                         f"{year / GB:.2f}", pct(year, R2_FREE_BYTES)))
    labels = [SYSTEMS[n]["label"] for n in SYSTEMS]
    return ("### 7c. Projection\n\nMedian `bytes_gz` per feed (7a) × expected responses per day: dynamic feeds "
            f"1,440 (1-min) or {24 * 60 // SLOW_POLL_MINUTES} ({SLOW_POLL_MINUTES}-min), static feeds 96. "
            f"Month = {DAYS_PER_MONTH} days, year = {DAYS_PER_YEAR} days, GB = 10^9 bytes. Limit: Cloudflare R2 "
            "free storage, 10 GB per account, both systems added up.\n\n"
            + md_table(["Scenario", "Dynamic polling", *(f"{l} MB/day" for l in labels), "Both MB/day",
                        "Both GB/month", "% of 10 GB", "Both GB/year", "% of 10 GB"], rows))


# ---------------------------------------------------------------------------
# Part 3 helpers
# ---------------------------------------------------------------------------

def tick_index(tick):
    """Minutes from the window start to a tick (the starting offset of 4b)."""
    return int((tick - WINDOW_START).total_seconds()) // 60


def id_value(value):
    """An ID as a JSON value (type and value), compared as in 2c."""
    return (json_type(value), value)


def is_number(value):
    """True for JSON numbers (booleans excluded)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def short(value, limit=80):
    """A JSON value as compact text for summary tables."""
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit - 1] + "…"


def ids_text(ids, limit=20):
    """Up to `limit` ID values as inline code, with the number left out."""
    values = sorted((v for _, v in ids), key=station_sort_key)
    text = ", ".join(f"`{v}`" for v in values[:limit])
    return text + (f" and {len(values) - limit} more" if len(values) > limit else "") if values else "none"


# ---------------------------------------------------------------------------
# 4. Sampling: observed activity, loss by interval, change size
# ---------------------------------------------------------------------------

SAMPLING_INTERVALS = [2, 5, 10, 15]
EXAMPLE_BLOCK_MINUTES, EXAMPLE_INTERVAL = 30, 5


def type_counts(station):
    """vehicle_types_available of a station as {vehicle_type_id: count}."""
    out = {}
    for item in station.get("vehicle_types_available") or []:
        if isinstance(item, dict) and is_number(item.get("count")):
            out[item.get("vehicle_type_id")] = item["count"]
    return out


class Sampling(Analyser):
    """4a–4c. Activity between station_status responses exactly 1 (or N) ticks apart.

    Only the last 15 ticks are kept for the pairs, plus one total per station and
    tick for the 4b hand-checkable example.
    """

    feeds = {"station_status"}

    def __init__(self, cfg):
        self.cfg = cfg
        self.field = cfg["status_fields"]["available"]
        self.snapshots = {}           # tick -> {station_id: (total, {type: count})}, recent ticks only
        self.steps = {}               # tick -> (activity, Counter per type) of the 1-min pair ending there
        self.prev_tick = None
        self.total, self.by_type = 0, Counter()
        self.pairs = Counter()        # 1-min response pairs: compared, excluded (gap)
        self.station_pairs = self.station_skipped = self.type_absent = self.type_steps = 0
        self.sizes = Counter()        # 4c: "1", ">=2"
        self.station_activity = Counter()
        # 4b: interval -> offset -> [activity at N, 1-min activity same spans, per type at N, per type 1-min]
        self.offsets = {n: defaultdict(lambda: [0, 0, Counter(), Counter()]) for n in SAMPLING_INTERVALS}
        self.n_pairs = {n: Counter() for n in SAMPLING_INTERVALS}
        self.columns, self.history, self.files = {}, {}, {}

    def pair_activity(self, before, after, one_minute=False):
        """Sum of |Δ| of the total and per type over stations in both responses."""
        total, types = 0, Counter()
        for sid, (count, kinds) in after.items():
            old = before.get(sid)
            if old is None:
                if one_minute:
                    self.station_skipped += 1
                continue
            delta = abs(count - old[0])
            total += delta
            for kind in kinds.keys() | old[1].keys():
                types[kind] += abs(kinds.get(kind, 0) - old[1].get(kind, 0))
                if one_minute:
                    self.type_steps += 1
                    self.type_absent += kind not in kinds or kind not in old[1]
            if one_minute:
                self.station_pairs += 1
                self.station_activity[sid] += delta
                if delta:
                    self.sizes["1" if delta == 1 else ">=2"] += 1
        if one_minute:
            self.station_skipped += len(before.keys() - after.keys())
        return total, types

    def observe(self, response):
        """Add one response: its 1-min pair and every N-min pair ending at its tick."""
        tick = response.request.tick
        snap = {}
        for station in response.doc.get("data", {}).get("stations", []):
            count = station.get(self.field)
            if is_number(count):
                snap[station.get("station_id")] = (count, type_counts(station))
        self.snapshots[tick] = snap
        self.files[tick] = response.request.file
        row = []
        for sid, (count, _) in snap.items():
            col = self.columns.setdefault(sid, len(self.columns))
            row.extend([None] * (col + 1 - len(row)))
            row[col] = count
        self.history[tick] = row

        prev = self.snapshots.get(tick - timedelta(minutes=1))
        if prev is not None:
            self.pairs["compared"] += 1
            total, types = self.pair_activity(prev, snap, one_minute=True)
            self.steps[tick] = (total, types)
            self.total += total
            self.by_type.update(types)
        elif self.prev_tick is not None:
            self.pairs["excluded"] += 1
        self.prev_tick = tick

        for n in SAMPLING_INTERVALS:
            start = tick - timedelta(minutes=n)
            if tick_index(start) < 0:
                continue
            spans = [tick - timedelta(minutes=i) for i in range(n)]
            if not all(t in self.steps for t in spans):
                # Kept only when every 1-min pair inside the span exists (gap rule).
                self.n_pairs[n]["excluded"] += 1
                continue
            self.n_pairs[n]["kept"] += 1
            total, types = self.pair_activity(self.snapshots[start], snap)
            acc = self.offsets[n][tick_index(start) % n]
            acc[0] += total
            acc[2].update(types)
            for t in spans:
                acc[1] += self.steps[t][0]
                acc[3].update(self.steps[t][1])

        oldest = tick - timedelta(minutes=max(SAMPLING_INTERVALS))
        for store in (self.snapshots, self.steps):
            for t in [t for t in store if t < oldest]:
                del store[t]

    def loss(self, n, kind=None):
        """Mean over starting offsets of 1 − activity at N ÷ 1-min activity over the same spans."""
        values = []
        for at_n, at_1, types_n, types_1 in self.offsets[n].values():
            a, b = (at_n, at_1) if kind is None else (types_n[kind], types_1[kind])
            if b:
                values.append(1 - a / b)
        return (100 * sum(values) / len(values)) if values else None

    def render_activity(self):
        """Summary section for 4a."""
        rows = [(f"Total (`{self.field}`)", self.total)]
        rows += [(f"Type `{k}`", v) for k, v in sorted(self.by_type.items(), key=lambda kv: str(kv[0]))]
        return ("### 4a. Observed activity\n\n"
                f"Sum of |Δ| between `station_status` responses exactly 1 tick apart (lower bound of rentals + "
                f"returns). Response pairs compared: {self.pairs['compared']}; excluded (gap): "
                f"{self.pairs['excluded']}. Station comparisons: {self.station_pairs}; station skipped for a pair "
                f"(in only one of the two responses): {self.station_skipped}. Per-type comparisons: "
                f"{self.type_steps}, of which {self.type_absent} with the type absent on one side (counted as 0).\n\n"
                + md_table(["Measure", "Activity (bikes)"], rows))

    def render_loss(self):
        """Summary section for 4b."""
        kinds = sorted(self.by_type, key=str)
        rows = [["1 min", self.pairs["compared"], self.pairs["excluded"], "", "", "0.00"] + ["0.00"] * len(kinds)]
        for n in SAMPLING_INTERVALS:
            accs = list(self.offsets[n].values())
            mean_n = sum(a[0] for a in accs) / len(accs) if accs else None
            mean_1 = sum(a[1] for a in accs) / len(accs) if accs else None
            loss = self.loss(n)
            rows.append([f"{n} min", self.n_pairs[n]["kept"], self.n_pairs[n]["excluded"],
                         fmt(mean_n, 1), fmt(mean_1, 1), "" if loss is None else f"{loss:.2f}"]
                        + ["" if self.loss(n, k) is None else f"{self.loss(n, k):.2f}" for k in kinds])
        return ("### 4b. Loss by interval\n\n"
                "For each interval N and each of the N starting minutes, pairs exactly N ticks apart; a pair is kept "
                "only when every 1-min pair inside it exists. Loss per offset = 1 − activity at N ÷ 1-min activity "
                "over the same spans; the table shows the mean over the N offsets. Activities are means over "
                "offsets.\n\n"
                + md_table(["Interval", "Pairs kept (all offsets)", "Pairs excluded (gap)", "Activity at N (mean)",
                            "1-min activity, same spans (mean)", "Loss % (total)"]
                           + [f"Loss % type `{k}`" for k in kinds], rows))

    def render_sizes(self):
        """Summary section for 4c."""
        steps = sum(self.sizes.values())
        return ("### 4c. Change size at 1 min\n\n"
                f"Station steps 1 tick apart where the total (`{self.field}`) changed: {steps} of "
                f"{self.station_pairs} station comparisons.\n\n"
                + md_table(["\\|Δ\\|", "Steps", "% of changing steps"],
                           [("1", self.sizes["1"], pct(self.sizes["1"], steps)),
                            ("≥ 2", self.sizes[">=2"], pct(self.sizes[">=2"], steps))]))

    def render_example(self):
        """Verification › Hand-checkable example for 4b: 1-min vs 5-min activity of one station."""
        title = "### 4b. One station, 1-min vs 5-min activity"
        if not self.station_activity:
            return f"{title}\n\nNo station activity found."
        sid, total = max(self.station_activity.items(), key=lambda kv: (kv[1], -self.columns[kv[0]]))
        col = self.columns[sid]

        def value(tick):
            row = self.history.get(tick)
            return row[col] if row is not None and col < len(row) else None

        last = tick_index(WINDOW_END)
        for start in range(0, last - EXAMPLE_BLOCK_MINUTES + 1, EXAMPLE_BLOCK_MINUTES):
            ticks = [WINDOW_START + timedelta(minutes=start + i) for i in range(EXAMPLE_BLOCK_MINUTES + 1)]
            values = [value(t) for t in ticks]
            if any(v is None for v in values):
                continue
            one = sum(abs(values[i + 1] - values[i]) for i in range(EXAMPLE_BLOCK_MINUTES))
            five = sum(abs(values[i + EXAMPLE_INTERVAL] - values[i])
                       for i in range(0, EXAMPLE_BLOCK_MINUTES, EXAMPLE_INTERVAL))
            if five < one:
                break
        else:
            return f"{title}\n\nStation `{sid}`: no complete {EXAMPLE_BLOCK_MINUTES}-min block with a loss."
        rows = []
        for i, (tick, v) in enumerate(zip(ticks, values)):
            sampled = i % EXAMPLE_INTERVAL == 0
            rows.append((iso(tick), f"`{self.files[tick]}`", v, "" if i == 0 else abs(v - values[i - 1]),
                         "yes" if sampled else "",
                         abs(v - values[i - EXAMPLE_INTERVAL]) if sampled and i else ""))
        rows.append(("Sum", "", "", one, "", five))
        return (f"{title}\n\nStation `{sid}` (highest 1-min activity over the window: {total}), first "
                f"{EXAMPLE_BLOCK_MINUTES}-min block from the window start (offset 0) where the 5-min activity is "
                f"lower than the 1-min activity. `{self.field}` per tick:\n\n"
                + md_table(["Tick", "Raw file", "Available", "\\|Δ\\| 1 min", "5-min sample",
                            "\\|Δ\\| 5 min"], rows)
                + f"\n\n1-min activity {one}, 5-min activity {five}, loss {pct(one - five, one)} %.")


# ---------------------------------------------------------------------------
# 6. Identity: station set, information ↔ status match, attributes, ID format
# ---------------------------------------------------------------------------

CHANGE_LIST_LIMIT = 50


def station_attributes(cfg, station):
    """6c attributes of one station_information item, as (comparable, display) per field."""
    name = station.get("name")
    if isinstance(name, list):
        # Localised text: compared as a language → text mapping, so item order does not count.
        name = {i.get("language"): i.get("text") for i in name if isinstance(i, dict)}
    fields = {"name": name, "lat": station.get("lat"), "lon": station.get("lon"),
              "capacity": station.get("capacity", "(absent)")}
    if cfg["docks_capacity"]:
        fields["vehicle_docks_capacity"] = station.get("vehicle_docks_capacity", "(absent)")
    return {k: (comparable(v), v) for k, v in fields.items()}


class Identity(Analyser):
    """6a–6c. Relies on the stream order: every station_information response comes before station_status."""

    feeds = {"station_information", "station_status"}

    def __init__(self, cfg):
        self.cfg = cfg
        self.info = []                 # (requested_at, id set, request) per station_information response
        self.info_times = []
        self.sizes = []
        self.seen = {}                 # id value -> [responses, first, last]
        self.attributes = {}           # id value -> attributes of its previous appearance
        self.changes = []              # 6c rows
        self.joined = self.unjoined = self.mismatched = 0
        self.status_only, self.info_only = Counter(), Counter()
        self.example = self.first = None

    def observe(self, response):
        """station_information: 6a, 6c; station_status: 6b against the latest earlier information."""
        req = response.request
        stations = response.doc.get("data", {}).get("stations", [])
        ids = {id_value(s.get("station_id")) for s in stations}
        if req.feed == "station_information":
            self.info.append((req.requested_at, ids, req, len(stations)))
            self.info_times.append(req.requested_at)
            self.sizes.append(len(ids))
            for sid in ids:
                entry = self.seen.setdefault(sid, [0, req.requested_at, None])
                entry[0] += 1
                entry[2] = req.requested_at
            for station in stations:
                sid = id_value(station.get("station_id"))
                attrs = station_attributes(self.cfg, station)
                old = self.attributes.get(sid)
                if old is not None:
                    for field, (value, shown) in attrs.items():
                        if value != old[field][0]:
                            self.changes.append((sid[1], field, old[field][1], shown, req.requested_at, req.file))
                self.attributes[sid] = attrs
            return
        i = bisect.bisect_left(self.info_times, req.requested_at) - 1
        if i < 0:
            self.unjoined += 1
            return
        self.joined += 1
        info = self.info[i]
        only_status, only_info = ids - info[1], info[1] - ids
        self.status_only.update(only_status)
        self.info_only.update(only_info)
        if self.first is None:
            self.first = (req, info, only_status, only_info, len(stations))
        if only_status or only_info:
            self.mismatched += 1
            if self.example is None:
                self.example = (req, info, only_status, only_info, len(stations))

    def render_station_set(self):
        """Summary section for 6a."""
        n = len(self.info)
        partial = [(f"`{sid[1]}`", e[0], iso(e[1]), iso(e[2]))
                   for sid, e in sorted(self.seen.items(), key=lambda kv: station_sort_key(kv[0][1])) if e[0] < n]
        return ("### 6a. Station set over time\n\n"
                f"{n} `station_information` responses used; stations per response: min "
                f"{min(self.sizes) if self.sizes else ''}, max {max(self.sizes) if self.sizes else ''}; distinct "
                f"station IDs: {len(self.seen)}. Stations not present in every response: {len(partial)}.\n\n"
                + (md_table(["Station", "Responses present", "First seen (UTC)", "Last seen (UTC)"], partial)
                   if partial else "None."))

    def render_match(self):
        """Summary section for 6b."""
        def listing(counter):
            rows = [(f"`{sid[1]}`", n) for sid, n in sorted(counter.items(), key=lambda kv: station_sort_key(kv[0][1]))]
            return md_table(["Station", "Status responses affected"], rows) if rows else "None."
        return ("### 6b. Information ↔ status match\n\n"
                f"Each `station_status` response joined to the latest `station_information` requested before it. "
                f"Status responses joined: {self.joined}; skipped (no earlier information): {self.unjoined}; with "
                f"at least one unmatched ID: {self.mismatched}.\n\n"
                "IDs with status but no information:\n\n" + listing(self.status_only)
                + "\n\nIDs with information but no status:\n\n" + listing(self.info_only))

    def render_attributes(self):
        """Summary section for 6c."""
        by_field = Counter(c[1] for c in self.changes)
        fields = ", ".join(f"`{f}`" for f in station_attributes(self.cfg, {}))
        # Values in full: a truncated list would hide the part that changed.
        rows = [(f"`{c[0]}`", f"`{c[1]}`", short(c[2], 10**6), short(c[3], 10**6), iso(c[4]), f"`{c[5]}`")
                for c in self.changes[:CHANGE_LIST_LIMIT]]
        out = [f"### 6c. Attribute stability\n\nFields compared: {fields}; each station against its own previous "
               f"appearance. Changes: {len(self.changes)}"
               + (" (" + ", ".join(f"`{f}` {n}" for f, n in sorted(by_field.items())) + ")" if by_field else "") + "."]
        if rows:
            if len(self.changes) > CHANGE_LIST_LIMIT:
                out.append(f"First {CHANGE_LIST_LIMIT} changes shown (by request time per station order of the stream).")
            out.append(md_table(["Station", "Field", "Previous", "New", "Requested at", "File"], rows))
        return "\n\n".join(out)

    def render_example(self):
        """Verification › Hand-checkable example for 6b."""
        title = "### 6b. One `station_status` response and its `station_information`"
        chosen, label = (self.example, "first status response with an unmatched ID") if self.example else (
            self.first, "no status response has an unmatched ID; first status response in the window")
        if chosen is None:
            return f"{title}\n\nNo status response was joined."
        req, info, only_status, only_info, n_status = chosen
        return (f"{title}\n\nChosen: {label}.\n\n"
                + md_table(["Role", "Raw file", "Requested at", "Stations"],
                           [("`station_status`", f"`{req.file}`", iso(req.requested_at), n_status),
                            ("`station_information` (latest before it)", f"`{info[2].file}`",
                             iso(info[0]), info[3])])
                + f"\n\nIDs with status but no information: {ids_text(only_status)}. "
                f"IDs with information but no status: {ids_text(only_info)}.")


UUID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def render_id_format(ids):
    """Summary section for 6d, over the same full ID set as 2c."""
    values = ids.values["station_id"]
    kinds, lengths = Counter(), []
    for vtype, value in values:
        if vtype == "integer" or (vtype == "string" and value.isdigit()):
            kinds["numeric"] += 1
            lengths.append(len(str(value)))
        elif vtype == "string" and UUID_PATTERN.match(value):
            kinds["UUID"] += 1
        else:
            kinds["other"] += 1
    types = ", ".join(f"{t} {n}" for t, n in sorted(Counter(t for t, _ in values).items()))
    length = f" (digits: {min(lengths)}–{max(lengths)})" if lengths else ""
    return (f"### 6d. ID format\n\n`station_id`, {len(values)} distinct values (2c set); JSON type: {types}; "
            f"numeric {kinds['numeric']}{length}, UUID {kinds['UUID']}, other {kinds['other']}.")


# ---------------------------------------------------------------------------
# 8. Quality
# ---------------------------------------------------------------------------

STALE_SECONDS, FUTURE_TOLERANCE_SECONDS = 24 * 3600, 60
AREA = {"lat": (41.20, 41.60), "lon": (1.85, 2.35)}
QUALITY_HEADER = ["check", "variant", "feed", "case_id", "detail", "responses_affected", "first_seen_utc",
                  "last_seen_utc", "first_example_file"]
QUALITY_FLAGS = ["is_installed", "is_renting", "is_returning"]

# Planned variants per check: (variant, feed, label). Variants found but not listed (8b) are added.
QUALITY_VARIANTS = {
    "8a": [("i", "station_status", "(i) available + docks available > capacity"),
           ("ii", "station_status", "(ii) (i) + disabled + docks disabled > capacity"),
           ("capacity_vs_docks", "station_information", "`capacity` ≠ `count` of the single `vehicle_docks_capacity` group"),
           ("docks_groups", "station_information", "`vehicle_docks_capacity` without exactly one group")],
    "8b": [],
    "8c": [("mismatch", "station_status", "Sum of type counts ≠ total available"),
           ("empty_total_0", "station_status", "Counted apart: types empty or missing, total = 0"),
           ("empty_total_gt0", "station_status", "Counted apart: types empty or missing, total > 0")],
    "8d": [("stale", "station_status", "`is_installed` true and `last_reported` older than 24 h")],
    "8e": [("future", "station_status", "`last_reported` later than request time + 60 s")],
    "8f": [(f, "station_status", f"`{f}` false") for f in QUALITY_FLAGS],
    "8g": [("duplicate", "station_status", "Same `station_id` twice in one response"),
           ("duplicate", "station_information", "Same `station_id` twice in one response")],
    "8h": [("out_of_area", "station_information", "Coordinates outside lat 41.20–41.60, lon 1.85–2.35")],
    "8i": [("timezone", "system_information", "`timezone` is `Europe/Berlin`"),
           ("combined", "free_bike_status", "No `current_fuel_percent` and `current_range_meters` = 0"),
           ("fuel_and_range_missing", "free_bike_status",
            "Breakdown: no `current_fuel_percent` and no `current_range_meters`"),
           ("fuel_missing_range_gt0", "free_bike_status",
            "Breakdown: no `current_fuel_percent` and `current_range_meters` > 0"),
           ("range_zero_only", "free_bike_status", "Breakdown: `current_range_meters` = 0, fuel present")],
    "8j": [("renting_false_avail_0", "station_status", "`is_renting` false, total available = 0"),
           ("renting_false_avail_gt0", "station_status", "`is_renting` false, total available > 0"),
           ("returning_false_docks_0", "station_status", "`is_returning` false, `num_docks_available` = 0"),
           ("returning_false_docks_gt0", "station_status", "`is_returning` false, `num_docks_available` > 0"),
           ("avail_0_renting_true", "station_status", "Total available = 0 and `is_renting` true")],
}
QUALITY_TITLES = {"8a": "Over capacity", "8b": "Negative counts", "8c": "Type breakdown mismatch",
                  "8d": "Stale station", "8e": "Future timestamp", "8f": "Inactive stations",
                  "8g": "Duplicate ID", "8h": "Out of area", "8i": "Known issues",
                  "8j": "Inactive flags vs availability (added after first look)"}


class Quality(Analyser):
    """8a–8j. Relies on the stream order: station_information comes before station_status (8a as-of join)."""

    feeds = {"station_status", "station_information", "system_information", "free_bike_status"}

    def __init__(self, cfg):
        self.cfg = cfg
        self.fields = cfg["status_fields"]
        self.cases = {}                        # (check, variant, feed, case_id) -> case
        self.occurrences = Counter()           # (check, variant, feed) -> occurrences
        self.affected = defaultdict(set)       # (check, variant, feed) -> files of responses affected
        self.items, self.responses = Counter(), Counter()
        self.ids = defaultdict(set)
        self.capacity, self.capacity_times = [], []
        self.unmatched = self.unjoined = 0
        self.any_flag = [0, set(), set()]      # 8f any flag false: occurrences, stations, responses

    def add(self, check, variant, req, case_id, detail):
        """Record one occurrence of a case in one response."""
        key = (check, variant, req.feed)
        self.occurrences[key] += 1
        self.affected[key].add(req.file)
        case = self.cases.get(key + (case_id,))
        if case is None:
            case = self.cases[key + (case_id,)] = {"detail": detail, "responses": 0, "first": req.requested_at,
                                                    "last": None, "file": req.file, "last_file": None}
        if case["last_file"] != req.file:
            case["responses"] += 1
            case["last_file"] = req.file
            case["last"] = req.requested_at

    def duplicates(self, req, items, key):
        """8g: IDs found more than once in one response."""
        for value, n in Counter(id_value(i.get(key)) for i in items).items():
            if n > 1:
                self.add("8g", "duplicate", req, str(value[1]), f"{key}={value[1]} appears {n} times")

    def observe(self, response):
        """Run the checks that apply to the response's feed."""
        req, doc = response.request, response.doc
        feed = req.feed
        data = doc.get("data", {}) if isinstance(doc, dict) else {}
        self.responses[feed] += 1
        if feed == "station_information":
            self.information(req, data.get("stations", []))
        elif feed == "station_status":
            self.status(req, data.get("stations", []))
        elif feed == "system_information" and self.cfg["known_issues"]:
            self.items[feed] += 1
            if data.get("timezone") == "Europe/Berlin":
                self.add("8i", "timezone", req, "(response)", "timezone=Europe/Berlin")
        elif feed == "free_bike_status" and self.cfg["known_issues"]:
            for bike in data.get("bikes", []):
                bid = bike.get("bike_id")
                self.items[feed] += 1
                self.ids[feed].add(id_value(bid))
                # "No value" = absent or null, for both fields.
                fuel, rng = bike.get("current_fuel_percent"), bike.get("current_range_meters")
                zero_range = is_number(rng) and rng == 0
                if fuel is None:
                    variant = ("combined" if zero_range else "fuel_and_range_missing" if rng is None
                               else "fuel_missing_range_gt0" if is_number(rng) and rng > 0 else None)
                else:
                    variant = "range_zero_only" if zero_range else None
                if variant:
                    self.add("8i", variant, req, str(bid),
                             f"current_fuel_percent={short(bike.get('current_fuel_percent', '(absent)'))}; "
                             f"current_range_meters={short(bike.get('current_range_meters', '(absent)'))}")

    def information(self, req, stations):
        """8a capacity snapshot (and Bicing capacity vs docks), 8g, 8h."""
        feed = req.feed
        capacity = {}
        for st in stations:
            sid = st.get("station_id")
            self.items[feed] += 1
            self.ids[feed].add(id_value(sid))
            capacity[id_value(sid)] = st.get("capacity")
            if self.cfg["docks_capacity"]:
                groups = st.get("vehicle_docks_capacity")
                if not isinstance(groups, list) or len(groups) != 1:
                    self.add("8a", "docks_groups", req, str(sid),
                             f"vehicle_docks_capacity={short(groups)}")
                elif groups[0].get("count") != st.get("capacity"):
                    self.add("8a", "capacity_vs_docks", req, str(sid),
                             f"capacity={st.get('capacity')}; count={groups[0].get('count')}")
            lat, lon = st.get("lat"), st.get("lon")
            if not (is_number(lat) and is_number(lon) and AREA["lat"][0] <= lat <= AREA["lat"][1]
                    and AREA["lon"][0] <= lon <= AREA["lon"][1]):
                self.add("8h", "out_of_area", req, str(sid), f"lat={lat}; lon={lon}")
        self.duplicates(req, stations, "station_id")
        self.capacity.append(capacity)
        self.capacity_times.append(req.requested_at)

    def status(self, req, stations):
        """8a (as-of join), 8b–8g and 8j on one station_status response."""
        feed, f = req.feed, self.fields
        kind = self.cfg["timestamp_kind"]
        i = bisect.bisect_left(self.capacity_times, req.requested_at) - 1
        capacity = self.capacity[i] if i >= 0 else None
        if capacity is None:
            self.unjoined += 1
        for st in stations:
            sid = st.get("station_id")
            self.items[feed] += 1
            self.ids[feed].add(id_value(sid))
            avail, docks = st.get(f["available"]), st.get(f["docks"])

            if capacity is not None:
                cap = capacity.get(id_value(sid))
                if not is_number(cap):
                    self.unmatched += 1
                elif is_number(avail) and is_number(docks):
                    if avail + docks > cap:
                        self.add("8a", "i", req, str(sid), f"{f['available']}={avail}; {f['docks']}={docks}; capacity={cap}")
                    if f["vehicles_disabled"]:
                        dis, ddis = st.get(f["vehicles_disabled"]), st.get(f["docks_disabled"])
                        if is_number(dis) and is_number(ddis) and avail + docks + dis + ddis > cap:
                            self.add("8a", "ii", req, str(sid),
                                     f"{f['available']}={avail}; {f['docks']}={docks}; {f['vehicles_disabled']}={dis}; "
                                     f"{f['docks_disabled']}={ddis}; capacity={cap}")

            for path, value in station_counts(st).items():
                if value < 0:
                    self.add("8b", path, req, str(sid), f"{path}={value}")

            types = st.get("vehicle_types_available")
            if not isinstance(types, list) or not types:
                variant = "empty_total_0" if avail == 0 else "empty_total_gt0"
                self.add("8c", variant, req, str(sid), f"vehicle_types_available={short(types)}; {f['available']}={avail}")
            else:
                total = sum(t.get("count", 0) for t in types if isinstance(t, dict) and is_number(t.get("count")))
                if total != avail:
                    self.add("8c", "mismatch", req, str(sid), f"sum of type counts={total}; {f['available']}={avail}")

            reported = to_utc(st.get("last_reported"), kind)
            if reported is not None:
                age = (req.requested_at - reported).total_seconds()
                if st.get("is_installed") is True and age > STALE_SECONDS:
                    self.add("8d", "stale", req, str(sid), f"last_reported={iso(reported)}; age_s={fmt(age)}")
                if -age > FUTURE_TOLERANCE_SECONDS:
                    self.add("8e", "future", req, str(sid),
                             f"last_reported={iso(reported)}; requested_at={iso(req.requested_at)}")

            false_flags = [flag for flag in QUALITY_FLAGS if st.get(flag) is False]
            for flag in false_flags:
                self.add("8f", flag, req, str(sid), "; ".join(f"{k}={json.dumps(st.get(k))}" for k in QUALITY_FLAGS))
            if false_flags:
                self.any_flag[0] += 1
                self.any_flag[1].add(id_value(sid))
                self.any_flag[2].add(req.file)

            renting, returning = st.get("is_renting"), st.get("is_returning")
            detail = (f"is_renting={json.dumps(renting)}; is_returning={json.dumps(returning)}; "
                      f"{f['available']}={avail}; {f['docks']}={docks}")
            if renting is False and is_number(avail):
                self.add("8j", "renting_false_avail_0" if avail == 0 else "renting_false_avail_gt0", req, str(sid), detail)
            if returning is False and is_number(docks):
                self.add("8j", "returning_false_docks_0" if docks == 0 else "returning_false_docks_gt0", req, str(sid), detail)
            if renting is True and is_number(avail) and avail == 0:
                self.add("8j", "avail_0_renting_true", req, str(sid), detail)
        self.duplicates(req, stations, "station_id")

    def rows(self, checks):
        """quality_cases.csv rows of the checks given."""
        out = []
        for (check, variant, feed, case_id), c in self.cases.items():
            if check in checks:
                out.append([check, variant, feed, case_id, c["detail"], c["responses"], iso(c["first"]),
                            iso(c["last"]), c["file"]])
        return sorted(out, key=lambda r: (METRICS.index(r[0]), r[1], r[2], station_sort_key(r[3])))

    def figures(self, label, feed, occurrences, distinct, responses, per_response=False):
        """One summary row: occurrences, distinct cases and responses affected, each with its %."""
        unit_items = "" if per_response else pct(occurrences, self.items[feed])
        unit_distinct = "" if per_response else pct(distinct, len(self.ids[feed]))
        return (label, f"`{feed}`", occurrences, unit_items, "" if per_response else distinct, unit_distinct,
                responses, pct(responses, self.responses[feed]))

    def render(self, check):
        """Summary section for one check."""
        out = [f"### {check}. {QUALITY_TITLES[check]}"]
        notes = []
        variants = list(QUALITY_VARIANTS[check])
        if check == "8a":
            if not self.fields["vehicles_disabled"]:
                variants = [v for v in variants if v[0] != "ii"]
                notes.append("(ii): n/a, no disabled counts published.")
            if not self.cfg["docks_capacity"]:
                variants = [v for v in variants if v[1] != "station_information"]
            notes.append(f"As-of join with the latest `station_information` before each status response; status "
                         f"responses with no earlier information: {self.unjoined}; station items with no capacity "
                         f"in the joined information (skipped): {self.unmatched}.")
        if check == "8i" and not self.cfg["known_issues"]:
            return f"{out[0]}\n\nNone listed in the plan for {self.cfg['label']}."
        listed = {(v, f) for v, f, _ in variants}
        variants += [(v, f, f"`{v}` < 0") for c, v, f in sorted(self.occurrences) if c == check and (v, f) not in listed]
        rows = []
        for variant, feed, label in variants:
            key = (check, variant, feed)
            distinct = sum(1 for k in self.cases if k[:3] == key)
            rows.append(self.figures(label, feed, self.occurrences[key], distinct, len(self.affected[key]),
                                     per_response=variant == "timezone"))
        if check == "8f":
            occ, stations, responses = self.any_flag
            rows.append(self.figures("Any of the three false", "station_status", occ, len(stations), len(responses)))
        if check == "8i":
            notes.append("The breakdown rows are exclusive of the combined row and of each other. "
                         "\"No\" value = field absent or null.")
        if check == "8j":
            notes.append(f"Total available = `{self.fields['available']}`. Counted over station items; "
                         "a station item can count in more than one row.")
        if not rows:
            out.append("None found (station items checked: "
                       f"{self.items['station_status']}, all count fields ≥ 0).")
        else:
            out.append(md_table(["Variant", "Feed", "Occurrences", "% of items", "Distinct stations/bikes",
                                 "% of distinct", "Responses affected", "% of responses"], rows))
        out += notes
        return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 9. free_bike_status (AMBici only)
# ---------------------------------------------------------------------------

class FreeBikes(Analyser):
    """9b–9c. Relies on the stream order: free_bike_status comes before station_status."""

    feeds = {"free_bike_status", "station_status"}

    def __init__(self, cfg):
        self.cfg = cfg
        self.shares = []                      # 9b: % of bikes with no station_id per response
        self.bikes = self.no_station = 0
        self.by_tick = {}                     # tick -> (last_updated, Counter of available bikes per station)
        self.groups = {True: Counter(), False: Counter()}   # same last_updated -> pairs, stations, mismatches
        self.status_unpaired = 0
        self.orphans = [0, set()]             # available bikes at stations not in station_status; stations

    def observe(self, response):
        """free_bike_status: 9b and the per-station counts; station_status: 9c comparison for the same tick."""
        req, doc = response.request, response.doc
        data = doc.get("data", {})
        if req.feed == "free_bike_status":
            bikes = data.get("bikes", [])
            missing = sum(1 for b in bikes if b.get("station_id") in (None, ""))
            self.bikes += len(bikes)
            self.no_station += missing
            if bikes:
                self.shares.append(100 * missing / len(bikes))
            counts = Counter(id_value(b["station_id"]) for b in bikes
                             if b.get("station_id") not in (None, "")
                             and b.get("is_reserved") is not True and b.get("is_disabled") is not True)
            self.by_tick[req.tick] = (doc.get("last_updated"), counts)
            return
        bikes = self.by_tick.pop(req.tick, None)
        if bikes is None:
            self.status_unpaired += 1
            return
        updated, counts = bikes
        group = self.groups[updated == doc.get("last_updated")]
        group["pairs"] += 1
        sids = set()
        for st in data.get("stations", []):
            sid = id_value(st.get("station_id"))
            sids.add(sid)
            group["stations"] += 1
            group["mismatches"] += counts.get(sid, 0) != st.get("num_bikes_available")
        for sid, n in counts.items():
            if sid not in sids:
                self.orphans[0] += n
                self.orphans[1].add(sid)

    def render_outside(self):
        """Summary section for 9b."""
        shares = self.shares
        return ("### 9b. Bikes outside stations\n\n"
                f"Bikes with no `station_id` (absent, null or empty): {self.no_station} of {self.bikes} bike items "
                f"({pct(self.no_station, self.bikes)} %). Per response ({len(shares)} responses), % of bikes: min "
                f"{fmt(min(shares) if shares else None)}, median {fmt(median(shares))}, max "
                f"{fmt(max(shares) if shares else None)}.")

    def render_consistency(self):
        """Summary section for 9c."""
        rows = []
        for label, keys in (("Same `last_updated`", [True]), ("Different `last_updated`", [False]),
                            ("All", [True, False])):
            pairs = sum(self.groups[k]["pairs"] for k in keys)
            stations = sum(self.groups[k]["stations"] for k in keys)
            mism = sum(self.groups[k]["mismatches"] for k in keys)
            rows.append((label, pairs, stations, mism, pct(mism, stations)))
        return ("### 9c. Consistency\n\n"
                "Per tick, available bikes per station from `free_bike_status` (not `is_reserved`, not "
                "`is_disabled`; a station with no such bike counts 0) vs `num_bikes_available`. Mismatch rate = "
                "mismatched (station, tick) pairs ÷ pairs compared.\n\n"
                + md_table(["Response pairs", "Ticks", "(station, tick) pairs compared", "Mismatches",
                            "Mismatch rate %"], rows)
                + f"\n\nTicks skipped: `station_status` without `free_bike_status` {self.status_unpaired}; "
                f"`free_bike_status` without `station_status` {len(self.by_tick)}. Available bikes at a "
                f"`station_id` not in `station_status`: {self.orphans[0]} (bike-tick occurrences), on "
                f"{len(self.orphans[1])} distinct station IDs.")


def render_extra_fields(profile):
    """Summary section for 9a: free_bike_status field paths with their 1d profile; Chat classifies."""
    rows = [(f"`{r['path']}`", r["types"], r["present_pct"], r["null_pct"], r["min"], r["max"],
             short(r["distinct_values"], 60) if r["distinct_values"] else r["distinct_count"], "")
            for r in profile.rows("free_bike_status")]
    return ("### 9a. Extra fields\n\n`free_bike_status` field paths with their 1d profile. The classification "
            "(equivalent in `station_status` or not) is done by Chat in the AMBici report.\n\n"
            + md_table(["Path", "Types", "% present", "% null", "Min", "Max", "Distinct values or count",
                        "Classification (Chat)"], rows))


def render_fbs_cost(cfg, used):
    """Summary section for 9d, from the 7b day."""
    day_end = VOLUME_DAY + timedelta(days=1)
    day = [r for r in used if r.stored and VOLUME_DAY <= r.tick < day_end]
    total = sum(r.bytes_gz or 0 for r in day)
    fbs = sum(r.bytes_gz or 0 for r in day if r.feed == "free_bike_status")
    return (f"### 9d. Cost\n\n`free_bike_status` on {VOLUME_DAY:%Y-%m-%d} (7b): {fbs} of {total} bytes_gz, "
            f"{pct(fbs, total)} % of AMBici's daily volume.")


# ---------------------------------------------------------------------------
# 10. Languages (AMBici only; exempt from the analysis window)
# ---------------------------------------------------------------------------

ABSENT = object()


def field_paths(doc):
    """Collapsed field paths of a document (keys and list items), as in 1d."""
    paths = set()

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{path}.{key}" if path else key
                paths.add(child)
                walk(value, child)
        elif isinstance(node, list):
            for item in node:
                paths.add(path + "[]")
                walk(item, path + "[]")

    walk(doc, "")
    return paths


def list_id_key(items):
    """The first 3a ID key carried by every item of a list of objects, or None."""
    if not items or not all(isinstance(i, dict) for i in items):
        return None
    return next((k for k in ID_KEYS if all(k in i for i in items)), None)


def value_differences(en, other, path="", key=None):
    """Yield (collapsed path, key, en value, other value) for every differing leaf (3a value rules).

    List items are matched by an ID key when every item carries one, otherwise by position.
    """
    if isinstance(en, dict) and isinstance(other, dict):
        for k in list(en) + [k for k in other if k not in en]:
            child = f"{path}.{k}" if path else k
            if k not in en or k not in other:
                yield child, k, en.get(k, ABSENT), other.get(k, ABSENT)
            else:
                yield from value_differences(en[k], other[k], child, k)
    elif isinstance(en, list) and isinstance(other, list):
        child = path + "[]"
        id_key = list_id_key(en + other)
        if id_key:
            a = {comparable(i[id_key]): i for i in en}
            b = {comparable(i[id_key]): i for i in other}
            pairs = [(a.get(k, ABSENT), b.get(k, ABSENT)) for k in list(a) + [k for k in b if k not in a]]
        else:
            pairs = [(en[i] if i < len(en) else ABSENT, other[i] if i < len(other) else ABSENT)
                     for i in range(max(len(en), len(other)))]
        for x, y in pairs:
            if x is ABSENT or y is ABSENT:
                yield child, key, x, y
            else:
                yield from value_differences(x, y, child, key)
    elif comparable(en) != comparable(other):
        yield path, key, en, other


def classify_language_difference(feed, path, key, en, other, language):
    """10b class of one differing value: translated text, language-dependent by design, or other."""
    if feed == "system_information" and path == "data.language":
        return "language-dependent"
    if not (isinstance(en, str) and isinstance(other, str)):
        return "other"
    if en.startswith(("http://", "https://")) or other.startswith(("http://", "https://")):
        swapped = re.sub(rf"(?<![A-Za-z]){re.escape(language)}(?![A-Za-z])", "en", other)
        return "language-dependent" if swapped == en else "other"
    if key is not None and (str(key) == "id" or str(key).endswith("_id")):
        return "other"
    return "translated text"


def load_json_gz(path):
    """Read one gzip JSON file."""
    with gzip.open(path, "rb") as fh:
        return json.load(fh)


def analyse_languages(cfg):
    """10a and 10b: each language copy against the nearest en observation of the same feed."""
    requests = load_requests(cfg)
    copies = [r for r in requests if r.purpose == "language_copy"]
    en = defaultdict(list)
    for r in requests:
        if r.purpose == "observation" and r.language == cfg["language"] and r.stored:
            en[r.feed].append(r)
    sets = sorted({r.tick for r in copies})
    feeds = [f for f in feed_order(cfg) if any(r.feed == f for r in copies)]
    pairs, structure, values = [], {}, {}
    for tick in sets:
        for feed in feeds:
            own = [r for r in copies if r.tick == tick and r.feed == feed]
            reference = min(r.requested_at for r in own)
            base = min(en[feed], key=lambda r: abs((r.requested_at - reference).total_seconds()))
            base_doc = load_json_gz(cfg["capture_dir"] / base.file)
            base_paths = field_paths(base_doc)
            pairs.append((iso(tick), f"`{feed}`", f"`{base.file}`",
                          fmt((base.requested_at - reference).total_seconds())))
            for copy in sorted(own, key=lambda r: r.language):
                if not copy.stored:
                    structure[(feed, iso(tick), copy.language)] = None
                    continue
                doc = load_json_gz(cfg["capture_dir"] / copy.file)
                paths = field_paths(doc)
                structure[(feed, iso(tick), copy.language)] = (sorted(base_paths - paths), sorted(paths - base_paths))
                if feed not in cfg["static_feeds"]:
                    continue
                for path, key, a, b in value_differences(base_doc, doc):
                    cls = classify_language_difference(feed, path, key, a, b, copy.language)
                    entry = values.setdefault((feed, path, cls), {"n": 0, "langs": set(), "example": None})
                    entry["n"] += 1
                    entry["langs"].add(copy.language)
                    if entry["example"] is None:
                        entry["example"] = (copy.language, a, b)
    return {"sets": sets, "feeds": feeds, "pairs": pairs, "structure": structure, "values": values,
            "copies": len(copies)}


def render_language_structure(cfg, lang):
    """Summary section for 10a."""
    rows, diffs = [], []
    languages = sorted({k[2] for k in lang["structure"]})
    for feed in [f for f in feed_order(cfg) if f not in lang["feeds"]]:
        rows.append([f"`{feed}`", "not copied (language-independent index)"] + [""] * len(languages))
    for feed in lang["feeds"]:
        cells = []
        for language in languages:
            results = [lang["structure"][(feed, iso(t), language)] for t in lang["sets"]]
            if any(r is None for r in results):
                cells.append("copy failed")
                continue
            same = all(not r[0] and not r[1] for r in results)
            cells.append("yes" if same else "**no**")
            for t, r in zip(lang["sets"], results):
                if r[0] or r[1]:
                    diffs.append((f"`{feed}`", iso(t), language, ", ".join(f"`{p}`" for p in r[0]) or "—",
                                  ", ".join(f"`{p}`" for p in r[1]) or "—"))
        rows.append([f"`{feed}`", "same paths as `en`"] + cells)
    out = ["### 10a. Structure",
           f"Copy sets: {', '.join(iso(t) for t in lang['sets'])} ({lang['copies']} copy requests). Each copy is "
           "paired with the `en` observation of the same feed nearest in request time (any `en` response, "
           "window-exempt):",
           md_table(["Copy set", "Feed", "`en` response used", "`en` − copy (s)"], lang["pairs"]),
           md_table(["Feed", "Compared"] + [f"`{l}` (both sets)" for l in languages], rows)]
    if diffs:
        out.append(md_table(["Feed", "Copy set", "Language", "Only in `en`", "Only in copy"], diffs))
    return "\n\n".join(out)


def render_language_values(cfg, lang):
    """Summary section for 10b."""
    rows = []
    for (feed, path, cls), e in sorted(lang["values"].items()):
        language, a, b = e["example"]
        shown = lambda v: "(absent)" if v is ABSENT else short(v, 60)
        rows.append((f"`{feed}`", f"`{path}`", cls, e["n"], ", ".join(sorted(e["langs"])),
                     f"en: {shown(a)} / {language}: {shown(b)}"))
    other = sum(e["n"] for (_, _, cls), e in lang["values"].items() if cls == "other")
    static = ", ".join(f"`{f}`" for f in lang["feeds"] if f in cfg["static_feeds"])
    return ("### 10b. Values\n\n"
            f"Static feeds compared: {static}. Differing values, aggregated by feed, path and class "
            f"(occurrences over both copy sets and both languages). \"Other\" occurrences: {other} "
            "(expected empty).\n\n"
            + (md_table(["Feed", "Path", "Class", "Occurrences", "Languages", "Example"], rows)
               if rows else "No differing values."))


# ---------------------------------------------------------------------------
# Verification: reconciliation
# ---------------------------------------------------------------------------

def reconcile(cfg, used, raw_files):
    """Reconcile the log, the raw files and the expected ticks over the responses used."""
    feeds = cfg["dynamic_feeds"] + cfg["static_feeds"]
    grids = {
        "dynamic": minute_grid(WINDOW_START, WINDOW_END),
        "static": minute_grid(WINDOW_START, WINDOW_END, STATIC_GRID_MINUTES),
    }

    # Requests in the log = stored responses + failed requests.
    stored_on_disk = {f for f, t in raw_files.items() if in_window(t)}
    stored_in_log = {r.file for r in used if r.stored}
    failed = [r for r in used if not r.stored]
    files = {
        "log_lines": len(used),
        "stored_on_disk": len(stored_on_disk),
        "failed": len(failed),
        "in_log_missing_on_disk": sorted(stored_in_log - stored_on_disk),
        "on_disk_not_in_log": sorted(stored_on_disk - stored_in_log),
    }

    # Per feed: expected ticks = ticks with a response + ticks without one.
    per_feed = []
    for feed in feeds:
        grid = grids["dynamic" if feed in cfg["dynamic_feeds"] else "static"]
        on_grid = [r for r in used if r.feed == feed and is_on_grid(cfg, r)]
        with_response = {r.tick for r in on_grid if r.stored}
        failed_ticks = {r.tick for r in on_grid if not r.stored} - with_response
        logged = {r.tick for r in on_grid}
        no_line = [t for t in grid if t not in logged]
        off_grid = [r for r in used if r.feed == feed and not is_on_grid(cfg, r)]
        duplicates = sum(n - 1 for n in Counter(r.tick for r in on_grid if r.stored).values() if n > 1)
        per_feed.append({
            "feed": feed, "expected": len(grid), "with_response": len(with_response & set(grid)),
            "failed": len(failed_ticks & set(grid)), "no_line": len(no_line),
            "off_grid": len(off_grid), "duplicates": duplicates,
        })

    all_ticks = {r.tick for r in used}
    missing_ticks = [t for t in grids["dynamic"] if t not in all_ticks]
    return {"files": files, "per_feed": per_feed, "ticks_in_window": len(grids["dynamic"]),
            "failed_requests": failed, "missing_ticks": missing_ticks}


def render_reconciliation(name, recon, load_errors, all_recons):
    """Summary section for Verification › Reconciliation, split around the gaps.csv check.

    Returns (text before the check, text after it); the check itself is the 5d.check block.
    """
    f = recon["files"]
    ok = (f["log_lines"] == f["stored_on_disk"] + f["failed"]
          and not f["in_log_missing_on_disk"] and not f["on_disk_not_in_log"])
    out = ["## Verification › Reconciliation",
           "Over the responses used. Any mismatch is reported, not corrected.",
           "### Requests in the log = stored responses + failed requests",
           md_table(["Requests in the log", "Stored responses (raw files on disk)", "Failed requests", "Holds"],
                    [(f["log_lines"], f["stored_on_disk"], f["failed"], "yes" if ok else "**no**")]),
           f"Stored responses counted from the raw files on disk whose file-name time is in the window. "
           f"Logged as stored but missing on disk: {len(f['in_log_missing_on_disk'])}"
           + (f" ({', '.join(f['in_log_missing_on_disk'][:5])})" if f["in_log_missing_on_disk"] else "")
           + f". On disk but not in the log: {len(f['on_disk_not_in_log'])}"
           + (f" ({', '.join(f['on_disk_not_in_log'][:5])})" if f["on_disk_not_in_log"] else "")
           + f". Stored responses that could not be read or parsed: {len(load_errors)}"
           + (f" ({'; '.join(f'{p}: {e}' for p, e in load_errors[:5])})" if load_errors else "") + "."]

    rows = []
    for p in recon["per_feed"]:
        holds = p["expected"] == p["with_response"] + p["failed"] + p["no_line"]
        rows.append((f"`{p['feed']}`", p["expected"], p["with_response"], p["failed"], p["no_line"],
                     "yes" if holds else "**no**", p["off_grid"], p["duplicates"]))
    out += ["### Per feed: expected ticks = ticks with a response + ticks without one",
            "Ticks without a response are split into failed request and no log line. Off-grid responses "
            "(script start, `index_refresh`) are used by the metrics but are never expected ticks.",
            md_table(["Feed", "Expected ticks", "With a response", "Without: failed request",
                      "Without: no log line", "Holds", "Off-grid responses", "Duplicate responses on a tick"], rows)]
    before, out = "\n\n".join(out), []

    failed_rows = [(iso(r.tick), iso(r.requested_at), r.purpose, f"`{r.feed}`", r.http_status, r.elapsed_ms, r.error)
                   for r in recon["failed_requests"]]
    out += ["### Failed requests in the window",
            md_table(["Tick", "Requested at", "Purpose", "Feed", "HTTP status", "Elapsed ms", "Error"], failed_rows)
            if failed_rows else "None."]

    out.append("### Check against the step 1 inventory")
    rows = [("Ticks in the window", INVENTORY["ticks_in_window"], recon["ticks_in_window"]),
            (f"Failed requests in the window ({SYSTEMS[name]['label']})",
             INVENTORY["failed_in_window"][name], len(recon["failed_requests"])),
            (f"Missing ticks: no log line at all ({SYSTEMS[name]['label']})", "—",
             ", ".join(iso(t) for t in recon["missing_ticks"]) or "none")]
    if set(all_recons) == set(SYSTEMS):
        pairs = sum(len(r["missing_ticks"]) for r in all_recons.values())
        minutes = len({t for r in all_recons.values() for t in r["missing_ticks"]})
        rows.append(("Missing ticks, total across both systems", INVENTORY["missing_ticks_total"],
                     f"{pairs} (system, tick) pairs on {minutes} distinct minutes"))
    out.append(md_table(["Item", "Expected (inventory)", "Found"], rows))
    return before, "\n\n".join(out)


# ---------------------------------------------------------------------------
# Run and outputs
# ---------------------------------------------------------------------------

# Streaming analysers and the metrics that need each one (--only builds just these).
ANALYSER_METRICS = {
    "feeds": {"1a", "2c", "2d"}, "versions": {"1b"}, "profile": {"1d", "1e", "2a", "9a"},
    "compliance": {"1f", "2a"}, "ids": {"2c", "2d", "6d"}, "content": {"3a", "3d"},
    "reporting": {"3b"}, "last_updated": {"3c", "3d"},
    "sampling": {"4a", "4b", "4c"}, "identity": {"6a", "6b", "6c"}, "quality": set(QUALITY_CHECKS),
    "free_bikes": {"9b", "9c"},
}


def analyse_system(name, metrics):
    """Load one system, stream its responses through the analysers the metrics need, return the results."""
    cfg = SYSTEMS[name]
    requests = load_requests(cfg)
    used, discarded = split_requests(cfg, requests)
    raw_files = scan_raw_files(cfg)

    commit = schema_commit()
    factories = {
        "feeds": lambda: FeedsPublished(cfg), "versions": lambda: DeclaredVersion(cfg),
        "profile": lambda: FieldProfile(cfg), "compliance": lambda: Compliance(cfg, commit),
        "ids": lambda: IdCollector(cfg), "content": lambda: ContentChanges(cfg, missing_ticks_by_feed(cfg, used)),
        "reporting": lambda: StationReporting(cfg), "last_updated": lambda: LastUpdated(cfg),
        "sampling": lambda: Sampling(cfg), "identity": lambda: Identity(cfg), "quality": lambda: Quality(cfg),
        "free_bikes": lambda: FreeBikes(cfg),
    }
    results = {"cfg": cfg, "used": used, "discarded": discarded, "raw_files": raw_files, "commit": commit,
               "load_errors": []}
    analysers = []
    for key, needed in ANALYSER_METRICS.items():
        if needed & metrics:
            results[key] = factories[key]()
            analysers.append(results[key])
    for response in (stream_responses(cfg, used, results["load_errors"]) if analysers else ()):
        for analyser in analysers:
            if analyser.wants(response.request.feed):
                analyser.observe(response)
    for analyser in analysers:
        analyser.finish()
    if {"10a", "10b"} & metrics:
        results["languages"] = analyse_languages(cfg)
    results["reconciliation"] = reconcile(cfg, used, raw_files)
    return results


def render_header(name, res):
    """Summary header: window, data discarded, configuration and schema commit."""
    cfg = res["cfg"]
    used = res["used"]
    responses = "in-window `en` responses" if cfg["language"] else "all in-window responses"
    discarded_rows = []
    for reason, reqs in sorted(res["discarded"].items()):
        ticks = [r.tick for r in reqs]
        discarded_rows.append((reason, len(reqs), sum(1 for r in reqs if r.stored),
                               sum(r.bytes_gz or 0 for r in reqs), f"{iso(min(ticks))} to {iso(max(ticks))}"))
    on_disk_outside = sum(1 for t in res["raw_files"].values() if not in_window(t))
    ts_fields = "; ".join(f"`{feed}`: " + ", ".join(f"`{p}`" for p in paths)
                          for feed, paths in cfg["timestamp_fields"].items())
    return "\n\n".join([
        f"# {cfg['label']} realtime capture — analysis summary",
        "Evidence for T006, produced by `spikes/realtime-capture-analysis/analyse_realtime_capture.py` "
        "(parts 1–3). Spec: [Analysis plan](../../../docs/spikes/s001-ambici-realtime-capture.md#analysis-plan).",
        "## Analysis window",
        f"{iso(WINDOW_START)} to {iso(WINDOW_END)}, both ticks included. Responses used: {responses} "
        f"({len(used)} log lines, {sum(1 for r in used if r.stored)} stored responses).",
        "## Data discarded",
        md_table(["Reason", "Requests", "Stored responses", "Bytes (gzip)", "Ticks"], discarded_rows)
        if discarded_rows else "None.",
        f"Raw files on disk outside the window: {on_disk_outside}.",
        "## Configuration used",
        md_table(["Item", "Value"], [
            ("Declared GBFS version (configured)", cfg["gbfs_version"]),
            ("Dynamic feeds (1-min grid)", ", ".join(f"`{f}`" for f in cfg["dynamic_feeds"])),
            ("Static feeds (15-min grid)", ", ".join(f"`{f}`" for f in cfg["static_feeds"])),
            ("Timestamp format", "POSIX seconds" if cfg["timestamp_kind"] == "posix" else "RFC 3339"),
            ("Timestamp fields (from the official schemas)", ts_fields),
        ]),
        "## Schema commit",
        f"MobilityData `gbfs-json-schema` commit `{res['commit']}` (from `schemas/SOURCE.md`).",
    ])


# Summary blocks in document order (--only replaces just the blocks run). Each metric owns the
# block with its id; 5d also owns 5d.check and 5d.example, 4b owns 4b.example, 6b owns 6b.example;
# 2a owns no block, only field_comparison.csv.
BLOCK_ORDER = ["5d.check", "4b.example", "5d.example", "6b.example", "1a", "1b", "1d", "1e", "1f", "2c", "2d",
               "3a", "3b", "3c", "3d", "4a", "4b", "4c", "5a", "5b", "5c", "5d", "6a", "6b", "6c", "6d",
               "7a", "7b", "7c"] + QUALITY_CHECKS + ["9a", "9b", "9c", "9d", "10a", "10b"]

# CSV files and the metric that owns each one (written only when that metric runs).
CONTENT_HEADER = ["feed", "requested_at_utc", "previous_change_requested_at_utc", "interval_s"]
REPORTING_HEADER = ["station_id", "intervals", "interval_median_s", "interval_p95_s", "interval_max_s",
                    "heartbeats", "silent_changes"]
GAPS_HEADER = ["feed", "start_utc", "end_utc", "duration_ticks", "class", "rule", "log_lines"]


def wrap_block(block_id, text):
    """Wrap a block's text in the BEGIN/END markers that --only uses to find it."""
    return f"<!-- BEGIN metric:{block_id} -->\n{text}\n<!-- END metric:{block_id} -->"


def metric_blocks(name, res, results, metrics, gaps):
    """Text of every summary block owned by the metrics run, keyed by block id."""
    cfg, used = res["cfg"], res["used"]
    blocks = {}
    if "1a" in metrics:
        blocks["1a"] = res["feeds"].render()
    if "1b" in metrics:
        blocks["1b"] = res["versions"].render()
    if {"1d", "1e"} & metrics:
        # FieldProfile renders 1d and 1e together (part 1 code, unchanged): split at the 1e heading.
        d, e = res["profile"].render().split("\n\n### 1e.", 1)
        blocks.update({"1d": d, "1e": "### 1e." + e})
    if "1f" in metrics:
        blocks["1f"] = res["compliance"].render()
    if {"2c", "2d"} & metrics:
        rest = "### 2c." + render_common_model(name, results).split("\n\n### 2c.", 1)[1]
        c, d = rest.split("\n\n### 2d.", 1)
        blocks.update({"2c": c, "2d": "### 2d." + d})
    if "3a" in metrics:
        blocks["3a"] = res["content"].render()
    if "3b" in metrics:
        blocks["3b"] = res["reporting"].render()
    if "3c" in metrics:
        blocks["3c"] = res["last_updated"].render()
    if "3d" in metrics:
        blocks["3d"] = render_declared_vs_measured(cfg, res["content"], res["last_updated"])
    if "5a" in metrics:
        blocks["5a"] = render_failed_requests(cfg, used)
    if "5b" in metrics:
        blocks["5b"] = render_latency(cfg, used)
    if "5c" in metrics:
        blocks["5c"] = render_stale(cfg, used)
    if "5d" in metrics:
        if gaps is None:
            missing = "Not computed: needs both systems (`--system both`)."
            blocks.update({"5d": f"### 5d. Gaps\n\n{missing}",
                           "5d.check": f"### Ticks inside gaps = ticks without a response (`gaps.csv` check)\n\n{missing}",
                           "5d.example": f"### 5d. One gap per class\n\n{missing}"})
        else:
            sleeps, sleep_counts = gaps["sleep"]
            blocks.update({"5d": render_gaps(name, gaps[name], sleep_counts, sleeps),
                           "5d.check": render_gaps_check(gaps[name], res["reconciliation"]),
                           "5d.example": render_gap_examples(name, results, gaps[name])})
    if "7a" in metrics:
        blocks["7a"] = render_size_per_request(cfg, used)
    if "7b" in metrics:
        blocks["7b"] = render_size_per_day(cfg, used)
    if "7c" in metrics:
        blocks["7c"] = render_projection(results)
    blocks.update(part3_blocks(res, metrics))
    return blocks


def part3_blocks(res, metrics):
    """Summary blocks of questions 4, 6, 8, 9, 10 and the 4b and 6b examples, for the metrics run."""
    cfg, used = res["cfg"], res["used"]
    blocks = {}
    renderers = {
        "4a": lambda: res["sampling"].render_activity(), "4b": lambda: res["sampling"].render_loss(),
        "4b.example": lambda: res["sampling"].render_example(), "4c": lambda: res["sampling"].render_sizes(),
        "6a": lambda: res["identity"].render_station_set(), "6b": lambda: res["identity"].render_match(),
        "6b.example": lambda: res["identity"].render_example(), "6c": lambda: res["identity"].render_attributes(),
        "6d": lambda: render_id_format(res["ids"]),
        "9a": lambda: render_extra_fields(res["profile"]), "9b": lambda: res["free_bikes"].render_outside(),
        "9c": lambda: res["free_bikes"].render_consistency(), "9d": lambda: render_fbs_cost(cfg, used),
        "10a": lambda: render_language_structure(cfg, res["languages"]),
        "10b": lambda: render_language_values(cfg, res["languages"]),
    }
    renderers.update({check: (lambda c=check: res["quality"].render(c)) for check in QUALITY_CHECKS})
    for block_id, render in renderers.items():
        if block_id.split(".")[0] in metrics:
            blocks[block_id] = render()
    return blocks


IMPLEMENTATION_NOTES = """## Implementation notes

- 1d: list-item paths (`…[]`) are not keyed fields, so they have no % present; their % null is over the items.
- 1f: validated with `jsonschema` defaults for draft-07, where `format` is an annotation and is not asserted. 1f violation counts in `field_comparison.csv` match the collapsed instance path literally, so `required` and `additionalProperties` violations count on the parent object's path.
- Median and p95 (all metrics): median as Python `statistics.median` (mean of the two middle values for an even count); p95 by the nearest-rank method.
- 3a: an interval between two changes is not counted when a gap lies between them; the first change after a gap, and the first change of each feed, have no previous change. Lists of objects are compared as a multiset of whole items, so the result does not depend on which ID key is matched first.
- 3b: a station counts in a pair only when it is in both responses. Interval = new `last_reported` − previous `last_reported` (the values, not the request times). Counts = every numeric field of the station except `last_reported`, with list items matched by `vehicle_type_id` / `vehicle_type_ids` rather than by position. "Not measurable" = `last_reported` equals `last_updated` for 100 % of station items.
- 3c: lag = `requested_at_utc` − `last_updated`; "older than ttl" = lag > the `ttl` of the same response; not applicable with `ttl` 0.
- 5a: the denominator is every request used, off-grid ones (Bicing `index_refresh`) included.
- 5d rule 2: the "previous tick" is the latest earlier tick with log lines; it overran when its last request ended (`requested_at_utc` + `elapsed_ms`) at or after the missing tick. The `log lines` column lists the failed requests and the other system's requests on the tick compared.
- 7b: the day is taken by tick (file-name time); off-grid responses are included in the sum and shown separately.
- 7c: month = 30 days, year = 365 days, GB = 10^9 bytes (Cloudflare's own GB definition not checked)."""

# Part 3 readings that change a result (approved at part 3 step 2); the AMBici-only ones go to AMBici.
PART3_NOTES = [
    (None, "4a: a vehicle type absent from `vehicle_types_available` counts as 0 (AMBici omits zero counts)."),
    (None, "4b: an N-minute pair is kept only when every 1-minute pair inside it exists; otherwise it is excluded and counted."),
    (None, "4b: loss per starting offset = 1 − activity at N min ÷ 1-min activity over the same spans; the loss % is the mean over the N offsets."),
    (None, "4c: only steps where the total changed (Δ ≠ 0), total available only."),
    (None, "6b, 8a: as-of join with the latest `station_information` requested strictly before the `station_status` response; status responses with no earlier information are skipped and counted."),
    (None, "6c: each station is compared with its own previous appearance; coordinates exactly; Bicing's localised `name` as a language → text mapping."),
    (None, "8d, 8e: request time = `requested_at_utc`; 8d stale = age > 86,400 s; 8e future = `last_reported` > request time + 60 s."),
    (None, "8h: boundaries count as inside (41.20 ≤ lat ≤ 41.60, 1.85 ≤ lon ≤ 2.35)."),
    ("9", "9b: no station = `station_id` absent, null or an empty string."),
    ("10", "10: each copy is paired with the `en` observation of the same feed nearest in request time, from any `en` response (window-exempt)."),
    ("10", "10b: list items matched by a 3a ID key when every item carries it, otherwise by position; a URL that becomes equal once the language code is swapped for `en` = language-dependent; other differing strings except ID fields (`id`, `*_id`) = translated text; numbers, booleans, ID fields, other URLs and items on one side only = other."),
]


def implementation_notes(cfg):
    """Implementation notes of one system: parts 1–2 plus the part 3 readings that apply to it."""
    lines = [text for question, text in PART3_NOTES if question is None or question in cfg["system_questions"]]
    return IMPLEMENTATION_NOTES + "\n" + "\n".join(f"- {line}" for line in lines)


def render_summary(name, res, results, recons, blocks):
    """Assemble the whole summary.md for one system (full run), with every metric block marked."""
    cfg = res["cfg"]

    def block(block_id):
        return wrap_block(block_id, blocks[block_id])

    before, after = render_reconciliation(name, res["reconciliation"], res["load_errors"], recons)
    parts = [
        render_header(name, res),
        before, block("5d.check"), after,
        "## Verification › Hand-checkable examples\n\nRaw file paths are relative to each system's capture folder.",
        block("4b.example"), block("5d.example"), block("6b.example"),
        "## 1. Schema", block("1a"), block("1b"),
        "### 1c. Versions offered\n\nDesk research by Chat; not computed by the script.",
        block("1d"), block("1e"), block("1f"),
        render_common_model(name, results).split("\n\n### 2c.", 1)[0], block("2c"), block("2d"),
        "## 3. Freshness", block("3a"), block("3b"), block("3c"), block("3d"),
        "## 4. Sampling", block("4a"), block("4b"), block("4c"),
        "## 5. Reliability", block("5a"), block("5b"), block("5c"), block("5d"),
        "## 6. Identity", block("6a"), block("6b"), block("6c"), block("6d"),
        "## 7. Volume", block("7a"), block("7b"), block("7c"),
        "## 8. Quality", *(block(c) for c in QUALITY_CHECKS),
    ]
    if "9" in cfg["system_questions"]:
        parts += ["## 9. `free_bike_status`", block("9a"), block("9b"), block("9c"), block("9d")]
    if "10" in cfg["system_questions"]:
        parts += ["## 10. Languages\n\nExempt from the analysis window: both language-copy sets are used.",
                  block("10a"), block("10b")]
    parts.append(implementation_notes(cfg))
    return "\n\n".join(parts) + "\n"


def update_summary(path, blocks):
    """--only: replace the marked blocks that were run; leave every other byte of summary.md as it is.

    A block not yet in the file is inserted after the nearest preceding block in BLOCK_ORDER.
    """
    text = path.read_text(encoding="utf-8")
    for block_id in BLOCK_ORDER:
        if block_id not in blocks:
            continue
        new = wrap_block(block_id, blocks[block_id])
        tag = re.escape(f"metric:{block_id} -->")
        pattern = re.compile(rf"<!-- BEGIN {tag}\n.*?\n<!-- END {tag}", re.S)
        if pattern.search(text):
            text = pattern.sub(lambda _: new, text, count=1)
            continue
        anchor = next((f"<!-- END metric:{p} -->" for p in reversed(BLOCK_ORDER[:BLOCK_ORDER.index(block_id)])
                       if f"<!-- END metric:{p} -->" in text), None)
        if anchor is None:
            sys.exit(f"{path}: no block to insert {block_id} after; run without --only first")
        i = text.index(anchor) + len(anchor)
        text = text[:i] + "\n\n" + new + text[i:]
    path.write_text(text, encoding="utf-8")


PROFILE_HEADER = ["feed", "path", "parent_path", "parent_occurrences", "occurrences", "types", "present_pct",
                  "null_pct", "min", "max", "timestamp", "timestamp_unparseable", "distinct_count",
                  "distinct_values"]
CHANGES_HEADER = ["feed", "path", "change", "file", "requested_at_utc", "previous_file",
                  "previous_requested_at_utc"]
VIOLATIONS_HEADER = ["feed", "keyword", "schema_path", "instance_path", "message", "occurrences",
                     "responses_affected", "first_example_file", "schema_commit"]


def write_quality_cases(path, checks, rows, full):
    """quality_cases.csv: a full run rewrites it; --only replaces only the rows of the checks run.

    The rows of other checks are kept as they are, and the file stays ordered by check.
    """
    kept = []
    if not full and path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            next(reader, None)
            kept = [row for row in reader if row and row[0] not in checks]
    merged = kept + [[str(v) for v in row] for row in rows]
    merged.sort(key=lambda row: METRICS.index(row[0]))  # stable: order within a check is kept
    write_csv(path, QUALITY_HEADER, merged)


def write_outputs(results, metrics, full):
    """Write the CSV files owned by the metrics run and summary.md (whole, or only the blocks run)."""
    recons = {name: res["reconciliation"] for name, res in results.items()}
    both = set(results) == set(SYSTEMS)
    gaps = None
    if "5d" in metrics and both:
        gaps = {"sleep": load_sleep_intervals()}
        gaps.update({name: classify_gaps(name, results, gaps["sleep"][0])[0] for name in SYSTEMS})
    all_metrics = metrics
    for name, res in results.items():
        metrics = {m for m in all_metrics if applies(name, m)}
        out_dir = res["cfg"]["out_dir"]
        checks = set(QUALITY_CHECKS) & metrics
        if checks:
            write_quality_cases(out_dir / "quality_cases.csv", checks, res["quality"].rows(checks), full)
        if "1d" in metrics:
            profile_rows = [[row[c] for c in PROFILE_HEADER] for row in res["profile"].all_rows()]
            write_csv(out_dir / "field_profile.csv", PROFILE_HEADER, profile_rows)
        if "1e" in metrics:
            write_csv(out_dir / "schema_changes.csv", CHANGES_HEADER, res["profile"].changes)
        if "1f" in metrics:
            write_csv(out_dir / "schema_violations.csv", VIOLATIONS_HEADER, res["compliance"].rows())
        if "3a" in metrics:
            write_csv(out_dir / "content_changes.csv", CONTENT_HEADER, res["content"].rows)
        if "3b" in metrics:
            write_csv(out_dir / "station_reporting.csv", REPORTING_HEADER, res["reporting"].rows())
        if gaps is not None:
            write_csv(out_dir / "gaps.csv", GAPS_HEADER, [gap_row(run) for run in gaps[name]])
        blocks = metric_blocks(name, res, results, metrics, gaps)
        if full:
            (out_dir / "summary.md").write_text(render_summary(name, res, results, recons, blocks),
                                                encoding="utf-8")
        else:
            update_summary(out_dir / "summary.md", blocks)
        print(f"{SYSTEMS[name]['label']}: wrote {out_dir.relative_to(REPO)}")
    if "2a" in all_metrics and both:
        path = SYSTEMS["bicing"]["out_dir"] / "field_comparison.csv"
        write_csv(path, field_comparison_header(), field_comparison_rows(results))
        print(f"wrote {path.relative_to(REPO)}")


def parse_only(parser, args):
    """Validate --only before anything runs; return the set of metric ids to run."""
    if args.only is None:
        return set(METRICS)
    metrics = {m.strip() for m in args.only.split(",") if m.strip()}
    unknown = sorted(metrics - set(METRICS))
    if unknown or not metrics:
        parser.error(f"--only: unknown metric ids {unknown}; implemented: {', '.join(METRICS)}")
    cross = sorted(metrics & CROSS_SYSTEM_METRICS)
    if cross and args.system != "both":
        parser.error(f"--only: {', '.join(cross)} need both systems; use --system both")
    if args.system != "both":
        other = sorted(m for m in metrics if not applies(args.system, m))
        if other:
            parser.error(f"--only: {', '.join(other)} do not apply to {args.system}")
    names = list(SYSTEMS) if args.system == "both" else [args.system]
    for name in names:
        path = SYSTEMS[name]["out_dir"] / "summary.md"
        if not path.exists():
            parser.error(f"--only: {path.relative_to(REPO)} does not exist; run without --only first")
    return metrics


def main():
    """Parse arguments, analyse the requested systems and write the evidence."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--system", choices=["ambici", "bicing", "both"], default="both")
    parser.add_argument("--only", metavar="IDS",
                        help="comma-separated metric ids to run (e.g. 3a,5d); other sections are kept as they are")
    args = parser.parse_args()
    metrics = parse_only(parser, args)
    names = list(SYSTEMS) if args.system == "both" else [args.system]
    results = {}
    for name in names:
        print(f"Analysing {SYSTEMS[name]['label']}...", flush=True)
        results[name] = analyse_system(name, {m for m in metrics if applies(name, m)})
    write_outputs(results, metrics, full=args.only is None)


if __name__ == "__main__":
    main()
