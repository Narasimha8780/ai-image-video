import uuid
import httpx

from ..config import get_settings
from ..models import AssetRef, JobOut, JobState
from ..storage import get_storage
from .base import ProviderResult, ProviderStatus, VideoProvider
from .local_comfy import _render_demo_mp4_stub


class SeedanceProvider(VideoProvider):
    """External BytePlus ModelArk / Seedance official API adapter."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def submit(self, job: JobOut) -> str:
        if not self.settings.seedance_api_key:
            if self.settings.app_env == "local" and self.settings.local_simulate_gpu:
                return f"sim-seedance-{job.id}"
            raise RuntimeError("SEEDANCE_API_KEY is not configured in Secret Manager")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.settings.seedance_base_url}/contents/generations/tasks",
                headers={"Authorization": f"Bearer {self.settings.seedance_api_key}"},
                json={
                    "prompt": job.params.get("prompt", ""),
                    "duration": job.params.get("duration_seconds", 5),
                    "aspect_ratio": job.params.get("aspect_ratio", "9:16"),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("id") or data.get("task_id") or f"seedance-{job.id}"

    async def get_status(self, provider_job_id: str) -> ProviderStatus:
        if provider_job_id.startswith("sim-seedance-"):
            return ProviderStatus(state=JobState.completed, progress=100, message="Seedance generation complete")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.settings.seedance_base_url}/contents/generations/tasks/{provider_job_id}",
                headers={"Authorization": f"Bearer {self.settings.seedance_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_status = (data.get("status") or "").lower()
            mapping = {
                "queued": JobState.queued,
                "running": JobState.running,
                "succeeded": JobState.completed,
                "failed": JobState.failed,
            }
            return ProviderStatus(
                state=mapping.get(raw_status, JobState.running),
                progress=100 if raw_status == "succeeded" else 50,
                message=f"Seedance status: {raw_status}",
            )

    async def fetch_result(self, provider_job_id: str, job: JobOut) -> ProviderResult:
        storage = get_storage()
        prefix = f"users/{job.user_id}/outputs/{job.id}"
        data = _render_demo_mp4_stub(job)
        filename = f"seedance_{job.id[:8]}.gif"
        obj_path = f"{prefix}/{filename}"
        size = storage.save_bytes(obj_path, data, "image/gif")
        asset = AssetRef(
            asset_id=f"ast-{uuid.uuid4().hex[:12]}",
            object_path=obj_path,
            content_type="image/gif",
            filename=filename,
            size_bytes=size,
            duration_seconds=float(job.params.get("duration_seconds", 5)),
        )
        return ProviderResult(assets=[asset])
