from __future__ import annotations
import io
from logging import getLogger
from typing import TYPE_CHECKING
import pymupdf4llm
import pymupdf
from PIL import Image
from s3fs import S3FileSystem
from swparse.settings import storage
if TYPE_CHECKING:
    from saq.types import Context
import pypdfium2 as pdfium
logger = getLogger(__name__)
BUCKET = storage.BUCKET
MINIO_ROOT_USER = storage.ROOT_USER
MINIO_ROOT_PASSWORD = storage.ROOT_PASSWORD

async def parse_mu_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False
    )

    with s3.open(s3_url) as doc:
        markdown = pymupdf4llm.to_markdown(
            pymupdf.open(ext,doc.read(),filetype=ext)
        )
    logger.error("parse_mu_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown
async def parse_pdf_markdown_s3(ctx: Context, *, s3_url: str) -> str:
    from swparse.convert import pdf_markdown
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False
    )

    with s3.open(s3_url,mode="rb") as doc:
        markdown,doc_images,out_meta = pdf_markdown(doc.read())
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown

async def parse_image_markdown_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    from swparse.convert import pdf_markdown
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False   
    )

    with s3.open(s3_url,mode="rb") as doc:
        pil_image = Image.open(doc.read()).convert("RGB")
    pdf = pdfium.PdfDocument.new()

    image = pdfium.PdfImage.new(pdf)
    image.set_bitmap(pdfium.PdfBitmap.from_pil(pil_image))
    width, height = image.get_size()

    matrix = pdfium.PdfMatrix().scale(width, height)
    image.set_matrix(matrix)

    page = pdf.new_page(width, height)
    page.insert_obj(image)
    page.gen_content()
    output= io.BytesIO()
    pdf.save(output)
    markdown = pdf_markdown(output.read())
    logger.error("parse_image_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown