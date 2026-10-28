# Cost model of s010 probe C (§2 C): for each scenario of Q1 and every month 1-12, storage per layer and R2 Class A
# and B operations of capture and pipeline, their monthly and accumulated cost against R2's free quotas, and whether
# each scenario fits the D2 gate (at most gate.max_eur_per_month in every month).
#
# Model (decision log numbers in brackets):
# - capture: B's objects, bytes and logs/ writes per day; static feeds at capture.static_captures_per_day.
# - bronze reads: one GET per new object; LISTs of the day prefixes at 1,000 keys per page (#23, #43).
# - silver and gold commits are MERGE commits costed from A's per-operation table (#27): a table load (a base plus
#   reads per JSON commit since the last checkpoint, (N - 1) / 2 on average), reads per file in the target
#   partition, and a checkpoint every N commits (#42). Optimize, then vacuum, per table as in #30 and #41.
# - storage is computed per day and billed as the month's mean, as R2 does; bronze and gold are kept, silver keeps
#   retention.silver_days. Delta overhead is the month's activity scaled to its log and history windows.
# - month 1 adds the initial load: one catch-up over the history archives and capture's backlog (#17).
# Sensitivity (#45, #47): A's four extrapolated measures, one at a time, re-run through the same model; reported only.
# Input:  params.toml, probe B's volumes.json, probe A's ops-<run_id>-by-op.csv (paths in params.toml).
# Output: output/cost_months.csv (scenario × month), output/cost_summary.csv (scenario, D2 gate), four charts in
#         output/cost-model/, and sensitivity.csv, break_even.csv and the tornado chart in
#         output/cost-model/sensitivity/; plus a console summary.
#
# Usage: uv run python cost_model.py [--params params.toml]
#        uv run python cost_model.py --synthetic   (hand-computed minimal case; writes to output/local/)

import argparse
import copy
import csv
import dataclasses
import json
import math
import sys
import time
import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # files only, no display
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "output"
BUCKETS_PER_DAY = {"snapshot": 0, "minute": 1440, "hour": 24, "day": 1}


@dataclass
class Feed:
    key: str  # provider/feed
    dynamic: bool
    objects_per_day: float
    bytes_per_day: float
    rows_per_day: float  # silver rows: distinct (station_id, last_reported) where B counts them, else raw records


@dataclass
class Ops:
    """A's measured operations per Delta operation (step 5); Class B unless named _a."""

    commit_a: float
    checkpoint_a: float  # extra Class A of a commit that writes a checkpoint
    load_b_base: float  # table load with no JSON commit after the checkpoint
    load_b_per_json: float
    b_per_file: float  # reads per data file, by MERGE in its target partition and by optimize
    checkpoint_b: float  # extra Class B of a checkpoint commit, at the measured checkpoint interval
    optimize_a: float
    optimize_b_fixed: float  # beyond the table load and the per-file reads
    vacuum_a: float
    vacuum_b: float  # beyond the table load
    commit_log_bytes: float
    optimize_log_bytes: float
    vacuum_log_bytes: float
    merge_rewritten_bytes: float


@dataclass
class Inputs:
    feeds: dict[str, Feed]
    logs_writes_per_day: float
    logs_bytes_per_day: float
    state_bytes: float
    stations: float
    history_bytes: float
    history_archives: int
    history_rows: dict[date, dict[str, float]]  # history day -> silver table -> rows
    ops: Ops


@dataclass
class Scenario:
    name: str
    kind: str  # "24/7", "sensitivity" or "on-demand"
    cadence_min: float = 0
    optimize_min: float = 0
    catch_ups: int = 0
    live_hours: float = 0
    judged: bool = False


@dataclass
class Activity:
    """One table's Delta activity in one month."""

    commits: float = 0
    files_read: float = 0  # sum over MERGE commits of the files in the target partition
    optimizes: float = 0  # each followed by a vacuum
    files_compacted: float = 0
    rows_written: float = 0

    def __iadd__(self, other: "Activity") -> "Activity":
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        return self


# ---------------------------------------------------------------- inputs


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values)


def derive_ops(path: Path) -> Ops:
    rows = list(csv.DictReader(path.open()))

    def num(row: dict, key: str) -> float:
        return float(row[key] or 0)

    # Appends outside `concurrent` whose table load starts from a checkpoint, as a production table's does (before
    # the first one, a load reads only JSON commits): B = base + per_json × JSON commits loaded.
    first_checkpoint = min(int(r["versions"]) for r in rows if r["check"] == "write" and r["checkpoint"] == "True")
    appends = [r for r in rows if r["check"] == "write" and r["handle_version"] and r["checkpoint"] != "True"
               and int(r["handle_version"]) >= first_checkpoint]
    xs, ys = [num(r, "json_commits_loaded") for r in appends], [num(r, "B") for r in appends]
    mx, my = mean(xs), mean(ys)
    per_json = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    base = my - per_json * mx

    def load(row: dict) -> float:
        return base + per_json * num(row, "json_commits_loaded")

    merges = [r for r in rows if r["check"] == "merge"]
    plain_merges = [r for r in merges if r["checkpoint"] != "True"]
    per_file = mean((num(r, "B") - load(r)) / num(r, "partition_files") for r in plain_merges)
    commit_a = max(num(r, "A") for r in appends + plain_merges)
    checkpoints = [r for r in rows if r["check"] in ("write", "merge") and r["checkpoint"] == "True"]
    # The largest extra over a plain commit; the table's first checkpoint, with no earlier one to read, costs less.
    checkpoint_b = max(
        num(r, "B") - load(r) - per_file * (num(r, "partition_files") if r["check"] == "merge" else 0)
        for r in checkpoints
    )
    optimize = next(r for r in rows if r["op"] == "optimize")
    vacuum = next(r for r in rows if r["op"] == "vacuum")  # the run that deletes files, not the dry run
    return Ops(
        commit_a=commit_a,
        checkpoint_a=max(num(r, "A") for r in checkpoints) - commit_a,
        load_b_base=base,
        load_b_per_json=per_json,
        b_per_file=per_file,
        checkpoint_b=checkpoint_b,
        optimize_a=num(optimize, "A"),
        optimize_b_fixed=num(optimize, "B") - load(optimize) - per_file * num(optimize, "files_removed"),
        vacuum_a=num(vacuum, "A"),
        vacuum_b=num(vacuum, "B") - load(vacuum),
        commit_log_bytes=mean(num(r, "json_bytes") for r in merges),
        optimize_log_bytes=num(optimize, "json_bytes"),
        vacuum_log_bytes=num(vacuum, "json_bytes"),
        merge_rewritten_bytes=mean(num(r, "bytes_added") for r in merges),
    )


