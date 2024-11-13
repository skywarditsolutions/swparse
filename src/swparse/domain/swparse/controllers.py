from __future__ import annotations

from typing import Annotated, Literal, TypeVar
from uuid import uuid4

import structlog
from litestar import Controller, MediaType, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.params import Body
from litestar_saq import Job, Queue
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.domain.swparse.middlewares import ApiKeyAuthMiddleware
from swparse.domain.swparse.schemas import JobMetadata, JobStatus, Status
from swparse.domain.swparse.utils import (
    get_hashed_file_name,
    get_job_metadata,
    handle_result_type,
    save_job_metadata,
    syntax_parser,
)

from .urls import PARSER_BASE

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD

# def _raise_http_exception(detail: str, status_code: int) -> None:
#     raise HTTPException(detail=detail, status_code=status_code)


# class UploadBody(BaseStruct):
#     file: UploadFile
#     parsing_instruction: Optional[str]


class ParserController(Controller):
    tags = ["Parsers"]
    path = PARSER_BASE
    middleware = [ApiKeyAuthMiddleware]

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
        hashed_filename = get_hashed_file_name(filename, content)
        s3_url = f"{BUCKET}/{hashed_filename}"

        if s3.exists(s3_url):
            job = await queue.enqueue(
                Job(
                    "get_extracted_url",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
            return JobStatus(id=job.id, status=Status.complete, s3_url=s3_url)

        with s3.open(s3_url, "wb") as f:
            f.write(content)

        kwargs = {"s3_url": s3_url, "ext": data.content_type}

        # if data.parsing_instruction:
        #     if data.parsing_instruction not in ContentType:
        #         try:
        #             syntax_parser(data.parsing_instruction)
        #         except:
        #             raise HTTPException(detail="Invalid result type", status_code=400)
        #         kwargs["result_type"] = data.parsing_instruction

        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                Job(
                    "parse_pdf_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type.split("/")[0].lower() == "image":
            job = await queue.enqueue(
                Job(
                    "parse_image_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type.split("/")[0].lower() == "text":
            job = await queue.enqueue(
                Job(
                    "extract_text_files",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ):
            job = await queue.enqueue(
                Job(
                    "parse_xlsx_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            logger.error("WORKED parse_docx_s3")
            job = await queue.enqueue(
                Job(
                    "parse_docx_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type == "application/msword":
            logger.error("WORKED parse_doc_s3")
            job = await queue.enqueue(
                Job(
                    "parse_doc_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.ms-powerpoint":
            logger.error("WORKED parse_ppt_s3")
            job = await queue.enqueue(
                Job(
                    "parse_ppt_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            logger.error("WORKED parse_pptx_s3")
            job = await queue.enqueue(
                Job(
                    "parse_pptx_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        else:
            job = await queue.enqueue(
                Job(
                    "extract_string",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )

        if not job:
            raise HTTPException(detail="JOB ERROR", status_code=400)

        if job.status == "failed":
            raise HTTPException(detail="JOB ERROR", status_code=400)

        return JobStatus(id=job.id, status=Status[job.status], s3_url=s3_url)

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
        new_uuid = uuid4()
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )

        s3_url = f"{BUCKET}/{new_uuid}_{filename}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)  # type: ignore
        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                "parse_docx_s3",
                s3_url=s3_url,
                page=page,
            )
            if not job:
                raise HTTPException(detail="JOB ERROR", status_code=400)

            if job.status == "failed":
                raise HTTPException(detail="JOB ERROR", status_code=400)

            return JobStatus(id=job.id, status=Status[job.status], s3_url=s3_url)
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

    @post(path="query_syntax")
    async def test_syntax(self, queries: str) -> list[dict]:
        try:
            result = syntax_parser(queries)
        except Exception as e:
            raise HTTPException(detail=f"Invalid query syntax: {e}", status_code=400)

        return result

    @get(
        path="job/{job_id:str}/result/{result_type:str}",
    )
    async def get_result(self, job_id: str, result_type: str = "markdown") -> dict:
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        jm = JobMetadata(
            credits_used=0,
            credits_max=1000000,
            job_credits_usage=0,
            job_pages=0,
            job_is_cache_hit=False,
        )

        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)
        if not job:
            job_metadata = get_job_metadata(s3)
            results = job_metadata.get(job_id)
            logger.error(results)
            if results is None:
                raise HTTPException(detail="Job not found", status_code=204)

        else:
            results = job.result
            await job.refresh(1)
            if results is None:
                raise HTTPException(detail="Job not found", status_code=204)
            save_job_metadata(s3, job_id, results)
        try:
            return handle_result_type(result_type, results, s3, jm, job_key)
        except Exception as err:
            logger.error(err)
            raise HTTPException(f"Format {result_type} is currently unsupported for {job_id}")
