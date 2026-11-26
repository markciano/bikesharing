"""Log cut of s019 Probe B: rewinds both tables in the copy's bucket to a pass's instant.

A pass is set by one of `processed_objects`' checkpoints in production: the latest
(pass 1) or the one before it (pass 2). With H the UTC hour of that checkpoint's
commit, the pass's production hour is H - 1, and its version N of
`processed_objects` is the one read by that hour's last run: the version of the
hour's last commit, minus 1. The pass's instant is the date of N's commit, and
`station_stock`'s version is its latest commit at or before that instant.

For each table, the cut lists `_delta_log/` in the copy's bucket (so that what an
earlier pass wrote is also found), rewrites `_last_checkpoint` to the latest
checkpoint at or before the pass's version, then deletes every log object of a
later version, newest first, so the log stays a valid prefix at every point.
Data files are not touched: those added after the cut are orphaned.

It talks to R2 straight with boto3, not through the counting proxy, and its
bucket is a constant: nothing here can reach production.

Inputs:  data/copy/delta-log.txt (production's log dates, RFC 3339 with offset),
         and .env with the copy token (as proxy.py).
Outputs: the copy's logs, cut; per table, the pass's version, its commits since
         the last checkpoint and the objects deleted; the production hour H - 1
         and the commits of `processed_objects` in it.

Usage:   uv run python count-per-call/cut_log.py --pass 1|2
"""

import argparse
import json
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from proxy import BUCKET, PROCESSED_OBJECTS_PATH, SPIKE_DIR, STATION_STOCK_PATH, TABLES, read_env

DELTA_LOG_DATES = SPIKE_DIR / "data" / "copy" / "delta-log.txt"

# The only log object names the cut knows (Delta protocol, "Delta Log Entries"). Any other
# name in `_delta_log/` stops it before anything is changed.
COMMIT = re.compile(r"^(\d{20})\.json$")
CHECKPOINT = re.compile(r"^(\d{20})\.checkpoint\.parquet$")
LAST_CHECKPOINT = "_last_checkpoint"


@dataclass
class TableLog:
    """Production's log dates of one table, in UTC."""

    commits: dict[int, datetime] = field(default_factory=dict)
    checkpoints: list[int] = field(default_factory=list)


@dataclass
class Plan:
    checkpoint: int           # version of the production checkpoint that sets the pass
    hour: datetime            # production hour H - 1, UTC
    commits_in_hour: int      # commits of processed_objects in that hour
    instant: datetime         # date of the commit of processed_objects' version N
    versions: dict[str, int]  # the pass's version per table


def read_log_dates(path=DELTA_LOG_DATES) -> dict[str, TableLog]:
    """Parse `<RFC 3339>;<key>` lines into each table's commit and checkpoint dates."""
    logs = {table: TableLog() for table in TABLES}
    for line in path.read_text().splitlines():
        stamp, _, key = line.partition(";")
        table = next(t for t in TABLES if key.startswith(f"{t}/_delta_log/"))
        name = key.removeprefix(f"{table}/_delta_log/")
        # rclone prints the local offset; fromisoformat keeps it, astimezone converts.
        when = datetime.fromisoformat(stamp).astimezone(UTC)
        if m := COMMIT.match(name):
            logs[table].commits[int(m[1])] = when
        elif m := CHECKPOINT.match(name):
            logs[table].checkpoints.append(int(m[1]))
    for log in logs.values():
        log.checkpoints.sort()
    return logs


def plan(pass_no: int, logs: dict[str, TableLog]) -> Plan:
    """Return the versions and production hour of pass 1 or 2."""
    po, ss = logs[PROCESSED_OBJECTS_PATH], logs[STATION_STOCK_PATH]
    checkpoint = po.checkpoints[-pass_no]
    # A checkpoint at version C is written by the run that commits C, right after it.
    h = po.commits[checkpoint].replace(minute=0, second=0, microsecond=0)
    hour = h - timedelta(hours=1)
    in_hour = [v for v, t in po.commits.items() if hour <= t < h]
    if not in_hour:
        raise SystemExit(f"No commit of {PROCESSED_OBJECTS_PATH} in {hour:%Y-%m-%dT%H}Z.")
    # The hour's last run reads the version before the one it commits.
    version = max(in_hour) - 1
    instant = po.commits[version]
    ss_version = max(v for v, t in ss.commits.items() if t <= instant)
    return Plan(checkpoint, hour, len(in_hour), instant,
                {STATION_STOCK_PATH: ss_version, PROCESSED_OBJECTS_PATH: version})


