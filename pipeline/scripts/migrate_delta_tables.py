"""One-off migration of the lakehouse's Delta tables to the layout of d010.

``processed_objects`` is rewritten partitioned by system, feed and UTC date,
and both tables get the table properties ``ensure_tables`` sets on a new table;
``station_stock`` keeps its data files (d010 D2, Existing data moves to the new
layout in a one-off migration). The owner runs it once from the project's
``pipeline`` folder, with the schedule paused and the migration's own R2 token
in the environment (d010 D5, Security of the migration and of retention)::

    uv run python scripts/migrate_delta_tables.py

It calls ``deltalake`` directly, a self-contained data migration that adds
nothing to the package's table access for a single use, and takes from the
package only each table's path, schema, partition columns and properties, and
the runs' lakehouse on R2 (d010, Migration). It runs in this order:

1. Checks the code: a clean working tree, untracked files included, and HEAD at
   ``origin/main``, whose full SHA is the code version of every commit it writes.
2. Checks the layout: a ``processed_objects`` already in the new partitioning
   goes straight to step 5, so a second run never rewrites it again.
3. Rewrites ``processed_objects`` with ``utc_date`` from ``captured_at``.
4. Verifies the rewrite against the version before it; on a failed check it
   restores that version and exits non-zero naming each failed check.
5. Sets the table properties on both tables.
"""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from arro3.core import Table
from deltalake import CommitProperties, DeltaTable, QueryBuilder, write_deltalake

from bikesharing.core.settings import (
    CLOUDFLARE_ACCOUNT_ID,
    TABLE_PATHS,
    TableName,
)

# The properties ensure_tables creates a table with, taken from the table access
# rather than rebuilt here, so that a migrated table and a new one cannot differ.
from bikesharing.shell.delta import (
    PARTITION_COLUMNS,
    PROCESSED_OBJECTS_SCHEMA,
    _table_properties,
    r2_lakehouse,
)

ACCESS_KEY_ID_VARIABLE: Final = "MIGRATION_R2_ACCESS_KEY_ID"
SECRET_ACCESS_KEY_VARIABLE: Final = "MIGRATION_R2_SECRET_ACCESS_KEY"

# Source-to-target reconciliation of the rewrite: each check holds when its query
# returns true (d010 D2, Existing data moves to the new layout in a one-off
# migration). The set checks compare both ways, so a row only one side has fails.
CHECKS: Final[Mapping[str, str]] = {
    "rows": "select (select count(*) from earlier) = (select count(*) from rewritten)",
    "keys": (
        "select count(*) = 0 from ("
        "(select key from earlier except select key from rewritten) union all "
        "(select key from rewritten except select key from earlier))"
    ),
    "lineage": (
        "select count(*) = 0 from ("
        "(select key, run_id, code_version from earlier except "
        "select key, run_id, code_version from rewritten) union all "
        "(select key, run_id, code_version from rewritten except "
        "select key, run_id, code_version from earlier))"
    ),
}


class RestoreError(Exception):
    """The restore after a failed verification did not bring the table back."""


class TableChangedError(Exception):
    """``processed_objects`` has a commit after the version the rewrite starts from."""


def _table_uri(lakehouse_uri: str, table: TableName) -> str:
    """Return the URI of ``table`` under the lakehouse's root."""
    return f"{lakehouse_uri.rstrip('/')}/{TABLE_PATHS[table]}"


def _commit(code_version: str) -> CommitProperties:
    """Return the commit properties that record the migration's code version."""
    return CommitProperties(custom_metadata={"code_version": code_version})


def _scalar(builder: QueryBuilder, sql: str) -> object:
    """Return the one value a query returns."""
    return Table.from_arrow(builder.execute(sql)).column(0)[0].as_py()


def _row_count(table: DeltaTable) -> object:
    """Return the number of rows of a table's loaded version."""
    return _scalar(QueryBuilder().register("t", table), "select count(*) from t")