def derive_inputs(params: dict) -> Inputs:
    volumes = json.loads((HERE / params["inputs"]["volumes"]).read_text())
    capture, cap = volumes["capture"], params["capture"]
    days, per_static_day = capture["days"], cap["static_captures_per_day"]
    feeds = {}
    for provider, provider_feeds in capture["raw"].items():
        for name, per_day in provider_feeds.items():
            key, values = f"{provider}/{name}", [per_day[d] for d in days]
            objects = sum(v["objects"] for v in values)
            if key in cap["dynamic_feeds"]:
                feeds[key] = Feed(key, True, objects / len(days), mean(v["bytes"] for v in values),
                                  mean(v.get("distinct_records", v["records"]) for v in values))
            else:  # B measured the current worker's cadence; production's comes from params, at B's size per object
                feeds[key] = Feed(key, False, per_static_day, per_static_day * sum(v["bytes"] for v in values) / objects,
                                  per_static_day * sum(v["records"] for v in values) / objects)
    stations = sum(
        sum(v["records"] for v in per_day.values()) / sum(v["objects"] for v in per_day.values())
        for provider_feeds in capture["raw"].values()
        for name, per_day in provider_feeds.items()
        if name == "station_information"
    )
    history_rows: dict[date, dict[str, float]] = {}
    for archive in volumes["history"]:
        for table in params["silver"]:
            hist = table.get("history")
            if not hist or hist["type"] != archive["type"]:
                continue
            if hist["rows"] == "distinct":  # spread the archive's distinct rows over its days by snapshots
                snaps = archive["snapshots_per_day"]
                total = sum(snaps.values())
                day_rows = {d: archive["distinct_rows"] * s / total for d, s in snaps.items()}
            else:
                day_rows = archive["rows_one_snapshot_per_day"]
            for d, rows in day_rows.items():
                per_table = history_rows.setdefault(date.fromisoformat(d), {})
                per_table[table["name"]] = per_table.get(table["name"], 0) + rows
    return Inputs(
        feeds=feeds,
        logs_writes_per_day=mean(capture["logs"][d]["writes"] for d in days),
        logs_bytes_per_day=mean(capture["logs"][d]["bytes"] for d in days),
        state_bytes=capture["state"]["bytes"],
        stations=stations,
        history_bytes=sum(a["archive_bytes"] for a in volumes["history"]),
        history_archives=len(volumes["history"]),
        history_rows=history_rows,
        ops=derive_ops(HERE / params["inputs"]["ops_by_op"]),
    )


# ---------------------------------------------------------------- scenarios and months


def scenarios(params: dict) -> list[Scenario]:
    s = params["scenarios"]
    out = [Scenario(f"24/7 {c} min", "24/7", cadence_min=c, optimize_min=s["optimize_24_7_min"])
           for c in s["cadences_min"]]
    sens = s["sensitivity"]
    out.append(Scenario(f"24/7 {sens['cadence_min']} min, optimize every {sens['optimize_min']} min", "sensitivity",
                        cadence_min=sens["cadence_min"], optimize_min=sens["optimize_min"]))
    for k in s["catch_ups"]:
        for h in s["live_hours"]:
            judged = k == s["judged"]["catch_ups"] and h == s["judged"]["live_hours"]
            out.append(Scenario(f"on-demand {k} catch-ups + {h} h live", "on-demand", catch_ups=k, live_hours=h,
                                judged=judged))
    return out


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, d.day)  # production starts on a day every month has (1-28)


def months(params: dict) -> list[tuple[int, date, int]]:
    start = date.fromisoformat(params["dates"]["production_start"])
    return [(m, add_months(start, m - 1), (add_months(start, m) - add_months(start, m - 1)).days)
            for m in range(1, params["gate"]["months"] + 1)]


# ---------------------------------------------------------------- tables


def tables(params: dict) -> list[dict]:
    return [{**t, "layer": "silver"} for t in params["silver"]] + [{**t, "layer": "gold"} for t in params["gold"]]


def silver_rows_per_day(table: dict, inputs: Inputs) -> float:
    return sum(inputs.feeds[f].rows_per_day for f in table["feeds"])


def entities(table: dict, inputs: Inputs) -> float:
    return inputs.stations if table["entity"] == "stations" else len(inputs.feeds)


def rows_written(table: dict, inputs: Inputs, days: float, commits: float, history_rows: float = 0) -> float:
    """Rows a table writes over `days` of data in `commits` commits."""
    if table["layer"] == "silver":
        return history_rows + days * silver_rows_per_day(table, inputs)
    # A gold commit upserts at least one row per entity; a snapshot rewrites them all each time.
    return entities(table, inputs) * max(BUCKETS_PER_DAY[table["grain"]] * days, commits)


def merge_reads(commits: float, start_files: float) -> float:
    """Files read by `commits` MERGEs into one partition that holds `start_files`, each adding one file."""
    return commits * start_files + commits * (commits - 1) / 2


def commits_per_day(table: dict, runs_per_day: float) -> float:
    return {"run": runs_per_day, "hour": min(runs_per_day, 24), "day": 1}[table["commits"]]


def activity_24_7(table: dict, inputs: Inputs, sc: Scenario, days: int) -> Activity:
    n = commits_per_day(table, 1440 / sc.cadence_min)
    # Optimize compacts today's partition at the end of each window that had commits; the first window of the day
    # starts on an empty partition, the others on the compacted file.
    windows = min(n, 1440 / sc.optimize_min)
    k = n / windows
    return Activity(
        commits=n * days,
        files_read=(merge_reads(k, 0) + (windows - 1) * merge_reads(k, 1)) * days,
        optimizes=windows * days,
        files_compacted=(n + windows - 1) * days,
        rows_written=rows_written(table, inputs, days, n * days),
    )


