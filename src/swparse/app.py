from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Annotated
from litestar_saq import QueueConfig, SAQConfig, SAQPlugin
from s3fs import S3FileSystem
from saq import Queue
from litestar.openapi.plugins import RapidocRenderPlugin
from litestar.exceptions import HTTPException

from litestar import Controller, HttpMethod, Litestar, get, post
from litestar.params import Body
from swparse.tasks import (
    parse_mu_s3,
    parse_pdf_markdown_s3,
    parse_image_markdown_s3,
    parse_pdf_page_markdown_s3,
)
from dataclasses import dataclass
from litestar.openapi.config import OpenAPIConfig
from swparse.settings import worker, storage
import enum


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


if TYPE_CHECKING:
    from litestar.datastructures import UploadFile

from litestar.enums import RequestEncodingType  # noqa: E402

logger = getLogger(__name__)


BUCKET = storage.BUCKET
MINIO_ROOT_USER = storage.ROOT_USER
MINIO_ROOT_PASSWORD = storage.ROOT_PASSWORD
queue = Queue.from_url(worker.REDIS_HOST, name="swparse")


class SWParse(Controller):
    tags = ["Skyward Parse"]
    path = "/api/parsing/"

    @post(path="upload")
    async def upload_and_parse_que(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> JobStatus:
        content = await data.read()
        filename = data.filename
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=storage.ENPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )

        s3_url = f"{BUCKET}/{filename}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)
        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue("parse_pdf_markdown_s3", s3_url=s3_url)
        elif data.content_type.split("/")[0].lower() == "image":
            job = await queue.enqueue(
                "parse_image_markdown_s3", s3_url=s3_url, ext=data.content_type
            )
        else:
            job = await queue.enqueue(
                "parse_mu_s3", s3_url=s3_url, ext=data.content_type
            )
        if not job:
            raise HTTPException(detail="JOB ERROR", status_code=400)

        if job.status == "failed":
            raise HTTPException(detail="JOB ERROR", status_code=400)

        return JobStatus(id=job.id, status=Status[job.status])  # type: ignore

    @post(path="upload/page/{page:int}")
    async def upload_parse_page_que(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        page: int = 1,
    ) -> JobStatus:
        """
        Parse docs by page.
        - page:int  : Page number , stats at 1.
        - upload: File Input
        """
        page -= 1
        if page < 0:
            page = 0
        content = await data.read()
        filename = data.filename
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=storage.ENPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )

        s3_url = f"{BUCKET}/{filename}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)
        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                "parse_pdf_page_markdown_s3", s3_url=s3_url, page=page
            )
            if not job:
                raise HTTPException(detail="JOB ERROR", status_code=400)

            if job.status == "failed":
                raise HTTPException(detail="JOB ERROR", status_code=400)

            else:
                return JobStatus(id=job.id, status=Status[job.status])
        else:
            raise HTTPException(detail="Unsupported File")

    @get(path="job/{job_id:str}")
    async def check_status(self, job_id: str) -> JobStatus:
        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)
        if not job:
            raise HTTPException(detail="JOB ERROR", status_code=400)
        
        if job.status == "failed":
            logger.error("JOB ERROR")
            raise HTTPException(detail="JOB ERROR", status_code=400)
        else:
            return JobStatus(id=job.id, status=Status[job.status])

    @get(path="job/{job_id:str}/result/{result_type:str}")
    async def get_result(self, job_id: str, result_type: str = "markdown") -> JobResult:
        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)
        if job:
            await job.refresh(1)
            markdown = job.result
            jm = JobMetadata(
                credits_used=0,
                credits_max=1000000,
                job_credits_usage=0,
                job_pages=0,
                job_is_cache_hit=False,
            )
            return JobResult(markdown=markdown, job_metadata=jm)
        else:
            raise HTTPException(f"No Such Job {job_id} ")


saq = SAQPlugin(
    config=SAQConfig(
        redis_url=worker.REDIS_URL,
        web_enabled=True,
        use_server_lifespan=False,
        queue_configs=[
            QueueConfig(
                timers={"sweep": 999999},  # type: ignore
                name="swparse",
                tasks=[
                    parse_mu_s3,
                    parse_pdf_markdown_s3,
                    parse_image_markdown_s3,
                    parse_pdf_page_markdown_s3,
                ],  # type: ignore
            ),
        ],
    ),
)
app = Litestar(
    route_handlers=[SWParse],
    plugins=[saq],
    openapi_config=OpenAPIConfig(
        title="SWParse API",
        description="Skyward's Image Reconising Multi Document Parser for RAG",
        version="0.1.0",
        path="/docs",
        render_plugins=[RapidocRenderPlugin()],
    ),
)
