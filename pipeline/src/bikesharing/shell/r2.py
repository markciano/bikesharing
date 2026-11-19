"""Lists, downloads and uploads over R2's S3 API with ``obstore``.

The shell reaches R2 through an ``S3Store`` built from credentials passed
explicitly; every function takes any ``obstore`` store, so the tests run the
same code on a ``LocalStore`` over local folders (d008 #25, Runtime and
dependencies). A batch's objects are downloaded to the run's work folder, where
DuckDB reads them (d008 #9, Bronze reading).
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Final

import obstore
from obstore.store import ObjectStore, S3Store

from bikesharing.core.batching import Batch
from bikesharing.core.discovery import ListingPlan

_REGION: Final = "auto"
_MAX_CONCURRENT_DOWNLOADS: Final = 16


def r2_store(
    bucket: str, *, account_id: str, access_key_id: str, secret_access_key: str
) -> ObjectStore:
    """Build the store of an R2 bucket.

    Parameters
    ----------
    bucket : str
        The bucket's name.
    account_id : str
        The Cloudflare account that owns the bucket; it sets the endpoint.
    access_key_id : str
        The R2 API token's access key ID.
    secret_access_key : str
        The R2 API token's secret access key.

    Returns
    -------
    ObjectStore
        An ``S3Store`` on ``https://<account_id>.r2.cloudflarestorage.com`` with
        region ``auto``. It uses only the credentials passed, none from the
        environment or a profile.
    """
    return S3Store(
        bucket,
        endpoint=f"https://{account_id}.r2.cloudflarestorage.com",
        region=_REGION,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )


def list_keys(store: ObjectStore, plan: ListingPlan) -> list[str]:
    """List the keys of a plan's prefix after its start key.

    Parameters
    ----------
    store : ObjectStore
        The bronze bucket's store.
    plan : ListingPlan
        The prefix to list and the key the listing starts after.

    Returns
    -------
    list[str]
        The keys under ``plan.prefix`` that sort after ``plan.start_after``, or
        all of them if it is None, in no guaranteed order.
    """
    return [
        meta["path"]
        for page in obstore.list(store, prefix=plan.prefix, offset=plan.start_after)
        for meta in page
    ]


def download_batch(store: ObjectStore, batch: Batch, folder: Path) -> list[Path]:
    """Download a batch's objects concurrently.

    Each object is written to ``folder/<key>``, so that its path ends with its
    key, from which the models take its system and capture instant.

    Parameters
    ----------
    store : ObjectStore
        The bronze bucket's store.
    batch : Batch
        The batch whose objects are downloaded.
    folder : Path
        The work folder under which the keys are recreated.

    Returns
    -------
    list[Path]
        The downloaded files' paths, in the batch's order.

    Raises
    ------
    FileNotFoundError
        If an object of the batch is not in the bucket.
    """
    keys = [bronze_object.key for bronze_object in batch.objects]
    with ThreadPoolExecutor(max_workers=_MAX_CONCURRENT_DOWNLOADS) as pool:
        return list(pool.map(lambda key: _download(store, key, folder), keys))


def upload_log(store: ObjectStore, key: str, body: str) -> None:
    """Upload a run's log object.

    Parameters
    ----------
    store : ObjectStore
        The store of the bucket that holds the logs.
    key : str
        The log object's key.
    body : str
        The log's text, written as UTF-8.
    """
    obstore.put(store, key, body.encode("utf-8"))


def _download(store: ObjectStore, key: str, folder: Path) -> Path:
    """Stream one object to ``folder/<key>`` and return that path."""
    path = folder / key
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        for chunk in obstore.get(store, key).stream():
            file.write(chunk)
    return path
