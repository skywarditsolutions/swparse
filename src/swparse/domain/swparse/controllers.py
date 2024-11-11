from __future__ import annotations

from typing import Annotated, Literal, TypeVar
from uuid import uuid4

import pandas as pd
import structlog
from litestar import Controller, MediaType, get, post
from litestar.datastructures import UploadFile  # noqa: TCH002
from litestar.enums import RequestEncodingType  # noqa: TCH002
from litestar.exceptions import HTTPException
from litestar.params import Body  # noqa: TCH002
from litestar_saq import Job, Queue
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.db.models.content_type import ContentType
from swparse.domain.swparse.middlewares import ApiKeyAuthMiddleware
from swparse.domain.swparse.schemas import JobMetadata, JobResult, JobStatus, Status
from swparse.domain.swparse.utils import extract_labels, extract_tables_from_html, syntax_parser

from .urls import PARSER_BASE

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


# def _raise_http_exception(detail: str, status_code: int) -> None:
#     raise HTTPException(detail=detail, status_code=status_code)


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
        file_name = data.filename
        new_uuid = uuid4()
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        s3_url = f"{BUCKET}/{new_uuid}_{file_name}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)

        if data.content_type in ["application/pdf"]:
            job = await queue.enqueue(
                Job(
                    "parse_pdf_s3",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type.split("/")[0].lower() == "image":
            job = await queue.enqueue(
                Job(
                    "parse_image_s3",
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
        elif data.content_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ):
            job = await queue.enqueue(
                Job(
                    "parse_xlsx_s3",
                    kwargs={
                        "s3_url": s3_url,
                        "ext": data.content_type,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            logger.error("WORKED parse_docx_s3")
            job = await queue.enqueue(
                Job(
                    "parse_docx_s3",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type == "application/msword":
            logger.error("WORKED parse_doc_s3")
            job = await queue.enqueue(
                Job(
                    "parse_doc_s3",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.ms-powerpoint":
            logger.error("WORKED parse_ppt_s3")
            job = await queue.enqueue(
                Job(
                    "parse_ppt_s3",
                    kwargs={
                        "s3_url": s3_url,
                    },
                    timeout=0,
                ),
            )
        elif data.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            logger.error("WORKED parse_pptx_s3")
            job = await queue.enqueue(
                Job(
                    "parse_pptx_s3",
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

    @get(path="job/test")
    async def job_test(self, test: str) -> list[dict]:
        try:
            result = syntax_parser(test)
        except:
            raise HTTPException(detail="Invalid query syntax", status_code=400)

        mdText = """Jake Turner is a 27-year-old midfielder wearing jersey number 8, earning a salary of $1.2 million annually. At 22, Alex Costa plays as a forward with number 10 and brings in a yearly income of $2 million. Liam Rivera, the 25-year-old center back wearing number 4, is paid $900,000 per year. The experienced 30-year-old goalkeeper, Mark Hughes, dons number 1 and earns $1.5 million annually. Known for his versatility, Ryan Lee is a 24-year-old right back wearing number 2, with a yearly salary of $850,000. With jersey number 7, Jordan Baker plays as a winger at 23 years old, making $1.1 million each year. Defensive stalwart Tom Fernandez, a 28-year-old left back wearing number 3, takes home $950,000 annually. Chris Yamada, 26, serves as the team’s attacking midfielder in jersey 11, earning $1.3 million a season. Sam Bennett, the 21-year-old center forward with number 9, is compensated $1.8 million per year. At 29, Ethan Patel plays defensive midfield with number 6 and earns $1 million annually. Tyler Green, a 20-year-old left winger with number 17, brings youthful energy to the team and a $750,000 salary. Center-back Oscar White, aged 27 and wearing number 5, has a contract worth $950,000 per year. Max Liu, the team’s 23-year-old right winger with jersey number 14, earns $1.2 million yearly. Playing as a defensive midfielder, Leo Park is 25, wears number 15, and brings in $800,000 annually. Noah Hill, the 31-year-old backup goalkeeper, wears number 16 and takes home $600,000 each year. At 24, Damian Cruz plays as a central midfielder with number 12, earning a $1 million salary. Jack Foster, a 29-year-old forward in jersey 19, is paid $1.5 million per season. Ben Murphy, the versatile 26-year-old center-back with number 18, earns $925,000 per season. Mason Evans, a promising 19-year-old right back, wears number 20 and makes $600,000 annually. Finally, Charlie Bell, a 28-year-old forward with number 21, contributes to the attack while earning $1.4 million each season."""
        return extract_labels(result, mdText)

    @get(
        path="job/{job_id:str}/result/{result_type:str}",
    )
    async def get_result(self, job_id: str, result_type: str = "markdown") -> JobResult:
        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)
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
        if job:
            await job.refresh(1)
            results = job.result
            try:
                match result_type:
                    case ContentType.MARKDOWN.value:
                        with s3.open(results["markdown"], mode="r") as out_file_md:
                            markdown = out_file_md.read()
                            return JobResult(markdown=markdown, html="", text="", job_metadata=jm)

                    case ContentType.HTML.value:
                        with s3.open(results["html"], mode="r") as out_file_html:
                            html = out_file_html.read()
                            return JobResult(markdown="", html=html, text="", job_metadata=jm)

                    case ContentType.TEXT.value:
                        with s3.open(results["text"], mode="r") as out_file_txt:
                            text = out_file_txt.read()
                            return JobResult(markdown="", html="", text=text, job_metadata=jm)
                    case ContentType.TABLE.value:
                        html = extract_tables_from_html(s3, results["html"])
                        result_html = "<br><br>"
                        if html:
                            result_html = result_html.join(html)
                        return JobResult(markdown="", html="", text="", table=result_html, job_metadata=jm)

                    case ContentType.MARKDOWN_TABLE.value:
                        table_file_path = results.get("table")
                        if table_file_path:
                            with s3.open(results["table"], mode="r") as out_file_html:
                                result_html = out_file_html.read()
                        else:
                            html = extract_tables_from_html(s3, results["html"])
                            result_html = "<br><br>".join(html)

                        dfs = pd.read_html(result_html)
                        markdown_tbls = ""
                        for i, df in enumerate(dfs):
                            markdown_tbls += f"## Table {i + 1}\n\n"
                            markdown_tbls += df.to_markdown()
                            markdown_tbls += "\n\n"

                        return JobResult(markdown="", html="", text="", table_md=markdown_tbls, job_metadata=jm)
                    case ContentType.IMAGES.value:
                        images = results.get("images")
                        return JobResult(markdown="", html="", text="", images=images)
                    case _:
                        # TODO: parse syntax
                        unsupported = f"Format {result_type} is currently unsupported."
                        raise HTTPException(unsupported)
            except KeyError:
                unsupported = f"Format {result_type} is currently unsupported for {job_key}"
                raise HTTPException(unsupported)

        raise HTTPException(f"No Such Job {job_id} ")
