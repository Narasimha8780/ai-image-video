from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    customer = "customer"
    admin = "admin"


class JobType(str, Enum):
    image = "image"
    talking_video = "talking_video"
    cinematic_video = "cinematic_video"


class JobState(str, Enum):
    queued = "queued"
    starting = "starting"
    running = "running"
    uploading = "uploading"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class EngineId(str, Enum):
    flux_schnell = "flux_schnell"
    sdxl = "sdxl"
    liveportrait_musetalk = "liveportrait_musetalk"
    wan2_2 = "wan2_2"
    seedance = "seedance"
    kling = "kling"


# --- Auth ---

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleSignInRequest(BaseModel):
    id_token: str
    email: Optional[str] = None
    display_name: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: UserRole
    credits: int
    daily_quota: int
    daily_used: int
    max_active_jobs: int
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Uploads ---

class UploadUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=3, max_length=128)
    purpose: Literal["portrait", "reference_image", "audio", "other"] = "reference_image"
    size_bytes: int = Field(..., gt=0, le=100 * 1024 * 1024)


class UploadUrlResponse(BaseModel):
    upload_id: str
    object_path: str
    upload_url: str
    method: str = "PUT"
    expires_in_seconds: int
    headers: dict[str, str] = Field(default_factory=dict)


# --- Jobs ---

class ImageParams(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: str = Field(default="", max_length=1000)
    aspect_ratio: Literal["1:1", "4:5", "9:16", "16:9"] = "4:5"
    seed: Optional[int] = Field(default=None, ge=0, le=2147483647)
    quality_preset: Literal["draft", "standard", "high"] = "standard"
    num_outputs: int = Field(default=1, ge=1, le=4)
    reference_image_path: Optional[str] = None


class TalkingVideoParams(BaseModel):
    portrait_path: str = Field(..., min_length=1)
    script_text: Optional[str] = Field(default=None, max_length=1200)
    audio_path: Optional[str] = None
    tts_voice: str = Field(default="en-US-Studio-O", max_length=80)
    language: str = Field(default="en-US", max_length=20)
    duration_seconds: int = Field(default=10, ge=5, le=30)
    orientation: Literal["vertical", "landscape"] = "vertical"
    rights_confirmed: bool = True


class CinematicVideoParams(BaseModel):
    mode: Literal["text_to_video", "image_to_video"] = "text_to_video"
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: str = Field(default="", max_length=1000)
    reference_image_path: Optional[str] = None
    duration_seconds: int = Field(default=5, ge=3, le=30)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    quality_preset: Literal["draft", "standard", "high"] = "standard"
    seed: Optional[int] = Field(default=None, ge=0, le=2147483647)


class JobCreateRequest(BaseModel):
    job_type: JobType
    engine: EngineId
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    params: dict[str, Any]


class AssetRef(BaseModel):
    asset_id: str
    object_path: str
    content_type: str
    filename: str
    size_bytes: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None


class JobOut(BaseModel):
    id: str
    user_id: str
    job_type: JobType
    engine: EngineId
    model_version: str
    state: JobState
    progress: int = 0
    status_message: str = ""
    params: dict[str, Any]
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[AssetRef] = Field(default_factory=list)
    estimated_credits: int
    actual_credits: Optional[int] = None
    estimated_seconds: int = 30
    retry_count: int = 0
    error_category: Optional[str] = None
    error_message: Optional[str] = None
    provider_job_id: Optional[str] = None
    idempotency_key: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    expires_at: Optional[str] = None


class AssetDownloadResponse(BaseModel):
    asset_id: str
    download_url: str
    filename: str
    content_type: str
    expires_in_seconds: int


# --- Usage & Models ---

class ModelRegistryItem(BaseModel):
    id: str
    name: str
    job_type: JobType
    provider: str
    version: str
    enabled: bool
    is_premium: bool = False
    base_credits: int
    notes: str
    license_note: str


class UsageTransaction(BaseModel):
    id: str
    user_id: str
    job_id: Optional[str] = None
    delta: int
    reason: str
    created_at: str


class UsageSummary(BaseModel):
    credits: int
    daily_quota: int
    daily_used: int
    max_active_jobs: int
    active_jobs: int
    transactions: list[UsageTransaction]


# --- Admin ---

class AdminUserUpdate(BaseModel):
    credits: Optional[int] = Field(default=None, ge=0)
    daily_quota: Optional[int] = Field(default=None, ge=1, le=1000)
    max_active_jobs: Optional[int] = Field(default=None, ge=1, le=50)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None


class AdminModelToggle(BaseModel):
    enabled: bool
