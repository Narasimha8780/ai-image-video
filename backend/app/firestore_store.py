import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .auth import hash_password
from .db import DEFAULT_MODELS, utc_now_iso
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


class FirestoreStore:
    """Firestore Native mode store for Cloud Run production deployment."""

    def __init__(self, project_id: str) -> None:
        from google.cloud import firestore

        self.db = firestore.Client(project=project_id)
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        for model in DEFAULT_MODELS:
            ref = self.db.collection("models").document(model["id"])
            if not ref.get().exists:
                ref.set(model)

        # Seed an initial admin account if no users exist yet
        existing = list(self.db.collection("users").limit(1).stream())
        if not existing:
            today = datetime.now(timezone.utc).date().isoformat()
            now = utc_now_iso()
            self.db.collection("users").document("user-admin-1").set(
                {
                    "id": "user-admin-1",
                    "email": "admin@example.com",
                    "display_name": "Studio Admin",
                    "password_hash": hash_password("admin123"),
                    "role": UserRole.admin.value,
                    "credits": 1000,
                    "daily_quota": 200,
                    "daily_used": 0,
                    "daily_reset_date": today,
                    "max_active_jobs": 20,
                    "is_active": True,
                    "created_at": now,
                }
            )

    def _doc_to_user(self, data: dict[str, Any]) -> UserOut:
        return UserOut(
            id=data["id"],
            email=data["email"],
            display_name=data["display_name"],
            role=UserRole(data["role"]),
            credits=data["credits"],
            daily_quota=data["daily_quota"],
            daily_used=data["daily_used"],
            max_active_jobs=data["max_active_jobs"],
            is_active=bool(data["is_active"]),
            created_at=data["created_at"],
        )

    def _doc_to_job(self, data: dict[str, Any]) -> JobOut:
        return JobOut(
            id=data["id"],
            user_id=data["user_id"],
            job_type=JobType(data["job_type"]),
            engine=data["engine"],
            model_version=data["model_version"],
            state=JobState(data["state"]),
            progress=data.get("progress", 0),
            status_message=data.get("status_message", ""),
            params=data.get("params", {}),
            input_refs=data.get("input_refs", []),
            output_refs=[AssetRef(**a) for a in data.get("output_refs", [])],
            estimated_credits=data["estimated_credits"],
            actual_credits=data.get("actual_credits"),
            estimated_seconds=data.get("estimated_seconds", 30),
            retry_count=data.get("retry_count", 0),
            error_category=data.get("error_category"),
            error_message=data.get("error_message"),
            provider_job_id=data.get("provider_job_id"),
            idempotency_key=data["idempotency_key"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            expires_at=data.get("expires_at"),
        )

    # --- Users ---

    def get_user_by_id(self, user_id: str) -> Optional[UserOut]:
        doc = self.db.collection("users").document(user_id).get()
        return self._doc_to_user(doc.to_dict()) if doc.exists else None

    def get_user_with_hash_by_email(self, email: str) -> Optional[tuple[UserOut, str]]:
        docs = list(self.db.collection("users").where("email", "==", email.lower()).limit(1).stream())
        if not docs:
            return None
        data = docs[0].to_dict()
        return self._doc_to_user(data), data["password_hash"]

    def create_user(self, email: str, display_name: str, password_hash: str, role: UserRole = UserRole.customer) -> UserOut:
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        today = datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()
        data = {
            "id": user_id,
            "email": email.lower(),
            "display_name": display_name,
            "password_hash": password_hash,
            "role": role.value,
            "credits": 100,
            "daily_quota": 25,
            "daily_used": 0,
            "daily_reset_date": today,
            "max_active_jobs": 4,
            "is_active": True,
            "created_at": now,
        }
        self.db.collection("users").document(user_id).set(data)
        self.db.collection("transactions").document(str(uuid.uuid4())).set(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "job_id": None,
                "delta": 100,
                "reason": "Initial signup credits",
                "created_at": now,
            }
        )
        return self._doc_to_user(data)

    def list_users(self) -> list[UserOut]:
        docs = self.db.collection("users").stream()
        return [self._doc_to_user(d.to_dict()) for d in docs]

    def update_user(self, user_id: str, updates: dict[str, Any]) -> Optional[UserOut]:
        allowed = {"credits", "daily_quota", "max_active_jobs", "is_active", "role"}
        fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if "role" in fields and isinstance(fields["role"], UserRole):
            fields["role"] = fields["role"].value
        ref = self.db.collection("users").document(user_id)
        if not ref.get().exists:
            return None
        if fields:
            ref.set(fields, merge=True)
        return self.get_user_by_id(user_id)

    def reserve_credits_and_quota(self, user_id: str, credits_needed: int, job_id: str) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()
        ref = self.db.collection("users").document(user_id)
        doc = ref.get()
        if not doc.exists:
            raise ValueError("User not found")
        data = doc.to_dict()
        daily_used = 0 if data.get("daily_reset_date") != today else data.get("daily_used", 0)
        if daily_used >= data.get("daily_quota", 25):
            raise PermissionError("Daily generation quota reached")
        if data.get("credits", 0) < credits_needed:
            raise PermissionError("Insufficient credits")
        if self.count_active_jobs(user_id) >= data.get("max_active_jobs", 4):
            raise PermissionError("Maximum concurrent active jobs reached")

        ref.set(
            {
                "credits": data["credits"] - credits_needed,
                "daily_used": daily_used + 1,
                "daily_reset_date": today,
            },
            merge=True,
        )
        tx_id = str(uuid.uuid4())
        self.db.collection("transactions").document(tx_id).set(
            {
                "id": tx_id,
                "user_id": user_id,
                "job_id": job_id,
                "delta": -credits_needed,
                "reason": "Job generation reserve",
                "created_at": now,
            }
        )

    def refund_credits(self, user_id: str, credits: int, job_id: str, reason: str) -> None:
        from google.cloud import firestore

        now = utc_now_iso()
        self.db.collection("users").document(user_id).update({"credits": firestore.Increment(credits)})
        tx_id = str(uuid.uuid4())
        self.db.collection("transactions").document(tx_id).set(
            {
                "id": tx_id,
                "user_id": user_id,
                "job_id": job_id,
                "delta": credits,
                "reason": reason,
                "created_at": now,
            }
        )

    def list_transactions(self, user_id: str, limit: int = 50) -> list[UsageTransaction]:
        docs = self.db.collection("transactions").where("user_id", "==", user_id).limit(limit).stream()
        items = [UsageTransaction(**d.to_dict()) for d in docs]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    # --- Jobs ---

    def get_job_by_idempotency(self, user_id: str, idempotency_key: str) -> Optional[JobOut]:
        docs = list(
            self.db.collection("jobs")
            .where("user_id", "==", user_id)
            .where("idempotency_key", "==", idempotency_key)
            .limit(1)
            .stream()
        )
        return self._doc_to_job(docs[0].to_dict()) if docs else None

    def create_job(self, job: JobOut) -> JobOut:
        data = job.model_dump()
        data["job_type"] = job.job_type.value
        data["engine"] = job.engine.value
        data["state"] = job.state.value
        data["output_refs"] = [a.model_dump() for a in job.output_refs]
        self.db.collection("jobs").document(job.id).set(data)
        return job

    def get_job(self, job_id: str) -> Optional[JobOut]:
        doc = self.db.collection("jobs").document(job_id).get()
        return self._doc_to_job(doc.to_dict()) if doc.exists else None

    def list_jobs(
        self,
        user_id: Optional[str] = None,
        job_type: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> list[JobOut]:
        query = self.db.collection("jobs")
        if user_id:
            query = query.where("user_id", "==", user_id)
        if job_type:
            query = query.where("job_type", "==", job_type)
        if state:
            query = query.where("state", "==", state)
        docs = query.limit(limit).stream()
        items = [self._doc_to_job(d.to_dict()) for d in docs]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    def update_job(self, job_id: str, **fields: Any) -> Optional[JobOut]:
        mapped: dict[str, Any] = {"updated_at": utc_now_iso()}
        for k, v in fields.items():
            if k == "output_refs" and v is not None:
                mapped["output_refs"] = [a.model_dump() if isinstance(a, AssetRef) else a for a in v]
            elif k == "state" and isinstance(v, JobState):
                mapped["state"] = v.value
            else:
                mapped[k] = v
        self.db.collection("jobs").document(job_id).set(mapped, merge=True)
        return self.get_job(job_id)

    def count_active_jobs(self, user_id: Optional[str] = None) -> int:
        active_states = ["queued", "starting", "running", "uploading"]
        query = self.db.collection("jobs").where("state", "in", active_states)
        if user_id:
            query = query.where("user_id", "==", user_id)
        return sum(1 for _ in query.stream())

    def find_asset(self, asset_id: str) -> Optional[tuple[JobOut, AssetRef]]:
        for job in self.list_jobs(limit=200):
            for asset in job.output_refs:
                if asset.asset_id == asset_id:
                    return job, asset
        return None

    # --- Models ---

    def list_models(self) -> list[ModelRegistryItem]:
        docs = self.db.collection("models").stream()
        return [ModelRegistryItem(**d.to_dict()) for d in docs]

    def get_model(self, model_id: str) -> Optional[ModelRegistryItem]:
        doc = self.db.collection("models").document(model_id).get()
        return ModelRegistryItem(**doc.to_dict()) if doc.exists else None

    def toggle_model(self, model_id: str, enabled: bool) -> Optional[ModelRegistryItem]:
        ref = self.db.collection("models").document(model_id)
        if not ref.get().exists:
            return None
        ref.set({"enabled": enabled}, merge=True)
        return self.get_model(model_id)
