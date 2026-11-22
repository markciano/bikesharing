"""Writes each event to a stream as it happens and keeps it for the run's log object.

Every event goes to stdout as soon as it is emitted, so Modal's logs hold it
even if the run is killed, and is kept in memory so the shell can upload the
whole run as one JSON Lines object at its end (d008, Observability).
"""

from collections.abc import Collection
from typing import TextIO

from bikesharing.core.events import Event, RunContext, to_json_line


class EventLog:
    """The run's events: written to a stream as they happen and kept in memory.

    Parameters
    ----------
    context : RunContext
        The run's common fields.
    secrets : Collection[str]
        The value of every secret the run holds; each is replaced with ``***``
        in every event.
    stream : TextIO
        Where each event is written, normally stdout.
    """

    def __init__(
        self, context: RunContext, secrets: Collection[str], stream: TextIO
    ) -> None:
        self._context = context
        self._secrets = tuple(secrets)
        self._stream = stream
        self._lines: list[str] = []

    def emit(self, event: Event) -> str:
        """Write an event to the stream, flush it and keep it.

        Parameters
        ----------
        event : Event
            The event to log.

        Returns
        -------
        str
            The event's JSON line, without a trailing newline.
        """
        line = to_json_line(event, self._context, self._secrets)
        self._stream.write(line + "\n")
        self._stream.flush()
        self._lines.append(line)
        return line

    def body(self) -> str:
        """Join the kept events as the run's log object.

        Returns
        -------
        str
            Every event emitted so far, in order, as JSON Lines: one line each,
            each ending in a newline. Empty if none was emitted.
        """
        return "".join(f"{line}\n" for line in self._lines)

    def lines(self) -> tuple[str, ...]:
        """Return every kept line, for the copy sent to monitoring.

        Returns
        -------
        tuple[str, ...]
            Every event emitted so far, in order, without newlines. Read after
            the log's upload, it also holds the events emitted since ``body``
            was read, such as ``log_upload_failed``.
        """
        return tuple(self._lines)
