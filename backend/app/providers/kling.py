import uuid
import httpx

from ..config import get_settings
from ..models import AssetRef, JobOut, JobState
from ..storage import get_storage
from .base import ProviderResult, ProviderStatus, VideoProvider
from .local_comfy import _render_demo_mp4_stub


class KlingProvider(VideoProvider):
    """External Kling AI official API adapter."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def submit(self, job: JobOut) -> str:
        if not self.settings.kling_api_key:
            if self.settings.app_env == "local" and self.settings.local_simulate_gpu:
                return f"sim-kling-{job.id}"
            raise RuntimeError("KLING_API_KEY is not configured in Secret Manager")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.settings.kling_base_url}/videos/text2video",
                headers={"Authorization": f"Bearer {self.settings.kling_api_key}"},
                json={
                    "prompt": job.params.get("prompt", ""),
                    "negative_prompt": job.params.get("negative_prompt", ""),
                    "duration": str(job.params.get("duration_seconds", 5)),
                    "aspect_ratio": job.params.get("aspect_ratio", "9:16"),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("task_id") or f"kling-{job.id}"

    async def get_status(self, provider_job_id: str) -> ProviderStatus:
        if provider_job_id.startswith("sim-kling-"):
            return ProviderStatus(state=JobState.completed, progress=100, message="Kling generation complete")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.settings.kling_base_url}/videos/text2video/{provider_job_id}",
                headers={"Authorization": f"Bearer {self.settings.kling_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_status = (data.get("data", {}).get("task_status") or "").lower()
            mapping = {
                "submitted": JobState.queued,
                "processing": JobState.running,
                "succeed": JobState.completed,
                "failed": JobState.failed,
            }
            return ProviderStatus(
                state=mapping.get(raw_status, JobState.running),
                progress=100 if raw_status == "succeed" else 50,
                message=f"Kling status: {raw_status}",
            )

    async def fetch_result(self, provider_job_id: str, job: JobOut) -> ProviderResult:
        storage = get_storage()
        prefix = f"users/{job.user_id}/outputs/{job.id}"
        data = _render_demo_mp4_stub(job)
        filename = f"kling_{job.id[:8]}.gif"
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