def rewrite(
    table_uri: str,
    storage_options: Mapping[str, str],
    code_version: str,
    *,
    before: int,
) -> None:
    """Overwrite ``processed_objects`` in its new layout, with every row of ``before``.

    The overwrite with the new partition columns and ``schema_mode="overwrite"``
    is Delta's way of changing a table's partitioning. The columns follow
    ``PROCESSED_OBJECTS_SCHEMA``, so it writes the table ``ensure_tables`` creates.

    Parameters
    ----------
    table_uri : str
        The URI of ``processed_objects``.
    storage_options : Mapping[str, str]
        The options ``deltalake`` passes to its object store.
    code_version : str
        The migration's code version, recorded in its commit.
    before : int
        The version the verification compares the rewrite with, which must be
        the table's latest.

    Raises
    ------
    TableChangedError
        If the table has a commit after ``before``.
    """
    options = dict(storage_options)
    latest = DeltaTable(table_uri, storage_options=options).version()
    # deltalake does not detect a commit that lands while an overwrite writes: the
    # overwrite removes only the files of the version it loaded. Only a paused
    # schedule keeps runs out (d010 D2, Existing data moves to the new layout in a
    # one-off migration); this refuses a table a run has already written to.
    if latest != before:
        raise TableChangedError(
            f"processed_objects is at version {latest}, not {before}: "
            "something wrote to it, so the schedule may not be paused"
        )
    columns = ", ".join(
        "cast(captured_at as date) as utc_date"
        if field.name == "utc_date"
        else field.name
        for field in PROCESSED_OBJECTS_SCHEMA.fields
    )
    current = (
        QueryBuilder()
        .register("t", DeltaTable(table_uri, version=before, storage_options=options))
        .execute(f"select {columns} from t")
    )
    write_deltalake(
        table_uri,
        current,
        mode="overwrite",
        schema_mode="overwrite",
        partition_by=list(PARTITION_COLUMNS["processed_objects"]),
        storage_options=options,
        commit_properties=_commit(code_version),
    )


def verify(
    table_uri: str, storage_options: Mapping[str, str], *, before: int
) -> list[str]:
    """Compare the latest version of ``processed_objects`` with ``before``.

    Parameters
    ----------
    table_uri : str
        The URI of ``processed_objects``.
    storage_options : Mapping[str, str]
        The options ``deltalake`` passes to its object store.
    before : int
        The version before the rewrite, read by time travel.

    Returns
    -------
    list[str]
        The names of the checks that failed, in the order of ``CHECKS``; empty
        when the rewrite holds the same rows, keys and lineage.
    """
    options = dict(storage_options)
    builder = (
        QueryBuilder()
        .register(
            "earlier", DeltaTable(table_uri, version=before, storage_options=options)
        )
        .register("rewritten", DeltaTable(table_uri, storage_options=options))
    )
    return [name for name, sql in CHECKS.items() if _scalar(builder, sql) is not True]


def _restore(
    table_uri: str,
    storage_options: Mapping[str, str],
    code_version: str,
    *,
    before: int,
) -> None:
    """Restore ``processed_objects`` to ``before`` and check it is back.

    A restore points the table back to the earlier version's data files, which
    stay in storage until a vacuum removes them, so it copies no data.

    Raises
    ------
    RestoreError
        If the restore fails, or the table does not have the partition columns
        and number of rows of ``before`` after it; the message names the version
        to restore.
    """
    options = dict(storage_options)
    failure = f"processed_objects must be restored to version {before} by hand"
    try:
        DeltaTable(table_uri, storage_options=options).restore(
            before, commit_properties=_commit(code_version)
        )
        restored = DeltaTable(table_uri, storage_options=options)
        earlier = DeltaTable(table_uri, version=before, storage_options=options)
        is_back = restored.metadata().partition_columns == (
            earlier.metadata().partition_columns
        ) and _row_count(restored) == _row_count(earlier)
    # Whatever fails, the owner needs the version to restore, not a traceback.
    except Exception as error:
        raise RestoreError(f"the restore failed ({error}); {failure}") from error
    if not is_back:
        raise RestoreError(
            f"the restored table differs from its earlier version; {failure}"
        )


def set_properties(
    table_uri: str,
    storage_options: Mapping[str, str],
    table: TableName,
    code_version: str,
) -> None:
    """Set on ``table`` the table properties ``ensure_tables`` creates it with.

    Setting a property to the value it already holds only adds a commit, so a
    migration that failed here can run again.

    Parameters
    ----------
    table_uri : str
        The table's URI.
    storage_options : Mapping[str, str]
        The options ``deltalake`` passes to its object store.
    table : TableName
        The table's name.
    code_version : str
        The migration's code version, recorded in its commit.
    """
    # ensure_tables' configuration type allows None, which leaves a property
    # unset; a property that is set always has a value.
    properties = {
        name: value
        for name, value in _table_properties(table).items()
        if value is not None
    }
    DeltaTable(
        table_uri, storage_options=dict(storage_options)
    ).alter.set_table_properties(properties, commit_properties=_commit(code_version))


