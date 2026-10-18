"""Analysis of the Cloudflare capture spike (step 7.1: completeness and validity).

Reads the local copy of the bucket (``../data/<variant>/...``) and overwrites
``output/report.md`` and ``output/issues.csv`` on every run. Standard library only.
"""

import csv
import gzip
import json
import re
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

VARIANTS = ["V2", "V4"]
DYNAMIC_FEEDS = [
    ("ambici", "station_status"),
    ("ambici", "free_bike_status"),
    ("bicing", "station_status"),
]

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
OUTPUT_DIR = BASE_DIR / "output"

TS_FORMAT = "%Y%m%dT%H%M%SZ"
OBJECT_NAME = re.compile(r"^(\d{8}T\d{6}Z)\.json\.gz$")
OBJECT_TS = re.compile(r"^\d{8}T\d{6}Z$")
LOG_NAME = re.compile(r"^(\d{8}T\d{6}Z)\.jsonl$")
STATIC_MINUTE = 17
LOG_KINDS = [
    "http_error",
    "fetch_error",
    "log_without_object",
    "object_without_log",
    "missing_log",
    "invalid_log",
]
F2_WRITES_PER_VARIANT_DAY = 6144  # F2 reference: 4 per minute + 16 per hour
FREE_CLASS_A_PER_MONTH = 1_000_000
PROJECTION_DAYS = 30


def parse_ts(text):
    """Parse a ``YYYYMMDDTHHMMSSZ`` key timestamp into an aware UTC datetime."""
    return datetime.strptime(text, TS_FORMAT).replace(tzinfo=timezone.utc)


def fmt_ts(moment):
    """Format a datetime as ISO 8601 UTC with minute precision."""
    return moment.strftime("%Y-%m-%dT%H:%MZ")


def floor_minute(moment):
    """Truncate a datetime to its whole minute."""
    return moment.replace(second=0, microsecond=0)


def is_expected_minute(minute):
    """Dynamic feeds are captured every minute except minute 17 of odd UTC hours."""
    return not (minute.minute == STATIC_MINUTE and minute.hour % 2 == 1)


