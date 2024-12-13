import enum
from dataclasses import dataclass
from typing import Literal, Any, TYPE_CHECKING

from swparse.__about__ import __version__ as current_version
from swparse.config.base import get_settings
from pydantic import BaseModel

if TYPE_CHECKING:
    from PIL.Image import Image


__all__ = ("SystemHealth",)

settings = get_settings()

class OcrItem(BaseModel):
    x: int
    y: int
    w: int
    h: int
    confidence: str
    text: str


class BBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class Item(BaseModel):
    type: str
    md: str
    bBox: BBox 
    value: str | None = None
    lvl: int|None | None= None
    rows: list[list[str]] | None= None
    isPerfectTable: bool | None= None
    csv: str | None= None


class Link(BaseModel):
    url: str | None = None
    text: str | None = None


class Page(BaseModel):
    page: int
    text: str
    md: str
    images: list[dict[str, str]]
    charts: list
    status: str
    width: int
    height: int
    triggeredAutoMode: bool
    structuredData: None
    noStructuredContent: bool
    noTextContent: bool
    items: list[Item]
    links: list[Link]


# class JobMetadata(BaseModel):
#     credits_used: float
#     job_credits_usage: int
#     job_pages: int
#     job_auto_mode_triggered_pages: int
#     job_is_cache_hit: bool
#     credits_max: int


# class JsonResult(BaseModel):
#     pages: list[Page]
#     job_metadata: JobMetadata


class LLAMAJSONOutput(BaseModel):
    markdown:str
    html:str 
    text:str
    pages: list[dict[str, Any]]
    metadata: dict[str, Any] 
    images: dict[str, str]



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
    aborting = "ERROR"
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
    table_md: str | None = ""
    images: str | None = None
    job_metadata: JobMetadata | None = None


@dataclass
class TextExtractResult:
    text: str
    status: Status
