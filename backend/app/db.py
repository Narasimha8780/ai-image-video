import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from .auth import hash_password
from .config import get_settings
from .models import (
    AssetRef,
    JobOut,
    JobState,
    JobType,
    ModelRegistryItem,
    UsageTransaction,
    UserOut,
    UserRole,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_MODELS: list[dict[str, Any]] = [
    {
        "id": "flux_schnell",
        "name": "FLUX.1-schnell (Quantized)",
        "job_type": JobType.image.value,
        "provider": "local_comfy",
        "version": "1.0-fp8",
        "enabled": True,
        "is_premium": False,
        "base_credits": 2,
        "notes": "Fast photorealistic AI influencer portraits on NVIDIA L4.",
        "license_note": "Apache-2.0 weights; verify commercial terms for downstream LoRAs.",
    },
    {
        "id": "sdxl",
        "name": "SDXL 1.0 Base",
        "job_type": JobType.image.value,
        "provider": "local_comfy",
        "version": "1.0",
        "enabled": True,
        "is_premium": False,
        "base_credits": 1,
        "notes": "Mature ComfyUI baseline with wide style support.",
        "license_note": "CreativeML Open RAIL++-M License.",
    },
    {
        "id": "liveportrait_musetalk",
        "name": "LivePortrait + MuseTalk",
        "job_type": JobType.talking_video.value,
        "provider": "local_comfy",
        "version": "1.5",
        "enabled": True,
        "is_premium": False,
        "base_credits": 8,
        "notes": "Audio-driven portrait animation + lip-sync, upscaled to 1080p MP4.",
        "license_note": "Verify TTS voice and portrait likeness rights before commercial use.",
    },
    {
        "id": "wan2_2",
        "name": "Wan 2.2 TI2V-5B",
        "job_type": JobType.cinematic_video.value,
        "provider": "local_comfy",
        "version": "2.2-5B",
        "enabled": True,
        "is_premium": False,
        "base_credits": 12,
        "notes": "Open cinematic video model; short clips joined with FFmpeg on L4.",
        "license_note": "Apache-2.0; check model card for commercial usage conditions.",
    },
    {
        "id": "seedance",
        "name": "Seedance (BytePlus ModelArk)",
        "job_type": JobType.cinematic_video.value,
        "provider": "seedance",
        "version": "api-v3",
        "enabled": True,
        "is_premium": True,
        "base_credits": 20,
        "notes": "Hosted premium video engine via official BytePlus API.",
        "license_note": "Subject to BytePlus ModelArk commercial terms & API key.",
    },
    {
        "id": "kling",
        "name": "Kling AI Official API",
        "job_type": JobType.cinematic_video.value,
        "provider": "kling",
        "version": "api-v1",
        "enabled": True,
        "is_premium": True,
        "base_credits": 22,
        "notes": "Hosted premium cinematic video engine via official Kling API.",
        "license_note": "Subject to Kling AI commercial terms & API key.",
    },
]


class LocalStore:
    """SQLite-backed store for local development and automated tests."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_schema()
        self._seed_defaults()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    credits INTEGER NOT NULL,
                    daily_quota INTEGER NOT NULL,
                    daily_used INTEGER NOT NULL,
                    daily_reset_date TEXT NOT NULL,
                    max_active_jobs INTEGER NOT NULL,
                    is_active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    state TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    status_message TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    input_refs_json TEXT NOT NULL,
                    output_refs_json TEXT NOT NULL,
                    estimated_credits INTEGER NOT NULL,
                    actual_credits INTEGER,
                    estimated_seconds INTEGER NOT NULL,
                    retry_count INTEGER NOT NULL,
                    error_category TEXT,
                    error_message TEXT,
                    provider_job_id TEXT,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    expires_at TEXT,
                    UNIQUE(user_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    job_id TEXT,
                    delta INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    version TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    is_premium INTEGER NOT NULL,
                    base_credits INTEGER NOT NULL,
                    notes TEXT NOT NULL,
                    license_note TEXT NOT NULL
                );
                """
            )

    def _seed_defaults(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            for model in DEFAULT_MODELS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO models
                    (id, name, job_type, provider, version, enabled, is_premium, base_credits, notes, license_note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model["id"],
                        model["name"],
                        model["job_type"],
                        model["provider"],
                        model["version"],
                        1 if model["enabled"] else 0,
                        1 if model["is_premium"] else 0,
                        model["base_credits"],
                        model["notes"],
                        model["license_note"],
                    ),
                )

            existing = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
            if existing == 0:
                demo_users = [
                    (
                        "user-creator-1",
                        "creator@example.com",
                        "Alex Creator",
                        hash_password("creator123"),
                        UserRole.customer.value,
                        250,
                        40,
                        0,
                        today,
                        5,
                        1,
                        now,
                    ),
                    (
                        "user-admin-1",
                        "admin@example.com",
                        "Studio Admin",
                        hash_password("admin123"),
                        UserRole.admin.value,
                        1000,
                        200,
                        0,
                        today,
                        20,
                        1,
                        now,
                    ),
                ]
                conn.executemany(
                    """
                    INSERT INTO users
                    (id, email, display_name, password_hash, role, credits, daily_quota, daily_used,
                     daily_reset_date, max_active_jobs, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    demo_users,
                )
                conn.execute(
                    "INSERT INTO transactions (id, user_id, job_id, delta, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), "user-creator-1", None, 250, "Initial welcome credits", now),
                )

    def _row_to_user(self, row: sqlite3.Row) -> UserOut:
        return UserOut(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            role=UserRole(row["role"]),
            credits=row["credits"],
            daily_quota=row["daily_quota"],
            daily_used=row["daily_used"],
            max_active_jobs=row["max_active_jobs"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    def _row_to_job(self, row: sqlite3.Row) -> JobOut:
        return JobOut(
            id=row["id"],
            user_id=row["user_id"],
            job_type=JobType(row["job_type"]),
            engine=row["engine"],
            model_version=row["model_version"],
            state=JobState(row["state"]),
            progress=row["progress"],
            status_message=row["status_message"],
            params=json.loads(row["params_json"]),
            input_refs=json.loads(row["input_refs_json"]),
            output_refs=[AssetRef(**item) for item in json.loads(row["output_refs_json"])],
            estimated_credits=row["estimated_credits"],
            actual_credits=row["actual_credits"],
            estimated_seconds=row["estimated_seconds"],
            retry_count=row["retry_count"],
            error_category=row["error_category"],
            error_message=row["error_message"],
            provider_job_id=row["provider_job_id"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            expires_at=row["expires_at"],
        )

    # --- User methods ---

    def get_user_by_id(self, user_id: str) -> Optional[UserOut]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(row) if row else None

    def get_user_with_hash_by_email(self, email: str) -> Optional[tuple[UserOut, str]]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
            if not row:
                return None
            return self._row_to_user(row), row["password_hash"]

    def create_user(self, email: str, display_name: str, password_hash: str, role: UserRole = UserRole.customer) -> UserOut:
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        today = datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users
                (id, email, display_name, password_hash, role, credits, daily_quota, daily_used,
                 daily_reset_date, max_active_jobs, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email.lower(), display_name, password_hash, role.value, 100, 25, 0, today, 4, 1, now),
            )
            conn.execute(
                "INSERT INTO transactions (id, user_id, job_id, delta, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, None, 100, "Initial signup credits", now),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(row)

    def list_users(self) -> list[UserOut]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            return [self._row_to_user(r) for r in rows]

    def update_user(self, user_id: str, updates: dict[str, Any]) -> Optional[UserOut]:
        allowed = {"credits", "daily_quota", "max_active_jobs", "is_active", "role"}
        fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not fields:
            return self.get_user_by_id(user_id)
        if "role" in fields and isinstance(fields["role"], UserRole):
            fields["role"] = fields["role"].value
        if "is_active" in fields:
            fields["is_active"] = 1 if fields["is_active"] else 0

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(row) if row else None

    def reserve_credits_and_quota(self, user_id: str, credits_needed: int, job_id: str) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError("User not found")
            daily_used = 0 if row["daily_reset_date"] != today else row["daily_used"]
            if daily_used >= row["daily_quota"]:
                raise PermissionError("Daily generation quota reached")
            if row["credits"] < credits_needed:
                raise PermissionError("Insufficient credits")
            active_cnt = conn.execute(
                "SELECT COUNT(*) as cnt FROM jobs WHERE user_id = ? AND state IN ('queued', 'starting', 'running', 'uploading')",
                (user_id,),
            ).fetchone()["cnt"]
            if active_cnt >= row["max_active_jobs"]:
                raise PermissionError("Maximum concurrent active jobs reached")

            conn.execute(
                "UPDATE users SET credits = credits - ?, daily_used = ?, daily_reset_date = ? WHERE id = ?",
                (credits_needed, daily_used + 1, today, user_id),
            )
            conn.execute(
                "INSERT INTO transactions (id, user_id, job_id, delta, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, job_id, -credits_needed, "Job generation reserve", now),
            )

    def refund_credits(self, user_id: str, credits: int, job_id: str, reason: str) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (credits, user_id))
            conn.execute(
                "INSERT INTO transactions (id, user_id, job_id, delta, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, job_id, credits, reason, now),
            )

    def list_transactions(self, user_id: str, limit: int = 50) -> list[UsageTransaction]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [UsageTransaction(**dict(r)) for r in rows]

    # --- Job methods ---

    def get_job_by_idempotency(self, user_id: str, idempotency_key: str) -> Optional[JobOut]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            return self._row_to_job(row) if row else None

    def create_job(self, job: JobOut) -> JobOut:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, user_id, job_type, engine, model_version, state, progress, status_message,
                    params_json, input_refs_json, output_refs_json, estimated_credits, actual_credits,
                    estimated_seconds, retry_count, error_category, error_message, provider_job_id,
                    idempotency_key, created_at, updated_at, started_at, completed_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.user_id,
                    job.job_type.value,
                    job.engine.value,
                    job.model_version,
                    job.state.value,
                    job.progress,
                    job.status_message,
                    json.dumps(job.params),
                    json.dumps(job.input_refs),
                    json.dumps([a.model_dump() for a in job.output_refs]),
                    job.estimated_credits,
                    job.actual_credits,
                    job.estimated_seconds,
                    job.retry_count,
                    job.error_category,
                    job.error_message,
                    job.provider_job_id,
                    job.idempotency_key,
                    job.created_at,
                    job.updated_at,
                    job.started_at,
                    job.completed_at,
                    job.expires_at,
                ),
            )
            return job

    def get_job(self, job_id: str) -> Optional[JobOut]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return self._row_to_job(row) if row else None

    def list_jobs(
        self,
        user_id: Optional[str] = None,
        job_type: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> list[JobOut]:
        clauses = []
        params: list[Any] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)
        if state:
            clauses.append("state = ?")
            params.append(state)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [self._row_to_job(r) for r in rows]

    def update_job(self, job_id: str, **fields: Any) -> Optional[JobOut]:
        if not fields:
            return self.get_job(job_id)
        fields["updated_at"] = utc_now_iso()
        mapped: dict[str, Any] = {}
        for k, v in fields.items():
            if k == "output_refs" and v is not None:
                mapped["output_refs_json"] = json.dumps([a.model_dump() if isinstance(a, AssetRef) else a for a in v])
            elif k == "state" and isinstance(v, JobState):
                mapped["state"] = v.value
            else:
                mapped[k] = v
        set_clause = ", ".join(f"{k} = ?" for k in mapped)
        values = list(mapped.values()) + [job_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return self._row_to_job(row) if row else None

    def count_active_jobs(self, user_id: Optional[str] = None) -> int:
        with self._lock, self._connect() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM jobs WHERE user_id = ? AND state IN ('queued', 'starting', 'running', 'uploading')",
                    (user_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM jobs WHERE state IN ('queued', 'starting', 'running', 'uploading')"
                ).fetchone()
            return row["cnt"]

    def find_asset(self, asset_id: str) -> Optional[tuple[JobOut, AssetRef]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 500").fetchall()
            for r in rows:
                job = self._row_to_job(r)
                for asset in job.output_refs:
                    if asset.asset_id == asset_id:
                        return job, asset
            return None

    # --- Model registry ---

    def list_models(self) -> list[ModelRegistryItem]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM models ORDER BY job_type, base_credits").fetchall()
            return [
                ModelRegistryItem(
                    id=r["id"],
                    name=r["name"],
                    job_type=JobType(r["job_type"]),
                    provider=r["provider"],
                    version=r["version"],
                    enabled=bool(r["enabled"]),
                    is_premium=bool(r["is_premium"]),
                    base_credits=r["base_credits"],
                    notes=r["notes"],
                    license_note=r["license_note"],
                )
                for r in rows
            ]

    def get_model(self, model_id: str) -> Optional[ModelRegistryItem]:
        with self._lock, self._connect() as conn:
            r = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
            if not r:
                return None
            return ModelRegistryItem(
                id=r["id"],
                name=r["name"],
                job_type=JobType(r["job_type"]),
                provider=r["provider"],
                version=r["version"],
                enabled=bool(r["enabled"]),
                is_premium=bool(r["is_premium"]),
                base_credits=r["base_credits"],
                notes=r["notes"],
                license_note=r["license_note"],
            )

    def toggle_model(self, model_id: str, enabled: bool) -> Optional[ModelRegistryItem]:
        with self._lock:
            with self._connect() as conn:
                conn.execute("UPDATE models SET enabled = ? WHERE id = ?", (1 if enabled else 0, model_id))
                conn.commit()
            return self.get_model(model_id)


@lru_cache
def get_store() -> LocalStore:
    settings = get_settings()
    if settings.app_env == "gcp":
        from .firestore_store import FirestoreStore

        return FirestoreStore(settings.gcp_project_id)  # type: ignore[return-value]
    return LocalStore(settings.local_db_path)
