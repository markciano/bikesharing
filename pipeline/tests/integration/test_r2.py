"""Tests of the R2 adapter: listing, batch download and log upload.

The adapter's functions take any ``obstore`` store, so the tests run its
production code on a ``LocalStore`` over local folders, with no network
(d008, Runtime and dependencies).
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from obstore.store import LocalStore, ObjectStore, S3Store

from bikesharing.core.batching import Batch
from bikesharing.core.discovery import BronzeObject, ListingPlan, parse_bronze_key
from bikesharing.shell.r2 import download_batch, list_keys, r2_store, upload_log

if TYPE_CHECKING:
    # obstore exports its config types for type checkers only.
    from obstore.store import S3Config

BICING_PREFIX = "raw/bicing/station_status/"
BICING_KEYS = [
    "raw/bicing/station_status/2026-10-22/20261022T074219Z.json.gz",
    "raw/bicing/station_status/2026-10-22/20261022T074319Z.json.gz",
    "raw/bicing/station_status/2026-10-22/20261022T074419Z.json.gz",
    "raw/bicing/station_status/2026-10-22/20261022T074519Z.json.gz",
]


def _plan(prefix: str, start_after: str | None) -> ListingPlan:
    return ListingPlan(
        system="bicing",
        prefix=prefix,
        start_after=start_after,
        full_sweep=start_after is None,
    )


def _batch(keys: list[str]) -> Batch:
    objects: tuple[BronzeObject, ...] = tuple(parse_bronze_key(key) for key in keys)
    return Batch(number=1, objects=objects)


def _s3_config(store: ObjectStore) -> S3Config:
    assert isinstance(store, S3Store)
    return store.config


def test_r2_store_uses_the_account_endpoint_and_the_credentials_passed() -> None:
    store = r2_store(
        "bikesharing-bronze",
        account_id="acct123",
        access_key_id="key-id",
        secret_access_key="secret",
    )

    config = _s3_config(store)
    assert config["bucket"] == "bikesharing-bronze"
    assert config["endpoint"] == "https://acct123.r2.cloudflarestorage.com"
    assert config["region"] == "auto"
    assert config["access_key_id"] == "key-id"
    assert config["secret_access_key"] == "secret"


def test_r2_store_ignores_the_aws_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "env-token")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_ENDPOINT", "https://elsewhere.example")

    store = r2_store(
        "bikesharing-bronze",
        account_id="acct123",
        access_key_id="key-id",
        secret_access_key="secret",
    )

    config = _s3_config(store)
    assert config["access_key_id"] == "key-id"
    assert config["secret_access_key"] == "secret"
    assert config["region"] == "auto"
    assert config["endpoint"] == "https://acct123.r2.cloudflarestorage.com"
    assert "session_token" not in config


def test_list_keys_returns_the_keys_after_the_start_key(bronze_folder: Path) -> None:
    store = LocalStore(bronze_folder)

    keys = list_keys(store, _plan(BICING_PREFIX, BICING_KEYS[1]))

    assert sorted(keys) == BICING_KEYS[2:]


def test_list_keys_returns_the_whole_prefix_without_a_start_key(
    bronze_folder: Path,
) -> None:
    store = LocalStore(bronze_folder)

    keys = list_keys(store, _plan(BICING_PREFIX, None))

    assert sorted(keys) == BICING_KEYS


def test_list_keys_stays_within_the_prefix(bronze_folder: Path) -> None:
    store = LocalStore(bronze_folder)

    keys = list_keys(store, _plan(BICING_PREFIX, None))

    assert all(key.startswith(BICING_PREFIX) for key in keys)


def test_list_keys_is_empty_when_the_start_key_is_the_last(bronze_folder: Path) -> None:
    store = LocalStore(bronze_folder)

    keys = list_keys(store, _plan(BICING_PREFIX, BICING_KEYS[-1]))

    assert keys == []


def test_download_batch_writes_each_object_under_its_key(
    bronze_folder: Path, tmp_path: Path
) -> None:
    store = LocalStore(bronze_folder)
    folder = tmp_path / "work"

    paths = download_batch(store, _batch(BICING_KEYS), folder)

    for key, path in zip(BICING_KEYS, paths, strict=True):
        assert path == folder / key
        assert path.read_bytes() == (bronze_folder / key).read_bytes()


def test_download_batch_returns_the_paths_in_the_batch_order(
    bronze_folder: Path, tmp_path: Path
) -> None:
    store = LocalStore(bronze_folder)
    keys = [BICING_KEYS[2], BICING_KEYS[0], BICING_KEYS[3], BICING_KEYS[1]]

    paths = download_batch(store, _batch(keys), tmp_path / "work")

    assert [path.name for path in paths] == [key.rsplit("/", 1)[1] for key in keys]


def test_download_batch_names_the_capture_instant_in_the_path(
    bronze_folder: Path, tmp_path: Path
) -> None:
    store = LocalStore(bronze_folder)

    (path,) = download_batch(store, _batch(BICING_KEYS[:1]), tmp_path / "work")

    instant = datetime.strptime(path.name.removesuffix(".json.gz"), "%Y%m%dT%H%M%SZ")
    assert instant.replace(tzinfo=UTC) == datetime(2026, 10, 22, 7, 42, 19, tzinfo=UTC)
    assert path.parent.parent.name == "station_status"


def test_download_batch_of_no_objects_returns_no_paths(
    bronze_folder: Path, tmp_path: Path
) -> None:
    store = LocalStore(bronze_folder)

    assert download_batch(store, _batch([]), tmp_path / "work") == []


def test_download_batch_fails_on_a_missing_object(
    bronze_folder: Path, tmp_path: Path
) -> None:
    store = LocalStore(bronze_folder)
    missing = "raw/bicing/station_status/2026-10-22/20261022T000000Z.json.gz"

    with pytest.raises(FileNotFoundError):
        download_batch(store, _batch([BICING_KEYS[0], missing]), tmp_path / "work")


def test_upload_log_writes_the_body_under_the_key(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    store = LocalStore(logs)
    key = "pipeline/2026-11-19/run.jsonl"
    body = '{"event": "run_started"}\n{"event": "run_finished"}\n'

    upload_log(store, key, body)

    assert (logs / key).read_text(encoding="utf-8") == body
