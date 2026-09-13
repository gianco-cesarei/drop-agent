"""
Cloudflare R2 Object Storage Uploader for Drop Agent.
Supports S3-compatible single and multipart upload, automatic MIME detection,
immutable cache headers, and public/presigned CDN URL generation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import mimetypes
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("drop_agent.r2")

DEFAULT_BUCKET = "drops-library"
DEFAULT_CACHE_CONTROL = "public, max-age=31536000, immutable"
MULTIPART_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks

MIME_TYPE_MAP = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".m3u8": "application/vnd.apple.mpegurl",
    ".cue": "application/x-cue",
    ".xml": "application/xml",
    ".md": "text/markdown",
}


def _slug_segment(value: Optional[str], fallback: str = "unknown") -> str:
    """Normalize string for safe S3 object key paths."""
    if not value:
        return fallback
    text = unicodedata.normalize("NFKC", str(value).strip())
    text = text.replace("/", "-").replace("\\", "-")
    kept = []
    allowed_chars = set(" _.()[]&+'-")
    for ch in text:
        if ch in allowed_chars or ch.isalnum():
            kept.append(ch)
    cleaned = re.sub(r"\s+", " ", "".join(kept)).strip()
    return cleaned[:120] or fallback


class R2Uploader:
    """Cloudflare R2 uploader with multipart chunking and S3 SigV4 support."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket: Optional[str] = None,
        public_url: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.account_id = (account_id or os.environ.get("DROPS_R2_ACCOUNT_ID", "")).strip()
        self.access_key_id = (access_key_id or os.environ.get("DROPS_R2_ACCESS_KEY_ID", "")).strip()
        self.secret_access_key = (secret_access_key or os.environ.get("DROPS_R2_SECRET_ACCESS_KEY", "")).strip()
        self.bucket = (bucket or os.environ.get("DROPS_R2_BUCKET", DEFAULT_BUCKET)).strip()
        self.public_url = (public_url or os.environ.get("DROPS_R2_PUBLIC_URL", "")).rstrip("/")
        self.dry_run = dry_run
        
        self.endpoint_url = (
            os.environ.get("DROPS_R2_ENDPOINT_URL", "") or
            (f"https://{self.account_id}.r2.cloudflarestorage.com" if self.account_id else "")
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.access_key_id and self.secret_access_key and (self.endpoint_url or self.account_id))

    def detect_mime_type(self, file_path: str) -> str:
        """Determines proper Content-Type for audio, artwork, and playlist files."""
        ext = Path(file_path).suffix.lower()
        if ext in MIME_TYPE_MAP:
            return MIME_TYPE_MAP[ext]
        mime, _ = mimetypes.guess_type(file_path)
        return mime or "application/octet-stream"

    def build_object_key(
        self,
        category: str,
        folder_name: str,
        filename: str
    ) -> str:
        """Constructs canonical R2 key e.g.: audio/deep-house/01. Artist - Track.mp3"""
        cat_slug = _slug_segment(category, "audio")
        dir_slug = _slug_segment(folder_name, "releases")
        file_slug = _slug_segment(filename, "track.mp3")
        return f"{cat_slug}/{dir_slug}/{file_slug}"

    def get_public_url(self, key: str) -> str:
        """Returns public CDN streaming URL for the uploaded asset."""
        if self.public_url:
            return f"{self.public_url}/{key}"
        return f"https://{self.bucket}.r2.dev/{key}"

    def upload_file(
        self,
        local_path: str,
        key: str,
        content_type: Optional[str] = None,
        cache_control: str = DEFAULT_CACHE_CONTROL
    ) -> str:
        """
        Uploads a local file to Cloudflare R2.
        Returns the public URL (or presigned/R2 URL) of the uploaded object.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        mime = content_type or self.detect_mime_type(local_path)
        file_size = os.path.getsize(local_path)

        if self.dry_run or not self.is_configured:
            logger.info("[DRY-RUN / LOCAL] Uploaded %s to R2 key '%s' (%s, %d bytes)", local_path, key, mime, file_size)
            return self.get_public_url(key)

        # 1. Try Boto3 client if available
        try:
            import boto3
            from botocore.config import Config

            s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )

            extra_args = {
                "ContentType": mime,
                "CacheControl": cache_control,
            }

            s3_client.upload_file(
                Filename=local_path,
                Bucket=self.bucket,
                Key=key,
                ExtraArgs=extra_args
            )
            logger.info("Successfully uploaded %s to R2: %s", local_path, key)
            return self.get_public_url(key)
        except ImportError:
            logger.debug("Boto3 not installed, executing pure Python SigV4 REST upload")

        # 2. Pure Python S3 SigV4 REST Upload Fallback
        return self._pure_s3_upload(local_path, key, mime, cache_control)

    def _pure_s3_upload(
        self,
        local_path: str,
        key: str,
        content_type: str,
        cache_control: str
    ) -> str:
        """Pure-Python AWS SigV4 PUT Object for environments without Boto3."""
        import urllib.request
        import urllib.error

        with open(local_path, "rb") as f:
            payload = f.read()

        payload_hash = hashlib.sha256(payload).hexdigest()
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # Parse host from endpoint_url
        endpoint_clean = self.endpoint_url.replace("https://", "").replace("http://", "").rstrip("/")
        host = endpoint_clean
        canonical_uri = f"/{self.bucket}/{key}"
        canonical_querystring = ""
        
        canonical_headers = (
            f"cache-control:{cache_control}\n"
            f"content-type:{content_type}\n"
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "cache-control;content-type;host;x-amz-content-sha256;x-amz-date"
        
        canonical_request = (
            f"PUT\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/auto/s3/aws4_request"
        string_to_sign = (
            f"{algorithm}\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        # Signing key calculation
        k_date = hmac.new(("AWS4" + self.secret_access_key).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
        k_region = hmac.new(k_date, b"auto", hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        upload_url = f"{self.endpoint_url}/{self.bucket}/{key}"
        headers = {
            "Host": host,
            "Content-Type": content_type,
            "Cache-Control": cache_control,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization_header,
        }

        req = urllib.request.Request(upload_url, data=payload, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201, 204):
                    logger.info("Pure S3 upload successful: %s", key)
                    return self.get_public_url(key)
                raise RuntimeError(f"R2 PUT failed with status {resp.status}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error("R2 SigV4 PUT Error %d: %s", e.code, err_body)
            raise RuntimeError(f"R2 upload HTTP {e.code}: {err_body}")
