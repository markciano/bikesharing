"""R2 operations and storage per bucket over d008's cost window (DI15).

Queries Cloudflare's GraphQL Analytics API with the token in the shell's
CF_ANALYTICS_API_TOKEN (Account Analytics: Read), for bikesharing-bronze and
bikesharing-lakehouse, over [2026-11-21T03:00Z, 2026-11-23T03:00Z):

  operations  r2OperationsAdaptiveGroups: requests per actionType and actionStatus
              (the query of s010 Step 5, sampled, so only totals are compared, F14)
  storage     r2StorageAdaptiveGroups: objectCount and payloadSize at the first
              and last sample of the window

Prints the API's figures only; never prints the token. Standard library only.
"""

import json
import os
import sys
import time
import urllib.request

ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
BUCKETS = ["bikesharing-bronze", "bikesharing-lakehouse"]
START, END = "2026-11-21T03:00:00Z", "2026-11-23T03:00:00Z"
URL = "https://api.cloudflare.com/client/v4/graphql"

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

t0 = time.monotonic()
token = os.environ.get("CF_ANALYTICS_API_TOKEN")
if not token:
    sys.exit("Missing CF_ANALYTICS_API_TOKEN in the shell's environment.")

for bucket in BUCKETS:
    body = json.dumps({"query": QUERY, "variables": {
        "acc": ACCOUNT_ID, "b": bucket, "s": START, "e": END}}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        sys.exit(f"{bucket}: {data['errors']}")
    account = data["data"]["viewer"]["accounts"][0]

    print(f"\n== {bucket}  {START} .. {END}")
    print(f"{'actionType':<34}{'status':<12}{'requests':>10}")
    total = 0
    for g in sorted(account["ops"], key=lambda g: g["dimensions"]["actionType"]):
        d, n = g["dimensions"], g["sum"]["requests"]
        total += n
        print(f"{d['actionType']:<34}{d['actionStatus']:<12}{n:>10,}")
    print(f"{'total':<46}{total:>10,}")

    samples = account["storage"]
    if samples:
        for label, s in (("first", samples[0]), ("last", samples[-1])):
            m = s["max"]
            print(f"storage {label:<6}{s['dimensions']['datetime']}  objects {m['objectCount']:,}  "
                  f"payload {m['payloadSize'] / 1e9:.3f} GB  metadata {m['metadataSize'] / 1e6:.1f} MB")
    else:
        print("storage: no samples")
print(f"\nElapsed: {time.monotonic() - t0:.0f} s")
