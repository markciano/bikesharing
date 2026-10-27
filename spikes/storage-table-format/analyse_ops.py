# Analysis of s010 probe A: joins the proxy log (r2_proxy.py) and the run's probe log (delta_probe.py
# full and extra) by time window into R2 operations per check, per operation window and per class,
# and runs the three analysis checks of §2 A.
#
# Attribution: a request belongs to the check whose window holds its start time; inside a check, to the
# operation window that holds it (a commit, a load, a vacuum), or else to the check's verification reads;
# requests in a measure window are the probe's own log reads. C takes the operation windows of the
# full checks. Counts are for the test bucket only; requests to other buckets are filtered out.
# Input:  output/probe-<run_id>.jsonl and the proxy log given; R2 metrics of the day, if known.
# Output: output/ops-<run_id>-by-check.csv, -by-op.csv, -by-class.csv and output/analysis-<run_id>.json.
#
# Usage: uv run python analyse_ops.py --run-id ID --proxy-log output/proxy-<UTC start>.jsonl
#                                     [--r2-class-a N --r2-class-b N]
#        uv run python analyse_ops.py --synthetic   (self-check on generated logs in output/local/)

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from r2_proxy import classify

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "output"
CLASSES = ("A", "B", "free", "unknown")


def ts(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def ok(req: dict) -> bool:
    return req["status"] is not None and 200 <= req["status"] < 300


def is_log_put(req: dict) -> bool:
    return req["operation"] == "PutObject" and "/_delta_log/" in f"/{req['key']}" and req["key"].endswith(".json")


def is_data_put(req: dict) -> bool:
    return req["operation"] == "PutObject" and "/_delta_log/" not in f"/{req['key']}"


# --- Attribution ------------------------------------------------------------


def attribute(req: dict, lines: list[dict]) -> dict:
    t = req["ts"]
    for i, line in enumerate(lines):
        if ts(line["start"]) <= t <= ts(line["end"]):
            for j, op in enumerate(line.get("ops", [])):
                if ts(op["start"]) <= t <= ts(op["end"]):
                    return {"line": i, "part": "op", "op": j}
            return {"line": i, "part": "verify", "op": None}
        measure = line.get("measure")
        if measure and ts(measure["start"]) <= t <= ts(measure["end"]):
            return {"line": i, "part": "measure", "op": None}
    return {"line": None, "part": "unattributed", "op": None}


def class_counts(reqs: list[dict]) -> dict:
    counts = Counter(r["class"] for r in reqs)
    failed = Counter(r["class"] for r in reqs if not ok(r))
    return {c: counts[c] for c in CLASSES} | {f"{c}_failed": failed[c] for c in CLASSES}


# --- Analysis checks (§2 A) -------------------------------------------------


def known_arithmetic(lines, reqs) -> dict:
    # One append of one file, on a commit that writes no checkpoint, gives one data PUT and one log PUT.
    cases, failures = 0, []
    for i, line in enumerate(lines):
        if line.get("phase") != "full" or line["check"] != "write":
            continue
        for j, op in enumerate(line.get("ops", [])):
            if op.get("handle_version") is None or op.get("files_added") != 1 or op.get("checkpoint"):
                continue
            cases += 1
            puts = [r for r in reqs if r["at"]["line"] == i and r["at"]["op"] == j and ok(r)]
            data, log = sum(map(is_data_put, puts)), sum(map(is_log_put, puts))
            if (data, log) != (1, 1):
                failures.append({"op": j, "versions": op.get("versions"), "data_puts": data, "log_puts": log})
    result = "ok" if cases and not failures else "FAIL"
    return {"result": result, "cases": cases, "failures": failures}


def independent_count(totals: dict, metrics: dict | None) -> dict:
    # The proxy's totals for the test bucket against its R2 metrics for the day, with and without failed
    # requests (R2's billing of them is undocumented, #28); `unknown` operations are tried as A, B or neither.
    if not metrics:
        return {"result": "skipped (no R2 metrics given)"}
    matches = []
    for basis in ("all", "ok_only"):
        a, b, u = (totals[basis][c] for c in ("A", "B", "unknown"))
        for unknown_as, (ca, cb) in (("none", (a, b)), ("A", (a + u, b)), ("B", (a, b + u))):
            if (ca, cb) == (metrics["A"], metrics["B"]):
                matches.append({"basis": basis, "unknown_as": unknown_as})
    return {"result": "ok" if matches else "FAIL", "metrics": metrics, "matches": matches}


def fault_injection(lines, reqs) -> dict:
    # Each stale pair of `concurrent` shows a log PUT rejected with 412, then a successful log PUT
    # (the stale append retried) or a raised conflict (the stale MERGE).
    pairs = {}
    for line in lines:
        if line.get("phase") != "full" or line["check"] != "concurrent" or line["result"] != "ok":
            continue
        for name in ("merge_pair", "append_pair"):
            pair = line["details"][name]
            inside = sorted((r for r in reqs if ts(pair["start"]) <= r["ts"] <= ts(pair["end"])),
                            key=lambda r: r["ts"])
            rejected = [r for r in inside if is_log_put(r) and r["status"] == 412]
            retried = rejected and any(is_log_put(r) and ok(r) and r["ts"] > rejected[0]["ts"] for r in inside)
            conflict = pair["outcome"].startswith("conflict")
            pairs[name] = {
                "outcome": "conflict" if conflict else pair["outcome"],
                "rejected_log_puts": len(rejected),
                "result": "ok" if rejected and (retried if not conflict else True) else "FAIL",
            }
    result = "ok" if len(pairs) == 2 and all(p["result"] == "ok" for p in pairs.values()) else "FAIL"
    return {"result": result, "pairs": pairs}


# --- Run --------------------------------------------------------------------


def analyse(lines: list[dict], proxy: list[dict], bucket: str, metrics: dict | None) -> dict:
    for req in proxy:
        req["at"] = attribute(req, lines)
    test = [r for r in proxy if r["bucket"] == bucket]

    by_check, by_op = [], []
    for i, line in enumerate(lines):
        mine = [r for r in test if r["at"]["line"] == i]
        for part in ("op", "verify", "measure"):
            in_part = [r for r in mine if r["at"]["part"] == part]
            if in_part:
                by_check.append({"phase": line.get("phase"), "check": line["check"], "part": part,
                                 "taken_by_c": line.get("phase") == "full" and part == "op",
                                 "requests": len(in_part)} | class_counts(in_part))
        for j, op in enumerate(line.get("ops", [])):
            in_op = [r for r in mine if r["at"]["op"] == j]
            ops = Counter(r["operation"] for r in in_op)
            by_op.append({
                "check": line["check"], "index": j, "op": op["op"],
                "versions": " ".join(map(str, op.get("versions", []))),
                **{k: op.get(k) for k in ("handle_version", "json_commits_loaded", "checkpoint", "partition_files",
                                          "files_added", "files_removed", "bytes_added", "json_bytes", "latency_ms")},
                "requests": len(in_op), **class_counts(in_op),
                "operations": " ".join(f"{k}:{v}" for k, v in sorted(ops.items())),
            })

    totals = {
        "all": {c: sum(r["class"] == c for r in test) for c in CLASSES},
        "ok_only": {c: sum(r["class"] == c and ok(r) for r in test) for c in CLASSES},
    }
    # A check whose client bypassed the proxy has no proxied request at all, to any bucket.
    bypass = [
        line["check"] for i, line in enumerate(lines)
        if line.get("proxied", True) and not any(r["at"]["line"] == i and r["at"]["part"] != "measure" for r in proxy)
    ]
    return {
        "by_check": by_check,
        "by_op": by_op,
        "totals": totals,
        "unattributed_test_bucket": sum(r["at"]["part"] == "unattributed" for r in test),
        "other_buckets": dict(Counter(str(r["bucket"]) for r in proxy if r["bucket"] != bucket)),
        "bypassed_proxy": bypass,
        "checks": {
            "known_arithmetic": known_arithmetic(lines, test),
            "independent_count": independent_count(totals, metrics),
            "fault_injection": fault_injection(lines, test),
        },
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def report(result: dict, run_id: str, out_dir: Path) -> None:
    write_csv(out_dir / f"ops-{run_id}-by-check.csv", result["by_check"])
    write_csv(out_dir / f"ops-{run_id}-by-op.csv", result["by_op"])
    write_csv(out_dir / f"ops-{run_id}-by-class.csv",
              [{"class": c, "all": result["totals"]["all"][c], "ok_only": result["totals"]["ok_only"][c]}
               for c in CLASSES])
    summary = {k: v for k, v in result.items() if k not in ("by_check", "by_op")}
    (out_dir / f"analysis-{run_id}.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(f"{'phase':<7}{'check':<12}{'part':<9}{'C':<3}" + "".join(f"{c:>9}" for c in CLASSES))
    for row in result["by_check"]:
        print(f"{row['phase'] or '-':<7}{row['check']:<12}{row['part']:<9}{'x' if row['taken_by_c'] else '':<3}"
              + "".join(f"{row[c]:>9}" for c in CLASSES))
    for basis, counts in result["totals"].items():
        print(f"total {basis:<22}" + "".join(f"{counts[c]:>9}" for c in CLASSES))
    print(f"unattributed (test bucket): {result['unattributed_test_bucket']}; "
          f"other buckets: {result['other_buckets']}")
    if result["bypassed_proxy"]:
        print(f"FLAG no proxied request, client bypassed the proxy: {', '.join(result['bypassed_proxy'])}")
    for name, check in result["checks"].items():
        print(f"{name:<18} {check['result']}")
    print(f"\noutput: {out_dir.relative_to(HERE)}/ops-{run_id}-*.csv, analysis-{run_id}.json")


# --- Synthetic self-check ---------------------------------------------------

T0 = 1_800_000_000.0
HOST = "acct.r2.cloudflarestorage.com"
TABLE = "/test-bucket/synthetic/station_status"


def iso(offset: float) -> str:
    return datetime.fromtimestamp(T0 + offset, UTC).isoformat()


def request(offset: float, method: str, path: str, status: int = 200, headers: dict | None = None) -> dict:
    return {"ts": T0 + offset, "time": iso(offset), "host": HOST, "method": method, "path": path, "status": status,
            **classify(method, HOST, path, headers or {})}


def synthetic_logs() -> tuple[list[dict], list[dict]]:
    log = TABLE + "/_delta_log/"
    data = TABLE + "/capture_date=2026-10-15/part-{}.parquet"
    put_if_absent = {"If-None-Match": "*"}
    lst = f"/test-bucket?list-type=2&prefix=synthetic/station_status/_delta_log/"
    op = lambda name, a, b, **kw: {"op": name, "start": iso(a), "end": iso(b), **kw}
    lines = [
        {"phase": "full", "check": "write", "start": iso(0), "end": iso(10), "result": "ok", "details": {},
         "ops": [op("append", 1, 2, handle_version=None, files_added=1, checkpoint=False, versions=[0]),
                 op("append", 3, 5, handle_version=0, files_added=1, checkpoint=False, versions=[1])],
         "measure": {"start": iso(11), "end": iso(12)}},
        {"phase": "full", "check": "concurrent", "start": iso(20), "end": iso(40), "result": "ok",
         "details": {"merge_pair": {"start": iso(20), "end": iso(28), "outcome": "conflict: concurrent data"},
                     "append_pair": {"start": iso(30), "end": iso(38), "outcome": "retried"}},
         "ops": [op("load", 20, 21), op("load", 21, 22), op("merge", 22, 24), op("merge", 24, 27),
                 op("merge", 28.5, 29.5), op("load", 30, 31), op("load", 31, 32), op("append", 32, 34),
                 op("append", 34, 37)]},
        {"phase": "full", "check": "vacuum", "start": iso(60), "end": iso(70), "result": "ok", "details": {},
         "ops": [op("vacuum_dry_run", 61, 62), op("vacuum", 63, 66)]},
        {"phase": "extra", "check": "polars", "start": iso(80), "end": iso(85), "result": "ok", "proxied": True},
        {"phase": "extra", "check": "token", "start": iso(90), "end": iso(95), "result": "ok", "proxied": True},
    ]
    proxy = [
        # write: create (data + log PUT), append (list, read, data + log PUT), a verify HEAD, measure reads
        request(1.1, "PUT", data.format(0)), request(1.2, "PUT", log + f"{0:020}.json", headers=put_if_absent),
        request(3.1, "GET", lst), request(3.2, "GET", log + f"{0:020}.json"),
        request(3.3, "PUT", data.format(1)), request(3.4, "PUT", log + f"{1:020}.json", headers=put_if_absent),
        request(6, "HEAD", log + f"{1:020}.json"),
        request(11.1, "GET", lst), request(11.2, "GET", log + f"{0:020}.json"),
        request(11.3, "GET", log + f"{1:020}.json"),
        # concurrent, MERGE pair: two loads, A commits, B is rejected (412), reads the winner, a 500, a retry
        request(20.5, "GET", lst), request(21.5, "GET", lst),
        request(22.5, "PUT", data.format(2)), request(23, "PUT", log + f"{2:020}.json", headers=put_if_absent),
        request(24.5, "PUT", data.format(3)), request(25, "PUT", log + f"{2:020}.json", 412, put_if_absent),
        request(25.5, "GET", log + f"{2:020}.json"), request(26, "GET", log + f"{2:020}.json", 500),
        request(29, "PUT", data.format(4)), request(29.2, "PUT", log + f"{3:020}.json", headers=put_if_absent),
        # concurrent, append pair: two loads, A commits, B is rejected (412) and retried on the next version
        request(30.5, "GET", lst), request(31.5, "GET", lst),
        request(32.5, "PUT", data.format(5)), request(33, "PUT", log + f"{4:020}.json", headers=put_if_absent),
        request(34.5, "PUT", data.format(6)), request(35, "PUT", log + f"{4:020}.json", 412, put_if_absent),
        request(35.5, "GET", log + f"{4:020}.json"), request(36, "PUT", log + f"{5:020}.json", headers=put_if_absent),
        # between checks: an unattributed read
        request(50, "GET", log + f"{5:020}.json"),
        # vacuum: listings, a bulk delete (unknown class), a single delete (free), two log commits
        request(61.5, "GET", lst), request(63.5, "GET", lst), request(64, "POST", "/test-bucket?delete"),
        request(64.5, "DELETE", data.format(0), 204),
        request(65, "PUT", log + f"{6:020}.json", headers=put_if_absent),
        request(65.5, "PUT", log + f"{7:020}.json", headers=put_if_absent),
        # extra: polars sends nothing through the proxy; token requests go to another bucket
        request(91, "GET", "/prod-bucket?list-type=2&max-keys=1", 403),
        request(92, "GET", "/prod-bucket/raw/ambici/x.json.gz", 403),
        request(93, "PUT", "/prod-bucket/s010-token-check/canary.txt", 403),
    ]
    return lines, proxy


# Hand-counted from synthetic_logs().
SYNTHETIC_EXPECTED = {
    "totals": {"all": {"A": 25, "B": 8, "free": 1, "unknown": 1},
               "ok_only": {"A": 23, "B": 7, "free": 1, "unknown": 1}},
    "per_check": {"write": {"A": 6, "B": 4}, "concurrent": {"A": 15, "B": 3}, "vacuum": {"A": 4, "unknown": 1, "free": 1}},
    "write_parts": {"op": {"A": 5, "B": 1}, "verify": {"B": 1}, "measure": {"A": 1, "B": 2}},
    "unattributed_test_bucket": 1,
    "other_buckets": {"prod-bucket": 3},
    "bypassed_proxy": ["polars"],
    "known_arithmetic": {"result": "ok", "cases": 1},
    "independent_count": {"result": "ok", "matches": [{"basis": "ok_only", "unknown_as": "A"}]},
    "fault_injection": "ok",
}

CLASSIFIER_CASES = [
    # (method, host, path, headers) -> (bucket, key, operation)
    (("GET", HOST, "/", {}), (None, "", "ListBuckets")),
    (("HEAD", HOST, "/b", {}), ("b", "", "HeadBucket")),
    (("GET", HOST, "/b?list-type=2&prefix=x%2F", {}), ("b", "", "ListObjectsV2")),
    (("GET", HOST, "/b?uploads", {}), ("b", "", "ListMultipartUploads")),
    (("GET", HOST, "/b/k%3D1/f.parquet", {}), ("b", "k=1/f.parquet", "GetObject")),
    (("HEAD", "b." + HOST, "/k", {}), ("b", "k", "HeadObject")),
    (("PUT", HOST, "/b/k", {"X-Amz-Copy-Source": "b/j"}), ("b", "k", "CopyObject")),
    (("PUT", HOST, "/b/k?partNumber=1&uploadId=u", {}), ("b", "k", "UploadPart")),
    (("POST", HOST, "/b/k?uploads", {}), ("b", "k", "CreateMultipartUpload")),
    (("POST", HOST, "/b/k?uploadId=u", {}), ("b", "k", "CompleteMultipartUpload")),
    (("DELETE", HOST, "/b/k?uploadId=u", {}), ("b", "k", "AbortMultipartUpload")),
    (("POST", HOST, "/b?delete", {}), ("b", "", "DeleteObjects")),
]


def run_synthetic() -> int:
    errors = []
    for args, expected in CLASSIFIER_CASES:
        c = classify(*args)
        if (c["bucket"], c["key"], c["operation"]) != expected:
            errors.append(f"classify{args[:3]}: {(c['bucket'], c['key'], c['operation'])} != {expected}")

    out_dir = OUTPUT_DIR / "local"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines, proxy = synthetic_logs()
    probe_path, proxy_path = out_dir / "probe-synthetic.jsonl", out_dir / "proxy-synthetic.jsonl"
    probe_path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    proxy_path.write_text("".join(json.dumps(r) + "\n" for r in proxy))
    result = analyse(load_jsonl(probe_path), load_jsonl(proxy_path), "test-bucket", {"A": 24, "B": 7})
    report(result, "synthetic", out_dir)

    exp = SYNTHETIC_EXPECTED
    got_check = Counter()
    for row in result["by_check"]:
        for c in CLASSES:
            got_check[(row["check"], c)] += row[c]
            if row["check"] == "write":
                got_check[("write", row["part"], c)] += row[c]
    actual = {
        "totals": result["totals"],
        "per_check": {k: {c: got_check[(k, c)] for c in v} for k, v in exp["per_check"].items()},
        "write_parts": {p: {c: got_check[("write", p, c)] for c in v} for p, v in exp["write_parts"].items()},
        "unattributed_test_bucket": result["unattributed_test_bucket"],
        "other_buckets": result["other_buckets"],
        "bypassed_proxy": result["bypassed_proxy"],
        "known_arithmetic": {k: result["checks"]["known_arithmetic"][k] for k in ("result", "cases")},
        "independent_count": {k: result["checks"]["independent_count"][k] for k in ("result", "matches")},
        "fault_injection": result["checks"]["fault_injection"]["result"],
    }
    errors += [f"{k}: got {actual[k]}, expected {v}" for k, v in exp.items() if actual[k] != v]
    print("\nsynthetic self-check: " + ("ok" if not errors else "FAIL\n  " + "\n  ".join(errors)))
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="s010 probe A: R2 operations per check, operation and class")
    parser.add_argument("--run-id", help="run_id printed by delta_probe.py full")
    parser.add_argument("--proxy-log", type=Path, help="output/proxy-<UTC start>.jsonl covering the run")
    parser.add_argument("--r2-class-a", type=int, help="Class A operations of the test bucket in R2 metrics, that day")
    parser.add_argument("--r2-class-b", type=int, help="Class B operations of the test bucket in R2 metrics, that day")
    parser.add_argument("--synthetic", action="store_true", help="self-check on generated logs in output/local/")
    args = parser.parse_args()
    if args.synthetic:
        return run_synthetic()
    if not args.run_id or not args.proxy_log:
        parser.error("--run-id and --proxy-log are required")
    if (args.r2_class_a is None) != (args.r2_class_b is None):
        parser.error("--r2-class-a and --r2-class-b go together")

    load_dotenv(HERE / ".env")
    bucket = os.environ.get("R2_TEST_BUCKET") or sys.exit("Missing in .env: R2_TEST_BUCKET")
    probe_path = OUTPUT_DIR / f"probe-{args.run_id}.jsonl"
    lines = [line for line in load_jsonl(probe_path) if line.get("phase") in ("full", "extra")]
    if not lines:
        sys.exit(f"No full or extra lines in {probe_path.relative_to(HERE)}")
    metrics = {"A": args.r2_class_a, "B": args.r2_class_b} if args.r2_class_a is not None else None
    result = analyse(lines, load_jsonl(args.proxy_log), bucket, metrics)
    report(result, args.run_id, OUTPUT_DIR)
    failed = [n for n, c in result["checks"].items() if c["result"] == "FAIL"]
    return 1 if failed or result["bypassed_proxy"] else 0


if __name__ == "__main__":
    sys.exit(main())
