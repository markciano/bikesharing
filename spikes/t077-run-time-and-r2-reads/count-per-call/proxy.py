"""Counting proxy of s019 Probe B, between deltalake and the copy's bucket on R2.

A reverse proxy on a free local port, in a process of its own that the caller
starts. deltalake reaches it over plain HTTP with no signature; the proxy
signs each request again with the copy token (SigV4) and forwards it to R2's
S3 endpoint, so only the proxy holds the token. The bucket is a constant:
nothing here can reach production.

Every request is recorded as one JSON line, with the label of the call in
progress, its S3 operation and R2 class (A, B, free), classified as in s010's
proxy (spikes/storage-table-format/r2_proxy.py).

Inputs:  .env with R2_ACCOUNT_ID, R2_COPY_ACCESS_KEY_ID, R2_COPY_SECRET_ACCESS_KEY.
Outputs: the JSON lines file the caller gives; in smoke mode,
         output/count-per-call/smoke-requests.jsonl.

Usage:   uv run python count-per-call/proxy.py --smoke
         (other scripts import CountingProxy)
"""

import argparse
import http.client
import json
import multiprocessing
import threading
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from bikesharing.shell.delta import PROCESSED_OBJECTS_PATH, STATION_STOCK_PATH, Lakehouse

SPIKE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SPIKE_DIR / ".env"
SMOKE_LOG = SPIKE_DIR / "output" / "count-per-call" / "smoke-requests.jsonl"
BUCKET = "bikesharing-t077-lakehouse-copy"
TABLES = (STATION_STOCK_PATH, PROCESSED_OBJECTS_PATH)

# R2 source card (docs/sources/cloudflare.md), as in s010's proxy. ListObjectsV2 is billed as
# ListObjects; DeleteObjects is not named, so it stays `unknown`.
CLASS_A = {
    "ListBuckets", "PutBucket", "ListObjects", "ListObjectsV2", "PutObject", "CopyObject",
    "CreateMultipartUpload", "UploadPart", "UploadPartCopy", "CompleteMultipartUpload",
    "ListMultipartUploads", "ListParts", "PutBucketEncryption", "PutBucketCors",
    "PutBucketLifecycleConfiguration",
}
CLASS_B = {
    "HeadBucket", "HeadObject", "GetObject", "GetBucketEncryption", "GetBucketLocation",
    "GetBucketCors", "GetBucketLifecycleConfiguration",
}
FREE = {"DeleteObject", "DeleteBucket", "AbortMultipartUpload"}

# Hop-by-hop, signing and length headers: never forwarded as received. The signing ones are
# rebuilt by the proxy's own signature, and the length from the body: forwarding the client's
# too would send two, which Cloudflare answers with 400.
DROP_REQUEST = {
    "content-length", "host", "connection", "keep-alive", "proxy-connection", "transfer-encoding", "te",
    "upgrade", "authorization", "x-amz-date", "x-amz-content-sha256", "x-amz-security-token",
}
DROP_RESPONSE = {"connection", "keep-alive", "transfer-encoding", "content-length"}


def r2_class(operation: str) -> str:
    """Return the R2 class of an S3 operation: A, B, free or unknown."""
    if operation in CLASS_A:
        return "A"
    if operation in CLASS_B:
        return "B"
    if operation in FREE:
        return "free"
    return "unknown"


def operation(method: str, has_bucket: bool, has_key: bool, query: dict) -> str:
    """Return the S3 operation of a path-style request, as in s010's proxy."""
    if not has_bucket:
        return "ListBuckets" if method == "GET" else "Unknown"
    if not has_key:
        if method == "GET":
            if "uploads" in query:
                return "ListMultipartUploads"
            if "location" in query:
                return "GetBucketLocation"
            return "ListObjectsV2" if query.get("list-type") == ["2"] else "ListObjects"
        if method == "POST" and "delete" in query:
            return "DeleteObjects"
        return {"HEAD": "HeadBucket", "PUT": "PutBucket", "DELETE": "DeleteBucket"}.get(
            method, "Unknown"
        )
    if method == "HEAD":
        return "HeadObject"
    if method == "GET":
        return "ListParts" if "uploadId" in query else "GetObject"
    if method == "PUT":
        if "partNumber" in query and "uploadId" in query:
            return "UploadPart"
        return "PutObject"
    if method == "POST":
        if "uploads" in query:
            return "CreateMultipartUpload"
        if "uploadId" in query:
            return "CompleteMultipartUpload"
    if method == "DELETE":
        return "AbortMultipartUpload" if "uploadId" in query else "DeleteObject"
    return "Unknown"


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    """Return the KEY=value lines of a .env file."""
    if not path.exists():
        raise SystemExit(f"Missing {path}: copy .env.example and fill it in.")
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip("\"'")
    missing = [k for k in ("R2_ACCOUNT_ID", "R2_COPY_ACCESS_KEY_ID", "R2_COPY_SECRET_ACCESS_KEY")
               if not env.get(k)]
    if missing:
        raise SystemExit(f"Missing in {path}: {', '.join(missing)}")
    return env