def r2_client():
    """A boto3 S3 client on R2 with the copy token."""
    import boto3
    from botocore.config import Config

    env = read_env()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_COPY_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_COPY_SECRET_ACCESS_KEY"],
        region_name="auto",
        # Checksums only where S3 requires them, as R2's boto3 guidance sets.
        config=Config(request_checksum_calculation="when_required",
                      response_checksum_validation="when_required"),
    )


def list_log(s3, table: str) -> dict[str, int]:
    """Return each object of the table's `_delta_log/` in the copy, with its size."""
    objects = {}
    for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=BUCKET, Prefix=f"{table}/_delta_log/"):
        for obj in page.get("Contents", []):
            objects[obj["Key"]] = obj["Size"]
    return objects


def checkpoint_rows(s3, key: str) -> int:
    """Return the row count of a checkpoint file: the actions `_last_checkpoint` calls size."""
    import duckdb

    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        s3.download_fileobj(BUCKET, key, tmp)
        tmp.flush()
        return duckdb.sql(f"SELECT count(*) FROM read_parquet('{tmp.name}')").fetchone()[0]


def cut(s3, table: str, version: int) -> dict:
    """Cut one table's log in the copy at `version`; return what was done."""
    prefix = f"{table}/_delta_log/"
    commits, checkpoints, later = {}, {}, []
    for key, size in list_log(s3, table).items():
        name = key.removeprefix(prefix)
        if name == LAST_CHECKPOINT:
            continue
        if m := COMMIT.match(name):
            commits[int(m[1])] = key
        elif m := CHECKPOINT.match(name):
            checkpoints[int(m[1])] = (key, size)
        else:
            raise SystemExit(f"Unknown log object {key}: nothing changed.")
        if int(m[1]) > version:
            later.append((int(m[1]), key))
    latest = max(commits)
    if latest < version:
        raise SystemExit(f"{table} is at version {latest} in the copy, below the pass's {version}: "
                         "an earlier cut went further back; copy the tables again (Step 2).")
    cp = max(v for v in checkpoints if v <= version)
    cp_key, cp_bytes = checkpoints[cp]
    last_checkpoint = {"version": cp, "size": checkpoint_rows(s3, cp_key)}
    s3.put_object(Bucket=BUCKET, Key=prefix + LAST_CHECKPOINT,
                  Body=json.dumps(last_checkpoint).encode())
    for _, key in sorted(later, reverse=True):
        s3.delete_object(Bucket=BUCKET, Key=key)
    return {"latest": latest, "checkpoint": cp, "last_checkpoint": last_checkpoint,
            "deleted": len(later)}


def main(pass_no: int) -> None:
    t0 = time.monotonic()
    p = plan(pass_no, read_log_dates())
    print(f"cut: pass {pass_no}, set by {PROCESSED_OBJECTS_PATH}'s checkpoint {p.checkpoint}")
    print(f"cut: production hour {p.hour:%Y-%m-%dT%H:%M}Z, "
          f"{p.commits_in_hour} commits of {PROCESSED_OBJECTS_PATH} (4 when its runs all read before the checkpoint)")
    print(f"cut: pass instant {p.instant:%Y-%m-%dT%H:%M:%S}Z")
    s3 = r2_client()
    print(f"{'table':<28}{'from':>6}{'to':>6}{'checkpoint':>12}{'since':>7}{'deleted':>9}")
    for table in TABLES:
        version = p.versions[table]
        done = cut(s3, table, version)
        print(f"{table:<28}{done['latest']:>6}{version:>6}{done['checkpoint']:>12}"
              f"{version - done['checkpoint']:>7}{done['deleted']:>9}")
        print(f"  _last_checkpoint: {json.dumps(done['last_checkpoint'])}")
    print(f"Elapsed: {time.monotonic() - t0:.1f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pass", dest="pass_no", type=int, choices=(1, 2), required=True,
                        help="1: before processed_objects' latest checkpoint; 2: before the one before it")
    main(parser.parse_args().pass_no)
