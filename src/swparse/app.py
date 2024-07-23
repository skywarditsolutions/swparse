from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Annotated
import mimetypes
import filetype
from litestar_saq import QueueConfig, SAQConfig, SAQPlugin
from s3fs import S3FileSystem
from saq import Queue
from litestar.openapi.plugins import StoplightRenderPlugin,ScalarRenderPlugin,RapidocRenderPlugin,YamlRenderPlugin

from litestar import Controller, Litestar, get, post , Request
from litestar.params import Body
from swparse.tasks import parse_mu_s3
from dataclasses import dataclass
from litestar.openapi.config import OpenAPIConfig


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
    status: str


@dataclass
class JobResult:
    markdown: str
    job_metadata: JobMetadata


if TYPE_CHECKING:
    from litestar.datastructures import UploadFile

from litestar.enums import RequestEncodingType

logger = getLogger(__name__)


BUCKET = "swparse"
MINIO_ROOT_USER="admin"
MINIO_ROOT_PASSWORD="0xc0d3skyward"  
queue = Queue.from_url("redis://localhost", name="swparse")     


class SWParse(Controller):
    path = "/api/parsing/"
    @post(path="upload")
    async def upload_and_que(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    ) -> JobStatus:
        content = await data.read()
        filename = data.filename
        s3 = S3FileSystem(
            # asynchronous=True,
            endpoint_url="http://localhost:9000/",
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False
        )
        
        s3_url = f"{BUCKET}/{filename}"
        with s3.open(s3_url, "wb") as f:
            f.write(content)
        job = await queue.enqueue("parse_mu_s3", s3_url=s3_url, ext=data.content_type)
        return {"id":job.id, "status":job.status}

    @get(path="job/{job_id:str}")
    async def check_status(self, job_id: str) -> JobStatus:
        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)
        if job:
            return {"id":job.id, "status":job.status}

        else:
            raise Exception(f"No Such Job {job_id} ")
    @get(path="job/{job_id:str}/result/{result_type:str}")
    async def get_result(self,job_id: str, result_type: str = "markdown") -> JobResult:
        job_key = queue.job_key_from_id(job_id)
        job=await queue.job(job_key)
        if job:
            await job.refresh(1)
            markdown = job.result
            jm=JobMetadata(credits_used=0,credits_max=1000000,job_credits_usage=0,job_pages=0,job_is_cache_hit=False)
            return JobResult(markdown=markdown,job_metadata=jm)
        else:
            raise Exception(f"No Such Job {job_id} ")
        



saq = SAQPlugin(
    config=SAQConfig(
        redis_url="redis://localhost:6379/0",
        web_enabled=True,
        use_server_lifespan=False,
        queue_configs=[
            QueueConfig(
                name="swparse",
                tasks=[
                    parse_mu_s3,
                ],
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
        render_plugins=[ScalarRenderPlugin()],
    ),
)


