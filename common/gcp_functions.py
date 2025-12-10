"""
Helpers for uploading gzip-compressed PNG, HTML, and JSON artifacts to GCS.

Relies on application default credentials (GOOGLE_APPLICATION_CREDENTIALS)
and a default bucket name provided via the `GCS_BUCKET_NAME` env var.
"""

from __future__ import annotations

import gzip
import json
import os
from typing import Iterable, Mapping, Optional

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

BucketName = Optional[str]

_DEFAULT_BUCKET = os.getenv("GCS_BUCKET_NAME")
_storage_client: Optional[storage.Client] = None


def _client() -> storage.Client:
    """Get or create a singleton storage client."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def _prepare_blob(
    destination: str, bucket_name: BucketName, content_type: str
) -> storage.Blob:
    """
    Create a blob handle with the correct content type and gzip encoding.
    """
    bucket = _client().bucket(bucket_name or _DEFAULT_BUCKET)
    blob = bucket.blob(destination)
    blob.content_type = content_type
    blob.content_encoding = "gzip"
    return blob


def upload_html_gzip(
    html: str,
    destination: str,
    bucket_name: BucketName = None,
) -> bool:
    """
    Upload HTML text as gzip-compressed content to GCS.

    Returns True when upload succeeds.
    """
    compressed = gzip.compress(html.encode("utf-8"))
    blob = _prepare_blob(destination, bucket_name, "text/html; charset=utf-8")

    # Make the upload request content-type match the blob metadata.
    blob.upload_from_string(
        compressed,
        content_type=blob.content_type,
    )
    return True


def upload_png_gzip(
    data: bytes,
    destination: str,
    bucket_name: BucketName = None,
) -> bool:
    """
    Upload PNG bytes as gzip-compressed content to GCS.

    Accepts in-memory bytes to avoid writing temporary files. Returns True when
    upload succeeds.
    """
    compressed = gzip.compress(data)
    blob = _prepare_blob(destination, bucket_name, "image/png")

    blob.upload_from_string(
        compressed,
        content_type=blob.content_type,
    )

    return True


def upload_dicts_gzip(
    rows: Iterable[Mapping[str, object]],
    destination: str,
    bucket_name: BucketName = None,
) -> bool:
    """
    Upload an iterable of dictionaries as gzip-compressed JSON to GCS.

    The input is serialized as a JSON array to preserve structure. Returns True
    when upload succeeds.
    """
    json_bytes = json.dumps(list(rows), separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(json_bytes)
    blob = _prepare_blob(destination, bucket_name, "application/json")

    blob.upload_from_string(
        compressed,
        content_type=blob.content_type,
    )
    return True
