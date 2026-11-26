from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"  # "local" | "gcp"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # GCP settings
    gcp_project_id: str = "ai-creator-studio-123456"
    gcp_region: str = "us-central1"
    firestore_database: str = "(default)"
    gcs_bucket: str = "ai-models"
    cloud_tasks_queue: str = "ai-studio-jobs"
    cloud_run_image_job: str = "ai-image-worker"
    cloud_run_video_job: str = "ai-video-worker"
    backend_public_url: str = "http://localhost:8000"

    # Local dev settings
    local_storage_dir: str = "./local_data/storage"
    local_db_path: str = "./local_data/studio.db"
    local_simulate_gpu: bool = True

    # External providers
    seedance_api_key: str = ""
    seedance_base_url: str = "https://ark.ap-southeast.byteplusapi.com/api/v3"
    kling_api_key: str = ""
    kling_base_url: str = "https://api.klingai.com/v1"

    # Cost & quota guardrails
    max_image_outputs: int = 4
    max_video_duration_seconds: int = 30
    max_upload_bytes: int = 100 * 1024 * 1024  # 100 MB
    signed_url_ttl_seconds: int = 900
    retention_days: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
