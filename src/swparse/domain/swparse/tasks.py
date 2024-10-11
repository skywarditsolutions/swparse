from __future__ import annotations

import io
from logging import getLogger
from typing import TYPE_CHECKING

import mammoth
import pandas as pd
import pypdfium2 as pdfium
from html2text import html2text
from markdownify import markdownify as md
from PIL import Image
from s3fs import S3FileSystem
from xlsx2html import xlsx2html

from swparse.config.app import settings
from swparse.domain.swparse.convert import convert_xlsx_csv, pdf_markdown

if TYPE_CHECKING:
    from saq.types import Context

logger = getLogger(__name__)
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


async def parse_xlsx_markdown_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    logger.error("READ Content")
    try:
        with s3.open(s3_url, mode="rb") as doc:
            xlsx_file = io.BytesIO(doc.read())
            out_file = io.StringIO()

            default_langs = "en"
            xlsx2html(xlsx_file, out_file, locale=default_langs)
            out_file.seek(0)
            result_html = out_file.read()
            markdown = html2text(result_html)

    except FileNotFoundError:
        logger.exception("File not found in %s", s3_url)
        markdown = ""
    except Exception as e:
        logger.exception("Error while parsing document: %s", e)
        markdown = ""

    logger.error(s3_url)
    logger.error("parse_xlsx_markdown_s3")
    return markdown


async def extract_string(ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    logger.error("extract_string")
    logger.error(s3_url)
    with s3.open(s3_url, mode="rb") as doc:
        byte_string = doc.read()
        try:
            return str(byte_string.decode("utf-8"))
        except UnicodeDecodeError:
            return str(byte_string)


async def parse_pdf_markdown_s3(ctx: Context, *, s3_url: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
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


async def parse_docx_markdown_s3(ctx: Context, *, s3_url: str) -> str:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    with s3.open(s3_url, mode="rb") as doc:
        result = mammoth.convert_to_html(doc)
        htmlData = result.value
        markdown = md(htmlData)
        logger.error("parse_docx_markdown_s3")
        logger.error(s3_url)
        logger.error(htmlData)
        logger.error(markdown)
    return markdown


async def parse_pdf_page_markdown_s3(ctx: Context, *, s3_url: str, page: int) -> str:
    from swparse.domain.swparse.convert import pdf_markdown

    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )

    with s3.open(s3_url, mode="rb") as doc:
        markdown, doc_images, out_meta = pdf_markdown(doc.read(), start_page=page, max_pages=1)
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return markdown


async def parse_image_markdown_s3(ctx: Context, *, s3_url: str, ext: str) -> str:
    from swparse.domain.swparse.convert import pdf_markdown

    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
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


async def extract_text_files(ctx: Context, *, s3_url: str, ext: str) -> str:
    try:
        s3 = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        with s3.open(s3_url, mode="rb") as doc:
            content = doc.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            if ext == "text/csv":
                csv_buffer = io.StringIO(content)
                df = pd.read_csv(csv_buffer)
                content = df.to_string(index=False)

            return content

    except Exception as e:
        logger.exception(f"Error while parsing document: {e}")

        return ""


async def convert_xlsx_to_csv(ctx: Context, *, s3_url: str, ext: str) -> str:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    with s3.open(s3_url, mode="rb") as doc:
        content = doc.read()
        return await convert_xlsx_csv(content)