class CountingProxy:
    """A reverse proxy to the copy's bucket that records every request.

    Use it as a context manager; `lakehouse` points deltalake at it, and
    `label(name)` tags the requests sent while its block runs.

    The server runs in its own process: `QueryBuilder.execute` holds the GIL while
    it waits for its reads, so a proxy thread in the caller's process could never
    answer them.
    """

    def __init__(self, log_path: Path, env: dict[str, str] | None = None):
        self.env = env or read_env()
        self.log_path = log_path
        self.port = None
        self._label = None
        self._pipe = None
        self._process = None

    def __enter__(self) -> "CountingProxy":
        context = multiprocessing.get_context("spawn")
        self._pipe, child = context.Pipe()
        self._process = context.Process(target=_serve, args=(self.log_path, self.env, child), daemon=True)
        self._process.start()
        # With the caller's copy of the child's end closed, a child that dies raises here.
        child.close()
        self.port = self._pipe.recv()
        return self

    def __exit__(self, *exc) -> None:
        self._pipe.send(("stop", None))
        self._process.join(timeout=30)
        self._pipe.close()

    @property
    def lakehouse(self) -> Lakehouse:
        """The copy's bucket, reached through this proxy."""
        return Lakehouse(
            uri=f"s3://{BUCKET}",
            storage_options={
                "AWS_ENDPOINT_URL": f"http://127.0.0.1:{self.port}",
                "AWS_REGION": "auto",
                "AWS_ALLOW_HTTP": "true",
                # The proxy signs; deltalake sends unsigned requests and holds no token.
                "AWS_SKIP_SIGNATURE": "true",
                "aws_conditional_put": "etag",
            },
        )

    @contextmanager
    def label(self, name: str) -> Iterator[None]:
        """Tag every request sent while the block runs with `name`."""
        previous = self._label
        self._set_label(name)
        try:
            yield
        finally:
            self._set_label(previous)

    def _set_label(self, name: str | None) -> None:
        self._label = name
        self._pipe.send(("label", name))
        self._pipe.recv()  # the proxy's acknowledgement: only then may requests follow


class _Server:
    """What the request handler needs, in the proxy's process: signature, label and log."""

    def __init__(self, log_file, env: dict[str, str]):
        # botocore is imported here, not at the top, so that r2_metrics.py can import
        # r2_class from the pipeline's environment, which has no botocore.
        from botocore.credentials import Credentials

        self.upstream_host = f"{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
        self.credentials = Credentials(env["R2_COPY_ACCESS_KEY_ID"], env["R2_COPY_SECRET_ACCESS_KEY"])
        self.current_label = None
        self._lock = threading.Lock()
        self._file = log_file

    def record(self, line: dict) -> None:
        with self._lock:
            self._file.write(json.dumps(line) + "\n")
            self._file.flush()

    def sign(self, method: str, raw_path: str, headers: dict, body: bytes) -> dict:
        """Return the headers of the request signed with the copy token for R2."""
        from botocore.auth import S3SigV4Auth
        from botocore.awsrequest import AWSRequest

        request =AWSRequest(method=method, url=f"https://{self.upstream_host}{raw_path}",
                             data=body, headers=headers)
        S3SigV4Auth(self.credentials, "s3", "auto").add_auth(request)
        return dict(request.headers.items())


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128  # the default, 5, is short for the engine's bursts of new connections


