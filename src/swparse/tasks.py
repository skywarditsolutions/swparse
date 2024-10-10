from __future__ import annotations
from logging import getLogger

import pymupdf
import mimetypes
import pymupdf4llm
from PIL import Image
import pypdfium2 as pdfium
from s3fs import S3FileSystem
from swparse.settings import storage


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from saq.types import Context

logger = getLogger(__name__)
BUCKET = storage.BUCKET
MINIO_ROOT_USER = storage.ROOT_USER
MINIO_ROOT_PASSWORD = storage.ROOT_PASSWORD


async def extract_text_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    from swparse.convert import pdf_markdown
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    logger.error("READ Content")
    logger.error(s3_url)
    try:
        with s3.open(s3_url, mode="rb") as doc:
            content = doc.read()
            logger.error("Content")
            logger.error(content)
            markdown, doc_images, out_meta = pdf_markdown(content, max_pages=20)

    except FileNotFoundError:
        logger.error(f"File not found in {s3_url}")
        markdown = ""
    except Exception as e:
        logger.error(f"Error gg while parsing document: {e}")
        markdown = ""

    logger.error(s3_url)
    logger.error("parse_plain_text_markdown_s3")
    return markdown


async def parse_mu_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )

    with s3.open(s3_url) as doc:
        try:
            markdown = pymupdf4llm.to_markdown(
                pymupdf.open(mimetypes.guess_extension(ext), doc.read())
            )
        except Exception as e:
            logger.error(f"Error: {e}")
            markdown = ""
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
        use_ssl=False,
    )

    with s3.open(s3_url, mode="rb") as doc:
        markdown, doc_images, out_meta = pdf_markdown(doc.read(), max_pages=20)
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown


async def parse_pdf_page_markdown_s3(ctx: Context, *, s3_url: str, page: int) -> str:
    from swparse.convert import pdf_markdown

    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=storage.ENPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )

    with s3.open(s3_url, mode="rb") as doc:
        markdown, doc_images, out_meta = pdf_markdown(
            doc.read(), start_page=page, max_pages=1
        )
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
        use_ssl=False,
    )

    with s3.open(s3_url, mode="rb") as doc:
        pil_image = Image.open(doc).convert("RGB")
    pdf = pdfium.PdfDocument.new()

    image = pdfium.PdfImage.new(pdf)
    image.set_bitmap(pdfium.PdfBitmap.from_pil(pil_image))
    width, height = image.get_size()

    matrix = pdfium.PdfMatrix().scale(width, height)
    image.set_matrix(matrix)

    page = pdf.new_page(width, height)
    page.insert_obj(image)
    page.gen_content()
    s3_url = f"{s3_url}.pdf"
    with s3.open(s3_url, "wb") as output:
        pdf.save(output)
    with s3.open(s3_url, "rb") as input_byte:
        markdown = pdf_markdown(input_byte)

    logger.error("parse_image_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown[0]
