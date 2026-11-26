import os
import tempfile
import time
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    os.environ["APP_ENV"] = "local"
    os.environ["LOCAL_DB_PATH"] = str(tmp_path / "test_studio.db")
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp_path / "storage")
    os.environ["LOCAL_SIMULATE_GPU"] = "true"

    from app.config import get_settings
    from app.db import get_store
    from app.storage import get_storage

    get_settings.cache_clear()
    get_store.cache_clear()
    get_storage.cache_clear()

    from app.main import app

    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()


def test_auth_and_me(client: TestClient):
    data = _login(client, "creator@example.com", "creator123")
    token = data["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "creator@example.com"
    assert me.json()["role"] == "customer"


def test_upload_and_image_job_idempotency_and_isolation(client: TestClient):
    creator = _login(client, "creator@example.com", "creator123")
    headers = {"Authorization": f"Bearer {creator['access_token']}"}

    # 1. Request signed upload URL
    up_resp = client.post(
        "/api/v1/uploads",
        headers=headers,
        json={"filename": "ref.png", "content_type": "image/png", "purpose": "reference_image", "size_bytes": 128},
    )
    assert up_resp.status_code == 200
    upload_info = up_resp.json()
    put_resp = client.put(upload_info["upload_url"], content=b"fake-png-bytes")
    assert put_resp.status_code == 200

    # 2. Submit image job with idempotency key
    idem_key = f"idem-{uuid.uuid4().hex}"
    job_payload = {
        "job_type": "image",
        "engine": "flux_schnell",
        "idempotency_key": idem_key,
        "params": {
            "prompt": "Studio portrait of a fashion creator in golden hour lighting",
            "aspect_ratio": "4:5",
            "quality_preset": "standard",
            "num_outputs": 2,
            "reference_image_path": upload_info["object_path"],
        },
    }
    j1 = client.post("/api/v1/jobs", headers=headers, json=job_payload)
    assert j1.status_code == 201
    j2 = client.post("/api/v1/jobs", headers=headers, json=job_payload)
    assert j2.status_code == 201
    assert j1.json()["id"] == j2.json()["id"]

    # Wait briefly for local simulated execution to complete
    job_id = j1.json()["id"]
    final_job = None
    for _ in range(20):
        r = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert r.status_code == 200
        final_job = r.json()
        if final_job["state"] == "completed":
            break
        time.sleep(0.2)

    assert final_job is not None
    assert final_job["state"] == "completed"
    assert len(final_job["output_refs"]) == 2

    # 3. Signed asset download
    asset_id = final_job["output_refs"][0]["asset_id"]
    dl = client.get(f"/api/v1/assets/{asset_id}/download", headers=headers)
    assert dl.status_code == 200
    file_resp = client.get(dl.json()["download_url"])
    assert file_resp.status_code == 200
    assert len(file_resp.content) > 100

    # 4. Another user cannot access creator's job or asset
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password123", "display_name": "Other User"},
    )
    assert reg.status_code == 200
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    assert client.get(f"/api/v1/jobs/{job_id}", headers=other_headers).status_code == 403
    assert client.get(f"/api/v1/assets/{asset_id}/download", headers=other_headers).status_code == 403


def test_admin_controls(client: TestClient):
    admin = _login(client, "admin@example.com", "admin123")
    creator = _login(client, "creator@example.com", "creator123")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    creator_headers = {"Authorization": f"Bearer {creator['access_token']}"}

    # Customer cannot access admin routes
    assert client.get("/api/v1/admin/overview", headers=creator_headers).status_code == 403

    # Admin can inspect overview & toggle model
    ov = client.get("/api/v1/admin/overview", headers=admin_headers)
    assert ov.status_code == 200
    assert ov.json()["total_users"] >= 2

    toggle = client.post("/api/v1/admin/models/kling", headers=admin_headers, json={"enabled": False})
    assert toggle.status_code == 200
    assert toggle.json()["enabled"] is False
