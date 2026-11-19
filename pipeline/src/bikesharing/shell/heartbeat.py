"""Pings the run's Healthchecks.io check, with retries.

A run sends ``start`` when it begins and then ``success`` or ``fail`` as its
last action. A ping that cannot be delivered is reported to the caller, never
raised, since a missing signal alerts the owner anyway (d008, Observability).
"""

import http.client
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

type Signal = Literal["start", "success", "fail"]

_PATH_SUFFIX: Final[dict[Signal, str]] = {
    "start": "/start",
    "success": "",
    "fail": "/fail",
}


@dataclass(frozen=True, slots=True)
class PingFailure:
    """A ping that failed on every attempt.

    Attributes
    ----------
    signal : Signal
        The signal that was not delivered.
    attempts : int
        How many attempts were made.
    error_type : str
        The last exception's type name. Never its message, which may quote the
        check's URL.
    """

    signal: Signal
    attempts: int
    error_type: str


def ping(
    url: str,
    signal: Signal,
    *,
    body: str = "",
    timeout_s: float = 10.0,
    delays_s: Sequence[float] = (1.0, 2.0),
    sleep: Callable[[float], None] = time.sleep,
) -> PingFailure | None:
    """Send a signal to the check, retrying a failed attempt.

    Parameters
    ----------
    url : str
        The check's ping URL. It is a secret: it is never logged or returned.
    signal : Signal
        ``start`` posts to ``<url>/start``, ``success`` to ``<url>`` and
        ``fail`` to ``<url>/fail``.
    body : str, default ""
        The POST body, sent as UTF-8; a failure ping carries the run's final
        events.
    timeout_s : float, default 10.0
        The timeout of each attempt.
    delays_s : Sequence[float], default (1.0, 2.0)
        The wait before each further attempt, so there is one more attempt than
        delays.
    sleep : Callable[[float], None], default time.sleep
        How the delays are waited; tests pass a recorder.

    Returns
    -------
    PingFailure | None
        None once an attempt gets a 2xx response; a ``PingFailure`` after the
        last attempt fails.
    """
    request = urllib.request.Request(
        url.rstrip("/") + _PATH_SUFFIX[signal],
        data=body.encode("utf-8"),
        method="POST",
    )
    error_type = ""
    attempts = 0
    for delay in (None, *delays_s):
        if delay is not None:
            sleep(delay)
        attempts += 1
        try:
            # urlopen raises for every response outside 2xx, so returning is success.
            with urllib.request.urlopen(request, timeout=timeout_s):
                return None
        except (OSError, http.client.HTTPException) as error:
            error_type = type(error).__name__
            if isinstance(error, urllib.error.HTTPError):
                error.close()
    return PingFailure(signal=signal, attempts=attempts, error_type=error_type)
