import base64
import hashlib
import hmac
import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

from .config import get_settings


class StorageService:
    """Handles private object storage with short-lived signed upload/download URLs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if self.settings.app_env == "local":
            os.makedirs(self.settings.local_storage_dir, exist_ok=True)

    def build_user_prefix(self, user_id: str) -> str:
        return f"users/{user_id}/"

    def validate_user_object_path(self, user_id: str, object_path: str) -> str:
        clean = object_path.lstrip("/")
        if ".." in clean or not clean.startswith(self.build_user_prefix(user_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: invalid object prefix",
            )
        return clean

    def _sign_local_token(self, payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        b64 = base64.urlsafe_b64encode(raw).decode("ascii")
        sig = hmac.new(self.settings.jwt_secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{b64}.{sig}"

    def verify_local_token(self, token: str) -> dict:
        try:
            b64, sig = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Malformed storage token") from exc
        expected = hmac.new(self.settings.jwt_secret.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=403, detail="Invalid storage signature")
        payload = json.loads(base64.urlsafe_b64decode(b64.encode("ascii")))
        if payload.get("exp", 0) < int(time.time()):
            raise HTTPException(status_code=403, detail="Signed URL expired")
        return payload

    def _gcp_signing_kwargs(self) -> dict:
        """On Cloud Run, default credentials have no local private key; pass service_account_email + token for IAM signBlob."""
        import google.auth
        from google.auth.transport import requests as google_requests

        creds, _ = google.auth.default()
        if not hasattr(creds, "sign_bytes"):
            creds.refresh(google_requests.Request())
            sa_email = getattr(creds, "service_account_email", None)
            if sa_email and sa_email != "default":
                return {"service_account_email": sa_email, "access_token": creds.token}
        return {}

    def create_signed_upload_url(self, object_path: str, content_type: str) -> tuple[str, dict[str, str]]:
        ttl = self.settings.signed_url_ttl_seconds
        if self.settings.app_env == "gcp":
            from datetime import timedelta
            from google.cloud import storage

            client = storage.Client(project=self.settings.gcp_project_id)
            bucket = client.bucket(self.settings.gcs_bucket)
            blob = bucket.blob(object_path)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=ttl),
                method="PUT",
                content_type=content_type,
                **self._gcp_signing_kwargs(),
            )
            return url, {"Content-Type": content_type}

        token = self._sign_local_token(
            {
                "op": "upload",
                "path": object_path,
                "content_type": content_type,
                "exp": int(time.time()) + ttl,
            }
        )
        return f"/api/v1/local-storage/upload/{token}", {"Content-Type": content_type}

    def create_signed_download_url(
        self, object_path: str, filename: Optional[str] = None, proxy_base_url: str = ""
    ) -> str:
        ttl = self.settings.signed_url_ttl_seconds
        if self.settings.app_env == "gcp":
            try:
                from datetime import timedelta
                from google.cloud import storage

                client = storage.Client(project=self.settings.gcp_project_id)
                bucket = client.bucket(self.settings.gcs_bucket)
                blob = bucket.blob(object_path)
                disposition = f'attachment; filename="{filename}"' if filename else None
                return blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=ttl),
                    method="GET",
                    response_disposition=disposition,
                    **self._gcp_signing_kwargs(),
                )
            except Exception as exc:
                print(f"[storage] GCS signed URL failed, falling back to authorized proxy stream: {exc}")
                token = self._sign_local_token(
                    {
                        "op": "download",
                        "path": object_path,
                        "filename": filename,
                        "exp": int(time.time()) + ttl,
                    }
                )
                base = proxy_base_url.rstrip("/")
                return f"{base}/api/v1/local-storage/download/{token}"

        token = self._sign_local_token(
            {
                "op": "download",
                "path": object_path,
                "filename": filename,
                "exp": int(time.time()) + ttl,
            }
        )
        return f"/api/v1/local-storage/download/{token}"

    def local_full_path(self, object_path: str) -> Path:
        base = Path(self.settings.local_storage_dir).resolve()
        target = (base / object_path).resolve()
        if not str(target).startswith(str(base)):
            raise HTTPException(status_code=403, detail="Invalid local storage path")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def save_bytes(self, object_path: str, data: bytes, content_type: str = "application/octet-stream") -> int:
        if self.settings.app_env == "gcp":
            from google.cloud import storage

            client = storage.Client(project=self.settings.gcp_project_id)
            bucket = client.bucket(self.settings.gcs_bucket)
            blob = bucket.blob(object_path)
            blob.upload_from_string(data, content_type=content_type)
            return len(data)

        target = self.local_full_path(object_path)
        target.write_bytes(data)
        return len(data)

    def read_bytes(self, object_path: str) -> bytes:
        if self.settings.app_env == "gcp":
            from google.cloud import storage

            client = storage.Client(project=self.settings.gcp_project_id)
            bucket = client.bucket(self.settings.gcs_bucket)
            return bucket.blob(object_path).download_as_bytes()

        target = self.local_full_path(object_path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Object not found")
        return target.read_bytes()


@lru_cache
def get_storage() -> StorageService:
    return StorageService()
