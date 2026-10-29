# Hand check of cost_model.py (s010 step 9, #48): recomputes month 1's Class A and Class B operations, and their cost
# after the free quotas, for two cells, without importing cost_model.py. Each term follows §2 C and its Hand check
# bullet, from params.toml, A's per-operation table (output/ops-*-by-op.csv) and B's output/volumes.json.
# Inputs: those three, plus output/cost_months.csv, the model's output it is compared with.
# Output: one table per class, hand value against the model's, ✅ or ❌ per row; exits 1 on any mismatch.
import csv
import math
import sys
import tomllib
from collections import defaultdict
from datetime import date
from pathlib import Path
import json

HERE = Path(__file__).parent
LIVE_CADENCE_24_7_MIN = 10  # the 24/7 cell checked besides the judged on-demand cell

params = tomllib.loads((HERE / "params.toml").read_text())
volumes = json.loads((HERE / params["inputs"]["volumes"]).read_text())
ops_rows = list(csv.DictReader((HERE / params["inputs"]["ops_by_op"]).open()))
model_rows = list(csv.DictReader((HERE / "output" / "cost_months.csv").open()))

cap_p, delta, prices, sc_p = params["capture"], params["delta"], params["prices"], params["scenarios"]
assert not cap_p["override"]["enabled"], "the hand check assumes B's capture operations (no override)"
assert sc_p["optimize_24_7_min"] == 1440, "the hand check assumes daily optimize in 24/7"
N = delta["checkpoint_interval"]
PAGE = params["pipeline"]["list_page_keys"]


def num(row: dict, key: str) -> float:
    return float(row[key] or 0)


# ---------------------------------------------------------------- A's measures, per operation
# Appends after the first checkpoint load the table from it: B = base + per_json × JSON commits loaded.
first_ckpt = min(int(r["versions"]) for r in ops_rows if r["check"] == "write" and r["checkpoint"] == "True")
appends = [r for r in ops_rows if r["check"] == "write" and r["checkpoint"] != "True" and r["handle_version"]
           and int(r["handle_version"]) >= first_ckpt]
LOAD_BASE = sum(num(r, "B") for r in appends if num(r, "json_commits_loaded") == 0) / sum(
    1 for r in appends if num(r, "json_commits_loaded") == 0)
loaded = [r for r in appends if num(r, "json_commits_loaded") > 0]
PER_JSON = sum((num(r, "B") - LOAD_BASE) / num(r, "json_commits_loaded") for r in loaded) / len(loaded)


def measured_load(r: dict) -> float:
    return LOAD_BASE + PER_JSON * num(r, "json_commits_loaded")


merges = [r for r in ops_rows if r["check"] == "merge" and r["checkpoint"] != "True"]
PER_FILE = sum((num(r, "B") - measured_load(r)) / num(r, "partition_files") for r in merges) / len(merges)
COMMIT_A = max(num(r, "A") for r in appends + merges)
ckpts = [r for r in ops_rows if r["check"] in ("write", "merge") and r["checkpoint"] == "True"]
CKPT_A = max(num(r, "A") for r in ckpts) - COMMIT_A
CKPT_B = max(num(r, "B") - measured_load(r) - PER_FILE * num(r, "partition_files") for r in ckpts)  # at N = 10
opt = next(r for r in ops_rows if r["op"] == "optimize")
vac = next(r for r in ops_rows if r["op"] == "vacuum")
OPT_A, VAC_A = num(opt, "A"), num(vac, "A")
OPT_B_FIXED = num(opt, "B") - measured_load(opt) - PER_FILE * num(opt, "files_removed")
VAC_B_FIXED = num(vac, "B") - measured_load(vac)
# A production table loads from its last checkpoint with (N - 1) / 2 JSON commits on average; optimize and vacuum
# load it too, so their load is scaled to N like a commit's, and only their fixed extra is A's.
LOAD = LOAD_BASE + PER_JSON * (N - 1) / 2

# ---------------------------------------------------------------- B's volumes
cap = volumes["capture"]
days_b = cap["days"]
dynamic = set(cap_p["dynamic_feeds"])
objects_per_day = {}  # production: dynamic feeds as measured, static feeds at the planned daily captures
for src, feeds in cap["raw"].items():
    for name, per_day in feeds.items():
        feed = f"{src}/{name}"
        objects_per_day[feed] = (sum(per_day[d]["objects"] for d in days_b) / len(days_b) if feed in dynamic
                                 else cap_p["static_captures_per_day"])
logs_per_day = sum(cap["logs"][d]["writes"] for d in days_b) / len(days_b)
history_days_by_type = defaultdict(set)
for archive in volumes["history"]:
    history_days_by_type[archive["type"]].update(archive["snapshots_per_day"])
