from __future__ import annotations

import io
from logging import getLogger
from typing import TYPE_CHECKING
from uuid import uuid4

import html_text
import mammoth
import mistletoe
import pandas as pd
import pypdfium2 as pdfium
from html2text import html2text
from markdownify import markdownify as md
from PIL import Image
from s3fs import S3FileSystem
import markdown as markdown_converter
from swparse.config.app import settings
from swparse.db.models import ContentType
from swparse.domain.swparse.convert import convert_xlsx_csv, pdf_markdown
from swparse.domain.swparse.utils import (
    change_file_ext,
    convert_xls_to_xlsx_bytes,
    get_file_name,
    save_file_s3,
    convert_pptx_to_md,
)
import tempfile
import os
from unoserver import client

if TYPE_CHECKING:
    from saq.types import Context

logger = getLogger(__name__)
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


async def parse_xlsx_s3(ctx: Context, *, s3_url: str, ext: str) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    result = {}
    logger.error("Started parse_xlsx_s3")
    logger.error(s3_url)
    try:
        with s3.open(s3_url, mode="rb") as doc:
            content = doc.read()
        if isinstance(content, str):
            content = content.encode()

        file_name = get_file_name(s3_url)
        # CSV Parsing
        csv_file = await convert_xlsx_csv(content)
        csv_file_name = change_file_ext(file_name, "csv")
        csv_file_path = save_file_s3(s3, csv_file_name, csv_file)

        if ext == "application/vnd.ms-excel":
            logger.error("Converting to xlsx first")
            content = convert_xls_to_xlsx_bytes(content)

        # HTML Parsing
        str_buffer = io.StringIO(csv_file)
        df = pd.read_csv(str_buffer)
        html_content = df.to_html()

        html_file_name = change_file_ext(file_name, "html")
        html_file_path = save_file_s3(s3, html_file_name, html_content)

        # Markdown Parsing
        markdown = html2text(html_content)
        md_file_name = change_file_ext(file_name, "md")
        md_file_path = save_file_s3(s3, md_file_name, markdown)

        # Parsing to Text
        text_content = html_text.extract_text(html_content, guess_layout=False)
        text_file_name = change_file_ext(file_name, "txt")
        txt_file_path = save_file_s3(s3, text_file_name, text_content)

        result = {
            ContentType.CSV.value: csv_file_path,
            ContentType.MARKDOWN.value: md_file_path,
            ContentType.HTML.value: html_file_path,
            ContentType.TEXT.value: txt_file_path,
        }

    except Exception as e:
        logger.exception(f"Error while parsing document: {e}")

    return result


async def extract_string(ctx: Context, *, s3_url: str, ext: str) -> dict[str, str]:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    logger.error("Started extract_string")
    logger.error(s3_url)
    file_name = get_file_name(s3_url)
    txt_file_name = change_file_ext(file_name, "txt")

    with s3.open(s3_url, mode="rb") as doc:
        byte_string = doc.read()
        try:
            out_txt = str(byte_string.decode("utf-8"))
            text_file_path = save_file_s3(s3, txt_file_name, out_txt)
        except UnicodeDecodeError:
            out_txt = str(byte_string)
            text_file_path = save_file_s3(s3, txt_file_name, out_txt)
        return {ContentType.TEXT.value: text_file_path}


def _pdf_exchange(s3_url: str, start_page: int = 0, end_page: int = 40) -> dict[str, str]:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )

    file_name = get_file_name(s3_url)

    with s3.open(s3_url, mode="rb") as doc:
        markdown, doc_images, out_meta = pdf_markdown(doc.read(), start_page=start_page, max_pages=end_page)

    html_results = mistletoe.markdown(markdown)
    text_results = html_text.extract_text(html_results, guess_layout=True)

    # Markdown Parsing
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown)
    # HTML Parsing
    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, html_results)
    # Markdown Parsing
    txt_file_name = change_file_ext(file_name, "txt")
    txt_file_path = save_file_s3(s3, txt_file_name, text_results)

    logger.info(md_file_path, html_file_path, txt_file_path)
    return {
        ContentType.MARKDOWN.value: md_file_path,
        ContentType.HTML.value: html_file_path,
        ContentType.TEXT.value: txt_file_path,
    }


