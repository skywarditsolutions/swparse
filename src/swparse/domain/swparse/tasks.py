from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import time
from io import BytesIO
from typing import TYPE_CHECKING
from uuid import uuid4

import html_text
import mammoth
import markdown as markdown_converter
import mistletoe
import pandas as pd
import pypdfium2 as pdfium
import structlog
from html2text import html2text
from markdownify import markdownify as md
from PIL import Image
from s3fs import S3FileSystem
from unoserver import client

from swparse.config.app import settings
from swparse.db.models import ContentType
from swparse.domain.swparse.convert import convert_xlsx_csv, pdf_markdown
from swparse.domain.swparse.utils import (
    change_file_ext,
    convert_pptx_to_md,
    convert_xls_to_xlsx_bytes,
    extract_md_components,
    extract_tables_gliner,
    format_timestamp,
    get_file_content,
    get_file_name,
    save_file_s3,
)

if TYPE_CHECKING:
    from saq.types import Context

logger = structlog.get_logger()
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD

s3 = S3FileSystem(
    endpoint_url=settings.storage.ENDPOINT_URL,
    key=MINIO_ROOT_USER,
    secret=MINIO_ROOT_PASSWORD,
    use_ssl=False,
)

s3fs = S3FileSystem(
    endpoint_url=settings.storage.ENDPOINT_URL,
    key=MINIO_ROOT_USER,
    secret=MINIO_ROOT_PASSWORD,
    use_ssl=False,
)


async def parse_xlsx_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    api_start_time = time.time()
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    result = {}
    logger.info("Started parse_xlsx_s3")
    try:
        with s3.open(s3_url, mode="rb") as doc:
            content = doc.read()
        if isinstance(content, str):
            content = content.encode()

        file_name = get_file_name(s3_url)
        # CSV Parsing
        csv_start_time = time.time()
        csv_file = await convert_xlsx_csv(content)
        csv_end_time = time.time()
        csv_file_name = change_file_ext(file_name, "csv")
        csv_file_path = save_file_s3(s3, csv_file_name, csv_file)

        if ext == "application/vnd.ms-excel":
            content = convert_xls_to_xlsx_bytes(content)

        # HTML Parsing
        html_start_time = time.time()
        str_buffer = io.StringIO(csv_file)
        df = pd.read_csv(str_buffer, header=0, skip_blank_lines=True, na_filter=False)
        df = df.fillna("")
        html_content = df.to_html(index=False, na_rep="")
        html_end_time = time.time()

        html_file_name = change_file_ext(file_name, "html")
        html_file_path = save_file_s3(s3, html_file_name, html_content)

        # Markdown Parsing
        md_start_time = time.time()
        markdown = df.to_markdown()
        md_end_time = time.time()
        md_file_name = change_file_ext(file_name, "md")
        md_file_path = save_file_s3(s3, md_file_name, markdown)

        # Parsing to Text
        txt_start_time = time.time()
        text_content = html_text.extract_text(html_content)
        txt_end_time = time.time()
        text_file_name = change_file_ext(file_name, "txt")
        txt_file_path = save_file_s3(s3, text_file_name, text_content)

        result = {
            ContentType.CSV.value: csv_file_path,
            ContentType.MARKDOWN.value: md_file_path,
            ContentType.HTML.value: html_file_path,
            ContentType.TEXT.value: txt_file_path,
        }

        if table_query:
            xlsx_tbl_qry_start = time.time()
            tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
            xlsx_tbl_qry_end = time.time()
            tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
            tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
            result[table_query["raw"]] = tables_file_path

            logger.info(f"XLSX tbl qry start: {format_timestamp(xlsx_tbl_qry_start)}")
            logger.info(f"XLSX tbl qry end: {format_timestamp(xlsx_tbl_qry_end)}")
            logger.info(f"XLSX tbl qry time taken {format_timestamp(xlsx_tbl_qry_end- xlsx_tbl_qry_start)}\n\n")

        meta_save_start_time = time.time()
        metadata = json.dumps(result)
        s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)
        meta_save_end_time = time.time()

    except Exception as e:
        logger.exception(f"Error while parsing document: {e}")

    api_end_time = time.time()

    logger.info(f"XLSX to csv start: {format_timestamp(csv_start_time)}")
    logger.info(f"XLSX to csv end: {format_timestamp(csv_end_time)}")
    logger.info(f"XLSX to CSV time taken {format_timestamp(csv_end_time - csv_start_time)}\n\n")

    logger.info(f"XLSX to HTML start: {format_timestamp(html_start_time)}")
    logger.info(f"XLSX to HTML end: {format_timestamp(html_end_time)}")
    logger.info(f"XLSX to HTML time taken {format_timestamp(html_end_time - html_start_time)}\n\n")

    logger.info(f"XLSX to MD start: {format_timestamp(md_start_time)}")
    logger.info(f"XLSX to MD end: {format_timestamp(md_end_time)}")
    logger.info(f"XLSX to MD time taken {format_timestamp(csv_end_time - csv_start_time)}\n\n")

    logger.info(f"XLSX to TXT start: {format_timestamp(txt_start_time)}")
    logger.info(f"XLSX to TXT end: {format_timestamp(txt_end_time)}")
    logger.info(f"XLSX to TXT time taken {format_timestamp(txt_end_time - txt_start_time)}\n\n")


    logger.info(f"XLSX Meta data saved start: {format_timestamp(meta_save_start_time)}")
    logger.info(f"XLSX Meta data saved end: {format_timestamp(meta_save_end_time)}")
    logger.info(f"XLSX Meta data saved time taken {format_timestamp(txt_end_time- txt_start_time)}\n\n")

    logger.info(f"XLSX api_start_time {format_timestamp(api_start_time)}")
    logger.info(f"XLSX api end time {format_timestamp(api_end_time)}")
    logger.info(f"XLSX API time taken {format_timestamp(api_end_time - api_start_time)}\n\n")
    return result