def activity_on_demand(table: dict, inputs: Inputs, sc: Scenario, days: int, params: dict) -> Activity:
    p = params["delta"]["catchup_partition_files"]
    # Catch-ups: sessions spread evenly, each commits once per table and pending day partition; the day of the
    # previous session is pending again, so a month has days + catch-ups of them.
    catchup = days + sc.catch_ups
    act = Activity(commits=catchup, files_read=catchup * p, optimizes=sc.catch_ups, files_compacted=catchup * (1 + p))
    # Live: one session per catch-up (#41), a commit per run on the partition the catch-up just compacted. Static
    # silver and daily gold were committed by the catch-up.
    runs = sc.live_hours * 60 / params["scenarios"]["live_cadence_min"] / sc.catch_ups
    n = {"run": runs, "hour": math.ceil(runs * params["scenarios"]["live_cadence_min"] / 60), "day": 0}[table["commits"]]
    if n:
        act += Activity(commits=n * sc.catch_ups, files_read=merge_reads(n, 1) * sc.catch_ups,
                        optimizes=sc.catch_ups, files_compacted=(n + 1) * sc.catch_ups)
    act.rows_written = rows_written(table, inputs, days, act.commits)
    return act


def activity_initial_load(table: dict, inputs: Inputs, backlog_days: int) -> Activity:
    """Month 1's catch-up over the history and capture's backlog: one commit per day with data, on a new table."""
    if table["layer"] == "gold":
        history_days, history_rows = len(inputs.history_rows), 0
    else:
        per_day = [r[table["name"]] for r in inputs.history_rows.values() if table["name"] in r]
        history_days, history_rows = len(per_day), sum(per_day)
    days = history_days + backlog_days
    if not days:
        return Activity()
    # Silver counts history rows apart, so its capture days are the backlog only; gold covers every day.
    data_days = backlog_days if table["layer"] == "silver" else days
    return Activity(commits=days, optimizes=1, files_compacted=days,
                    rows_written=rows_written(table, inputs, data_days, days, history_rows))


def table_ops(act: Activity, ops: Ops, delta: dict) -> tuple[float, float, float]:
    """Class A, Class B and checkpoints of one table's month."""
    n = delta["checkpoint_interval"]
    load = ops.load_b_base + ops.load_b_per_json * (n - 1) / 2
    checkpoints = act.commits / n
    class_a = act.commits * ops.commit_a + checkpoints * ops.checkpoint_a + act.optimizes * (ops.optimize_a + ops.vacuum_a)
    class_b = (act.commits * load + act.files_read * ops.b_per_file
               + checkpoints * ops.checkpoint_b * n / delta["measured_checkpoint_interval"]
               + act.optimizes * (load + ops.optimize_b_fixed) + act.files_compacted * ops.b_per_file
               + act.optimizes * (load + ops.vacuum_b))
    return class_a, class_b, checkpoints


# ---------------------------------------------------------------- bronze and capture


def day_pages(objects: float, page: int) -> int:
    """LIST pages for one full day prefix."""
    return max(1, math.ceil(objects / page))


def run_pages(objects_per_day: float, runs_per_day: int, page: int) -> int:
    """LIST pages over a day's runs, each listing the day prefix as it stands (no watermark, #43)."""
    return sum(max(1, math.ceil(objects_per_day * r / runs_per_day / page)) for r in range(1, runs_per_day + 1))


def bronze_ops(params: dict, inputs: Inputs, sc: Scenario, days: int, first: bool) -> dict:
    page = params["pipeline"]["list_page_keys"]
    dynamic = [f for f in inputs.feeds.values() if f.dynamic]
    all_day_pages = sum(day_pages(f.objects_per_day, page) for f in inputs.feeds.values())
    objects_per_day = sum(f.objects_per_day for f in inputs.feeds.values())
    if sc.kind == "on-demand":
        live_cadence = params["scenarios"]["live_cadence_min"]
        runs_per_day = int(1440 / live_cadence)
        runs = sc.live_hours * 60 / live_cadence  # in the month
        lists = ((days + sc.catch_ups) * all_day_pages
                 + runs * sum(run_pages(f.objects_per_day, runs_per_day, page) / runs_per_day for f in dynamic))
    else:
        runs_per_day = int(1440 / sc.cadence_min)
        static_pages = sum(day_pages(f.objects_per_day, page) for f in inputs.feeds.values() if not f.dynamic)
        lists = days * (sum(run_pages(f.objects_per_day, runs_per_day, page) for f in dynamic) + static_pages)
    gets, puts = days * objects_per_day, 0
    if first:
        backlog = backlog_days(params)
        lists += backlog * all_day_pages + (1 if inputs.history_archives else 0)
        gets += backlog * objects_per_day + inputs.history_archives
        puts += inputs.history_archives  # the archives' upload to bronze
    return {"a": lists + puts, "b": gets}


def capture_ops(params: dict, inputs: Inputs, days: int) -> dict:
    cap = params["capture"]
    raw = days * sum(f.objects_per_day for f in inputs.feeds.values())
    logs = days * inputs.logs_writes_per_day
    state = days * cap["state_writes_per_static_pass"] * cap["static_captures_per_day"]
    class_b = days * cap["class_b_per_day"]
    if cap["override"]["enabled"]:  # R2's metrics prevail (#24, #36); the split keeps B's shares
        scale = cap["override"]["class_a_per_month"] * days / 30 / (raw + logs + state)
        raw, logs, state = raw * scale, logs * scale, state * scale
        class_b = cap["override"]["class_b_per_month"] * days / 30
    return {"raw": raw, "logs": logs, "state": state, "b": class_b}


def backlog_days(params: dict) -> int:
    return (date.fromisoformat(params["dates"]["production_start"])
            - date.fromisoformat(params["dates"]["capture_start"])).days


# ---------------------------------------------------------------- storage


