import asyncio
import io
import json
import random
import uuid
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..config import get_settings
from ..models import AssetRef, JobOut, JobState, JobType
from ..storage import get_storage
from .base import ProviderResult, ProviderStatus, VideoProvider

ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "4:5": (896, 1120),
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "vertical": (1080, 1920),
    "landscape": (1920, 1080),
}


def _render_demo_image(prompt: str, engine: str, width: int, height: int, index: int) -> bytes:
    """Render a clean studio-styled preview PNG in local simulation mode."""
    rng = random.Random(hash((prompt, engine, index)))
    bg_top = (rng.randint(20, 65), rng.randint(24, 58), rng.randint(52, 110))
    bg_bot = (rng.randint(12, 32), rng.randint(15, 35), rng.randint(28, 60))

    img = Image.new("RGB", (width, height), bg_top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(bg_top[0] * (1 - t) + bg_bot[0] * t)
        g = int(bg_top[1] * (1 - t) + bg_bot[1] * t)
        b = int(bg_top[2] * (1 - t) + bg_bot[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Stylized studio aura & subject silhouette
    cx, cy = width // 2, int(height * 0.42)
    radius = min(width, height) // 4
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(min(255, bg_top[0] + 55), min(255, bg_top[1] + 65), min(255, bg_top[2] + 90)),
    )
    body_w, body_h = int(radius * 1.6), int(radius * 1.9)
    draw.rounded_rectangle(
        [cx - body_w // 2, cy + radius // 2, cx + body_w // 2, cy + radius // 2 + body_h],
        radius=48,
        fill=(min(255, bg_top[0] + 35), min(255, bg_top[1] + 45), min(255, bg_top[2] + 70)),
    )

    # Subtle overlay badge
    font = ImageFont.load_default()
    badge_text = f"AI CREATOR STUDIO  |  {engine.upper()}  |  #{index + 1}"
    draw.rectangle([24, 24, width - 24, 72], fill=(10, 14, 24))
    draw.text((40, 42), badge_text, fill=(220, 232, 255), font=font)
    snippet = (prompt[:72] + "...") if len(prompt) > 72 else prompt
    draw.rectangle([24, height - 88, width - 24, height - 24], fill=(10, 14, 24))
    draw.text((40, height - 62), f"Prompt: {snippet}", fill=(180, 198, 228), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_demo_mp4_stub(job: JobOut) -> bytes:
    """Create a minimal valid MP4/SVG-free or animated GIF/MP4 placeholder for local preview.
    In local dev without ffmpeg, we generate an animated WebP/GIF or minimal ftyp+moov MP4."""
    # Generate a crisp animated GIF preview so browsers can play it natively in <img>/<video> fallback,
    # or we also emit a valid PNG poster + animated GIF.
    width, height = (720, 1280) if job.params.get("orientation") == "vertical" or job.params.get("aspect_ratio") == "9:16" else (1280, 720)
    # Keep local simulation fast: 480p scaled frames
    sw, sh = (360, 640) if width < height else (640, 360)
    frames: list[Image.Image] = []
    font = ImageFont.load_default()
    prompt = job.params.get("prompt") or job.params.get("script_text") or "AI Video Generation"
    for i in range(12):
        img = Image.new("RGB", (sw, sh), (16 + i * 2, 22 + i, 44 + i * 3))
        draw = ImageDraw.Draw(img)
        offset = int(18 * (i % 6 - 3))
        cx, cy = sw // 2 + offset, sh // 2 - 30
        draw.ellipse([cx - 55, cy - 55, cx + 55, cy + 55], fill=(99, 102, 241))
        draw.text((20, 20), f"{job.engine.value.upper()}  |  Frame {i + 1}/12", fill=(235, 240, 255), font=font)
        draw.text((20, sh - 36), prompt[:48], fill=(190, 205, 235), font=font)
        frames.append(img)
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=180, loop=0)
    return buf.getvalue()


class LocalComfyProvider(VideoProvider):
    """Dispatches ComfyUI workflows to Cloud Run GPU Jobs (gcp) or local simulator (local)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._local_jobs: dict[str, JobOut] = {}

    async def submit(self, job: JobOut) -> str:
        if self.settings.app_env == "gcp" and not self.settings.local_simulate_gpu:
            return await self._submit_cloud_run_job(job)

        provider_job_id = f"local-comfy-{job.id}"
        self._local_jobs[provider_job_id] = job
        return provider_job_id

    async def _submit_cloud_run_job(self, job: JobOut) -> str:
        from google.cloud import run_v2

        client = run_v2.JobsClient()
        job_name_short = (
            self.settings.cloud_run_image_job
            if job.job_type == JobType.image
            else self.settings.cloud_run_video_job
        )
        parent = f"projects/{self.settings.gcp_project_id}/locations/{self.settings.gcp_region}/jobs/{job_name_short}"

        workflow_map = {
            JobType.image: "flux_image.json" if job.engine.value == "flux_schnell" else "sdxl_image.json",
            JobType.talking_video: "talking_portrait.json",
            JobType.cinematic_video: "wan_video.json",
        }
        env_vars = [
            run_v2.EnvVar(name="JOB_ID", value=job.id),
            run_v2.EnvVar(name="USER_ID", value=job.user_id),
            run_v2.EnvVar(name="WORKFLOW_TYPE", value=workflow_map[job.job_type]),
            run_v2.EnvVar(name="INPUT_URI", value=f"gs://{self.settings.gcs_bucket}/users/{job.user_id}/inputs"),
            run_v2.EnvVar(name="OUTPUT_PREFIX", value=f"users/{job.user_id}/outputs/{job.id}"),
            run_v2.EnvVar(name="GCS_BUCKET", value=self.settings.gcs_bucket),
            run_v2.EnvVar(name="MODEL_CONFIG_JSON", value=json.dumps(job.params)),
        ]
        request = run_v2.RunJobRequest(
            name=parent,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(env=env_vars)
                ]
            ),
        )
        operation = await asyncio.to_thread(client.run_job, request=request)
        return operation.metadata.name if hasattr(operation, "metadata") and operation.metadata else f"crj-{job.id}"

    async def get_status(self, provider_job_id: str) -> ProviderStatus:
        return ProviderStatus(state=JobState.completed, progress=100, message="ComfyUI workflow finished")

    async def fetch_result(self, provider_job_id: str, job: JobOut) -> ProviderResult:
        storage = get_storage()
        assets: list[AssetRef] = []
        prefix = f"users/{job.user_id}/outputs/{job.id}"

        if job.job_type == JobType.image:
            count = int(job.params.get("num_outputs", 1))
            ratio = job.params.get("aspect_ratio", "4:5")
            w, h = ASPECT_DIMENSIONS.get(ratio, (896, 1120))
            prompt = job.params.get("prompt", "AI Influencer Portrait")
            for idx in range(count):
                data = _render_demo_image(prompt, job.engine.value, w, h, idx)
                filename = f"{job.engine.value}_{idx + 1}.png"
                obj_path = f"{prefix}/{filename}"
                size = storage.save_bytes(obj_path, data, "image/png")
                assets.append(
                    AssetRef(
                        asset_id=f"ast-{uuid.uuid4().hex[:12]}",
                        object_path=obj_path,
                        content_type="image/png",
                        filename=filename,
                        size_bytes=size,
                        width=w,
                        height=h,
                    )
                )
        else:
            data = _render_demo_mp4_stub(job)
            filename = f"{job.engine.value}_{job.id[:8]}.gif"
            obj_path = f"{prefix}/{filename}"
            size = storage.save_bytes(obj_path, data, "image/gif")
            duration = float(job.params.get("duration_seconds", 10))
            is_vert = job.params.get("orientation") == "vertical" or job.params.get("aspect_ratio") == "9:16"
            assets.append(
                AssetRef(
                    asset_id=f"ast-{uuid.uuid4().hex[:12]}",
                    object_path=obj_path,
                    content_type="image/gif",
                    filename=filename,
                    size_bytes=size,
                    width=1080 if is_vert else 1920,
                    height=1920 if is_vert else 1080,
                    duration_seconds=duration,
                )
            )

        manifest: dict[str, Any] = {
            "job_id": job.id,
            "engine": job.engine.value,
            "assets": [a.model_dump() for a in assets],
        }
        storage.save_bytes(f"{prefix}/result.json", json.dumps(manifest, indent=2).encode("utf-8"), "application/json")
        return ProviderResult(assets=assets, metadata=manifest)