async def extract_string(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    logger.info("Started extract_string")
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
    result = {ContentType.TEXT.value: text_file_path}

    metadata = json.dumps(result)
    s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)

    return result


def _pdf_exchange(s3_url: str, start_page: int = 0, end_page: int = 40) -> dict[str, str]:
    file_name = get_file_name(s3_url)

    with s3.open(s3_url, mode="rb") as doc:
        content = doc.read()

    markdown, doc_images, out_meta, json_result = pdf_markdown(content, start_page=start_page, max_pages=end_page)    
    html_results = mistletoe.markdown(markdown)
    text_results = html_text.extract_text(html_results, guess_layout=True)

    all_images = {}
    # Save Images
    per_page_json_image_start = time.time()
    for per_page_result in json_result:
        per_page_images = []
        per_page_result["items"] = extract_md_components(per_page_result.get("md"))
        doc_images = per_page_result.get("doc_images")
        if doc_images is None:
            continue
        for image_name, img in doc_images.items():
            image_name = image_name.lower()
            buffered = BytesIO()
            img.save(buffered, format=image_name.split(".")[-1])
            img_b = buffered.getvalue()
            img_file_path = save_file_s3(s3, image_name, img_b)
            all_images[image_name] = img_file_path
            per_page_images.append({image_name:img_file_path})
        per_page_result.pop("doc_images")
        per_page_result.update({"images":per_page_images})

    per_page_json_image_end = time.time()
    caching_start = time.time()
    # Markdown saving
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown)
    # HTML Parsing
    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, html_results)
    # Text Parsing
    txt_file_name = change_file_ext(file_name, "txt")
    txt_file_path = save_file_s3(s3, txt_file_name, text_results)

    # JSON file saving
    json_file_name = change_file_ext(file_name, "json")
    json_file_path = save_file_s3(s3, json_file_name, json.dumps(json_result))

    # Saving image metadata
    img_file_name = change_file_ext(file_name, "json")
    img_file_path = save_file_s3(s3, img_file_name, json.dumps(all_images))
    caching_end = time.time()

    logger.info(f"Caching start: {format_timestamp(caching_start)}")
    logger.info(f"Caching end: {format_timestamp(caching_end)}")
    logger.info(f"Caching time taken {format_timestamp(caching_end - caching_start)}\n\n")

    logger.info(f"PDF per page JSON images start: {format_timestamp(per_page_json_image_start)}")
    logger.info(f"PDF per page JSON images end: {format_timestamp(per_page_json_image_end)}")
    logger.info(f"PDF per page JSON images time taken {format_timestamp(per_page_json_image_end - per_page_json_image_start)}\n\n")

    return {
        ContentType.MARKDOWN.value: md_file_path,
        ContentType.HTML.value: html_file_path,
        ContentType.TEXT.value: txt_file_path,
        ContentType.IMAGES.value: img_file_path,
        ContentType.JSON.value: json_file_path,
    }