def storage_means(params: dict, inputs: Inputs, start: date, days: int) -> dict:
    """Mean bytes per layer over the month's days (R2 bills the mean of the daily peaks)."""
    capture_start = date.fromisoformat(params["dates"]["capture_start"])
    bpr = params["delta"]["bytes_per_row"]
    window = params["retention"]["silver_days"]
    capture_bytes = sum(f.bytes_per_day for f in inputs.feeds.values()) + inputs.logs_bytes_per_day
    capture_rows = sum(silver_rows_per_day(t, inputs) for t in params["silver"])
    history_rows = {d: sum(r.values()) for d, r in inputs.history_rows.items()}
    history_days = sum(1 for d in inputs.history_rows if d < capture_start)
    gold = [{**t, "layer": "gold"} for t in params["gold"]]
    totals = {"bronze": 0.0, "silver": 0.0, "gold": 0.0}
    for i in range(days):
        d = start + timedelta(days=i)
        captured = (d - capture_start).days + 1
        first_in_window = d - timedelta(days=window - 1)
        in_window = (d - max(capture_start, first_in_window)).days + 1
        totals["bronze"] += inputs.history_bytes + captured * capture_bytes + inputs.state_bytes
        totals["silver"] += bpr * (sum(r for h, r in history_rows.items() if first_in_window <= h <= d)
                                   + in_window * capture_rows)
        loaded = history_days + captured
        totals["gold"] += bpr * sum(
            entities(t, inputs) * (1 if t["grain"] == "snapshot" else BUCKETS_PER_DAY[t["grain"]] * loaded)
            for t in gold)
    return {layer: total / days for layer, total in totals.items()}


def delta_overhead(params: dict, ops: Ops, days: int, commits: float, optimizes: float, checkpoints: float,
                   rows: float) -> float:
    """_delta_log kept retention.delta_log_days, and files removed by MERGE and optimize kept until vacuum."""
    ret, delta = params["retention"], params["delta"]
    log = (commits * ops.commit_log_bytes + optimizes * (ops.optimize_log_bytes + ops.vacuum_log_bytes)
           + checkpoints * delta["checkpoint_bytes"])
    removed = commits * ops.merge_rewritten_bytes + rows * delta["bytes_per_row"]
    return log / days * ret["delta_log_days"] + removed / days * ret["delta_history_days"]


# ---------------------------------------------------------------- model


def model(params: dict, inputs: Inputs, only: list[Scenario] | None = None) -> list[dict]:
    pr = params["prices"]
    month_list = months(params)
    storage = {m: storage_means(params, inputs, start, days) for m, start, days in month_list}
    out = []
    for sc in only or scenarios(params):
        accumulated = 0.0
        for m, start, days in month_list:
            cap = capture_ops(params, inputs, days)
            bronze = bronze_ops(params, inputs, sc, days, m == 1)
            layer_a = {"silver": 0.0, "gold": 0.0}
            layer_b = {"silver": 0.0, "gold": 0.0}
            commits = optimizes = checkpoints = rows = 0.0
            for t in tables(params):
                act = (activity_on_demand(t, inputs, sc, days, params) if sc.kind == "on-demand"
                       else activity_24_7(t, inputs, sc, days))
                if m == 1:
                    act += activity_initial_load(t, inputs, backlog_days(params))
                a, b, ck = table_ops(act, inputs.ops, params["delta"])
                layer_a[t["layer"]] += a
                layer_b[t["layer"]] += b
                commits, optimizes, checkpoints = commits + act.commits, optimizes + act.optimizes, checkpoints + ck
                rows += act.rows_written
            st = {**storage[m], "delta_overhead": delta_overhead(params, inputs.ops, days, commits, optimizes,
                                                                 checkpoints, rows)}
            gb = {k: v / pr["gb_bytes"] for k, v in st.items()}
            gb_total = sum(gb.values())
            a_total = cap["raw"] + cap["logs"] + cap["state"] + bronze["a"] + layer_a["silver"] + layer_a["gold"]
            b_total = cap["b"] + bronze["b"] + layer_b["silver"] + layer_b["gold"]
            usd = {
                "storage": max(0.0, gb_total - pr["free_storage_gb_month"]) * pr["storage_usd_per_gb_month"],
                "a": max(0.0, a_total - pr["free_class_a"]) * pr["class_a_usd_per_million"] / 1e6,
                "b": max(0.0, b_total - pr["free_class_b"]) * pr["class_b_usd_per_million"] / 1e6,
            }
            # Per layer: each cost item split by the layer's share of its quantity.
            shares = {
                "bronze": (gb["bronze"], cap["raw"] + cap["logs"] + cap["state"] + bronze["a"], cap["b"] + bronze["b"]),
                "silver": (gb["silver"], layer_a["silver"], layer_b["silver"]),
                "gold": (gb["gold"], layer_a["gold"], layer_b["gold"]),
                "delta_overhead": (gb["delta_overhead"], 0, 0),
            }
            eur_layer = {k: pr["usd_to_eur"] * (usd["storage"] * s / gb_total + usd["a"] * a / a_total
                                                + usd["b"] * b / b_total)
                         for k, (s, a, b) in shares.items()}
            eur_total = pr["usd_to_eur"] * sum(usd.values())
            accumulated += eur_total
            out.append({
                "scenario": sc.name, "kind": sc.kind, "judged": sc.judged, "month": m, "start": start.isoformat(),
                "days": days,
                **{f"gb_{k}": v for k, v in gb.items()}, "gb_total": gb_total,
                "a_capture_raw": cap["raw"], "a_capture_logs": cap["logs"], "a_capture_state": cap["state"],
                "a_bronze_pipeline": bronze["a"], "a_silver": layer_a["silver"], "a_gold": layer_a["gold"],
                "a_total": a_total,
                "b_capture": cap["b"], "b_bronze_get": bronze["b"], "b_silver": layer_b["silver"],
                "b_gold": layer_b["gold"], "b_total": b_total,
                "commits": commits,
                "quota_storage_pct": 100 * gb_total / pr["free_storage_gb_month"],
                "quota_a_pct": 100 * a_total / pr["free_class_a"],
                "quota_b_pct": 100 * b_total / pr["free_class_b"],
                "usd_storage": usd["storage"], "usd_class_a": usd["a"], "usd_class_b": usd["b"],
                "usd_total": sum(usd.values()),
                **{f"eur_{k}": v for k, v in eur_layer.items()},
                "eur_total": eur_total, "eur_accumulated": accumulated,
            })
    return out


