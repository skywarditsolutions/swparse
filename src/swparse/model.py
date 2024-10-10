import enum
from dataclasses import dataclass

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


@dataclass
class JobResult:
    markdown: str
    job_metadata: JobMetadata


@dataclass
class TextExtractResult:
    text:str
    status: Status