async def parse_docx_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    logger.info("Started parse_docx_s3")

    file_name = get_file_name(s3_url)

    # HTML parsing
    with s3.open(s3_url, mode="rb") as byte_content:
        convert_html_start = time.time()
        result = mammoth.convert_to_html(byte_content)  # type: ignore
        htmlData: str = result.value  # type: ignore
        convert_html_end = time.time()
        # TODO: refactor using a html tree

        docx_img_start = time.time()
        img_tags = re.findall(r'<img\s+[^>]*src=[\'"].+?[\'"][^>]*>', htmlData)

        images = {}

        for i, img in enumerate(img_tags):

            src = re.search(r'src=[\'"]([^\'"]+)[\'"]', img).group(1)
            header, encoded = src.split(",", 1)
            image_type = header.split(";")[0].split(":")[1].split("/")[1]
            image_bytes = base64.b64decode(encoded)

            image_key = f"image-{i}.{image_type}"
            htmlData = htmlData.replace(img, f'<img src="{image_key}" alt="{image_key}" />', 1)
            image_file_path = save_file_s3(s3, image_key, image_bytes)
            images[image_key] = image_file_path

    docx_img_end = time.time()

    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, htmlData)

    # Markdown parsing
    md_start =time.time()
    markdown = md(htmlData)  # type: ignore
    md_end =time.time()
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown)

    # Parsing to Text
    text_content = html_text.extract_text(htmlData, guess_layout=True)
    text_file_name = change_file_ext(file_name, "txt")
    txt_file_path = save_file_s3(s3, text_file_name, text_content)

    # Saving image metadata
    file_name = file_name + "_image_metadata"
    img_file_name = change_file_ext(file_name, "json")
    img_file_path = save_file_s3(s3, img_file_name, json.dumps(images))


    result = {
        ContentType.HTML.value: html_file_path,
        ContentType.MARKDOWN.value: md_file_path,
        ContentType.TEXT.value: txt_file_path,
        ContentType.IMAGES.value: img_file_path,
    }

    if table_query:
        table_query_start = time.time()
        tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
        table_query_end = time.time()
        tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
        tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
        result[table_query["raw"]] = tables_file_path
        logger.info(f"DOCX to table qry extraction start: {format_timestamp(table_query_start)}")
        logger.info(f"DOCX to table qry extraction end: {format_timestamp(table_query_end)}")
        logger.info(f"DOCX to table qry extraction time taken {format_timestamp(table_query_end - table_query_start)}\n\n")


    metadata = json.dumps(result)
    s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)
 
    logger.info(f"DOCX to HTML start: {format_timestamp(convert_html_start)}")
    logger.info(f"DOCX to HTML end: {format_timestamp(convert_html_end)}")
    logger.info(f"DOCX to HTML time taken {format_timestamp(convert_html_end - convert_html_start)}\n\n")

    logger.info(f"DOCX image prepare start: {format_timestamp(docx_img_start)}")
    logger.info(f"DOCX image prepare end: {format_timestamp(docx_img_end)}")
    logger.info(f"DOCX image prepare time taken {format_timestamp(docx_img_end - docx_img_start)}\n\n")

    logger.info(f"DOCX to MD start: {format_timestamp(md_start)}")
    logger.info(f"DOCX to MD end: {format_timestamp(md_end)}")
    logger.info(f"DOCX to MD time taken {format_timestamp(md_end - md_start)}\n\n")

    logger.info(f"DOCX to HTML start: {format_timestamp(docx_img_start)}")
    logger.info(f"DOCX to HTML end: {format_timestamp(docx_img_end)}")
    logger.info(f"DOCX to HTML time taken {format_timestamp(docx_img_end - docx_img_start)}\n\n")

    return result