def summarise(params: dict, rows: list[dict]) -> list[dict]:
    limit, reported = params["gate"]["max_eur_per_month"], params["gate"]["reported_months"]
    out = []
    for name in dict.fromkeys(r["scenario"] for r in rows):
        sc_rows = [r for r in rows if r["scenario"] == name]
        worst = max(sc_rows, key=lambda r: r["eur_total"])
        out.append({
            "scenario": name, "kind": sc_rows[0]["kind"], "judged": sc_rows[0]["judged"],
            **{f"eur_month_{m}": next(r["eur_total"] for r in sc_rows if r["month"] == m) for m in reported},
            "eur_max_month": worst["eur_total"], "worst_month": worst["month"],
            "eur_accumulated": sc_rows[-1]["eur_accumulated"],
            "fits_gate": all(r["eur_total"] <= limit for r in sc_rows),
        })
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: round(v, 6) if isinstance(v, float) else v for k, v in row.items()})


def report(params: dict, inputs: Inputs, rows: list[dict], out_dir: Path) -> list[dict]:
    summary = summarise(params, rows)
    write_csv(out_dir / "cost_months.csv", rows)
    write_csv(out_dir / "cost_summary.csv", summary)
    reported = params["gate"]["reported_months"]
    print(f"stations {inputs.stations:.0f}, feeds {len(inputs.feeds)}, history days {len(inputs.history_rows)}, "
          f"backlog days {backlog_days(params)}, production start {params['dates']['production_start']}, "
          f"USD→EUR {params['prices']['usd_to_eur']} ({params['prices']['usd_to_eur_date'] or 'no date'})")
    print(f"\n{'scenario':<46}" + "".join(f"{'m' + str(m):>8}" for m in reported) + f"{'max':>8}{'12 m':>9}  gate")
    for s in summary:
        mark = " (judged)" if s["judged"] else ""
        gate = "reported" if s["kind"] == "sensitivity" else ("fits" if s["fits_gate"] else "over")
        print(f"{s['scenario'] + mark:<46}" + "".join(f"{s[f'eur_month_{m}']:>8.2f}" for m in reported)
              + f"{s['eur_max_month']:>8.2f}{s['eur_accumulated']:>9.2f}  {gate}")
    print(f"\nEUR per month; gate: at most {params['gate']['max_eur_per_month']} in every month "
          f"1-{params['gate']['months']}. Written: {out_dir / 'cost_months.csv'}, {out_dir / 'cost_summary.csv'}")
    return summary


# ---------------------------------------------------------------- sensitivity and break-even (#45, #47)

# A's four extrapolated measures and where each lives: in Ops (A's per-operation table) or in params["delta"].
MEASURES = {
    "reads per file": ("ops", "b_per_file"),
    "checkpoint interval N": ("delta", "checkpoint_interval"),
    "Parquet bytes per row": ("delta", "bytes_per_row"),
    "bytes rewritten per MERGE": ("ops", "merge_rewritten_bytes"),
}


def measure_value(params: dict, inputs: Inputs, measure: str) -> float:
    where, key = MEASURES[measure]
    return getattr(inputs.ops, key) if where == "ops" else params["delta"][key]


def vary(params: dict, inputs: Inputs, measure: str, factor: float) -> tuple[dict, Inputs]:
    """Copies of params and inputs with one measure scaled by `factor`; the originals are untouched."""
    where, key = MEASURES[measure]
    if where == "ops":
        ops = dataclasses.replace(inputs.ops, **{key: getattr(inputs.ops, key) * factor})
        return params, dataclasses.replace(inputs, ops=ops)
    varied = copy.deepcopy(params)
    varied["delta"][key] *= factor
    return varied, inputs


def worst_month(params: dict, inputs: Inputs, sc: Scenario) -> tuple[float, int]:
    worst = max(model(params, inputs, only=[sc]), key=lambda r: r["eur_total"])
    return worst["eur_total"], worst["month"]


def sensitivity(params: dict, inputs: Inputs, cases: list[Scenario]) -> list[dict]:
    """Each case's worst month with each measure at each factor, the rest unchanged."""
    out = []
    for sc in cases:
        base, _ = worst_month(params, inputs, sc)
        for measure in MEASURES:
            for factor in params["sensitivity"]["factors"]:
                eur, month = worst_month(*vary(params, inputs, measure, factor), sc)
                out.append({"scenario": sc.name, "measure": measure, "factor": factor,
                            "value": measure_value(params, inputs, measure) * factor, "eur_max_month": eur,
                            "worst_month": month, "eur_baseline": base, "eur_change": eur - base})
    return out


def break_even(params: dict, inputs: Inputs, sc: Scenario, measure: str) -> float | None:
    """The factor above 1 at which the worst month reaches the gate; None if not by sensitivity.break_even_max.
    A doubling scan finds the first factor over the gate, then bisection narrows it to a relative 1e-9."""
    limit, top = params["gate"]["max_eur_per_month"], params["sensitivity"]["break_even_max"]

    def over(factor: float) -> bool:
        return worst_month(*vary(params, inputs, measure, factor), sc)[0] >= limit

    if over(1):
        return 1.0
    lo, hi = 1.0, 2.0
    while not over(min(hi, top)):
        if hi >= top:
            return None
        lo, hi = hi, hi * 2
    hi = min(hi, top)
    while hi / lo - 1 > 1e-9:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if over(mid) else (mid, hi)
    return hi


def break_evens(params: dict, inputs: Inputs, sc: Scenario) -> list[dict]:
    out = []
    for measure in MEASURES:
        t0 = time.monotonic()
        factor = break_even(params, inputs, sc, measure)
        value = measure_value(params, inputs, measure)
        out.append({"scenario": sc.name, "measure": measure, "value": value,
                    "break_even_factor": factor if factor is not None else "",
                    "break_even_value": value * factor if factor is not None else "",
                    "note": "" if factor is not None else f"break-even > ×{params['sensitivity']['break_even_max']}"})
        print(f"  break-even {measure}: "
              + (f"×{factor:.3f}" if factor is not None else out[-1]["note"]) + f" ({time.monotonic() - t0:.1f} s)")
    return out


