import hashlib
import io
import json
import os
from itertools import islice
from logging import getLogger
from operator import attrgetter
from typing import IO
from uuid import uuid4

import pandas as pd
from litestar.exceptions import HTTPException
from lxml import html
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.shapes.base import BaseShape
from pptx.shapes.shapetree import SlideShapes
from s3fs import S3FileSystem
from snakemd import Document as SnakeMdDocument
from snakemd.elements import MDList
from xls2xlsx import XLS2XLSX

from swparse.config.app import settings
from swparse.db.models.content_type import ContentType
from swparse.domain.swparse.schemas import JobMetadata, JobResult

logger = getLogger(__name__)
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD

s3 = S3FileSystem(
    endpoint_url=settings.storage.ENDPOINT_URL,
    key=MINIO_ROOT_USER,
    secret=MINIO_ROOT_PASSWORD,
    use_ssl=False,
)


def convert_xls_to_xlsx_bytes(content: bytes) -> bytes:

    x2x = XLS2XLSX(io.BytesIO(content))
    workbook = x2x.to_xlsx()

    with io.BytesIO() as buffer:
        workbook.save(buffer)
        buffer.seek(0)
        return buffer.read()


def save_file_s3(s3fs: S3FileSystem, file_name: str, content: bytes | str) -> str:
    new_uuid = uuid4()
    s3_url = f"{BUCKET}/{new_uuid}_{file_name}"
    if isinstance(content, str):
        content = content.encode(encoding="utf-8", errors="ignore")
    with s3fs.open(s3_url, mode="wb") as f:
        f.write(content)
        return s3_url


def get_file_name(s3_url: str) -> str:
    return os.path.basename(s3_url).split("/")[-1]


def change_file_ext(file_name: str, extension: str) -> str:
    file_path = file_name.split(".")
    file_path[-1] = extension
    return ".".join(file_path)


def extract_tables_from_html(s3fs: S3FileSystem, html_file_path: str) -> list[str] | None:
    with s3fs.open(html_file_path, mode="rb") as doc:
        content = doc.read().decode()

    tree = html.fromstring(content)
    tables = tree.xpath("//table")
    if not tables:
        # No table found in the html file
        return None

    html_tables: list[str] = []
    for table in tables:
        html_table = html.tostring(table, method="html", pretty_print=True)

        if isinstance(html_table, bytes):
            html_table = html_table.decode()
        html_tables.append(html_table)

    return html_tables


def ungroup_shapes(shapes: SlideShapes) -> list[BaseShape]:
    res = []
    for shape in shapes:
        try:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                res.extend(ungroup_shapes(shape.shapes))
            else:
                res.append(shape)
        except Exception as e:
            raise Exception(f"{e}")
    return res


def is_title(shape: BaseShape) -> bool:
    if shape.is_placeholder and shape.placeholder_format.type in [
        PP_PLACEHOLDER.TITLE,
        PP_PLACEHOLDER.SUBTITLE,
        PP_PLACEHOLDER.VERTICAL_TITLE,
        PP_PLACEHOLDER.CENTER_TITLE,
    ]:
        return True
    return False


def is_text_block(shape: BaseShape) -> bool:
    if shape.has_text_frame:
        if (
            shape.is_placeholder
            and shape.placeholder_format.type == PP_PLACEHOLDER.BODY
        ) or (
            shape.is_placeholder
            and shape.placeholder_format.type == PP_PLACEHOLDER.OBJECT
        ) or shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
            return True
    return False

def is_list_block(shape: BaseShape) -> bool:
    levels = []
    for para in shape.text_frame.paragraphs:
        if para.level not in levels:
            levels.append(para.level)
        if para.level != 0 or len(levels) > 1:
            return True
    return False

def is_list_nested(shape: BaseShape) -> bool:
    levels = []
    for para in shape.text_frame.paragraphs:
        if para.level not in levels:
            levels.append(para.level)
        if len(levels) > 1:
            return True
    return False

def add_to_list(nested_list: MDList, level: int, text: str):
    if level == 0:
        nested_list._items.append(text) # type: ignore
    else:
        if not nested_list._items or not isinstance(nested_list._items[-1], list): # type: ignore
            nested_list._items.append(MDList([])) # type: ignore
        add_to_list(nested_list._items[-1], level - 1, text) # type: ignore



