"""Tests of the OTLP exporter against a local stub of Grafana Cloud's OTLP endpoint.

The stub is a real HTTP server on a free local port, so the tests run the
production code with ``urllib`` and no network beyond the loopback, with a small
timeout (d009, Pipeline's OTLP payload and exporter).
"""

import contextlib
import json
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from bikesharing.core.otlp_payload import logs_request
from bikesharing.shell.otlp_exporter import OtlpTarget, send_logs

TOKEN = "dXNlcjp0b2tlbg=="
LINES = (
    json.dumps(
        {
            "ts": "2026-01-01T00:00:00.871Z",
            "level": "info",
            "component": "pipeline",
            "version": "v1",
            "run_id": "20261018T120003Z",
            "event": "run_started",
        }
    ),
)


@dataclass
class _Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class _Stub:
    """Grafana's stand-in: records requests and answers from a script."""

    port: int
    statuses: list[int] = field(default_factory=list)
    requests: list[_Request] = field(default_factory=list)
    response_delay_s: float = 0.0

    @property
    def target(self) -> OtlpTarget:
        return OtlpTarget(
            endpoint=f"http://127.0.0.1:{self.port}/otlp/v1/logs", token=TOKEN
        )


@pytest.fixture
def stub() -> Iterator[_Stub]:
    state = _Stub(port=0)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            state.requests.append(
                _Request(
                    "POST",
                    self.path,
                    dict(self.headers.items()),
                    self.rfile.read(length),
                )
            )
            time.sleep(state.response_delay_s)
            status = state.statuses.pop(0) if state.statuses else 200
            # A client that timed out has already closed the connection, as the
            # stalled-answer test intends, so the failed write is expected.
            with contextlib.suppress(BrokenPipeError):
                self.send_response(status)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

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


def test_send_logs_posts_the_request_as_json_with_the_basic_credential(
    stub: _Stub,
) -> None:
    send_logs(stub.target, LINES)

    [request] = stub.requests
    assert request.method == "POST"
    assert request.path == "/otlp/v1/logs"
    assert request.headers["Authorization"] == f"Basic {TOKEN}"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.body) == logs_request(LINES)


def test_send_logs_returns_on_a_2xx_answer(stub: _Stub) -> None:
    stub.statuses[:] = [204]

    send_logs(stub.target, LINES)

    assert len(stub.requests) == 1


def test_send_logs_sends_nothing_when_there_are_no_lines(stub: _Stub) -> None:
    send_logs(stub.target, ())

    assert stub.requests == []


def test_send_logs_raises_oserror_on_a_non_2xx_answer(stub: _Stub) -> None:
    stub.statuses[:] = [500]

    with pytest.raises(OSError):
        send_logs(stub.target, LINES)

    assert len(stub.requests) == 1


# Verifies d009 R5
def test_send_logs_raises_oserror_when_the_answer_stalls_past_the_timeout(
    stub: _Stub,
) -> None:
    stub.response_delay_s = 0.5

    with pytest.raises(OSError):
        send_logs(stub.target, LINES, timeout_s=0.05)


def test_send_logs_raises_oserror_when_the_connection_is_refused() -> None:
    target = OtlpTarget(
        endpoint=f"http://127.0.0.1:{_unused_port()}/otlp/v1/logs", token=TOKEN
    )

    with pytest.raises(OSError):
        send_logs(target, LINES)
