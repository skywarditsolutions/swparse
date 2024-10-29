import enum
from dataclasses import dataclass
from typing import Literal

from swparse.__about__ import __version__ as current_version
from swparse.config.base import get_settings

__all__ = ("SystemHealth",)

settings = get_settings()


@dataclass
class SystemHealth:
    database_status: Literal["online", "offline"]
    cache_status: Literal["online", "offline"]
    app: str = settings.app.NAME
    version: str = current_version


class Status(enum.StrEnum):
    deferred = "PENDING"
    failed = "ERROR"
    aborted = "ERROR"
    new = "PENDING"
    queued = "PENDING"
    active = "PENDING"
    complete = "SUCCESS"


@dataclass
class JobMetadata:
    credits_used: float
    credits_max: int
    job_credits_usage: int
    job_pages: int
    job_is_cache_hit: bool


@dataclass
class JobStatus:
    id: str
    status: Status
    s3_url: str | None = ""


@dataclass
class JobResult:
    markdown: str
    html: str
    text: str
    table: str | None = ""
    job_metadata: JobMetadata


@dataclass
class TextExtractResult:
    text: str
    status: Status
