"""Bronze-side gzip reader (spike s008, P1 + P4 consumer).

Input: the gzip bytes stored by a collector. Output: the decompressed bytes; `ValueError` if not gzip.
"""

import gzip


def decompress_payload(data: bytes) -> bytes:
    try:
        return gzip.decompress(data)
    except gzip.BadGzipFile as error:
        raise ValueError("payload is not gzip") from error
