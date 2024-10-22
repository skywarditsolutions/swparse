from __future__ import annotations

import io
from logging import getLogger
from typing import TYPE_CHECKING

import mammoth
import mistletoe
import pandas as pd
import pypdfium2 as pdfium
from html2text import html2text
from markdownify import markdownify as md
from PIL import Image
from s3fs import S3FileSystem
from xlsx2html import xlsx2html

from swparse.config.app import settings
from swparse.db.models  import ContentType 
from swparse.domain.swparse.convert import convert_xlsx_csv, pdf_markdown
from swparse.domain.swparse.utils import convert_xls_to_xlsx_bytes, save_file_s3, get_file_name, change_file_ext

if TYPE_CHECKING:
    from saq.types import Context

logger = getLogger(__name__)
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
MD_EXT = ".extracted.md"
TXT_EXT = ".extracted.txt"
HTML_EXT = ".extracted.html"
CSV_EXT = ".extracted.csv"
JSON_EXT = ".extracted.json"


async def parse_xlsx_markdown_s3(ctx: Context, *, s3_url: str, ext: str) -> dict[str,str]:
    s3 = S3FileSystem(
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
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
        xlsx_file = io.BytesIO(content)
        out_file = io.StringIO()
        xlsx2html(xlsx_file, out_file, locale="en")
        out_file.seek(0)
        result_html = out_file.read()
        html_file_name = change_file_ext(file_name, "html")
        html_file_path = save_file_s3(s3, html_file_name, result_html)
            
        # Markdown Parsing
        markdown = html2text(result_html)
        md_file_name = change_file_ext(file_name, "md")
        md_file_path = save_file_s3(s3, md_file_name, markdown)
        
        return  {
            ContentType.CSV.value: csv_file_path,
            ContentType.MARKDOWN.value: md_file_path,
            ContentType.HTML.value: html_file_path,
        }
        
    except FileNotFoundError:
        logger.exception("File not found in %s", s3_url)
         
    except Exception as e:
        logger.exception("Error while parsing document: %s", e)

    logger.error(s3_url)
    logger.error("parse_xlsx_markdown_s3")
    return {}


async def extract_string(ctx: Context, *, s3_url: str, ext: str) -> dict[str,str]:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    logger.error("extract_string")
    logger.error(s3_url)
    file_name = get_file_name(s3_url)
    txt_file_name = change_file_ext(file_name, "txt")

    with s3.open(s3_url, mode="rb") as doc:
        byte_string = doc.read()
        try:
            out_txt = str(byte_string.decode("utf-8"))
            text_file_path = save_file_s3(s3, txt_file_name, out_txt)
            return {ContentType.TEXT.value: text_file_path}
        except UnicodeDecodeError:
            out_txt = str(byte_string)
            text_file_path = save_file_s3(s3, txt_file_name, out_txt)
            return {ContentType.TEXT.value:text_file_path }


async def parse_pdf_markdown_s3(ctx: Context, *, s3_url: str) -> dict[str, str]:
    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    out_md = f"{s3_url}.{MD_EXT}"
    out_txt = f"{s3_url}.{TXT_EXT}"
    out_html = f"{s3_url}.{HTML_EXT}"

    with s3.open(s3_url, mode="rb") as doc:  # type: ignore
        markdown, doc_images, out_meta = pdf_markdown(doc.read(), max_pages=20)

    with s3.open(out_md, mode="w") as out_file_md:  # type: ignore
        out_file_md.write(markdown)  # type: ignore
    with s3.open(out_html, mode="w") as out_file_html:  # type: ignore
        out_file_html.write(mistletoe.markdown(markdown))  # type: ignore
    with s3.open(out_txt, mode="w") as out_file_txt:  # type: ignore
        out_file_txt.write(markdown)  # type: ignore
    results = {ContentType.MARKDOWN.value: out_md, ContentType.HTML.value: out_html, ContentType.TEXT.value: out_txt}
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    return results


async def parse_docx_markdown_s3(ctx: Context, *, s3_url: str) ->dict[str,str]:
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
        result = mammoth.convert_to_html(byte_content) # type: ignore
        htmlData:str = result.value # type: ignore
    html_file_name = change_file_ext(file_name, "html")
    html_file_path = save_file_s3(s3, html_file_name, htmlData)
    
    # Markdown parsing
    markdown = md(htmlData) # type: ignore
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown)
    
    logger.error("parse_docx_markdown_s3")
    logger.error(s3_url)
    
    logger.error(markdown)
    return  {
        ContentType.HTML.value: html_file_path,
        ContentType.MARKDOWN.value: md_file_path,
    }


async def parse_pdf_page_markdown_s3(ctx: Context, *, s3_url: str, page: int) -> dict[str,str]:
    from swparse.domain.swparse.convert import pdf_markdown

    s3 = S3FileSystem(
        # asynchronous=True,
        endpoint_url=settings.storage.ENDPOINT_URL,
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        use_ssl=False,
    )
    file_name = get_file_name(s3_url)
    with s3.open(s3_url, mode="rb") as doc:
        markdown, doc_images, out_meta = pdf_markdown(doc.read(), start_page=page, max_pages=1)
    logger.error("parse_pdf_markdown_s3")
    logger.error(s3_url)
    logger.error(markdown)
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown)
    return  {
        ContentType.MARKDOWN.value: md_file_path,
    }


async def parse_image_markdown_s3(ctx: Context, *, s3_url: str, ext: str) -> dict[str, str]:
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
    file_name = get_file_name(s3_url)
    md_file_name = change_file_ext(file_name, "md")
    md_file_path = save_file_s3(s3, md_file_name, markdown[0])
    return  {ContentType.MARKDOWN.value: md_file_path}


async def extract_text_files(ctx: Context, *, s3_url: str, ext: str) -> dict[str,str]:
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
            result = {ContentType.TEXT.value: text_file_path}

            if ext == "text/csv":
                csv_buffer = io.StringIO(content)
                df = pd.read_csv(csv_buffer)
                txt_content = df.to_string(index=False)
                text_file_name = change_file_ext(file_name, "txt")
                text_file_path = save_file_s3(s3, text_file_name, txt_content)
            
     
                html_content = df.to_html()
                html_file_name = change_file_ext(file_name, "html")
                html_file_path = save_file_s3(s3, html_file_name, html_content)
           
            
                # Markdown Parsing
                markdown = html2text(html_content)
                md_file_name = change_file_ext(file_name, "md")
                md_file_path = save_file_s3(s3, md_file_name, markdown)
    
                result = { 
                ContentType.TEXT.value:text_file_path,
                ContentType.MARKDOWN.value: md_file_path,
                ContentType.HTML.value: html_file_path
                }
                
            return result

    except Exception as e:
        logger.exception(f"Error while parsing document: {e}")

        return {}


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
    return {"csv":csv_file_path}