def sensitivity_cases(params: dict) -> tuple[Scenario, list[Scenario]]:
    """The judged cell, and the cases the sensitivity runs on: the judged cell and 24/7 at cadence_24_7_min."""
    all_sc = scenarios(params)
    judged = next(s for s in all_sc if s.judged)
    cadence = params["sensitivity"]["cadence_24_7_min"]
    return judged, [judged, next(s for s in all_sc if s.kind == "24/7" and s.cadence_min == cadence)]


def sensitivity_report(params: dict, inputs: Inputs, out_dir: Path) -> tuple[list[dict], list[dict]]:
    judged, cases = sensitivity_cases(params)
    print(f"\nsensitivity on {', '.join(s.name for s in cases)}; break-even on the judged cell")
    sens = sensitivity(params, inputs, cases)
    be = break_evens(params, inputs, judged)
    write_csv(out_dir / "cost-model" / "sensitivity" / "sensitivity.csv", sens)
    write_csv(out_dir / "cost-model" / "sensitivity" / "break_even.csv", be)
    for r in sens:
        print(f"  {r['scenario']:<40}{r['measure']:<28}×{r['factor']:<5}{r['eur_max_month']:>8.2f}"
              f"{r['eur_change']:>+8.2f}")
    return sens, be


# ---------------------------------------------------------------- charts (light theme, dataviz reference palette)

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]  # fixed order
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # blue, light to dark


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2, "legend.frameon": False, "legend.labelcolor": INK_2, "font.size": 9,
    })


def gate_line(ax, limit: float, horizontal: bool = True) -> None:
    (ax.axhline if horizontal else ax.axvline)(limit, color=INK, linewidth=1, linestyle=(0, (4, 3)))
    if horizontal:
        ax.annotate(f"€{limit:g} gate", (1, limit), xycoords=("axes fraction", "data"), xytext=(0, 3),
                    textcoords="offset points", ha="right", va="bottom", color=INK)


def save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_monthly(params: dict, rows: list[dict], path: Path) -> Path:
    limit = params["gate"]["max_eur_per_month"]
    series = [s for s in dict.fromkeys(r["scenario"] for r in rows)
              if any(r["scenario"] == s and (r["kind"] == "24/7" or r["judged"]) for r in rows)]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, name in enumerate(series):
        sc_rows = [r for r in rows if r["scenario"] == name]
        label = name + (" (judged)" if sc_rows[0]["judged"] else "")
        ax.plot([r["month"] for r in sc_rows], [r["eur_total"] for r in sc_rows], color=SERIES[i % len(SERIES)],
                linewidth=2, marker="o", markersize=4, label=label)
    gate_line(ax, limit)
    ax.set(title="Monthly cost against the D2 gate", xlabel="Month", ylabel="EUR per month")
    ax.set_xticks(range(1, params["gate"]["months"] + 1))
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    return save(fig, path)


def chart_grid(params: dict, summary: list[dict], path: Path) -> Path:
    s = params["scenarios"]
    by_name = {r["scenario"]: r["eur_max_month"] for r in summary}
    grid = [[by_name[f"on-demand {k} catch-ups + {h} h live"] for h in s["live_hours"]] for k in s["catch_ups"]]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blue", SEQUENTIAL)
    # The scale spans the grid's own range, so neighbouring cells differ; the values are printed in each cell.
    im = ax.imshow(grid, cmap=cmap, vmin=min(map(min, grid)), vmax=max(map(max, grid)), origin="lower",
                   aspect="auto")
    ax.grid(False)
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            dark = im.norm(v) > 0.55  # light ink on the darker cells
            judged = (s["catch_ups"][i], s["live_hours"][j]) == (s["judged"]["catch_ups"], s["judged"]["live_hours"])
            ax.text(j, i, f"{v:.2f}" + ("\njudged" if judged else ""), ha="center", va="center",
                    color=SURFACE if dark else INK, fontweight="bold" if judged else "normal")
    ki, hj = s["catch_ups"].index(s["judged"]["catch_ups"]), s["live_hours"].index(s["judged"]["live_hours"])
    ax.add_patch(Rectangle((hj - 0.5, ki - 0.5), 1, 1, fill=False, edgecolor=INK, linewidth=2))
    ax.set_xticks(range(len(s["live_hours"])), [f"{h:g} h" for h in s["live_hours"]])
    ax.set_yticks(range(len(s["catch_ups"])), [str(k) for k in s["catch_ups"]])
    ax.set(title="On-demand: worst month (EUR)", xlabel="Live hours per month", ylabel="Catch-ups per month")
    fig.colorbar(im, ax=ax, label="EUR, worst month").outline.set_visible(False)
    return save(fig, path)


def chart_cadence(params: dict, summary: list[dict], path: Path) -> Path:
    rows = [r for r in summary if r["kind"] == "24/7"]
    labels = [r["scenario"].removeprefix("24/7 ") for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, [r["eur_max_month"] for r in rows], color=SERIES[0], width=0.6)
    ax.bar_label(bars, fmt="%.2f", padding=2, color=INK_2)
    gate_line(ax, params["gate"]["max_eur_per_month"])
    ax.grid(axis="x", visible=False)
    ax.set(title="24/7: worst month by commit cadence", xlabel="Commit every", ylabel="EUR, worst month")
    return save(fig, path)


