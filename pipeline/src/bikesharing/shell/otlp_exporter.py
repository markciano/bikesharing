"""Sends a run's OTLP request to Grafana Cloud once, raising on any failure.

The copy of the run's logs is best effort: the caller catches what this module
raises, so a failed send never changes a run (d009 D2, The copy to Grafana never
affects a run).
"""

import http.client
import json
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass

from bikesharing.core.otlp_payload import logs_request


@dataclass(frozen=True)
class OtlpTarget:
    """Where and how to send the logs.

    Attributes
    ----------
    endpoint : str
        ``OTLP_ENDPOINT``: Grafana Cloud's OTLP/HTTP logs URL, ending in
        ``/v1/logs``.
    token : str
        ``OTLP_TOKEN``: the Basic credential, base64 of ``<instance ID>:<token>``.
        It is a secret: it is never logged or put in an error.
    """

    endpoint: str
    token: str


def send_logs(
    target: OtlpTarget, lines: Sequence[str], *, timeout_s: float = 10.0
) -> None:
    """POST the run's OTLP request once, and return at once with no lines.

    Parameters
    ----------
    target : OtlpTarget
        The endpoint and its credential.
    lines : Sequence[str]
        The run's JSON lines, without their newline.
    timeout_s : float, default 10.0
        The timeout of the connection and of each read, the heartbeat's limit.

    Raises
    ------
    OSError
        On a non-2xx answer, a timeout or a network error. Its message holds no
        header, so it never quotes the credential.
    """
    if not lines:
        return
    request = urllib.request.Request(
        target.endpoint,
        data=json.dumps(logs_request(lines)).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {target.token}",
        },
        method="POST",
    )
    try:
        # urlopen raises for every response outside 2xx, so returning is success.
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            response.read()
    except http.client.HTTPException as error:
        # A protocol error that is not an OSError, such as a truncated body, is
        # raised as one so that the caller has a single failure to catch.
        raise OSError(type(error).__name__) from error
