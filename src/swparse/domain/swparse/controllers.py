from __future__ import annotations

from typing import Annotated, Literal, TypeVar

import structlog
from litestar import Controller, MediaType, get, post
from litestar.datastructures import UploadFile  # noqa: TCH002
from litestar.enums import RequestEncodingType  # noqa: TCH002
from litestar.exceptions import HTTPException
from litestar.params import Body  # noqa: TCH002
from litestar_saq import Job, Queue
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.domain.swparse.schemas import JobMetadata, JobResult, JobStatus, Status

from .urls import PARSER_BASE

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


def _raise_http_exception(detail: str, status_code: int) -> None:
    raise HTTPException(detail=detail, status_code=status_code)


class ParserController(Controller):
    tags = ["Parsers"]
    path = PARSER_BASE

    @post(
        operation_id="ParserQueue",
        name="parsers:start",
        path="upload",
        cache=False,
        summary="Upload to S3 and Queue the Parser",
        description="After queue started , use the jobid to check for the status",
    )
    async def upload_and_parse_que(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> JobStatus:
        content = await data.read()
        filename = data.filename
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        s3_url = f"{BUCKET}/{filename}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)  # type: ignore

        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                Job(
                    "parse_pdf_markdown_s3",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type.split("/")[0].lower() == "image":
            job = await queue.enqueue(
                Job(
                    "parse_image_markdown_s3",
                    kwargs={
                        "s3_url": s3_url,
                        "ext": data.content_type,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type.split("/")[0].lower() == "text":
            job = await queue.enqueue(
                Job(
                    "extract_text_files",
                    kwargs={
                        "s3_url": s3_url,
                        "ext": data.content_type,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            job = await queue.enqueue(
                Job(
                    "parse_xlsx_markdown_s3",
                    kwargs={
                        "s3_url": s3_url,
                        "ext": data.content_type,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            job = await queue.enqueue(
                Job(
                    "parse_docx_markdown_s3",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
        else:
            job = await queue.enqueue(
                Job(
                    "extract_string",
                    kwargs={
                        "s3_url": s3_url,
                        "ext": data.content_type,
                    },
                    timeout=0,
                ),
            )

        if not job:
            raise HTTPException(detail="JOB ERROR", status_code=400)

        if job.status == "failed":
            raise HTTPException(detail="JOB ERROR", status_code=400)

        return JobStatus(id=job.id, status=Status[job.status])  # type: ignore

    @post(
        path="upload/page/{page:int}",
        name="parsers:page",
        media_type=MediaType.JSON,
        cache=False,
        summary="Parse By Page",
        description="After queue started , use the jobid to check for the status",
    )
    async def upload_parse_page_que(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        page: int = 1,
    ) -> JobStatus:
        """Parse docs by page.
        - page:int  : Page number , stats at 1.
        - upload: File Input
        """
        page -= 1
        page = max(page, 0)
        content = await data.read()
        filename = data.filename
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )

        s3_url = f"{BUCKET}/{filename}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)  # type: ignore
        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                "parse_docx_markdown_s3",
                s3_url=s3_url,
                page=page,
            )
            if not job:
                raise HTTPException(detail="JOB ERROR", status_code=400)

            if job.status == "failed":
                raise HTTPException(detail="JOB ERROR", status_code=400)

            return JobStatus(id=job.id, status=Status[job.status])
        raise HTTPException(detail="Unsupported File")

    @get(
        path="job/{job_id:str}",
    )
    async def check_status(self, job_id: str) -> JobStatus:
        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)
        if not job:
            raise HTTPException(detail="JOB ERROR", status_code=400)

        if job.status == "failed":
            logger.error("JOB ERROR")
            raise HTTPException(detail="JOB ERROR", status_code=400)
        return JobStatus(id=job.id, status=Status[job.status])

    @get(
        path="job/{job_id:str}/result/{result_type:str}",
    )
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
        raise HTTPException(f"No Such Job {job_id} ")