def _serve(log_path: Path, env: dict[str, str], pipe) -> None:
    """The proxy's process: serve until `stop` arrives, or the caller is gone."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log_file:
        state = _Server(log_file, env)
        server = _HTTPServer(("127.0.0.1", 0), _handler(state))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        pipe.send(server.server_address[1])
        try:
            while True:
                message, value = pipe.recv()
                if message == "stop":
                    break
                state.current_label = value
                pipe.send("ok")
        except EOFError:
            pass
        server.shutdown()
        server.server_close()


def _handler(proxy: _Server) -> type[BaseHTTPRequestHandler]:
    local = threading.local()  # one upstream connection per client connection, kept alive

    def upstream() -> http.client.HTTPSConnection:
        if getattr(local, "conn", None) is None:
            local.conn = http.client.HTTPSConnection(proxy.upstream_host, timeout=120)
        return local.conn

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # keep-alive, as object_store expects

        def log_message(self, *args) -> None:
            pass

        def _read_body(self) -> bytes:
            if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                chunks = []
                while size := int(self.rfile.readline().split(b";")[0], 16):
                    chunks.append(self.rfile.read(size))
                    self.rfile.readline()
                self.rfile.readline()
                return b"".join(chunks)
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def _forward(self) -> None:
            label, start = proxy.current_label, time.time()
            body = self._read_body()
            headers = {k: v for k, v in self.headers.items() if k.lower() not in DROP_REQUEST}
            if body or self.command in ("PUT", "POST"):
                headers["Content-Length"] = str(len(body))
            signed = proxy.sign(self.command, self.path, headers, body)

            status, resp_headers, resp_body, error = None, [], b"", None
            for attempt in (1, 2):  # once more on a dropped keep-alive connection
                try:
                    conn = upstream()
                    conn.request(self.command, self.path, body=body or None, headers=signed)
                    resp = conn.getresponse()
                    status, resp_headers, resp_body = resp.status, resp.getheaders(), resp.read()
                    error = None
                    break
                except (http.client.HTTPException, OSError) as exc:
                    local.conn.close()
                    local.conn = None
                    error = repr(exc)

            # Recorded before answering: R2 has served the request even if the client is
            # gone, and a call's lines are in the log by the time it returns.
            parts = urlsplit(self.path)
            query = parse_qs(parts.query, keep_blank_values=True)
            bucket, _, key = unquote(parts.path).lstrip("/").partition("/")
            op = operation(self.command, bool(bucket), bool(key), query)
            proxy.record({
                "label": label,
                "time": datetime.fromtimestamp(start, UTC).isoformat(),
                "method": self.command,
                "operation": op,
                "class": r2_class(op),
                "key": key,
                "query": parts.query,
                "conditional": any(h.lower() in ("if-none-match", "if-match") for h in headers),
                "status": status,
                "error": error,
                "request_bytes": len(body),
                "response_bytes": len(resp_body),
                "duration_ms": round((time.time() - start) * 1000, 1),
            })

            if status is None:
                self.send_response(502)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_response(status)
                for k, v in resp_headers:
                    if k.lower() not in DROP_RESPONSE:
                        self.send_header(k, v)
                # HEAD and 304 carry the object's length with no body; object_store reads it.
                no_body = self.command == "HEAD" or status in (204, 304)
                length = dict((k.lower(), v) for k, v in resp_headers).get("content-length", "0")
                self.send_header("Content-Length", length if no_body else str(len(resp_body)))
                self.end_headers()
                if not no_body:
                    self.wfile.write(resp_body)

        do_GET = do_HEAD = do_PUT = do_POST = do_DELETE = _forward

    return Handler


def table_of(key: str) -> str:
    """Return the table a key belongs to, or `other`."""
    return next((t for t in TABLES if key == t or key.startswith(t + "/")), "other")


def summary(lines: list[dict]) -> None:
    """Print GetObject, other Class B and Class A per table and in total."""
    rows: dict[str, Counter] = {}
    for line in lines:
        # A listing names its table in the prefix parameter, not in the key.
        key = line["key"] or (parse_qs(line["query"]).get("prefix") or [""])[0]
        c = rows.setdefault(table_of(key), Counter())
        c["GetObject"] += line["operation"] == "GetObject"
        c["B other"] += line["class"] == "B" and line["operation"] != "GetObject"
        c["A"] += line["class"] == "A"
        c["free/unknown"] += line["class"] in ("free", "unknown")
        c["failed"] += line["status"] is None or line["status"] >= 500
    total = sum(rows.values(), Counter())
    print(f"{'table':<28}{'GetObject':>10}{'B other':>9}{'B total':>9}{'A':>6}{'free/unk':>10}{'failed':>8}")
    for name, c in [*sorted(rows.items()), ("total", total)]:
        print(f"{name:<28}{c['GetObject']:>10,}{c['B other']:>9,}{c['GetObject'] + c['B other']:>9,}"
              f"{c['A']:>6,}{c['free/unknown']:>10,}{c['failed']:>8,}")


def smoke() -> None:
    """Open each table once through the proxy and print its requests."""
    from deltalake import DeltaTable

    t0 = time.monotonic()
    print(f"smoke: started {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}")
    with CountingProxy(SMOKE_LOG) as proxy, proxy.label("smoke"):
        lakehouse = proxy.lakehouse
        for path in TABLES:
            table = DeltaTable(lakehouse.table_uri(path), storage_options=dict(lakehouse.storage_options))
            print(f"smoke: {path} at version {table.version()}")
    lines = [json.loads(line) for line in SMOKE_LOG.read_text().splitlines()]
    print(f"smoke: {len(lines)} requests in {SMOKE_LOG.relative_to(SPIKE_DIR)}")
    summary(lines)
    print(f"Elapsed: {time.monotonic() - t0:.1f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--smoke", action="store_true",
                        help="open each table of the copy once and print the requests per table")
    args = parser.parse_args()
    if args.smoke:
        smoke()
    else:
        parser.print_help()
