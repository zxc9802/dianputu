from __future__ import annotations

import base64
from datetime import UTC, datetime
import hashlib
import hmac
from typing import NamedTuple
from urllib.parse import quote, urlsplit

from app.core.config import ObjectStorageSettings, get_object_storage_settings


class DecodedDataUrl(NamedTuple):
    content: bytes
    content_type: str
    extension: str


def decode_data_url(data_url: str) -> DecodedDataUrl | None:
    if not data_url.startswith("data:"):
        return None
    header, separator, payload = data_url.partition(",")
    if not separator or ";base64" not in header:
        return None
    content_type = header.removeprefix("data:").split(";", 1)[0] or "application/octet-stream"
    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get(content_type, "bin")
    return DecodedDataUrl(base64.b64decode(payload, validate=False), content_type, extension)


def _normalize_prefix(prefix: str) -> str:
    return prefix.strip("/")


def build_object_key(settings: ObjectStorageSettings, folder: str, extension: str) -> str:
    digest = hashlib.sha256(f"{datetime.now(UTC).isoformat()}:{folder}".encode("utf-8")).hexdigest()[:16]
    timestamp = datetime.now(UTC).strftime("%Y%m%d/%H%M%S")
    parts = [_normalize_prefix(settings.key_prefix), folder.strip("/"), timestamp]
    return "/".join(part for part in parts if part) + f"-{digest}.{extension.lstrip('.')}"


def build_public_url(settings: ObjectStorageSettings, key: str) -> str:
    return settings.public_base_url.rstrip("/") + "/" + quote(key.lstrip("/"), safe="/")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signature_key(secret_key: str, date: str, region: str) -> bytes:
    date_key = _sign(("AWS4" + secret_key).encode("utf-8"), date)
    region_key = _sign(date_key, region)
    service_key = _sign(region_key, "s3")
    return _sign(service_key, "aws4_request")


async def upload_bytes_to_object_storage(
    content: bytes,
    *,
    content_type: str,
    folder: str,
    extension: str,
    settings: ObjectStorageSettings | None = None,
) -> str:
    settings = settings or get_object_storage_settings()
    if not settings.configured:
        return ""

    import httpx

    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    region = settings.region or "auto"
    key = build_object_key(settings, folder, extension)
    endpoint = settings.endpoint.rstrip("/")
    parsed = urlsplit(endpoint)
    host = parsed.netloc
    canonical_uri = "/" + quote(f"{settings.bucket}/{key}", safe="/")
    payload_hash = hashlib.sha256(content).hexdigest()
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{datestamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _signature_key(settings.secret_access_key, datestamp, region)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={settings.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.put(
            endpoint + canonical_uri,
            content=content,
            headers={
                "Authorization": authorization,
                "Content-Type": content_type,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
            },
        )
        response.raise_for_status()
    return build_public_url(settings, key)


async def upload_data_url_to_object_storage(data_url: str, *, folder: str) -> str:
    decoded = decode_data_url(data_url)
    if decoded is None:
        return ""
    return await upload_bytes_to_object_storage(
        decoded.content,
        content_type=decoded.content_type,
        folder=folder,
        extension=decoded.extension,
    )