async def parse_docx_s3(ctx: Context, *, s3_url: str) -> dict[str, str]:
    logger.error("Started parse_docx_s3")
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    file_name = get_file_name(s3_url)
    # HTML parsing
    with s3.open(s3_url, mode="rb") as byte_content:
        result = mammoth.convert_to_html(byte_content)  # type: ignore
        htmlData: str = result.value  # type: ignore
    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, htmlData)

    # Markdown parsing
    markdown = md(htmlData)  # type: ignore
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown)

    # Parsing to Text
    text_content = html_text.extract_text(htmlData, guess_layout=False)
    text_file_name = change_file_ext(file_name, "txt")
    txt_file_path = save_file_s3(s3, text_file_name, text_content)

    return {
        ContentType.HTML.value: html_file_path,
        ContentType.MARKDOWN.value: md_file_path,
        ContentType.TEXT.value: txt_file_path,
    }


async def parse_pdf_s3(ctx: Context, *, s3_url: str) -> dict[str, str]:
    logger.error("Started parse_pdf_s3")
    results = _pdf_exchange(s3_url)
    return results


async def parse_pdf_page_s3(ctx: Context, *, s3_url: str, page: int) -> dict[str, str]:
    return _pdf_exchange(s3_url, start_page=page)


async def parse_image_s3(ctx: Context, *, s3_url: str, ext: str) -> dict[str, str]:
    logger.error("Started parse_image_s3")
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

    logger.error("parse_image_s3")
    logger.error(s3_url)
    return _pdf_exchange(s3_url)


async def extract_text_files(ctx: Context, *, s3_url: str, ext: str) -> dict[str, str]:
    logger.error("Started extract_text_files")
    result = {}
    try:
        s3 = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        file_name = get_file_name(s3_url)
        with s3.open(s3_url, mode="rb") as doc:
            content = doc.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            text_file_name = change_file_ext(file_name, "txt")
            text_file_path = save_file_s3(s3, text_file_name, content)

            if ext == "text/xml":
                df = pd.read_xml(io.StringIO(content))
                html_content = df.to_html()

            elif ext == "text/csv":
                csv_buffer = io.StringIO(content)
                df = pd.read_csv(csv_buffer)
                txt_content = df.to_string(index=False)
                text_file_name = change_file_ext(file_name, "txt")
                text_file_path = save_file_s3(s3, text_file_name, txt_content)
                html_content = df.to_html()

            else:
                html_content = markdown_converter.markdown(content)

            html_file_name = change_file_ext(file_name, "html")
            html_file_path = save_file_s3(s3, html_file_name, html_content)

            # Markdown Parsing
            markdown = html2text(html_content)
            md_file_name = change_file_ext(file_name, "md")
            md_file_path = save_file_s3(s3, md_file_name, markdown)

            result = {
                ContentType.MARKDOWN.value: md_file_path,
                ContentType.TEXT.value: text_file_path,
                ContentType.HTML.value: html_file_path,
            }

    except Exception as e:
        logger.exception(f"Error while parsing document: {e}")

    return result


async def convert_xlsx_to_csv(ctx: Context, *, s3_url: str, ext: str) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    with s3.open(s3_url, mode="rb") as doc:
        content = doc.read()
        csv_content = await convert_xlsx_csv(content)
    file_name = get_file_name(s3_url)
    csv_file_name = change_file_ext(file_name, "csv")
    csv_file_path = save_file_s3(s3, csv_file_name, csv_content)
    return {"csv": csv_file_path}


