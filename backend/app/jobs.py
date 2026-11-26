import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from .config import get_settings
from .db import get_store, utc_now_iso
from .models import (
    CinematicVideoParams,
    EngineId,
    ImageParams,
    JobCreateRequest,
    JobOut,
    JobState,
    JobType,
    TalkingVideoParams,
    UserOut,
)
from .providers import KlingProvider, LocalComfyProvider, SeedanceProvider, VideoProvider
from .storage import get_storage


def get_provider(engine: EngineId) -> VideoProvider:
    if engine == EngineId.seedance:
        return SeedanceProvider()
    if engine == EngineId.kling:
        return KlingProvider()
    return LocalComfyProvider()


def validate_and_normalize_params(user_id: str, req: JobCreateRequest) -> tuple[dict[str, Any], list[str]]:
    storage = get_storage()
    input_refs: list[str] = []

    if req.job_type == JobType.image:
        if req.engine not in (EngineId.flux_schnell, EngineId.sdxl):
            raise HTTPException(status_code=400, detail="Unsupported engine for image generation")
        parsed = ImageParams(**req.params)
        if parsed.reference_image_path:
            clean = storage.validate_user_object_path(user_id, parsed.reference_image_path)
            input_refs.append(clean)
            parsed.reference_image_path = clean
        return parsed.model_dump(), input_refs

    if req.job_type == JobType.talking_video:
        if req.engine != EngineId.liveportrait_musetalk:
            raise HTTPException(status_code=400, detail="Unsupported engine for talking video")
        parsed = TalkingVideoParams(**req.params)
        if not parsed.rights_confirmed:
            raise HTTPException(status_code=400, detail="You must confirm rights to the uploaded portrait and voice")
        if not parsed.script_text and not parsed.audio_path:
            raise HTTPException(status_code=400, detail="Provide either a script or an audio file")
        clean_portrait = storage.validate_user_object_path(user_id, parsed.portrait_path)
        input_refs.append(clean_portrait)
        parsed.portrait_path = clean_portrait
        if parsed.audio_path:
            clean_audio = storage.validate_user_object_path(user_id, parsed.audio_path)
            input_refs.append(clean_audio)
            parsed.audio_path = clean_audio
        return parsed.model_dump(), input_refs

    if req.job_type == JobType.cinematic_video:
        if req.engine not in (EngineId.wan2_2, EngineId.seedance, EngineId.kling):
            raise HTTPException(status_code=400, detail="Unsupported engine for cinematic video")
        parsed = CinematicVideoParams(**req.params)
        if parsed.mode == "image_to_video" and not parsed.reference_image_path:
            raise HTTPException(status_code=400, detail="Reference image is required for image-to-video")
        if parsed.reference_image_path:
            clean_ref = storage.validate_user_object_path(user_id, parsed.reference_image_path)
            input_refs.append(clean_ref)
            parsed.reference_image_path = clean_ref
        return parsed.model_dump(), input_refs

    raise HTTPException(status_code=400, detail="Unsupported job type")