def minutes_between(start, end):
    """Every whole minute from start to end, both inclusive."""
    count = int((end - start).total_seconds() // 60) + 1
    return [start + timedelta(minutes=i) for i in range(count)]


def scan_logs(variant):
    """Return the sorted log timestamps (from file names) of a variant."""
    found = []
    logs_dir = DATA_DIR / variant / "logs"
    if logs_dir.is_dir():
        for path in logs_dir.glob("*/*.jsonl"):
            match = LOG_NAME.match(path.name)
            if match:
                found.append(parse_ts(match.group(1)))
    return sorted(found)


def scan_objects(variant):
    """Yield (source, feed, ts, path) for every raw object; also return ignored names."""
    objects = []
    ignored = []
    raw_dir = DATA_DIR / variant / "raw"
    if raw_dir.is_dir():
        for path in raw_dir.glob("*/*/*/*"):
            if not path.is_file():
                continue
            match = OBJECT_NAME.match(path.name)
            if not match:
                ignored.append(path)
                continue
            source, feed = path.parts[-4], path.parts[-3]
            objects.append((source, feed, parse_ts(match.group(1)), path))
    return objects, ignored


def scan_log_files(variant):
    """Return ([(ts, path)], ignored) for every log file of a variant, ts from the name."""
    found, ignored = [], []
    logs_dir = DATA_DIR / variant / "logs"
    if logs_dir.is_dir():
        for path in logs_dir.glob("*/*"):
            if not path.is_file():
                continue
            match = LOG_NAME.match(path.name)
            if match:
                found.append((match.group(1), path))
            else:
                ignored.append(path)
    return sorted(found, key=lambda item: item[0]), ignored


def parse_log_line(text):
    """Return the parsed log line as a dict, or None if it is not a valid line."""
    try:
        line = json.loads(text)
    except ValueError:
        return None
    if not isinstance(line, dict):
        return None
    if not all(k in line for k in ("ts", "source", "feed", "status", "error")):
        return None
    if not (isinstance(line["ts"], str) and OBJECT_TS.match(line["ts"])):
        return None
    if not (isinstance(line["source"], str) and isinstance(line["feed"], str)):
        return None
    if line["status"] is not None and not isinstance(line["status"], int):
        return None
    return line


def reconcile_logs(variant, window, window_objects, existing_keys):
    """Section (c) for one variant: compare the log lines with the raw objects.

    Logs and objects are matched by (source, feed, UTC minute): passes run at a
    non-zero second. Returns a dict with log file counts, line counts, issues and
    the `state/` write estimate.
    """
    files, ignored = scan_log_files(variant)
    result = {
        "files": 0,
        "lines": 0,
        "kinds": Counter(),
        "outside": Counter(),
        "ignored": len(ignored),
        "issues": [],
        "state_writes": 0,
    }
    seen = set()
    minutes_with_log = set()
    for ts_text, path in files:
        minute = floor_minute(parse_ts(ts_text))
        if minute not in window:
            result["outside"][minute.strftime("%Y-%m-%d")] += 1
            continue
        result["files"] += 1
        minutes_with_log.add(minute)
        rel = path.relative_to(DATA_DIR).as_posix()
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw_line.strip():
                continue
            result["lines"] += 1
            line = parse_log_line(raw_line)
            if line is None:
                result["kinds"]["invalid_log"] += 1
                result["issues"].append((variant, "", "", ts_text, "invalid_log", rel))
                continue
            source, feed, ts, status, error = (
                line["source"], line["feed"], line["ts"], line["status"], line["error"],
            )
            line_minute = floor_minute(parse_ts(ts))
            seen.add((source, feed, line_minute))
            if feed == "gbfs" and status == 200 and error is None:
                result["state_writes"] += 1
            if status not in (None, 200):
                kind, detail = "http_error", str(status)
            elif status is None and error is not None:
                kind, detail = "fetch_error", str(error)
            elif feed != "gbfs" and status == 200 and (source, feed, line_minute) not in existing_keys:
                kind, detail = "log_without_object", ""
            else:
                continue
            result["kinds"][kind] += 1
            result["issues"].append((variant, source, feed, ts, kind, detail))
    for minute in sorted(window - minutes_with_log):
        result["kinds"]["missing_log"] += 1
        result["issues"].append((variant, "", "", minute.strftime(TS_FORMAT), "missing_log", ""))
    for source, feed, ts, minute in window_objects:
        if (source, feed, minute) not in seen:
            result["kinds"]["object_without_log"] += 1
            result["issues"].append(
                (variant, source, feed, ts.strftime(TS_FORMAT), "object_without_log", "")
            )
    return result


def validate(path):
    """Return None if the object is valid gzip + JSON, else (kind, message)."""
    try:
        body = gzip.decompress(path.read_bytes())
    except (OSError, EOFError, zlib.error) as exc:
        return "invalid_gzip", str(exc)
    try:
        json.loads(body)
    except ValueError as exc:
        return "invalid_json", str(exc)
    return None


def analyse(now):
    """Run the whole analysis and return (report_text, issue_rows)."""
    log_ts = {v: scan_logs(v) for v in VARIANTS}
    with_logs = [v for v in VARIANTS if log_ts[v]]
    header = ["# Remote capture analysis", ""]
    if not with_logs:
        header.append(f"Run: {fmt_ts(now)}")
        header += ["", "No logs found in `data/`: nothing to analyse."]
        return "\n".join(header) + "\n", []

    start = max(floor_minute(log_ts[v][0]) for v in with_logs)
    end = max(floor_minute(log_ts[v][-1]) for v in with_logs)
    minutes = minutes_between(start, end) if end >= start else []
    expected_minutes = [m for m in minutes if is_expected_minute(m)]
    expected_set = set(expected_minutes)
    window = set(minutes)

    issues = []
    completeness = {}  # (variant, source, feed) -> dict
    invalid = defaultdict(Counter)  # (variant, source, feed) -> Counter(kind)
    outside = defaultdict(Counter)  # (variant, source, feed) -> Counter(day)
    unexpected = Counter()  # (variant, source, feed) -> dynamic objects off-schedule
    ignored_files = []
    window_objects = {}  # variant -> [(source, feed, ts, minute)] inside the window
    existing_keys = {}  # variant -> {(source, feed, minute)} of every raw object

    for variant in VARIANTS:
        objects, ignored = scan_objects(variant)
        ignored_files += ignored
        window_objects[variant] = []
        existing_keys[variant] = {(s_, f_, floor_minute(t_)) for s_, f_, t_, _ in objects}
        captured = defaultdict(set)  # (source, feed) -> valid minutes
        present = defaultdict(set)  # (source, feed) -> minutes with an object
        for source, feed, ts, path in objects:
            key = (variant, source, feed)
            minute = floor_minute(ts)
            if minute not in window:
                outside[key][minute.strftime("%Y-%m-%d")] += 1
                continue
            window_objects[variant].append((source, feed, ts, minute))
            present[(source, feed)].add(minute)
            problem = validate(path)
            if problem:
                kind, detail = problem
                invalid[key][kind] += 1
                issues.append((variant, source, feed, ts.strftime(TS_FORMAT), kind, detail))
            elif (source, feed) in DYNAMIC_FEEDS and minute not in expected_set:
                unexpected[key] += 1
            else:
                captured[(source, feed)].add(minute)
        for source, feed in DYNAMIC_FEEDS:
            got = captured[(source, feed)]
            missing = [m for m in expected_minutes if m not in present[(source, feed)]]
            for m in missing:
                issues.append((variant, source, feed, m.strftime(TS_FORMAT), "missing", ""))
            completeness[(variant, source, feed)] = {
                "captured": got,
                "missing": missing,
            }

    reconciliation = {}
    for variant in VARIANTS:
        reconciliation[variant] = reconcile_logs(
            variant, window, window_objects[variant], existing_keys[variant]
        )
        issues += reconciliation[variant]["issues"]

    issues.sort()

    lines = header
    lines += [
        f"- Window start: {fmt_ts(start)}",
        f"- Window end: {fmt_ts(end)}",
        f"- Window minutes: {len(minutes)}",
        f"- Expected per dynamic feed: {len(expected_minutes)}",
        f"- Run: {fmt_ts(now)}",
    ]
    for v in VARIANTS:
        if v not in with_logs:
            lines.append(f"- Note: variant {v} has no logs; it is not used to set the window start.")
    lines += ["", "## (a) Completeness", ""]

    days = sorted({m.strftime("%Y-%m-%d") for m in minutes})
    for (variant, source, feed), data in completeness.items():
        lines += [f"### {variant} {source}/{feed}", ""]
        lines += ["| Day (UTC) | Expected | Captured | % |", "|---|---|---|---|"]
        for day in days:
            day_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1) - timedelta(minutes=1)
            partial = start > day_start or end < day_end
            exp = [m for m in expected_minutes if m.strftime("%Y-%m-%d") == day]
            cap = [m for m in exp if m in data["captured"]]
            pct = f"{100 * len(cap) / len(exp):.2f}" if exp else "n/a"
            label = f"{day} (partial)" if partial else day
            lines.append(f"| {label} | {len(exp)} | {len(cap)} | {pct} |")
        total_cap = len([m for m in expected_minutes if m in data["captured"]])
        pct = f"{100 * total_cap / len(expected_minutes):.2f}" if expected_minutes else "n/a"
        lines += [f"| **Window** | {len(expected_minutes)} | {total_cap} | {pct} |", ""]
        by_hour = Counter(m.hour for m in data["missing"])
        lines.append("Missing per UTC hour: " + ", ".join(f"{h:02d}={by_hour[h]}" for h in range(24)))
        extra = unexpected[(variant, source, feed)]
        lines += ["", f"Valid objects at off-schedule minutes (not counted as captured): {extra}", ""]

    lines += ["## (b) Validity and objects outside the window", "", "### Invalid objects", ""]
    if invalid:
        lines += ["| Variant | Feed | Kind | Count |", "|---|---|---|---|"]
        for (variant, source, feed), kinds in sorted(invalid.items()):
            for kind, count in sorted(kinds.items()):
                lines.append(f"| {variant} | {source}/{feed} | {kind} | {count} |")
    else:
        lines.append("None.")
    lines += ["", "### Objects outside the window", ""]
    if outside:
        lines += ["| Variant | Feed | Day (UTC) | Objects |", "|---|---|---|---|"]
        for (variant, source, feed), per_day in sorted(outside.items()):
            for day, count in sorted(per_day.items()):
                lines.append(f"| {variant} | {source}/{feed} | {day} | {count} |")
    else:
        lines.append("None.")
    if ignored_files:
        lines += ["", f"Files ignored (name is not `<ts>.json.gz`): {len(ignored_files)}"]
    lines += section_reconciliation(reconciliation)
    lines += section_static(window_objects, minutes, unexpected)
    lines += section_writes(window_objects, reconciliation, len(minutes))
    return "\n".join(lines) + "\n", issues


