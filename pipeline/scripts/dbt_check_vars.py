"""Print, as JSON, the dbt variables the pipeline's checks run dbt with.

The variables are those the shell passes to ``dbt build`` (d008, Tests and CI),
over the bronze fixtures and empty Parquet files of the lakehouse's inputs. The
read schema comes from ``bikesharing.core.read_schema``, so that it lives in one
place. DuckDB reads only inside the run's work folder, so the fixtures are copied
there under their bronze keys, as the shell downloads a batch (d008 #9, Bronze
reading).

Usage: ``uv run python scripts/dbt_check_vars.py <work folder>``, from ``pipeline/``.
"""

import json
import shutil
import sys
from pathlib import Path

import duckdb

from bikesharing.core.read_schema import STATION_FIELDS, STATION_STATUS_COLUMNS

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "bronze"

# The columns of processed_objects and of station_stock (d008, bikesharing.shell.delta
# and dbt model contracts), with no rows: dbt needs only their names and types.
CAPTURE_HISTORY_SQL = """
select
    null::varchar as key,
    null::varchar as system,
    null::varchar as feed,
    null::timestamptz as captured_at,
    null::integer as station_count,
    null::varchar as status,
    null::varchar as run_id,
    null::varchar as code_version
limit 0
"""

LATEST_CAPTURES_SQL = """
select
    null::varchar as system,
    null::varchar as station_id,
    null::timestamptz as captured_at,
    null::date as local_date,
    null::smallint as local_minute,
    null::integer as num_vehicles_available,
    null::integer as num_docks_available,
    null::integer as num_vehicles_disabled,
    null::integer as num_docks_disabled,
    null::boolean as is_installed,
    null::boolean as is_renting,
    null::boolean as is_returning,
    null::timestamptz as last_reported,
    null::timestamptz as last_updated,
    null::varchar as run_id,
    null::varchar as code_version
limit 0
"""


def copy_fixtures(work: Path) -> dict[str, list[str]]:
    """Copy the bronze fixtures to ``work`` under their keys and list them per system.

    Parameters
    ----------
    work : Path
        The folder standing in for the run's work folder.

    Returns
    -------
    dict[str, list[str]]
        Per system, the copied ``station_status`` files' paths, sorted.
    """
    bronze_files: dict[str, list[str]] = {}
    for system in STATION_STATUS_COLUMNS:
        sources = sorted(
            (FIXTURES / "raw" / system / "station_status").rglob("*.json.gz")
        )
        copies = []
        for source in sources:
            copy = work / "bronze" / source.relative_to(FIXTURES)
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copy)
            copies.append(str(copy))
        bronze_files[system] = copies
    return bronze_files


def write_empty_parquet(sql: str, path: Path) -> str:
    """Write the result of ``sql``, with no rows, as a Parquet file.

    Parameters
    ----------
    sql : str
        A query that names and types the file's columns.
    path : Path
        The file to write.

    Returns
    -------
    str
        The file's path.
    """
    with duckdb.connect() as con:
        con.sql(sql).write_parquet(str(path))
    return str(path)


def check_vars(work: Path) -> dict[str, object]:
    """Build the dbt variables of the checks inside ``work``.

    Parameters
    ----------
    work : Path
        The folder standing in for the run's work folder.

    Returns
    -------
    dict[str, object]
        The variables of ``bikesharing.shell.dbt_runner``, for both selections.
    """
    return {
        "bronze_files": copy_fixtures(work),
        "read_columns": {
            system: dict(columns) for system, columns in STATION_STATUS_COLUMNS.items()
        },
        "station_fields": {
            system: sorted(fields) for system, fields in STATION_FIELDS.items()
        },
        "capture_history_file": write_empty_parquet(
            CAPTURE_HISTORY_SQL, work / "capture_history.parquet"
        ),
        "latest_captures_file": write_empty_parquet(
            LATEST_CAPTURES_SQL, work / "latest_captures.parquet"
        ),
        "run_id": "check",
        "code_version": "check",
    }


if __name__ == "__main__":
    print(json.dumps(check_vars(Path(sys.argv[1]))))