async def parse_doc_s3(ctx: Context, *, s3_url: str) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL, key=MINIO_ROOT_USER, secret=MINIO_ROOT_PASSWORD, use_ssl=False
    )
    file_name = get_file_name(s3_url)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_input_path = os.path.join(temp_dir, file_name)
        with s3.open(s3_url, "rb") as s3_file:
            with open(temp_input_path, "wb") as local_file:
                local_file.write(s3_file.read())

        conv = client.UnoClient(server="libreoffice", port="2003", host_location="remote")
        results = {}

        txt_name = change_file_ext(file_name, "txt")
        temp_txt_path = os.path.join(temp_dir, txt_name)
        conv.convert(inpath=temp_input_path, outpath=temp_txt_path)
        with open(temp_txt_path, "rb") as converted_file:
            txt_s3_path = save_file_s3(s3, txt_name, converted_file.read())
        results[ContentType.TEXT.value] = txt_s3_path

        html_name = change_file_ext(file_name, "html")
        temp_html_path = os.path.join(temp_dir, html_name)
        conv.convert(inpath=temp_input_path, outpath=temp_html_path)
        with open(temp_html_path, "rb") as converted_file:
            html_s3_path = save_file_s3(s3, html_name, converted_file.read())
        results[ContentType.HTML.value] = html_s3_path

        with open(temp_html_path, "r") as html_file:
            markdown = md(html_file.read())
            md_file_name = change_file_ext(file_name, "md")
            md_file_path = save_file_s3(s3, md_file_name, markdown)
        results[ContentType.MARKDOWN.value] = md_file_path

    return results


async def parse_ppt_s3(ctx: Context, *, s3_url: str) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL, key=MINIO_ROOT_USER, secret=MINIO_ROOT_PASSWORD, use_ssl=False
    )
    file_name = get_file_name(s3_url)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_input_path = os.path.join(temp_dir, file_name)
        with s3.open(s3_url, "rb") as s3_file:
            with open(temp_input_path, "wb") as local_file:
                local_file.write(s3_file.read())

        conv = client.UnoClient(server="libreoffice", port="2003", host_location="remote")

        results = {}

        pptx_name = change_file_ext(file_name, "pptx")
        temp_pptx_path = os.path.join(temp_dir, pptx_name)
        conv.convert(inpath=temp_input_path, outpath=temp_pptx_path)
        with open(temp_pptx_path, "rb") as converted_file:
            pptx_s3_path = save_file_s3(s3, pptx_name, converted_file.read())
        results[ContentType.TEXT.value] = pptx_s3_path
        md_file_name = change_file_ext(file_name, "md")
        new_uuid = uuid4()
        md_file_path = f"{BUCKET}/{new_uuid}_{md_file_name}"
        markdown = convert_pptx_to_md(pptx_s3_path, md_file_path)
        html_results = mistletoe.markdown(markdown)
        text_results = html_text.extract_text(html_results, guess_layout=True)

        html_file_name = change_file_ext(file_name, "html")
        html_file_path = save_file_s3(s3, html_file_name, html_results)

        txt_file_name = change_file_ext(file_name, "txt")
        txt_file_path = save_file_s3(s3, txt_file_name, text_results)

        results = {
            ContentType.MARKDOWN.value: md_file_path,
            ContentType.HTML.value: html_file_path,
            ContentType.TEXT.value: txt_file_path,
        }
        return results


async def parse_pptx_s3(ctx: Context, *, s3_url: str) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    file_name = get_file_name(s3_url)
    md_file_name = change_file_ext(file_name, "md")
    with s3.open(s3_url, mode="rb") as pptx_file:
        markdown_content = convert_pptx_to_md(pptx_file, file_name)
    md_file_path = save_file_s3(s3, md_file_name, markdown_content)

    html_content = mistletoe.markdown(markdown_content)
    text_content = html_text.extract_text(html_content, guess_layout=True)

    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, html_content)

    txt_file_name = change_file_ext(file_name, "txt")
    txt_file_path = save_file_s3(s3, txt_file_name, text_content)

    results = {
        ContentType.MARKDOWN.value: md_file_path,
        ContentType.HTML.value: html_file_path,
        ContentType.TEXT.value: txt_file_path,
    }
    return results
