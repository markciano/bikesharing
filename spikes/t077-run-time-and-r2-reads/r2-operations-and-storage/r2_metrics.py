"""R2 operations and storage per bucket over d008's cost window (DI15).

Queries Cloudflare's GraphQL Analytics API with the token in the shell's
CF_ANALYTICS_API_TOKEN (Account Analytics: Read), for bikesharing-bronze and
bikesharing-lakehouse, over [2026-11-21T03:00Z, 2026-11-23T03:00Z):

  operations  r2OperationsAdaptiveGroups: requests per actionType and actionStatus
              (the query of s010 Step 5, sampled, so only totals are compared, F14)
  storage     r2StorageAdaptiveGroups: objectCount and payloadSize at the first
              and last sample of the window

s019 Probe B adds optional --bucket, --start and --end (whole UTC minutes, as
YYYY-MM-DDTHH:MM:00Z), and each bucket's GetObject, Class B and Class A
totals, classed as count-per-call/proxy.py classes them. With no arguments
it prints the baseline's figures.

Prints the API's figures only; never prints the token.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

# The proxy's classification, so both sides of Probe B's check class operations alike.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "count-per-call"))
from proxy import r2_class  # noqa: E402

ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
BUCKETS = ["bikesharing-bronze", "bikesharing-lakehouse"]
START, END = "2026-11-21T03:00:00Z", "2026-11-23T03:00:00Z"
URL = "https://api.cloudflare.com/client/v4/graphql"
MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z$")

QUERY = """
query($acc: String!, $b: String!, $s: Time!, $e: Time!) {
  viewer { accounts(filter: {accountTag: $acc}) {
    ops: r2OperationsAdaptiveGroups(limit: 10000,
        filter: {bucketName: $b, datetime_geq: $s, datetime_lt: $e}) {
      sum { requests } dimensions { actionType actionStatus }
    }
    storage: r2StorageAdaptiveGroups(limit: 10000, orderBy: [datetime_ASC],
        filter: {bucketName: $b, datetime_geq: $s, datetime_lt: $e}) {
      max { objectCount payloadSize metadataSize } dimensions { datetime }
    }
  } }
}
"""


def minute(value: str) -> str:
    if not MINUTE.match(value):
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DDTHH:MM:00Z, got {value!r}")
    return value


parser = argparse.ArgumentParser(description="R2 operations and storage per bucket, from Cloudflare's GraphQL Analytics API.")
parser.add_argument("--bucket", help=f"one bucket (default: {', '.join(BUCKETS)})")
parser.add_argument("--start", type=minute, default=START, help=f"window start, inclusive (default: {START})")
parser.add_argument("--end", type=minute, default=END, help=f"window end, exclusive (default: {END})")
args = parser.parse_args()
buckets = [args.bucket] if args.bucket else BUCKETS
if args.start >= args.end:
    sys.exit("--start must be before --end.")

t0 = time.monotonic()
token = os.environ.get("CF_ANALYTICS_API_TOKEN")
if not token:
    sys.exit("Missing CF_ANALYTICS_API_TOKEN in the shell's environment.")

for bucket in buckets:
    body = json.dumps({"query": QUERY, "variables": {
        "acc": ACCOUNT_ID, "b": bucket, "s": args.start, "e": args.end}}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        sys.exit(f"{bucket}: {data['errors']}")
    account = data["data"]["viewer"]["accounts"][0]

    print(f"\n== {bucket}  {args.start} .. {args.end}")
    print(f"{'actionType':<34}{'status':<12}{'requests':>10}")
    total = 0
    by_class = {"GetObject": 0, "B": 0, "A": 0, "other": 0}
    for g in sorted(account["ops"], key=lambda g: g["dimensions"]["actionType"]):
        d, n = g["dimensions"], g["sum"]["requests"]
        total += n
        cls = r2_class(d["actionType"])
        by_class[cls if cls in ("A", "B") else "other"] += n
        if d["actionType"] == "GetObject":
            by_class["GetObject"] += n
        print(f"{d['actionType']:<34}{d['actionStatus']:<12}{n:>10,}")
    print(f"{'total':<46}{total:>10,}")
    print(f"GetObject {by_class['GetObject']:,}  Class B other {by_class['B'] - by_class['GetObject']:,}  "
          f"Class B {by_class['B']:,}  Class A {by_class['A']:,}  free/unknown {by_class['other']:,}")

    samples = account["storage"]
    if samples:
        for label, s in (("first", samples[0]), ("last", samples[-1])):
            m = s["max"]
            print(f"storage {label:<6}{s['dimensions']['datetime']}  objects {m['objectCount']:,}  "
                  f"payload {m['payloadSize'] / 1e9:.3f} GB  metadata {m['metadataSize'] / 1e6:.1f} MB")
    else:
        print("storage: no samples")
print(f"\nElapsed: {time.monotonic() - t0:.0f} s")