async def parse_pdf_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    logger.info("Started parse_pdf_s3")
    api_start_time = time.time()
    results = _pdf_exchange(s3_url)

    if table_query:
        file_name = get_file_name(s3_url)
        markdown = get_file_content(s3, results["markdown"])
        pdf_tbl_qry_start = time.time()
        tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
        pdf_tbl_qry_end = time.time()
        tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
        tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
        results[table_query["raw"]] = tables_file_path

        logger.info(f"pdf_tbl_qry start {format_timestamp(pdf_tbl_qry_start)}")
        logger.info(f"pdf_tbl_qry end {format_timestamp(pdf_tbl_qry_end)}")
        logger.info(f"pdf_tbl_qry time taken {format_timestamp(pdf_tbl_qry_end - pdf_tbl_qry_start)}\n\n")

    metadata = json.dumps(results)
    s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)
    api_end_time = time.time()

    logger.info(f"api_start_time {format_timestamp(api_start_time)}")
    logger.info(f"api_end_time {format_timestamp(api_end_time)}")
    logger.info(f"API time taken {format_timestamp(api_end_time - api_start_time)}\n\n")
    return results


async def parse_pdf_page_s3(ctx: Context, *, s3_url: str, page: int) -> dict[str, str]:
    return _pdf_exchange(s3_url, start_page=page)


async def parse_image_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    logger.info("Started parse_image_s3")
 
    with s3.open(s3_url, mode="rb") as doc:
        image_to_pdf_start = time.time()
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
    image_to_pdf_end = time.time()
    pdf_s3_url = change_file_ext(s3_url, "pdf")
    with s3.open(pdf_s3_url, "wb") as output:
        pdf.save(output)

    results = _pdf_exchange(pdf_s3_url)

    if table_query:
        file_name = get_file_name(pdf_s3_url)
        markdown = get_file_content(s3, results["markdown"])
        img_tbl_qry_start = time.time()
        tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
        img_tbl_qry_end = time.time()
        tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
        tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
        results[table_query["raw"]] = tables_file_path

        logger.info(f"Img tbl qry start {format_timestamp(img_tbl_qry_start)}")
        logger.info(f"Img tbl qry end {format_timestamp(img_tbl_qry_end)}")
        logger.info(f"Img tbl qry time taken {format_timestamp(img_tbl_qry_end - img_tbl_qry_start)}\n\n")


    metadata = json.dumps(results)
    s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)


    logger.info(f"image_to_pdf start {format_timestamp(image_to_pdf_start)}")
    logger.info(f"image_to_pdf end {format_timestamp(image_to_pdf_end)}")
    logger.info(f"image_to_pdf time taken {format_timestamp(image_to_pdf_end - image_to_pdf_start)}\n\n")

    return results


async def extract_text_files(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    logger.info("Started extract_text_files")
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
                html_content = df.to_html(index=False)

            elif ext == "text/csv":
                csv_buffer = io.StringIO(content)
                df = pd.read_csv(csv_buffer, index_col=False)
                txt_content = df.to_string(index=False)
                text_file_name = change_file_ext(file_name, "txt")
                text_file_path = save_file_s3(s3, text_file_name, txt_content)
                html_content = df.to_html(index=False)

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
            if table_query:
                tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
                tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
                tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
                result[table_query["raw"]] = tables_file_path

            metadata = json.dumps(result)
            s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)

    except Exception as e:
        logger.exception(f"Error while parsing document: {e}")

    return result


async def parse_doc_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
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

        with open(temp_html_path) as html_file:
            markdown = md(html_file.read())
            md_file_name = change_file_ext(file_name, "md")
            md_file_path = save_file_s3(s3, md_file_name, markdown)
        results[ContentType.MARKDOWN.value] = md_file_path

        if table_query:
            tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
            tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
            tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
            results[table_query["raw"]] = tables_file_path

        metadata = json.dumps(results)
        s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)

    return results


async def parse_ppt_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
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
        with s3.open(pptx_s3_path, "rb") as pptx_file:
            markdown = convert_pptx_to_md(pptx_file, file_name)
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
        metadata = json.dumps(results)
        s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)

        return results