def estimate_credits(job_type: JobType, engine: EngineId, params: dict[str, Any], base_credits: int) -> tuple[int, int]:
    """Return (estimated_credits, estimated_seconds)."""
    if job_type == JobType.image:
        outputs = int(params.get("num_outputs", 1))
        quality_mult = 2 if params.get("quality_preset") == "high" else 1
        return base_credits * outputs * quality_mult, 12 * outputs

    duration = int(params.get("duration_seconds", 10))
    if job_type == JobType.talking_video:
        blocks = max(1, (duration + 9) // 10)
        return base_credits * blocks, duration * 3

    # cinematic_video
    blocks = max(1, (duration + 4) // 5)
    quality_mult = 2 if params.get("quality_preset") == "high" else 1
    return base_credits * blocks * quality_mult, duration * 5


async def create_and_enqueue_job(user: UserOut, req: JobCreateRequest) -> JobOut:
    store = get_store()
    settings = get_settings()

    # Idempotency check so duplicate browser clicks do not create duplicate paid jobs
    existing = store.get_job_by_idempotency(user.id, req.idempotency_key)
    if existing:
        return existing

    model = store.get_model(req.engine.value)
    if not model or not model.enabled:
        raise HTTPException(status_code=400, detail=f"Model '{req.engine.value}' is currently unavailable")

    params, input_refs = validate_and_normalize_params(user.id, req)
    est_credits, est_seconds = estimate_credits(req.job_type, req.engine, params, model.base_credits)

    job_id = f"job-{uuid.uuid4().hex[:12]}"
    try:
        store.reserve_credits_and_quota(user.id, est_credits, job_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc

    now = utc_now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=settings.retention_days)).isoformat()
    job = JobOut(
        id=job_id,
        user_id=user.id,
        job_type=req.job_type,
        engine=req.engine,
        model_version=model.version,
        state=JobState.queued,
        progress=5,
        status_message="Queued for dispatch",
        params=params,
        input_refs=input_refs,
        output_refs=[],
        estimated_credits=est_credits,
        actual_credits=None,
        estimated_seconds=est_seconds,
        retry_count=0,
        idempotency_key=req.idempotency_key,
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
    )
    store.create_job(job)
    await enqueue_job_dispatch(job.id)
    return job


async def enqueue_job_dispatch(job_id: str) -> None:
    settings = get_settings()
    if (
        settings.app_env == "gcp"
        and not settings.local_simulate_gpu
        and settings.backend_public_url.startswith("https://")
    ):
        try:
            from google.cloud import tasks_v2

            client = tasks_v2.CloudTasksClient()
            parent = client.queue_path(settings.gcp_project_id, settings.gcp_region, settings.cloud_tasks_queue)
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{settings.backend_public_url}/api/v1/internal/dispatch/{job_id}",
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"job_id": job_id}).encode("utf-8"),
                }
            }
            await asyncio.to_thread(client.create_task, request={"parent": parent, "task": task})
            return
        except Exception as exc:
            print(f"[jobs] Cloud Tasks dispatch failed, falling back to in-process async dispatch: {exc}")

    # Local dev or direct Cloud Run dispatch fallback
    asyncio.create_task(run_job_execution(job_id))


async def run_job_execution(job_id: str) -> None:
    store = get_store()
    job = store.get_job(job_id)
    if not job or job.state == JobState.cancelled:
        return

    provider = get_provider(job.engine)
    try:
        store.update_job(
            job_id,
            state=JobState.starting,
            progress=15,
            status_message="Starting worker & loading model weights",
            started_at=utc_now_iso(),
        )
        await asyncio.sleep(0.4)

        current = store.get_job(job_id)
        if not current or current.state == JobState.cancelled:
            return

        provider_job_id = await provider.submit(current)
        store.update_job(
            job_id,
            state=JobState.running,
            progress=45,
            status_message=f"Running inference ({job.engine.value})",
            provider_job_id=provider_job_id,
        )
        await asyncio.sleep(0.8)

        # Poll provider status
        for _ in range(30):
            current = store.get_job(job_id)
            if not current or current.state == JobState.cancelled:
                return
            pstatus = await provider.get_status(provider_job_id)
            if pstatus.state == JobState.completed:
                break
            if pstatus.state == JobState.failed:
                raise RuntimeError(pstatus.error_message or "Provider execution failed")
            store.update_job(
                job_id,
                progress=max(45, min(85, pstatus.progress)),
                status_message=pstatus.message or "Processing...",
            )
            await asyncio.sleep(0.5)

        store.update_job(
            job_id,
            state=JobState.uploading,
            progress=90,
            status_message="Uploading output assets to private bucket",
        )
        result = await provider.fetch_result(provider_job_id, current)
        store.update_job(
            job_id,
            state=JobState.completed,
            progress=100,
            status_message="Generation completed",
            output_refs=result.assets,
            actual_credits=job.estimated_credits,
            completed_at=utc_now_iso(),
        )
    except Exception as exc:
        store.update_job(
            job_id,
            state=JobState.failed,
            progress=0,
            status_message="Job failed",
            error_category="execution_error",
            error_message=str(exc),
        )
        # Refund reserved credits on failure if not already refunded
        if job.actual_credits is None:
            store.refund_credits(job.user_id, job.estimated_credits, job.id, "Refund for failed job")
