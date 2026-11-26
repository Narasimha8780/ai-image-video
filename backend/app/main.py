import uuid
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_google_token,
    verify_password,
)
from .config import get_settings
from .db import get_store
from .jobs import create_and_enqueue_job, enqueue_job_dispatch, run_job_execution
from .models import (
    AdminModelToggle,
    AdminUserUpdate,
    AssetDownloadResponse,
    GoogleSignInRequest,
    JobCreateRequest,
    JobOut,
    JobState,
    LoginRequest,
    ModelRegistryItem,
    RegisterRequest,
    TokenResponse,
    UploadUrlRequest,
    UploadUrlResponse,
    UsageSummary,
    UserOut,
    UserRole,
)
from .storage import get_storage

settings = get_settings()

app = FastAPI(
    title="AI Creator Studio API",
    version="1.0.0",
    description="Backend API for AI Influencer Images, Talking-Head Videos, and Cinematic Clips",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {exc}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "env": settings.app_env}


# --- Auth routes ---

@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    store = get_store()
    if store.get_user_with_hash_by_email(req.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = store.create_user(req.email, req.display_name, hash_password(req.password))
    token = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, user=user)


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    store = get_store()
    found = store.get_user_with_hash_by_email(req.email)
    if not found:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user, pw_hash = found
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    if not verify_password(req.password, pw_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, user=user)


@app.post("/api/v1/auth/google", response_model=TokenResponse)
async def google_sign_in(req: GoogleSignInRequest):
    store = get_store()
    info = verify_google_token(req.id_token)
    email = info.get("email") or req.email
    if not email:
        raise HTTPException(status_code=400, detail="Google account email missing")
    found = store.get_user_with_hash_by_email(email)
    if found:
        user, _ = found
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
    else:
        display_name = info.get("name") or req.display_name or email.split("@")[0]
        user = store.create_user(email, display_name, hash_password(uuid.uuid4().hex))
    token = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, user=user)


@app.get("/api/v1/auth/me", response_model=UserOut)
async def get_me(user: UserOut = Depends(get_current_user)):
    return user


# --- Uploads ---

@app.post("/api/v1/uploads", response_model=UploadUrlResponse)
async def create_upload_url(req: UploadUrlRequest, user: UserOut = Depends(get_current_user)):
    storage = get_storage()
    upload_id = f"upl-{uuid.uuid4().hex[:12]}"
    safe_name = req.filename.replace("/", "_").replace("\\", "_")
    object_path = f"users/{user.id}/inputs/{upload_id}_{safe_name}"
    url, headers = storage.create_signed_upload_url(object_path, req.content_type)
    return UploadUrlResponse(
        upload_id=upload_id,
        object_path=object_path,
        upload_url=url,
        method="PUT",
        expires_in_seconds=settings.signed_url_ttl_seconds,
        headers=headers,
    )


@app.put("/api/v1/local-storage/upload/{token}")
async def local_storage_upload(token: str, request: Request):
    if settings.app_env != "local":
        raise HTTPException(status_code=404, detail="Not available in GCP mode")
    storage = get_storage()
    payload = storage.verify_local_token(token)
    if payload.get("op") != "upload":
        raise HTTPException(status_code=403, detail="Invalid upload token")
    body = await request.body()
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed upload size")
    storage.save_bytes(payload["path"], body, payload.get("content_type", "application/octet-stream"))
    return {"status": "uploaded", "object_path": payload["path"], "size_bytes": len(body)}


@app.get("/api/v1/local-storage/download/{token}")
async def local_storage_download(token: str):
    if settings.app_env != "local":
        raise HTTPException(status_code=404, detail="Not available in GCP mode")
    storage = get_storage()
    payload = storage.verify_local_token(token)
    if payload.get("op") != "download":
        raise HTTPException(status_code=403, detail="Invalid download token")
    data = storage.read_bytes(payload["path"])
    filename = payload.get("filename") or payload["path"].split("/")[-1]
    media_type = "image/png" if filename.endswith(".png") else "image/gif" if filename.endswith(".gif") else "application/octet-stream"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# --- Jobs ---

@app.post("/api/v1/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(req: JobCreateRequest, user: UserOut = Depends(get_current_user)):
    return await create_and_enqueue_job(user, req)


@app.get("/api/v1/jobs", response_model=list[JobOut])
async def list_jobs(
    job_type: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    user: UserOut = Depends(get_current_user),
):
    store = get_store()
    return store.list_jobs(user_id=user.id, job_type=job_type, state=state)


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: UserOut = Depends(get_current_user)):
    store = get_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return job