async def parse_pptx_s3(ctx: Context, *, s3_url: str, ext: str, table_query: dict | None) -> dict[str, str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    file_name = get_file_name(s3_url)
    md_file_name = change_file_ext(file_name, "md")
    pptx_to_md_start = time.time()
    with s3.open(s3_url, mode="rb") as pptx_file:
        markdown_content = convert_pptx_to_md(pptx_file, file_name)
    pptx_to_md_end = time.time()
    md_file_path = save_file_s3(s3, md_file_name, markdown_content)

    pptx_to_html_start = time.time()
    html_content = mistletoe.markdown(markdown_content)
    pptx_to_html_end = time.time()

    pptx_to_txt_start = time.time()
    text_content = html_text.extract_text(html_content, guess_layout=True)
    pptx_to_txt_end = time.time()

    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, html_content)

    txt_file_name = change_file_ext(file_name, "txt")
    txt_file_path = save_file_s3(s3, txt_file_name, text_content)

    results = {
        ContentType.MARKDOWN.value: md_file_path,
        ContentType.HTML.value: html_file_path,
        ContentType.TEXT.value: txt_file_path,
    }

    if table_query:
        pptx_tbl_qry_start = time.time()
        tables_content = extract_tables_gliner(table_query["tables"], markdown_content, table_query["output"])
        pptx_tbl_qry_end = time.time()
        tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
        tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
        results[table_query["raw"]] = tables_file_path
        logger.info(f"pptx_tbl_qry start {format_timestamp(pptx_tbl_qry_start)}")
        logger.info(f"pptx_tbl_qry end {format_timestamp(pptx_tbl_qry_end)}")
        logger.info(f"pptx_tbl_qry time taken {format_timestamp(pptx_tbl_qry_end - pptx_tbl_qry_start)}\n\n")

    metadata = json.dumps(results)
    s3.setxattr(s3_url, copy_kwargs={"ContentType": ext}, metadata=metadata)

    logger.info(f"pptx_to_md start {format_timestamp(pptx_to_md_start)}")
    logger.info(f"pptx_to_md end {format_timestamp(pptx_to_md_end)}")
    logger.info(f"pptx_to_md time taken {format_timestamp(pptx_to_md_end - pptx_to_md_start)}\n\n")

    logger.info(f"pptx_to_html start {format_timestamp(pptx_to_html_start)}")
    logger.info(f"pptx_to_html end {format_timestamp(pptx_to_html_end)}")
    logger.info(f"pptx_to_html time taken {format_timestamp(pptx_to_html_end - pptx_to_html_start)}\n\n")

    logger.info(f"pptx_to_txt start {format_timestamp(pptx_to_txt_start)}")
    logger.info(f"pptx_to_txt end {format_timestamp(pptx_to_txt_end)}")
    logger.info(f"pptx_to_txt time taken {format_timestamp(pptx_to_txt_end - pptx_to_txt_start)}\n\n")

    return results


async def get_extracted_url(ctx: Context, *, s3_url: str, table_query: dict | None) -> dict[str, str]:
    metadata_json_str = s3fs.getxattr(s3_url, "metadata")
    metadata = json.loads(metadata_json_str)

    image_file_path = metadata.get("images")
    # images metadata normalization
    if image_file_path:
        try:
            image_metadata = json.loads(image_file_path)
            file_name = get_file_name(s3_url)
            img_file_name = change_file_ext(file_name, "json")
            img_file_path = save_file_s3(s3, img_file_name, json.dumps(image_metadata))
            metadata["images"]=img_file_path
            new_meatadata = json.dumps(metadata)
            s3.setxattr(s3_url, copy_kwargs={"ContentType": "images"}, metadata=new_meatadata)
        except Exception as err:
            # correct filepath
            pass


    if table_query:
        file_name = get_file_name(s3_url)
        markdown = get_file_content(s3, metadata["markdown"])
        tables_content = extract_tables_gliner(table_query["tables"], markdown, table_query["output"])
        tables_file_name = change_file_ext("extracted_tables_" + file_name, table_query["output"])
        tables_file_path = save_file_s3(s3, tables_file_name, tables_content)
        metadata[table_query["raw"]] = tables_file_path
    logger.info("metadata")
    logger.info(metadata)

    return metadata


async def extract_advanced_tables(ctx: Context, *, markdown: str, table_query: dict) -> dict[str, str]:
    return extract_tables_gliner(table_query, markdown)