def section_reconciliation(reconciliation):
    """Report section (c): logs against objects, per variant."""
    lines = ["", "## (c) Reconciliation of logs and objects", ""]
    lines += ["| Variant | Log files | Lines | " + " | ".join(LOG_KINDS) + " |"]
    lines += ["|---|---|---|" + "---|" * len(LOG_KINDS)]
    for variant in VARIANTS:
        r = reconciliation[variant]
        counts = " | ".join(str(r["kinds"][k]) for k in LOG_KINDS)
        lines.append(f"| {variant} | {r['files']} | {r['lines']} | {counts} |")
    lines += ["", "### Log files outside the window", ""]
    if any(reconciliation[v]["outside"] for v in VARIANTS):
        lines += ["| Variant | Day (UTC) | Log files |", "|---|---|---|"]
        for variant in VARIANTS:
            for day, count in sorted(reconciliation[variant]["outside"].items()):
                lines.append(f"| {variant} | {day} | {count} |")
    else:
        lines.append("None.")
    ignored = sum(reconciliation[v]["ignored"] for v in VARIANTS)
    if ignored:
        lines += ["", f"Log files ignored (name is not `<ts>.jsonl`): {ignored}"]
    return lines


def section_static(window_objects, minutes, unexpected):
    """Report section (d): static feeds at the minute-17 passes.

    The dynamic objects in odd-hour minute-17 passes are the off-schedule count of
    section (a), not recomputed.
    """
    passes = [m for m in minutes if m.minute == STATIC_MINUTE]
    dynamic_set = set(DYNAMIC_FEEDS)
    lines = ["", "## (d) Static feeds", "", f"Minute-17 passes in the window: {len(passes)}", ""]
    lines += ["### Static objects per pass", ""]
    lines += ["| Variant | Source | Objects per pass | Passes |", "|---|---|---|---|"]
    checks = []
    sources = sorted({s for s, _ in DYNAMIC_FEEDS})
    for variant in VARIANTS:
        static_at = defaultdict(Counter)  # source -> minute -> objects
        dynamic_at = defaultdict(set)  # minute -> dynamic feeds present
        off_minute = 0
        for source, feed, _ts, minute in window_objects[variant]:
            if (source, feed) in dynamic_set:
                dynamic_at[minute].add((source, feed))
            else:
                static_at[source][minute] += 1
                if minute.minute != STATIC_MINUTE:
                    off_minute += 1
        for source in sources:
            distribution = Counter(static_at[source][m] for m in passes)
            for n_objects, n_passes in sorted(distribution.items()):
                lines.append(f"| {variant} | {source} | {n_objects} | {n_passes} |")
        odd = [m for m in passes if m.hour % 2 == 1]
        even = [m for m in passes if m.hour % 2 == 0]
        odd_with_dynamic = sum(n for (v, _s, _f), n in unexpected.items() if v == variant)
        even_complete = sum(1 for m in even if len(dynamic_at[m]) == len(DYNAMIC_FEEDS))
        checks.append((variant, len(odd), odd_with_dynamic, len(even), even_complete, off_minute))
    lines += ["", "### Alternation checks", ""]
    lines += [
        "| Variant | Odd-hour passes | Dynamic objects off-schedule, from (a) (expected 0) "
        "| Even-hour passes | With all 3 dynamic objects (expected all) "
        "| Static objects at other minutes (expected 0) |",
        "|---|---|---|---|---|---|",
    ]
    for variant, odd_n, odd_bad, even_n, even_ok, off in checks:
        lines.append(f"| {variant} | {odd_n} | {odd_bad} | {even_n} | {even_ok} | {off} |")
    return lines


