"""Media handling: proof-upload validation, storage, signed URLs
(spec §7.13/§15/§18.17) — the behaviour `storage/models.py`'s own
placeholder comment named as this app's job. `core.Media` (core/models.py)
is the DB table; this module is everything around it.

Deliberately not django-storages' `FileField`/`Storage` machinery —
`core.Media.storage_key` is a plain text column (the SQL schema's own
shape, D-25-style "SQL wins on structure"), not a `FileField`, and proofs
need signed, time-limited, staff-only GET URLs rather than a public
media URL. A thin boto3 client fits that directly.

Two backends, chosen once from `settings.S3_ENDPOINT` (never mixed):
- **S3-compatible** (MinIO on Clawsrv, D-28) when `S3_ENDPOINT` is set —
  the real production path.
- **Local filesystem**, under `settings.MEDIA_ROOT` — used automatically
  whenever `S3_ENDPOINT` is blank (local dev, tests: no MinIO container
  in either). `signed_proof_url()` has no local-mode equivalent yet
  (there is no consumer for it until milestone 5's staff EFT queue
  actually needs to *display* a proof) — it raises clearly rather than
  faking a signature, so a future caller can't be quietly handed a URL
  that isn't actually access-controlled.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from django.conf import settings

# §7.13: "Accepted proof types: image/jpeg, image/png, image/webp,
# application/pdf, max 8 MB, validated by magic bytes not extension."
_MAX_PROOF_BYTES = 8 * 1024 * 1024


def _is_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


_SNIFFERS = (
    ("image/jpeg", ".jpg", _is_jpeg),
    ("image/png", ".png", _is_png),
    ("image/webp", ".webp", _is_webp),
    ("application/pdf", ".pdf", _is_pdf),
)


class InvalidUpload(Exception):
    """`reason` matches Appendix C's `upload_invalid` `detail` values:
    `type` (unrecognised/disallowed content), `size` (over 8 MB or
    empty), `corrupt` (reserved for a future deeper check — this module
    only does magic-byte sniffing, not full codec validation)."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def sniff_mime_type(data: bytes) -> str | None:
    """Magic-byte sniff only — never trusts a client-supplied
    Content-Type/filename extension (§7.13's explicit requirement)."""
    for mime_type, _ext, check in _SNIFFERS:
        if check(data):
            return mime_type
    return None


def validate_proof(data: bytes) -> str:
    """Raises `InvalidUpload` or returns the sniffed mime type."""
    if not data:
        raise InvalidUpload("The uploaded file is empty.", reason="size")
    if len(data) > _MAX_PROOF_BYTES:
        raise InvalidUpload("Files must be 8 MB or smaller.", reason="size")
    mime_type = sniff_mime_type(data)
    if mime_type is None:
        raise InvalidUpload(
            "Only JPEG, PNG, WebP images or a PDF are accepted.", reason="type",
        )
    return mime_type


def _extension_for(mime_type: str) -> str:
    for candidate_mime, ext, _check in _SNIFFERS:
        if candidate_mime == mime_type:
            return ext
    return ""


def _s3_client() -> Any:  # pragma: no cover - exercised only when S3_ENDPOINT is set
    # boto3 ships no py.typed marker/stubs (mypy's import-untyped, seen
    # wherever boto3 is imported) — `Any` here is the honest type, not a
    # cop-out; there is no real static type for what boto3.client("s3")
    # returns without a stub package this project doesn't depend on.
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )


def store_proof_bytes(data: bytes, mime_type: str) -> str:
    """Stores already-validated proof bytes; returns the `storage_key` to
    put on the `core.Media` row. Caller (`core.eft.record_proof_upload`)
    owns the DB row — this only owns the bytes.
    """
    storage_key = f"proofs/{uuid.uuid4().hex}{_extension_for(mime_type)}"
    if settings.S3_ENDPOINT:  # pragma: no cover - no MinIO in dev/test
        _s3_client().put_object(
            Bucket=settings.S3_BUCKET_PROOFS, Key=storage_key, Body=data, ContentType=mime_type,
        )
    else:
        path = settings.MEDIA_ROOT / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return storage_key


def sha256_digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def signed_proof_url(storage_key: str, *, expires_seconds: int = 300) -> str:
    """§7.13: "signed GET URLs valid 5 minutes, staff-only." S3-only for
    now — no consumer needs this until the staff EFT queue (milestone 5)
    displays a proof; raising here instead of returning an unsigned path
    means that caller can't accidentally ship a URL with no real access
    control in local/dev mode.
    """
    if not settings.S3_ENDPOINT:  # pragma: no cover - no MinIO in dev/test
        raise NotImplementedError(
            "signed_proof_url() requires S3_ENDPOINT (MinIO/S3) to be configured; "
            "there is no signed-URL equivalent for the local filesystem fallback."
        )
    url: str = _s3_client().generate_presigned_url(  # pragma: no cover
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_PROOFS, "Key": storage_key},
        ExpiresIn=expires_seconds,
    )
    return url
