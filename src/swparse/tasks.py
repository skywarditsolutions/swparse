from __future__ import annotations

import asyncio
from logging import getLogger
from typing import TYPE_CHECKING
import pymupdf4llm
import pymupdf
from s3fs import S3FileSystem

if TYPE_CHECKING:
    from saq.types import Context

logger = getLogger(__name__)
BUCKET = "swparse"
MINIO_ROOT_USER = "admin"
MINIO_ROOT_PASSWORD = "0xc0d3skyward"


async def parse_mu_s3   (ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url="http://minio:9000/",
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False
    )

    with s3.open(s3_url) as doc:
        markdown = pymupdf4llm.to_markdown(
            pymupdf.open(ext,doc.read(),filetype=ext)
        )
    logger.error(s3_url)
    logger.error(markdown)
    return markdown