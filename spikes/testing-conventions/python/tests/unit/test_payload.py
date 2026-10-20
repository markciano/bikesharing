"""Unit tests for poc.payload: bronze-side gzip reader."""

import gzip

import pytest

from poc.payload import decompress_payload


def test_decompress_payload_returns_the_original_bytes():
    original = b'{"data": {"stations": []}}'

    assert decompress_payload(gzip.compress(original)) == original


def test_decompress_payload_rejects_bytes_that_are_not_gzip():
    with pytest.raises(ValueError):
        decompress_payload(b'{"data": {"stations": []}}')