def process_shapes(shapes: list[BaseShape], file: SnakeMdDocument):
    try:
        for shape in shapes:
            if is_title(shape):
                file.add_heading(text=shape.text_frame.text, level=1)
            elif is_text_block(shape):
                if is_list_block(shape):
                    if is_list_nested(shape):
                        items = MDList([])
                        for paragraph in shape.text_frame.paragraphs:
                            add_to_list(items, paragraph.level, paragraph.text)
                        file.add_block(items)
                    else:
                        items = []
                        for paragraph in shape.text_frame.paragraphs:
                            add_to_list(items, paragraph.level, paragraph.text)
                        file.add_unordered_list(items=items)
                else:
                    for paragraph in shape.text_frame.paragraphs:
                        file.add_paragraph(text=paragraph.text)
            elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                pass
            elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
                column_names = [cell.text for cell in shape.table.rows[0].cells]
                data = [[cell.text for cell in row.cells] for row in islice(shape.table.rows, 1, None)]
                file.add_table(
                    header=column_names,
                    data=data,
                )
            else:
                pass
            try:
                ph = shape.placeholder_format
                if (
                    ph.type == PP_PLACEHOLDER.OBJECT
                    and hasattr(shape, "image")
                    and getattr(shape, "image")
                ):
                    pass
            except:
                pass
    except Exception as e:
        raise Exception


def convert_pptx_to_md(pptx_content: IO[bytes], pptx_filename: str) -> str:
    try:
        prs = Presentation(pptx_content)
        md_file = SnakeMdDocument()
        for idx, slide in enumerate(prs.slides):
            shapes = []
            shapes = sorted(ungroup_shapes(slide.shapes), key=attrgetter("top", "left"))
            process_shapes(shapes, md_file)
        return str(md_file)
    except Exception as e:
        raise Exception
        

def get_hashed_file_name(filename:str, content:bytes)->str:
    file_ext = filename.split(".")[-1]
    check_sum = hashlib.md5(content).hexdigest()
    return f"{check_sum}.{file_ext}"


def get_job_metadata(s3: S3FileSystem) -> dict[str, dict[str, str]]:
    job_file_path = f"{BUCKET}/job_metadata.json"
    content = {}
    if s3.exists(job_file_path):
        with s3.open(job_file_path, mode="r") as f:
            content = json.loads(f.read())
    return content

def save_job_metadata(s3: S3FileSystem, job_id: str, results: dict[str, str]) -> None:
    job_file_path = f"{BUCKET}/job_metadata.json"
    existing_job_metadata = get_job_metadata(s3)
    existing_job_metadata[job_id] = results
    try:
        with s3.open(job_file_path, mode="w") as f:
            f.write(json.dumps(existing_job_metadata))
    except Exception as err:
        raise HTTPException(f"Save job metadata error: {err}")


def get_file_content(s3:S3FileSystem, file_path:str)->str:
    with s3.open(file_path, mode="r") as f:
        content = f.read()
        if isinstance(content, bytes):
            content = content.decode()
    return content

def handle_result_type(result_type:str, results:dict[str,str], s3:S3FileSystem, jm:JobMetadata)->JobResult:
    try:
        if result_type == ContentType.MARKDOWN.value:
            markdown = get_file_content(s3, results["markdown"])
            return JobResult(markdown=markdown, html="", text="", job_metadata=jm)

        if result_type == ContentType.HTML.value:
            html = get_file_content(s3, results["html"])
            return JobResult(markdown="", html=html, text="", job_metadata=jm)

        if result_type == ContentType.TEXT.value:
            text = get_file_content(s3, results["text"])
            return JobResult(markdown="", html="", text=text, job_metadata=jm)

        if result_type == ContentType.TABLE.value:
            html = extract_tables_from_html(s3, results["html"])
            result_html = "<br><br>"
            if html:
                result_html = result_html.join(html)
            return JobResult(markdown="", html="", text="", table=result_html, job_metadata=jm)

        if result_type == ContentType.MARKDOWN_TABLE.value:
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
        raise HTTPException(f"Format {result_type} is currently unsupported for {job_key}")

    except Exception as e:
        raise HTTPException(f"Format {result_type} is currently unsupported for {job_key}")
