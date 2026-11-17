# Probe B of s017: runs one batch window and publishes stg_probe to a local Delta table.
# --mode dbt builds the dbt project through dbtRunner, logs every dbt event to out/events.jsonl
# and prints each node's result as JSON; --mode baseline runs the SQL dbt compiled
# (dbt_project/target/compiled/, from `dbt compile`) directly on DuckDB, with no dbt.
# Both modes then MERGE stg_probe into out/delta/stg_probe and print the Delta row count.
# Run from the spike root with the R2 variables of .env in the environment.

import argparse
import json
import os
from pathlib import Path

import duckdb
from deltalake import DeltaTable, write_deltalake
from google.protobuf.json_format import MessageToDict

from dbt.cli.main import dbtRunner, dbtRunnerResult

OUT = Path("out")
PROJECT = ["--project-dir", "dbt_project", "--profiles-dir", "dbt_project"]
COMPILED = Path("dbt_project/target/compiled/dbt_in_the_pipeline/models/staging")
MODELS = ["base_probe_read", "stg_probe", "stg_probe_quarantine"]
DELTA = OUT / "delta" / "stg_probe"
MERGE_KEY = "t.station_id = s.station_id and t.captured_at = s.captured_at"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one batch of probe B and MERGE stg_probe into Delta.")
    parser.add_argument("--mode", choices=["dbt", "baseline"], required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--feed", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--hour", required=True, help="HH, UTC")
    parser.add_argument("--accepted", nargs="+", help="accepted values of is_renting, as JSON (e.g. true)")
    return parser.parse_args()


def run_dbt(args: argparse.Namespace) -> Path:
    window = {"source": args.source, "feed": args.feed, "date": args.date, "hour": args.hour}
    if args.accepted:
        window["accepted"] = [json.loads(value) for value in args.accepted]
    OUT.mkdir(exist_ok=True)
    with open(OUT / "events.jsonl", "w") as events:

        # The callback only records: one line per event, as dbt emits it.
        def record(event) -> None:
            line = {
                "name": event.info.name,
                "level": event.info.level,
                "data": MessageToDict(event.data, preserving_proto_field_name=True),
            }
            events.write(json.dumps(line) + "\n")

        res: dbtRunnerResult = dbtRunner(callbacks=[record]).invoke(
            ["build", *PROJECT, "--vars", json.dumps(window)]
        )
    if res.result is None:
        raise SystemExit(f"dbt did not run: {res.exception}")
    nodes = [
        {
            "unique_id": r.node.unique_id,
            "status": str(r.status),
            "failures": r.failures,
            "rows_affected": (r.adapter_response or {}).get("rows_affected"),
            "execution_time": round(r.execution_time, 3),
        }
        for r in res.result.results
    ]
    print(json.dumps({"success": res.success, "nodes": nodes}, indent=2))
    return OUT / "scratch.duckdb"


def run_baseline() -> Path:
    db = OUT / "baseline.duckdb"
    for path in (db, db.with_suffix(".duckdb.wal")):
        path.unlink(missing_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    # The same S3 secret as profiles.yml; R2 wants the endpoint without its scheme.
    con.execute(
        "CREATE SECRET r2 (TYPE s3, KEY_ID ?, SECRET ?, ENDPOINT ?, REGION 'auto', URL_STYLE 'path')",
        [
            os.environ["R2_ACCESS_KEY_ID"],
            os.environ["R2_SECRET_ACCESS_KEY"],
            os.environ["R2_ENDPOINT"].removeprefix("https://"),
        ],
    )
    # The compiled SQL names its tables "scratch"."main"."…", so the fresh file is attached as scratch.
    con.execute(f"ATTACH '{db}' AS scratch; USE scratch;")
    for model in MODELS:
        con.execute(f"CREATE TABLE {model} AS {(COMPILED / f'{model}.sql').read_text()}")
    tests = {
        sql.stem: con.sql(f"SELECT count(*) FROM ({sql.read_text()})").fetchone()[0]
        for sql in sorted((COMPILED / "stg_probe.yml").glob("*.sql"))
    }
    con.close()
    print(json.dumps({"tests": tests}, indent=2))
    return db


def publish(db: Path) -> None:
    # dbt-duckdb keeps scratch.duckdb open in this process with the default config; DuckDB
    # rejects a second connection to the same file with another config, such as read_only.
    con = duckdb.connect(str(db))
    table = con.sql("SELECT * FROM stg_probe").to_arrow_table()
    con.close()
    if not DeltaTable.is_deltatable(str(DELTA)):
        write_deltalake(str(DELTA), table)
    else:
        (
            DeltaTable(str(DELTA))
            .merge(table, MERGE_KEY, source_alias="s", target_alias="t")
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute()
        )
    print(json.dumps({"delta_rows": DeltaTable(str(DELTA)).to_pyarrow_table().num_rows}))


def main() -> None:
    args = parse_args()
    db = run_dbt(args) if args.mode == "dbt" else run_baseline()
    publish(db)


if __name__ == "__main__":
    main()
