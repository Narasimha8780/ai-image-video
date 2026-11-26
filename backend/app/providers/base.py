from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ..models import AssetRef, JobOut, JobState


@dataclass
class ProviderStatus:
    state: JobState
    progress: int = 0
    message: str = ""
    error_category: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ProviderResult:
    assets: list[AssetRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class VideoProvider(ABC):
    """Unified adapter interface for local ComfyUI GPU jobs and hosted APIs (Seedance, Kling)."""

    @abstractmethod
    async def submit(self, job: JobOut) -> str:
        """Submit a job to the underlying provider and return provider_job_id."""

    @abstractmethod
    async def get_status(self, provider_job_id: str) -> ProviderStatus:
        """Poll current execution status and normalize to internal JobState."""

    @abstractmethod
    async def fetch_result(self, provider_job_id: str, job: JobOut) -> ProviderResult:
        """Fetch completed outputs and store them into the private storage bucket."""