def chart_layers(rows: list[dict], path: Path) -> Path:
    judged = [r for r in rows if r["judged"]]
    layers = ["bronze", "silver", "gold", "delta_overhead"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bottom = [0.0] * len(judged)
    for i, layer in enumerate(layers):
        values = [r[f"eur_{layer}"] for r in judged]
        ax.bar([r["month"] for r in judged], values, bottom=bottom, color=SERIES[i], width=0.7,
               edgecolor=SURFACE, linewidth=1, label=layer.replace("_", " "))
        bottom = [b + v for b, v in zip(bottom, values)]
    ax.grid(axis="x", visible=False)
    ax.set_xticks([r["month"] for r in judged])
    ax.set(title=f"Cost per layer: {judged[0]['scenario']} (judged)", xlabel="Month", ylabel="EUR per month")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    return save(fig, path)


def chart_tornado(params: dict, sens: list[dict], be: list[dict], path: Path) -> Path:
    cases = list(dict.fromkeys(r["scenario"] for r in sens))
    lo_f, hi_f = min(params["sensitivity"]["factors"]), max(params["sensitivity"]["factors"])
    be_label = {r["measure"]: (f"break-even ×{r['break_even_factor']:.1f}" if r["break_even_factor"] != ""
                               else r["note"]) for r in be}
    judged = be[0]["scenario"] if be else None
    fig, axes = plt.subplots(len(cases), 1, figsize=(8, 2.4 * len(cases) + 0.6), squeeze=False)
    for ax, case in zip(axes[:, 0], cases):
        rows = [r for r in sens if r["scenario"] == case]
        base = rows[0]["eur_baseline"]
        # Widest swing on top, as a tornado reads.
        order = sorted(MEASURES, key=lambda m: max(abs(r["eur_change"]) for r in rows if r["measure"] == m))
        for y, m in enumerate(order):
            for f, color in ((lo_f, SERIES[0]), (hi_f, SERIES[1])):
                eur = next(r["eur_max_month"] for r in rows if r["measure"] == m and r["factor"] == f)
                ax.barh(y, eur - base, left=base, color=color, height=0.55,
                        label=f"×{f:g}" if y == 0 else None)
        labels = [m + (f"\n{be_label[m]}" if case == judged else "") for m in order]
        ax.set_yticks(range(len(order)), labels)
        ax.axvline(base, color=INK_2, linewidth=1)
        ax.grid(axis="y", visible=False)
        ax.set_title(case + (" (judged)" if case == judged else ""))
        ax.set_xlabel(f"EUR, worst month (baseline {base:.2f})")
        ax.legend(loc="lower right")
    fig.suptitle("Sensitivity: one measure at a time", x=0.01, ha="left", fontweight="bold", color=INK)
    return save(fig, path)


def charts(params: dict, rows: list[dict], summary: list[dict], sens: list[dict], be: list[dict],
           out_dir: Path) -> list[Path]:
    style()
    d = out_dir / "cost-model"
    written = [chart_monthly(params, rows, d / "monthly_cost.png"),
               chart_grid(params, summary, d / "on_demand_grid.png"),
               chart_cadence(params, summary, d / "worst_month_by_cadence.png"),
               chart_layers(rows, d / "judged_cost_per_layer.png"),
               chart_tornado(params, sens, be, d / "sensitivity" / "tornado.png")]
    print("\ncharts: " + ", ".join(str(p.relative_to(HERE)) for p in written))
    return written


def analyse(params: dict, inputs: Inputs, rows: list[dict], out_dir: Path) -> tuple[list[dict], list[dict]]:
    """Summary, sensitivity, break-even and charts for a model run."""
    summary = report(params, inputs, rows, out_dir)
    sens, be = sensitivity_report(params, inputs, out_dir)
    charts(params, rows, summary, sens, be, out_dir)
    return sens, be


# ---------------------------------------------------------------- synthetic check


def synthetic() -> tuple[dict, Inputs]:
    """A minimal case: one dynamic and one static feed, three tables, N = 10, month 1 of a 30-day month."""
    params = {
        "dates": {"capture_start": "2026-10-30", "production_start": "2026-11-01"},  # 2 backlog days
        "gate": {"months": 1, "reported_months": [1], "max_eur_per_month": 2.0},
        # The checked scenario is 24/7 at 60 min; the others only feed the charts.
        "scenarios": {"cadences_min": [30, 60], "optimize_24_7_min": 1440,
                      "sensitivity": {"cadence_min": 60, "optimize_min": 60},
                      "catch_ups": [4, 10], "live_hours": [1, 2], "live_cadence_min": 1,
                      "judged": {"catch_ups": 10, "live_hours": 2}},
        "sensitivity": {"factors": [0.5, 2], "cadence_24_7_min": 60, "break_even_max": 1000},
        "capture": {"static_captures_per_day": 1, "state_writes_per_static_pass": 2, "class_b_per_day": 10,
                    "override": {"enabled": False}},
        "pipeline": {"list_page_keys": 1000},
        "delta": {"checkpoint_interval": 10, "measured_checkpoint_interval": 10, "catchup_partition_files": 1,
                  "bytes_per_row": 20, "checkpoint_bytes": 35000},
        "retention": {"silver_days": 365, "delta_history_days": 7, "delta_log_days": 30},
        "silver": [{"name": "dyn", "commits": "run", "feeds": ["p/dyn"], "history": {"type": "X", "rows": "distinct"}},
                   {"name": "static", "commits": "day", "feeds": ["p/static"]}],
        "gold": [{"name": "g", "commits": "hour", "grain": "hour", "entity": "stations"}],
        "prices": {"storage_usd_per_gb_month": 0.015, "class_a_usd_per_million": 4.5, "class_b_usd_per_million": 0.36,
                   "free_storage_gb_month": 0.01, "free_class_a": 1000, "free_class_b": 10000, "gb_bytes": 1e9,
                   "usd_to_eur": 0.9, "usd_to_eur_date": "synthetic"},
    }
    inputs = Inputs(
        feeds={"p/dyn": Feed("p/dyn", True, 1200, 1_000_000, 1000),
               "p/static": Feed("p/static", False, 1, 10_000, 100)},
        logs_writes_per_day=100, logs_bytes_per_day=50_000, state_bytes=4000, stations=10,
        history_bytes=5000, history_archives=1,
        history_rows={date(2026, 10, 1): {"dyn": 50}, date(2026, 10, 2): {"dyn": 50}},
        ops=Ops(commit_a=6, checkpoint_a=3, load_b_base=14, load_b_per_json=2, b_per_file=3, checkpoint_b=33,
                optimize_a=8, optimize_b_fixed=3, vacuum_a=9, vacuum_b=15, commit_log_bytes=2000,
                optimize_log_bytes=16000, vacuum_log_bytes=600, merge_rewritten_bytes=30000),
    )
    return params, inputs


# Hand computation for 24/7 at 60 min (24 runs a day), month 1 = November 2026 (30 days). Table load at N = 10:
# 14 + 2 × 4.5 = 23 Class B. Initial load: 2 history days and 2 backlog days (Oct 30-31).
# - capture A: raw 30 × 1,201 = 36,030; logs 30 × 100 = 3,000; state 30 × 2 = 60. Capture B: 30 × 10 = 300.
# - bronze A: LISTs per day: dyn at run r lists 50·r keys, 1 page for r ≤ 20, 2 for r = 21-24 → 28; static 1 → 29;
#   month 870; initial load 2 days × (2 + 1) + 1 history prefix = 7; the archive's PUT 1. Total 878.
# - bronze B: GETs 30 × 1,201 + 2 × 1,201 + 1 archive = 38,433.
# - dyn (24/day, daily optimize): commits 720 + 4 initial = 724; files read 30 × 24·23/2 = 8,280; optimizes 30 + 1;
#   compacted 720 + 4. A = 724·6 + 72.4·3 + 31·(8 + 9) = 5,088.2.
#   B = 724·23 + 8,280·3 + 72.4·33 + 31·(23 + 3) + 724·3 + 31·(23 + 15) = 48,037.2.
# - static (1/day): commits 30 + 2; optimizes 31; compacted 32. A = 728.6; B = 736 + 105.6 + 806 + 96 + 1,178 = 2,921.6.
# - g (hour, 24/day): as dyn, with 4 initial commits (2 history + 2 backlog days): A 5,088.2, B 48,037.2.
# - A total 39,090 + 878 + 5,816.8 + 5,088.2 = 50,873; B total 300 + 38,433 + 50,958.8 + 48,037.2 = 137,729.
# - storage on Nov k: bronze 5,000 + 4,000 + (2 + k) × 1,060,000, mean 18,559,000; silver (100 + (2 + k) × 1,100)
#   × 20, mean 387,000; gold 10 × 24 × (4 + k) × 20, mean 93,600.
# - Delta overhead: log (1,480·2,000 + 93·16,600 + 148·35,000) / 30 × 30 = 9,683,800; removed
#   (1,480·30,000 + (35,300 silver + 8,160 gold rows)·20) / 30 × 7 = 10,562,813.333.
# - cost: storage (0.0392862133 - 0.01 free) GB × 0.015 = 0.0004392932; A 49,873 × 4.5e-6 = 0.2244285;
#   B 127,729 × 0.36e-6 = 0.04598244; USD 0.2708502332; EUR × 0.9 = 0.24376520988.
SYNTHETIC_EXPECTED = {
    "a_capture_raw": 36_030, "a_capture_logs": 3_000, "a_capture_state": 60, "b_capture": 300,
    "a_bronze_pipeline": 878, "b_bronze_get": 38_433,
    "a_silver": 5_816.8, "a_gold": 5_088.2, "b_silver": 50_958.8, "b_gold": 48_037.2,
    "a_total": 50_873, "b_total": 137_729, "commits": 1_480,
    "gb_bronze": 0.018559, "gb_silver": 0.000387, "gb_gold": 0.0000936, "gb_delta_overhead": 0.0202466133333333,
    "usd_storage": 0.0004392932, "usd_class_a": 0.2244285, "usd_class_b": 0.04598244,
    "eur_total": 0.24376520988,
}

# Sensitivity, reads per file × 2 (3 → 6 Class B per file): B adds 3 per file read and per file compacted, that is
# 3 × (8,280 + 724) = 27,012 for dyn and g, and 3 × 32 = 96 for static: b_total 191,849. Cost B (191,849 - 10,000)
# × 0.36e-6 = 0.06546564; USD 0.2903334332; EUR 0.26130008988.
# Break-even of reads per file: B is linear in the factor x, B(x) = 83,609 + 54,120·x (18,040 files × 3), with
# storage and Class A fixed; EUR 2 = 0.9 × (0.0004392932 + 0.2244285 + (B(x) - 10,000) × 0.36e-6) gives
# x = ((2 / 0.9 - 0.2248677932) / 0.36e-6 + 10,000 - 83,609) / 54,120 = 101.15664721515.
SYNTHETIC_SENSITIVITY_EUR = 0.26130008988
SYNTHETIC_BREAK_EVEN = 101.15664721515061


def run_synthetic() -> int:
    params, inputs = synthetic()
    out_dir = OUTPUT_DIR / "local"
    rows = model(params, inputs)
    sens, _ = analyse(params, inputs, rows, out_dir)
    checked = Scenario("24/7 60 min", "24/7", cadence_min=60, optimize_min=1440)
    row = next(r for r in rows if r["scenario"] == checked.name)
    errors = [f"{k}: model {row[k]!r}, hand {v!r}" for k, v in SYNTHETIC_EXPECTED.items()
              if not math.isclose(row[k], v, rel_tol=1e-9, abs_tol=1e-12)]
    case = next(r for r in sens
                if r["scenario"] == checked.name and r["measure"] == "reads per file" and r["factor"] == 2)
    if not math.isclose(case["eur_max_month"], SYNTHETIC_SENSITIVITY_EUR, rel_tol=1e-9):
        errors.append(f"sensitivity reads per file ×2: model {case['eur_max_month']!r}, "
                      f"hand {SYNTHETIC_SENSITIVITY_EUR!r}")
    factor = break_even(params, inputs, checked, "reads per file")
    if factor is None or not math.isclose(factor, SYNTHETIC_BREAK_EVEN, rel_tol=1e-6):
        errors.append(f"break-even reads per file: model {factor!r}, hand {SYNTHETIC_BREAK_EVEN!r}")
    print("\nsynthetic check: " + ("ok" if not errors else "FAIL\n  " + "\n  ".join(errors)))
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="s010 probe C: R2 cost per scenario and month")
    parser.add_argument("--params", default="params.toml", help="parameter file (default: params.toml)")
    parser.add_argument("--synthetic", action="store_true", help="hand-computed minimal case; writes to output/local/")
    args = parser.parse_args()
    if args.synthetic:
        return run_synthetic()
    params = tomllib.loads((HERE / args.params).read_text())
    inputs = derive_inputs(params)
    print(f"A's operations: {inputs.ops}\n")
    t0 = time.monotonic()
    analyse(params, inputs, model(params, inputs), OUTPUT_DIR)
    print(f"\nelapsed {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
