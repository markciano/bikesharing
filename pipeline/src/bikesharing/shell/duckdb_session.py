"""DuckDB with the run's sandbox and memory settings.

DuckDB reads only inside the run's work folder, reaches no network, loads no
extension and keeps its memory below the container's limit; the configuration is
locked last, so that nothing a query does can lift it (d008 #9, #10, Bronze
reading). ``apply_sandbox`` holds these settings for every connection the run
opens; ``Plugin`` applies them to dbt's.
"""

from collections.abc import Sequence
from typing import Any

from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection


def _literal(value: str) -> str:
    """Return ``value`` as a SQL string literal.

    DuckDB's ``SET`` takes no bound parameters; the values are the run's own
    paths and limits, never feed values.
    """
    return "'" + value.replace("'", "''") + "'"


def apply_sandbox(
    con: DuckDBPyConnection,
    *,
    memory_limit: str,
    temp_directory: str,
    allowed_directories: Sequence[str],
) -> None:
    """Apply the sandbox and memory settings to an open connection, and lock them.

    Parameters
    ----------
    con : DuckDBPyConnection
        A connection whose database has just started, with nothing run on it.
    memory_limit : str
        DuckDB's ``memory_limit``, with its unit, e.g. ``"1024MiB"``.
    temp_directory : str
        The folder DuckDB spills to; it lies inside an allowed directory.
    allowed_directories : Sequence[str]
        The only folders DuckDB may read or write.
    """
    directories = ", ".join(_literal(directory) for directory in allowed_directories)
    # The order matters: the paths are set while external access is still on,
    # and the lock goes last.
    con.execute(f"set memory_limit = {_literal(memory_limit)}")
    con.execute(f"set temp_directory = {_literal(temp_directory)}")
    con.execute(f"set allowed_directories = [{directories}]")
    con.execute("set autoinstall_known_extensions = false")
    con.execute("set autoload_known_extensions = false")
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")


class Plugin(BasePlugin):
    """dbt-duckdb plugin that applies the sandbox once, on dbt's connection.

    dbt-duckdb applies a profile's ``settings`` again on every cursor, which a
    sandboxed and locked DuckDB refuses; ``configure_connection`` runs once per
    database (d008 DI6). ``profiles.yml`` passes the values as the plugin's
    ``config``: ``memory_limit``, ``temp_directory`` and ``allowed_directory``.
    """

    def initialize(self, plugin_config: dict[str, Any]) -> None:
        """Keep the settings the profile passes.

        Parameters
        ----------
        plugin_config : dict[str, Any]
            The plugin's ``config`` in ``profiles.yml``.
        """
        self._memory_limit = str(plugin_config["memory_limit"])
        self._temp_directory = str(plugin_config["temp_directory"])
        self._allowed_directory = str(plugin_config["allowed_directory"])

    def configure_connection(self, conn: DuckDBPyConnection) -> None:
        """Apply the sandbox to dbt's connection.

        Parameters
        ----------
        conn : DuckDBPyConnection
            dbt-duckdb's connection, just opened on the scratch database.
        """
        apply_sandbox(
            conn,
            memory_limit=self._memory_limit,
            temp_directory=self._temp_directory,
            allowed_directories=[self._allowed_directory],
        )
