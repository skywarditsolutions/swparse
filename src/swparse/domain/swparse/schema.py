from __future__ import annotations

from pydantic import BaseModel
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

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
    lvl: int|None | None= None
    value: str | None= None
    md: str
    bBox: BBox
    rows: list[list[str]] | None= None
    isPerfectTable: bool | None= None
    csv: str | None= None


class Link(BaseModel):
    url: str
    text: str


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
    # items: list[Item]
    # links: list[Link]
    links: list
    items:list[dict[str, Any]]


class JobMetadata(BaseModel):
    credits_used: float
    job_credits_usage: int
    job_pages: int
    job_auto_mode_triggered_pages: int
    job_is_cache_hit: bool
    credits_max: int


class JsonResult(BaseModel):
    pages: list[Page]
    job_metadata: JobMetadata


class LLAMAJSONOutput(BaseModel):
    markdown:str
    html:str 
    text:str
    pages: list[dict[str, Any]]
    metadata: dict[str, Any] 
    images: dict[str, str]