def section_writes(window_objects, reconciliation, window_minutes):
    """Report section (e): estimated Class A writes against the F2 reference."""
    lines = ["", "## (e) Class A writes (estimate)", ""]
    lines += [
        "Estimate = raw objects + log files + `state/` writes. A `state/` write is counted "
        "per `gbfs` log line with status 200 and no error, which is when the capturers "
        "persist the index (a 200 whose body is not valid JSON, or whose `put` fails, "
        "carries an error and is not counted). The R2 dashboard is the authoritative "
        "figure.",
        "",
        "| Variant | Raw objects | Log files | `state/` writes | Total | Per day | F2 reference per day "
        "| 30-day projection |",
        "|---|---|---|---|---|---|---|---|",
    ]
    grand_per_day = 0.0
    for variant in VARIANTS:
        r = reconciliation[variant]
        objects = len(window_objects[variant])
        total = objects + r["files"] + r["state_writes"]
        per_day = total / window_minutes * 1440 if window_minutes else 0.0
        grand_per_day += per_day
        lines.append(
            f"| {variant} | {objects} | {r['files']} | {r['state_writes']} | {total} | "
            f"{per_day:,.0f} | {F2_WRITES_PER_VARIANT_DAY:,} | {per_day * PROJECTION_DAYS:,.0f} |"
        )
    projection = grand_per_day * PROJECTION_DAYS
    lines += [
        "",
        f"Both variants, {PROJECTION_DAYS}-day projection: {projection:,.0f} "
        f"({100 * projection / FREE_CLASS_A_PER_MONTH:.1f} % of the "
        f"{FREE_CLASS_A_PER_MONTH:,} free per month).",
    ]
    return lines


def main():
    """Write the report and the issues file next to this script."""
    now = datetime.now(timezone.utc)
    report, issues = analyse(now)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "report.md").write_text(report, encoding="utf-8")
    with open(OUTPUT_DIR / "issues.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant", "source", "feed", "ts", "kind", "detail"])
        writer.writerows(issues)


if __name__ == "__main__":
    main()