@app.post("/api/v1/jobs/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: str, user: UserOut = Depends(get_current_user)):
    store = get_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")
    if job.state != JobState.failed:
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    # Re-reserve credits only if they were refunded on failure
    if job.actual_credits is None:
        try:
            store.reserve_credits_and_quota(job.user_id, job.estimated_credits, job.id)
        except PermissionError as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc

    updated = store.update_job(
        job_id,
        state=JobState.queued,
        progress=5,
        status_message="Re-queued for retry",
        retry_count=job.retry_count + 1,
        error_category=None,
        error_message=None,
    )
    await enqueue_job_dispatch(job_id)
    return updated


@app.delete("/api/v1/jobs/{job_id}", response_model=JobOut)
async def cancel_or_delete_job(job_id: str, user: UserOut = Depends(get_current_user)):
    store = get_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    if job.state in (JobState.queued, JobState.starting, JobState.running):
        updated = store.update_job(
            job_id,
            state=JobState.cancelled,
            status_message="Cancelled by user",
        )
        if job.actual_credits is None:
            store.refund_credits(job.user_id, job.estimated_credits, job.id, "Refund for cancelled job")
        return updated

    # For completed/failed jobs, mark output_refs cleared to simulate deletion
    return store.update_job(job_id, status_message="Outputs deleted by user", output_refs=[])


@app.get("/api/v1/assets/{asset_id}/download", response_model=AssetDownloadResponse)
async def download_asset(asset_id: str, user: UserOut = Depends(get_current_user)):
    store = get_store()
    storage = get_storage()
    found = store.find_asset(asset_id)
    if not found:
        raise HTTPException(status_code=404, detail="Asset not found")
    job, asset = found
    if job.user_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    url = storage.create_signed_download_url(asset.object_path, asset.filename)
    return AssetDownloadResponse(
        asset_id=asset.asset_id,
        download_url=url,
        filename=asset.filename,
        content_type=asset.content_type,
        expires_in_seconds=settings.signed_url_ttl_seconds,
    )


# --- Internal Cloud Tasks dispatch target ---

@app.post("/api/v1/internal/dispatch/{job_id}")
async def internal_dispatch(job_id: str):
    await run_job_execution(job_id)
    return {"status": "dispatched", "job_id": job_id}


# --- Models & Usage ---

@app.get("/api/v1/models", response_model=list[ModelRegistryItem])
async def list_models(user: UserOut = Depends(get_current_user)):
    return get_store().list_models()


@app.get("/api/v1/usage", response_model=UsageSummary)
async def get_usage(user: UserOut = Depends(get_current_user)):
    store = get_store()
    return UsageSummary(
        credits=user.credits,
        daily_quota=user.daily_quota,
        daily_used=user.daily_used,
        max_active_jobs=user.max_active_jobs,
        active_jobs=store.count_active_jobs(user.id),
        transactions=store.list_transactions(user.id),
    )


# --- Admin Console ---

@app.get("/api/v1/admin/overview")
async def admin_overview(admin: UserOut = Depends(require_admin)):
    store = get_store()
    all_jobs = store.list_jobs(limit=200)
    users = store.list_users()
    failed = [j for j in all_jobs if j.state == JobState.failed]
    completed = [j for j in all_jobs if j.state == JobState.completed]
    active = [j for j in all_jobs if j.state in (JobState.queued, JobState.starting, JobState.running, JobState.uploading)]
    total_credits_spent = sum(j.actual_credits or 0 for j in completed)
    return {
        "total_users": len(users),
        "total_jobs": len(all_jobs),
        "active_queue_depth": len(active),
        "completed_jobs": len(completed),
        "failed_jobs": len(failed),
        "total_credits_consumed": total_credits_spent,
    }


@app.get("/api/v1/admin/users", response_model=list[UserOut])
async def admin_list_users(admin: UserOut = Depends(require_admin)):
    return get_store().list_users()


@app.patch("/api/v1/admin/users/{user_id}", response_model=UserOut)
async def admin_update_user(user_id: str, body: AdminUserUpdate, admin: UserOut = Depends(require_admin)):
    updated = get_store().update_user(user_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@app.get("/api/v1/admin/jobs", response_model=list[JobOut])
async def admin_list_jobs(
    state: Optional[str] = Query(default=None),
    admin: UserOut = Depends(require_admin),
):
    return get_store().list_jobs(state=state, limit=200)


@app.post("/api/v1/admin/models/{model_id}", response_model=ModelRegistryItem)
async def admin_toggle_model(model_id: str, body: AdminModelToggle, admin: UserOut = Depends(require_admin)):
    updated = get_store().toggle_model(model_id, body.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")
    return updated
