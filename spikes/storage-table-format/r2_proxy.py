# Request counter of s010 probe A: a mitmproxy addon that logs every request the probe sends to R2.
#
# Each request is classified as an S3 operation and its R2 class (A, B, free) as listed in the
# R2 source card (docs/sources/r2-storage.md). Operations the card does not name are `unknown`;
# the independent count against R2's metrics (analyse_ops.py) settles them.
# Input:  the probe's HTTPS traffic, inspected by mitmproxy (decision log #19).
# Output: output/proxy-<UTC start>.jsonl, one JSON line per request.
#
# Usage: uv run mitmdump -s r2_proxy.py   (listens on 127.0.0.1:8080, PROXY_URL in .env)

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "output"
R2_SUFFIX = ".r2.cloudflarestorage.com"

# R2 source card, Facts. ListObjectsV2 is billed as ListObjects (the card names only the latter, TODO there);
# DeleteObjects is not named, so it stays `unknown` until the independent count classifies it.
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


def r2_class(operation: str) -> str:
    if operation in CLASS_A:
        return "A"
    if operation in CLASS_B:
        return "B"
    if operation in FREE:
        return "free"
    return "unknown"


def bucket_and_key(host: str, path: str) -> tuple[str | None, str]:
    # Virtual-hosted style is <bucket>.<account>.r2.cloudflarestorage.com; any other host is path style.
    if host.endswith(R2_SUFFIX) and host.count(".") == 4:
        return host.split(".")[0], path.lstrip("/")
    bucket, _, key = path.lstrip("/").partition("/")
    return bucket or None, key


def operation(method: str, has_key: bool, has_bucket: bool, query: dict, headers: dict) -> str:
    # S3 REST API: the operation follows from method, bucket/key and subresource query parameters.
    copy = "x-amz-copy-source" in headers
    if not has_bucket:
        return "ListBuckets" if method == "GET" else "Unknown"
    if not has_key:
        if method == "GET":
            for sub, op in (("uploads", "ListMultipartUploads"), ("location", "GetBucketLocation"),
                            ("cors", "GetBucketCors"), ("lifecycle", "GetBucketLifecycleConfiguration"),
                            ("encryption", "GetBucketEncryption")):
                if sub in query:
                    return op
            return "ListObjectsV2" if query.get("list-type") == ["2"] else "ListObjects"
        if method == "PUT":
            for sub, op in (("cors", "PutBucketCors"), ("lifecycle", "PutBucketLifecycleConfiguration"),
                            ("encryption", "PutBucketEncryption")):
                if sub in query:
                    return op
            return "PutBucket"
        return {"HEAD": "HeadBucket", "DELETE": "DeleteBucket"}.get(method) or (
            "DeleteObjects" if method == "POST" and "delete" in query else "Unknown"
        )
    if method == "HEAD":
        return "HeadObject"
    if method == "GET":
        return "ListParts" if "uploadId" in query else "GetObject"
    if method == "PUT":
        if "partNumber" in query and "uploadId" in query:
            return "UploadPartCopy" if copy else "UploadPart"
        return "CopyObject" if copy else "PutObject"
    if method == "POST":
        if "uploads" in query:
            return "CreateMultipartUpload"
        if "uploadId" in query:
            return "CompleteMultipartUpload"
    if method == "DELETE":
        return "AbortMultipartUpload" if "uploadId" in query else "DeleteObject"
    return "Unknown"


def classify(method: str, host: str, raw_path: str, headers: dict) -> dict:
    parts = urlsplit(raw_path)
    query = parse_qs(parts.query, keep_blank_values=True)
    headers = {k.lower(): v for k, v in headers.items()}
    bucket, key = bucket_and_key(host, unquote(parts.path))
    op = operation(method, bool(key), bool(bucket), query, headers)
    return {
        "bucket": bucket,
        "key": key,
        "operation": op,
        "class": r2_class(op),
        # Delta commits are put-if-absent (If-None-Match: *), F1.
        "conditional": any(h in headers for h in ("if-none-match", "if-match")),
    }


class R2Logger:
    def __init__(self):
        self.file = None

    def running(self):
        start = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        OUTPUT_DIR.mkdir(exist_ok=True)
        path = OUTPUT_DIR / f"proxy-{start}.jsonl"
        self.file = path.open("a")
        print(f"r2_proxy: logging to {path.relative_to(HERE)}")

    def response(self, flow):
        self.log(flow)

    def error(self, flow):
        # Failed flows (no response) are logged too, with status null.
        self.log(flow)

    def log(self, flow):
        req, resp = flow.request, flow.response
        if req.method == "CONNECT":
            return
        end = resp.timestamp_end if resp and resp.timestamp_end else datetime.now(UTC).timestamp()
        line = {
            "time": datetime.fromtimestamp(req.timestamp_start, UTC).isoformat(),
            "ts": req.timestamp_start,
            "host": req.pretty_host,
            "method": req.method,
            "path": urlsplit(req.path).path,
            "query": urlsplit(req.path).query,
            **classify(req.method, req.pretty_host, req.path, dict(req.headers)),
            "status": resp.status_code if resp else None,
            "error": str(flow.error) if flow.error else None,
            # Bodies are buffered by default, so raw (on-wire) sizes are exact.
            "request_bytes": len(req.raw_content or b""),
            "response_bytes": len(resp.raw_content or b"") if resp else 0,
            "duration_ms": round((end - req.timestamp_start) * 1000, 1),
        }
        self.file.write(json.dumps(line) + "\n")
        self.file.flush()

    def done(self):
        if self.file:
            self.file.close()


addons = [R2Logger()]