history_days = len(set().union(*history_days_by_type.values()))
history_archives = len(volumes["history"])

# ---------------------------------------------------------------- month 1
start = date.fromisoformat(params["dates"]["production_start"])
next_month = date(start.year + start.month // 12, start.month % 12 + 1, start.day)
DAYS = (next_month - start).days
BACKLOG = (start - date.fromisoformat(params["dates"]["capture_start"])).days


def day_pages(objects: float) -> int:
    return max(1, math.ceil(objects / PAGE))


def run_pages(per_day: float, runs: int) -> int:
    """Pages over a day's runs, each listing the day prefix as it stands at run r of `runs`."""
    return sum(max(1, math.ceil(per_day * r / runs / PAGE)) for r in range(1, runs + 1))


def files_read(commits: float, start_files: float) -> float:
    """Files read by `commits` MERGEs into one partition holding `start_files`, each adding one file."""
    return commits * start_files + commits * (commits - 1) / 2


class Activity:
    def __init__(self, commits=0.0, read=0.0, optimizes=0.0, compacted=0.0):
        self.commits, self.read, self.optimizes, self.compacted = commits, read, optimizes, compacted

    def __add__(self, o):
        return Activity(self.commits + o.commits, self.read + o.read, self.optimizes + o.optimizes,
                        self.compacted + o.compacted)

    def class_a(self) -> float:
        return self.commits * COMMIT_A + self.commits / N * CKPT_A + self.optimizes * (OPT_A + VAC_A)

    def class_b(self) -> float:
        return (self.commits * LOAD + self.read * PER_FILE + self.commits / N * CKPT_B * N / delta[
            "measured_checkpoint_interval"] + self.optimizes * (LOAD + OPT_B_FIXED) + self.compacted * PER_FILE
                + self.optimizes * (LOAD + VAC_B_FIXED))


def tables():
    return [dict(t, layer="silver") for t in params["silver"]] + [dict(t, layer="gold") for t in params["gold"]]


def initial_load(t: dict) -> Activity:
    """One commit per day with data on a new table (no file to read), and one optimize over all of them."""
    if t["layer"] == "gold":
        days = history_days + BACKLOG
    else:
        days = (len(history_days_by_type[t["history"]["type"]]) if "history" in t else 0) + BACKLOG
    return Activity(commits=days, optimizes=1, compacted=days)


def activity_24_7(t: dict, cadence: int) -> Activity:
    runs = 1440 // cadence
    n = {"run": runs, "hour": min(runs, 24), "day": 1}[t["commits"]]
    # Daily optimize: the k-th commit of the day finds k - 1 files in today's partition.
    return Activity(commits=n * DAYS, read=files_read(n, 0) * DAYS, optimizes=DAYS, compacted=n * DAYS)


def activity_on_demand(t: dict, catch_ups: int, live_hours: float) -> Activity:
    # Each catch-up redoes the previous session's day, so the month has DAYS + catch_ups day partitions, each with
    # the compacted file of the day before (catchup_partition_files).
    p = delta["catchup_partition_files"]
    commits = DAYS + catch_ups
    act = Activity(commits=commits, read=commits * p, optimizes=catch_ups, compacted=commits * (1 + p))
    # live_hours are per month, split evenly over one session per catch-up; static silver and daily gold are left
    # to the catch-ups; an hourly table commits once per started hour of a session.
    runs = live_hours * 60 / sc_p["live_cadence_min"] / catch_ups
    n = {"run": runs, "hour": math.ceil(runs * sc_p["live_cadence_min"] / 60), "day": 0}[t["commits"]]
    if n:
        act += Activity(commits=n * catch_ups, read=files_read(n, 1) * catch_ups, optimizes=catch_ups,
                        compacted=(n + 1) * catch_ups)
    return act


def cell(kind: str, **sc) -> dict:
    out = defaultdict(float)
    # Capture
    out["a_capture_raw"] = DAYS * sum(objects_per_day.values())
    out["a_capture_logs"] = DAYS * logs_per_day
    out["a_capture_state"] = DAYS * cap_p["state_writes_per_static_pass"] * cap_p["static_captures_per_day"]
    out["b_capture"] = DAYS * cap_p["class_b_per_day"]
    # Bronze: the pipeline's LISTs (Class A) and one GET per new object (Class B); month 1 adds the backlog's day
    # prefixes, one LIST of the history prefix, the archives' upload (PUT) and a GET of every backlog object.
    all_pages = sum(day_pages(o) for o in objects_per_day.values())
    dyn = [o for f, o in objects_per_day.items() if f in dynamic]
    if kind == "24/7":
        runs = 1440 // sc["cadence"]
        static_pages = sum(day_pages(o) for f, o in objects_per_day.items() if f not in dynamic)
        lists = DAYS * (sum(run_pages(o, runs) for o in dyn) + static_pages)
    else:
        runs_per_day = 1440 // sc_p["live_cadence_min"]
        live_runs = sc["live_hours"] * 60 / sc_p["live_cadence_min"]
        lists = ((DAYS + sc["catch_ups"]) * all_pages
                 + live_runs * sum(run_pages(o, runs_per_day) / runs_per_day for o in dyn))
    lists += BACKLOG * all_pages + 1
    out["a_bronze_pipeline"] = lists + history_archives
    out["b_bronze_get"] = (DAYS + BACKLOG) * sum(objects_per_day.values()) + history_archives
    # Silver and gold
    for t in tables():
        act = initial_load(t) + (activity_24_7(t, sc["cadence"]) if kind == "24/7"
                                 else activity_on_demand(t, sc["catch_ups"], sc["live_hours"]))
        out[f"a_{t['layer']}"] += act.class_a()
        out[f"b_{t['layer']}"] += act.class_b()
    out["a_total"] = sum(v for k, v in out.items() if k.startswith("a_"))
    out["b_total"] = sum(v for k, v in out.items() if k.startswith("b_"))
    out["usd_class_a"] = max(0.0, out["a_total"] - prices["free_class_a"]) * prices["class_a_usd_per_million"] / 1e6
    out["usd_class_b"] = max(0.0, out["b_total"] - prices["free_class_b"]) * prices["class_b_usd_per_million"] / 1e6
    return out


judged = sc_p["judged"]
CELLS = [
    (f"24/7 {LIVE_CADENCE_24_7_MIN} min", cell("24/7", cadence=LIVE_CADENCE_24_7_MIN)),
    (f"on-demand {judged['catch_ups']} catch-ups + {judged['live_hours']:g} h live",
     cell("on-demand", catch_ups=judged["catch_ups"], live_hours=judged["live_hours"])),
]
ROWS = [
    ("Class A", [("capture raw/ [Class A ops]", "a_capture_raw"), ("capture logs/ [Class A ops]", "a_capture_logs"),
                 ("capture state/ [Class A ops]", "a_capture_state"), ("bronze LIST+PUT [Class A ops]", "a_bronze_pipeline"),
                 ("silver [Class A ops]", "a_silver"), ("gold [Class A ops]", "a_gold"),
                 ("total [Class A ops]", "a_total"), ("cost after free quota [USD]", "usd_class_a")]),
    ("Class B", [("capture [Class B ops]", "b_capture"), ("bronze GET [Class B ops]", "b_bronze_get"),
                 ("silver [Class B ops]", "b_silver"), ("gold [Class B ops]", "b_gold"),
                 ("total [Class B ops]", "b_total"), ("cost after free quota [USD]", "usd_class_b")]),
]

model = {name: next(r for r in model_rows if r["scenario"] == name and r["month"] == "1") for name, _ in CELLS}
print(f"month 1: {start} to {next_month}, {DAYS} days; backlog {BACKLOG} days; history {history_days} days, "
      f"{history_archives} archives; N = {N}")
print(f"A's measures: load {LOAD_BASE:g} + {PER_JSON:g}/JSON (mean {LOAD:g} at N = {N}), {PER_FILE:g} B per file, "
      f"checkpoint +{CKPT_A:g} A +{CKPT_B:g} B at N = {delta['measured_checkpoint_interval']}, "
      f"optimize {OPT_A:g} A + load + {OPT_B_FIXED:g} B + per file, vacuum {VAC_A:g} A + load + {VAC_B_FIXED:g} B")
mismatches = 0
for title, rows in ROWS:
    print(f"\n{title:<32}" + "".join(f"{name:>32}   " for name, _ in CELLS))
    print(f"{'':<32}" + f"{'hand':>16}{'model':>16}   " * len(CELLS))
    for label, key in rows:
        line = f"{label:<32}"
        for name, hand in CELLS:
            m = num(model[name], key)
            ok = math.isclose(hand[key], m, rel_tol=1e-9, abs_tol=1e-6)
            mismatches += not ok
            line += f"{hand[key]:>16,.2f}{m:>16,.2f} {'✅' if ok else '❌'}"
        print(line)
print(f"\n{'all rows match' if not mismatches else f'{mismatches} rows differ'}")
sys.exit(1 if mismatches else 0)