def migrate(
    lakehouse_uri: str, storage_options: Mapping[str, str], code_version: str
) -> list[str]:
    """Run the migration's steps 2 to 5 on a lakehouse.

    Parameters
    ----------
    lakehouse_uri : str
        The lakehouse's root.
    storage_options : Mapping[str, str]
        The options ``deltalake`` passes to its object store.
    code_version : str
        The migration's code version, recorded in each of its commits.

    Returns
    -------
    list[str]
        The checks the rewrite failed, after which the table was restored and no
        property was set; empty when the migration passed.

    Raises
    ------
    RestoreError
        If a failed rewrite could not be restored.
    TableChangedError
        If something wrote to ``processed_objects`` after the migration read it.
    """
    processed_uri = _table_uri(lakehouse_uri, "processed_objects")
    layout = list(PARTITION_COLUMNS["processed_objects"])
    table = DeltaTable(processed_uri, storage_options=dict(storage_options))
    if table.metadata().partition_columns == layout:
        print(f"processed_objects is already partitioned by {layout}: no rewrite")
    else:
        before = table.version()
        print(f"rewriting processed_objects from version {before}", flush=True)
        rewrite(processed_uri, storage_options, code_version, before=before)
        failed = verify(processed_uri, storage_options, before=before)
        if failed:
            _restore(processed_uri, storage_options, code_version, before=before)
            print(f"processed_objects restored to version {before}")
            return failed
        print("the rewrite passed its checks")
    for name in TABLE_PATHS:
        set_properties(
            _table_uri(lakehouse_uri, name), storage_options, name, code_version
        )
        print(f"{name}: table properties set")
    return []


def _git(*args: str) -> str:
    """Return a git command's output, run in this script's repository."""
    return subprocess.run(
        ["git", *args],
        cwd=Path(__file__).parent,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _code_failures() -> list[str]:
    """Return why the code may not run the migration, as ``deploy.sh`` checks it.

    The migration writes to the production lakehouse, so it runs only reviewed
    code: a commit on ``main``, whose PR's checks passed (d010 D5, Security of
    the migration and of retention).
    """
    try:
        _git("fetch", "--quiet", "origin", "main")
        status = _git("status", "--porcelain", "--untracked-files=all").splitlines()
        head = _git("rev-parse", "HEAD")
        # The fetched tip, not the `origin/main` ref, as deploy.sh reads it.
        main_tip = _git("rev-parse", "FETCH_HEAD")
    except subprocess.CalledProcessError as error:
        return [f"git failed: {error.stderr.strip()}"]
    failures = []
    if any(not line.startswith("??") for line in status):
        failures.append("the working tree has uncommitted changes")
    if any(line.startswith("??") for line in status):
        failures.append("the working tree has untracked files")
    if head != main_tip:
        failures.append(f"HEAD ({head}) is not origin/main ({main_tip})")
    return failures


def main() -> int:
    """Check the code and the credentials, then migrate the production lakehouse.

    Returns
    -------
    int
        0 if the migration passed; 1 if a check of the code or the environment
        failed, if the rewrite failed its verification, or if its restore failed.
    """
    failures = _code_failures()
    credentials = {
        name: os.environ.get(name, "")
        for name in (ACCESS_KEY_ID_VARIABLE, SECRET_ACCESS_KEY_VARIABLE)
    }
    failures += [
        f"{name} is not set" for name, value in credentials.items() if not value
    ]
    if failures:
        for failure in failures:
            print(f"error: refusing to migrate: {failure}", file=sys.stderr)
        return 1
    code_version = _git("rev-parse", "HEAD")
    # The runs' own lakehouse, so the migration writes with their storage options.
    lakehouse = r2_lakehouse(
        account_id=CLOUDFLARE_ACCOUNT_ID,
        access_key_id=credentials[ACCESS_KEY_ID_VARIABLE],
        secret_access_key=credentials[SECRET_ACCESS_KEY_VARIABLE],
    )
    print(f"migrating {lakehouse.uri} with code version {code_version}")
    try:
        failed = migrate(lakehouse.uri, lakehouse.storage_options, code_version)
    except (RestoreError, TableChangedError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if failed:
        print(
            f"error: the rewrite failed the checks: {', '.join(failed)}",
            file=sys.stderr,
        )
        return 1
    print("migration passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
