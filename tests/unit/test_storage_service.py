"""Unit tests for storage/service.py's proof-upload validation (spec
§7.13) — pure functions, no DB, no S3/MinIO. `store_proof_bytes`'s local
filesystem fallback needs `settings.MEDIA_ROOT` and touches disk, so it's
exercised in the integration suite instead (tests/integration/test_eft.py),
same split the rest of this project draws between unit and integration.
"""
from __future__ import annotations

import pytest

from storage.service import InvalidUpload, public_dish_image_url, sniff_mime_type, validate_proof

# Real magic bytes for each accepted type, plus enough padding that a
# "too small to be a real file" check (if this module ever grows one)
# wouldn't trip on these fixtures by accident.
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 32
_PDF = b"%PDF-1.4\n" + b"\x00" * 32


class TestSniffMimeType:
    def test_jpeg(self) -> None:
        assert sniff_mime_type(_JPEG) == "image/jpeg"

    def test_png(self) -> None:
        assert sniff_mime_type(_PNG) == "image/png"

    def test_webp(self) -> None:
        assert sniff_mime_type(_WEBP) == "image/webp"

    def test_pdf(self) -> None:
        assert sniff_mime_type(_PDF) == "application/pdf"

    def test_unrecognised_bytes_return_none(self) -> None:
        assert sniff_mime_type(b"not a real file at all") is None

    def test_a_gif_is_not_accepted(self) -> None:
        # §7.13's accepted list is explicit: jpeg/png/webp/pdf only.
        assert sniff_mime_type(b"GIF89a" + b"\x00" * 32) is None

    def test_extension_is_never_trusted_only_magic_bytes(self) -> None:
        # A `.jpg`-named payload that isn't really a JPEG must not sniff
        # as one — §7.13: "validated by magic bytes not extension."
        assert sniff_mime_type(b"this is actually plain text") is None


class TestValidateProof:
    def test_valid_jpeg_returns_its_mime_type(self) -> None:
        assert validate_proof(_JPEG) == "image/jpeg"

    def test_empty_file_is_rejected_as_size(self) -> None:
        with pytest.raises(InvalidUpload) as exc_info:
            validate_proof(b"")
        assert exc_info.value.reason == "size"

    def test_oversized_file_is_rejected_as_size(self) -> None:
        oversized = _JPEG + b"\x00" * (8 * 1024 * 1024)
        with pytest.raises(InvalidUpload) as exc_info:
            validate_proof(oversized)
        assert exc_info.value.reason == "size"

    def test_exactly_8mb_is_accepted(self) -> None:
        exactly_8mb = _JPEG + b"\x00" * (8 * 1024 * 1024 - len(_JPEG))
        assert len(exactly_8mb) == 8 * 1024 * 1024
        assert validate_proof(exactly_8mb) == "image/jpeg"

    def test_unrecognised_type_is_rejected_as_type(self) -> None:
        with pytest.raises(InvalidUpload) as exc_info:
            validate_proof(b"not a real file at all")
        assert exc_info.value.reason == "type"


class TestPublicDishImageUrl:
    def test_cdn_wins(self, settings) -> None:
        settings.CDN_BASE_URL = "https://cdn.example"
        settings.S3_PUBLIC_ENDPOINT = "https://minio.example"
        assert public_dish_image_url("dish-images/abc.png") == "https://cdn.example/dish-images/abc.png"

    def test_s3_public_endpoint(self, settings) -> None:
        settings.CDN_BASE_URL = ""
        settings.S3_PUBLIC_ENDPOINT = "https://minio.example"
        settings.S3_BUCKET_PUBLIC = "curry-media"
        assert (
            public_dish_image_url("dish-images/abc.png")
            == "https://minio.example/curry-media/dish-images/abc.png"
        )

    def test_local_media_path(self, settings) -> None:
        settings.CDN_BASE_URL = ""
        settings.S3_PUBLIC_ENDPOINT = ""
        settings.MEDIA_URL = "/media/"
        assert public_dish_image_url("dish-images/abc.png") == "/media/dish-images/abc.png"

    def test_empty_key(self) -> None:
        assert public_dish_image_url("") == ""
