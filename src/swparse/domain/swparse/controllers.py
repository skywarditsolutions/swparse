from __future__ import annotations

from typing import Annotated, Literal, Optional, TypeVar
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
from swparse.db.models.content_type import ContentType
from swparse.domain.swparse.middlewares import ApiKeyAuthMiddleware
from swparse.domain.swparse.schemas import JobMetadata, JobStatus, Status
from swparse.domain.swparse.utils import (
    get_hashed_file_name,
    get_job_metadata,
    handle_result_type,
    parse_table_query,
    save_job_metadata,
    get_memory_usage
)
from swparse.lib.schema import BaseStruct
from .urls import PARSER_BASE

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
CACHING_ON = settings.app.CACHING_ON

class UploadBody(BaseStruct):
    file: UploadFile
    parsing_instruction: Optional[str] = None
    sheet_index: Optional[list[str | int]] = None 
    force_ocr: bool = False
    plain_text: bool = False


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
        data: Annotated[UploadBody, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> JobStatus:
        memory_info =  get_memory_usage()
        logger.info(f"Memory usage of upload controller start: {memory_info.rss / 1024**2:.2f} MB")
        file = data.file
        content = await file.read()
        filename = file.filename
        s3fs = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        hashed_input ={
            "content": content
        }
        if data.force_ocr:
            hashed_input["force_ocr"] = True
            
        if data.sheet_index:
            hashed_input["sheet_index"] = data.sheet_index
            
        if data.plain_text:
            hashed_input["plain_text"] = data.plain_text
        
        hashed_filename = get_hashed_file_name(filename, hashed_input)
            
        s3_url = f"{BUCKET}/{hashed_filename}"

        metadata = {}
        kwargs = {"s3_url": s3_url, "ext": file.content_type, "table_query": None}
        if data.parsing_instruction:
            if data.parsing_instruction not in ContentType:
                try:
                    table_query = parse_table_query(data.parsing_instruction)
                    table_query["raw"] = data.parsing_instruction
                    kwargs["table_query"] = table_query
                except:
                    raise HTTPException(detail="Invalid result type", status_code=400)
            metadata["result_type"] = data.parsing_instruction

        if s3fs.exists(s3_url):
            logger.info("it's already exist")
            if CACHING_ON:
                metadata_json_str = s3fs.getxattr(s3_url, "metadata")
                if metadata_json_str:
                    del kwargs["ext"]
                    job = await queue.enqueue(
                        Job(
                            "get_extracted_url",
                            kwargs=kwargs,
                            timeout=0,
                        ),
                    )
                    save_job_metadata(s3fs, job.id, metadata)
                    return JobStatus(id=job.id, status=Status[job.status], s3_url=s3_url)
        else:
            with s3fs.open(s3_url, "wb") as f:
                f.write(content)

        if file.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                Job(
                    "parse_pdf_s3",
                    kwargs={
                        **kwargs,
                        "force_ocr": data.force_ocr,
                        "plain_text": data.plain_text
                        },
                    timeout=0,
                ),
            )
        elif file.content_type.split("/")[0].lower() == "image":
            job = await queue.enqueue(
                Job(
                    "parse_image_s3",
                    kwargs={
                        **kwargs,
                        "force_ocr":data.force_ocr},
                    timeout=0,
                ),
            )
        elif file.content_type.split("/")[0].lower() == "text":
            job = await queue.enqueue(
                Job(
                    "extract_text_files",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        elif file.content_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ):
            sheet_index = data.sheet_index
            
            job = await queue.enqueue(
                Job(
                    "parse_xlsx_s3",
                    kwargs={
                        **kwargs, 
                        "sheet_index": sheet_index
                    },
                    timeout=0,
                ),
            )
        elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            job = await queue.enqueue(
                Job(
                    "parse_docx_s3",
                    kwargs=kwargs,
                    timeout=0,
                ),
            )
        # elif file.content_type == "application/msword":
        #     job = await queue.enqueue(
        #         Job(
        #             "parse_doc_s3",
        #             kwargs=kwargs,
        #             timeout=0,
        #         ),
        #     )
        # elif file.content_type == "application/vnd.ms-powerpoint":
        #     job = await queue.enqueue(
        #         Job(
        #             "parse_ppt_s3",
        #             kwargs=kwargs,
        #             timeout=0,
        #         ),
        #     )
        elif file.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
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
        save_job_metadata(s3fs, job.id, metadata)

        if job.status == "failed":
            raise HTTPException(detail="JOB ERROR", status_code=400)
        
        memory_info =  get_memory_usage()
        logger.info(f"Memory usage of upload controller end: {memory_info.rss / 1024**2:.2f} MB")

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
        s3fs = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )

        s3_url = f"{BUCKET}/{new_uuid}_{filename}"
        with s3fs.open(s3_url, "wb") as f:
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
            result = parse_table_query(queries)
        except Exception as e:
            raise HTTPException(detail=f"Invalid query syntax: {e}", status_code=400)

        return result

    @get(
        path="job/{job_id:str}/result/{result_type:str}",
    )
    async def get_result(self, job_id: str, result_type: str = "markdown") -> dict|list:
        s3fs = S3FileSystem(
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
            results = get_job_metadata(s3fs, job_id)
            metadata: dict[str, str] = results["metadata"]
        else:
            metadata = job.result
            await job.refresh(1)
        results = save_job_metadata(s3fs, job_id, metadata)
        metadata: dict[str, str] = results["metadata"]

        try:
            return handle_result_type(result_type, metadata, s3fs, jm, job_key)
        except Exception as err:
            logger.error(err)
            raise HTTPException(f"Format {result_type} is currently unsupported for {job_id}")
