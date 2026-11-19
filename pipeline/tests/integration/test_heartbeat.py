"""Tests of the heartbeat pings against a local stub of the Healthchecks.io check.

The stub is a real HTTP server on a free local port, so the tests run the
production code with ``urllib`` and no network beyond the loopback, with small
timeouts and delays (d008, Observability).
"""

import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bikesharing.shell.heartbeat import PingFailure, ping

CHECK_ID = "5f3c9a1e-secret-check-id"
SMALL_DELAYS = (0.01, 0.01)


@dataclass
class _Request:
    method: str
    path: str
    body: bytes


@dataclass
class _Stub:
    """The check's stand-in: records requests and answers from a script."""

    port: int
    statuses: list[int] = field(default_factory=list)
    requests: list[_Request] = field(default_factory=list)
    response_delay_s: float = 0.0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/ping/{CHECK_ID}"


@pytest.fixture
def stub() -> Iterator[_Stub]:
    state = _Stub(port=0)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            state.requests.append(_Request("POST", self.path, self.rfile.read(length)))
            time.sleep(state.response_delay_s)
            status = state.statuses.pop(0) if state.statuses else 200
            self.send_response(status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format: str, *args: object) -> None:
            """Keep the test output free of the server's access log."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    state.port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield state
    server.shutdown()
    server.server_close()


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# Verifies d008 R14
def test_start_then_success_pings_the_check_in_order(stub: _Stub) -> None:
    started = ping(stub.url, "start", delays_s=SMALL_DELAYS)
    finished = ping(stub.url, "success", delays_s=SMALL_DELAYS)

    assert started is None
    assert finished is None
    assert [(r.method, r.path) for r in stub.requests] == [
        ("POST", f"/ping/{CHECK_ID}/start"),
        ("POST", f"/ping/{CHECK_ID}"),
    ]


# Verifies d008 R15
def test_fail_pings_the_fail_path_with_its_body(stub: _Stub) -> None:
    body = '{"event": "run_finished"}\n{"event": "batch_failed"}\n'

    result = ping(stub.url, "fail", body=body, delays_s=SMALL_DELAYS)

    assert result is None
    assert [(r.method, r.path, r.body) for r in stub.requests] == [
        ("POST", f"/ping/{CHECK_ID}/fail", body.encode("utf-8"))
    ]


def test_a_trailing_slash_in_the_url_does_not_double_the_separator(stub: _Stub) -> None:
    ping(stub.url + "/", "start", delays_s=SMALL_DELAYS)

    assert [r.path for r in stub.requests] == [f"/ping/{CHECK_ID}/start"]


# Verifies d008 R15
def test_a_ping_that_fails_once_is_retried_after_the_first_delay(stub: _Stub) -> None:
    stub.statuses[:] = [500, 200]
    slept: list[float] = []

    result = ping(stub.url, "success", delays_s=(1.0, 2.0), sleep=slept.append)

    assert result is None
    assert len(stub.requests) == 2
    assert slept == [1.0]


# Verifies d008 R15
def test_a_ping_that_keeps_failing_is_given_up_after_the_last_attempt(
    stub: _Stub,
) -> None:
    stub.statuses[:] = [503, 503, 503, 503]
    slept: list[float] = []

    result = ping(stub.url, "fail", body="x", delays_s=(1.0, 2.0), sleep=slept.append)

    assert result == PingFailure(signal="fail", attempts=3, error_type="HTTPError")
    assert len(stub.requests) == 3
    assert slept == [1.0, 2.0]


# Verifies d008 R24
def test_a_refused_connection_reports_only_the_exception_type() -> None:
    url = f"http://127.0.0.1:{_unused_port()}/ping/{CHECK_ID}"

    result = ping(url, "success", delays_s=SMALL_DELAYS)

    assert isinstance(result, PingFailure)
    assert result.attempts == 3
    assert result.error_type == "URLError"
    assert CHECK_ID not in repr(result)


# Verifies d008 R24
@pytest.mark.parametrize("url", [f"hc-ping.com/{CHECK_ID}", ""])
def test_a_malformed_url_is_one_failed_attempt_that_does_not_quote_it(url: str) -> None:
    slept: list[float] = []

    result = ping(url, "success", delays_s=(1.0, 2.0), sleep=slept.append)

    assert result == PingFailure(signal="success", attempts=1, error_type="ValueError")
    assert CHECK_ID not in repr(result)
    assert slept == []


def test_an_attempt_that_exceeds_the_timeout_counts_as_failed(stub: _Stub) -> None:
    stub.response_delay_s = 0.3

    result = ping(stub.url, "start", timeout_s=0.05, delays_s=(0.01,))

    assert isinstance(result, PingFailure)
    assert result.attempts == 2
    assert result.error_type == "TimeoutError"


def test_with_no_delays_a_ping_is_attempted_once(stub: _Stub) -> None:
    stub.statuses[:] = [500]

    result = ping(stub.url, "start", delays_s=())

    assert result == PingFailure(signal="start", attempts=1, error_type="HTTPError")
