import hashlib
import io
import math
import os
import re
from uuid import uuid4
from typing import IO

from lxml import html
from s3fs import S3FileSystem
from xls2xlsx import XLS2XLSX
from pptx import Presentation
from swparse.config.app import settings
from pptx.shapes.base import BaseShape
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.shapes.shapetree import SlideShapes
import json
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
from itertools import islice
from lark import Lark, Token, Transformer
import pandas as pd

import html_text
import mistletoe
from gliner import GLiNER
from nltk import tokenize, download
from xls2xlsx import XLS2XLSX

from swparse.config.app import settings
from swparse.db.models.content_type import ContentType
from swparse.domain.swparse.schemas import JobMetadata

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
            (shape.is_placeholder and shape.placeholder_format.type == PP_PLACEHOLDER.BODY)
            or (shape.is_placeholder and shape.placeholder_format.type == PP_PLACEHOLDER.OBJECT)
            or shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX
        ):
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
        nested_list._items.append(text)  # type: ignore
    else:
        if not nested_list._items or not isinstance(nested_list._items[-1], list):  # type: ignore
            nested_list._items.append(MDList([]))  # type: ignore
        add_to_list(nested_list._items[-1], level - 1, text)  # type: ignore


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
                if ph.type == PP_PLACEHOLDER.OBJECT and hasattr(shape, "image") and getattr(shape, "image"):
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


class TreeToJson(Transformer):
    def __init__(self, visit_tokens: bool = True):
        super().__init__(visit_tokens)
        self.tables = set()

    def start(self, items: list[Token]):
        return {"tables": items[0:-1], "output": items[-1].lower()}

    def instruction(self, items: list[Token]):
        headers = [label["name"] for label in items[1:-1]]
        if len(headers) != len(dict.fromkeys(headers)):
            raise ValueError("Duplicate labels")
        return {"mode": items[-1], "table_name": items[0], "labels": items[1:-1]}

    def mode(self, items: list[Token]):
        mode_map = {
            "by_sentence": "sent",
            "sent": "sent",
            "bysentence": "sent",
            "by_line": "ln",
            "ln": "ln",
            "byline": "ln",
        }
        if not len(items):
            return "sent"
        return mode_map[items[0].value.replace(" ", "_").lower()]

    def output(self, items: list[Token]):
        if not len(items):
            return "json"
        return items[0].value.lower()

    def table_ident(self, items: list[Token]):
        table_name = items[0].value.replace(" ", "_").lower()
        if table_name in self.tables:
            raise Exception(f"Duplicate table name: {table_name}")
        self.tables.add(table_name)
        return table_name

    def value(self, items: list[Token]):
        name = items[0].replace(" ", "_").lower()
        if len(items) == 1:
            return {"name": name, "type": "string"}
        return {"name": name, "type": items[1]}

    def field(self, items: list[Token]):
        return items[0].value

    def type(self, items: list[Token]):
        return items[0].value


def syntax_parser(extraction_query: str) -> list[dict]:
    lang = """start: instruction+ output
        instruction: table_ident value+ mode ";"
        table_ident: FIELD_NAME "="
        value: field type?
        field: FIELD_NAME ","?
        mode: ("-"MODE)?
        output: (("as "|"AS ")OUTPUT)?
        OUTPUT: /csv|md|json/i
        MODE: /by( |_)?sentence|by( |_)?line|ln|sent|sentence|line/i
        FIELD_NAME: /[a-zA-Z0-9_]+((_| )[a-zA-Z0-9_]+)*/
        type: ":" DATATYPES ","?
        DATATYPES: DATATYPE"[]"?
        DATATYPE: "str" | "string" | "text" | "int" | "integer" | "number" | "float" | "date" | "bool" | "boolean"
        %import common.WS
        %ignore WS
        """
    lang_parser = Lark(lang)
    tree = lang_parser.parse(extraction_query)
    return TreeToJson().transform(tree)


def extract_labels(table_queries: list[dict], markdownText: str, output: str):
    download("punkt_tab")
    model = GLiNER.from_pretrained("gliner-community/gliner_large-v2.5")

    text = html_text.extract_text(mistletoe.markdown(markdownText))
    sent_tokens = tokenize.sent_tokenize(text)
    ln_tokens = tokenize.line_tokenize(text)

    results = []

    for query in table_queries:
        list_labels = []
        int_labels = []
        float_labels = []
        labels = []
        for label in query["labels"]:
            if label["type"][-2:] == "[]":
                list_labels.append(label["name"])
                label["type"] = label["type"][:-2]
            if label["type"] in ["int", "integer", "number"]:
                int_labels.append(label["name"])
            elif label["type"] in ["float"]:
                float_labels.append(label["name"])
            labels.append(label["name"])

        table = {
            "table_name": query["table_name"],
            "headers": labels,
            "rows": [],
        }

        tokens = sent_tokens if query["mode"] == "sent" else ln_tokens

        for token in tokens:
            entities = model.predict_entities(token, labels, threshold=0.5)
            row = {}
            for list_label in list_labels:
                row[list_label] = []

            extracted_labels = list(dict.fromkeys([entity["label"] for entity in entities]))

            if len(extracted_labels) < math.floor(len(labels) * 0.8):
                continue

            for entity in entities:
                if entity["label"] in int_labels or entity["label"] in float_labels:
                    match = re.search(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", entity["text"])
                    if entity["label"] in int_labels:
                        entity["text"] = int(match.group()) if match else None
                    else:
                        entity["text"] = float(match.group().replace(",", "")) if match else None

                if entity["text"]:
                    if entity["label"] in list_labels:
                        row[entity["label"]].append(entity["text"])
                    else:
                        row[entity["label"]] = entity["text"]

            table["rows"].append(row)

        results.append(table)

    if output == "json":
        return results
    else:
        data_frames = []
        table_names = []
        max_header = 0
        for table in results:
            rows = []
            for row in table["rows"]:
                processed_row = {
                    col: ", ".join(value) if isinstance(value, list) else value for col, value in row.items()
                }
                rows.append(processed_row)

            if max_header < len(table["headers"]):
                max_header = len(table["headers"])
            df = pd.DataFrame(rows, columns=table["headers"])

            data_frames.append(df)
            table_names.append(table["table_name"])

        csv_result = ""
        md_result = ""

        for i, df in enumerate(data_frames):
            if output == "csv":
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_string = csv_buffer.getvalue()

                if i != 0:
                    csv_result += f"\n============={',' * (max_header - 1)}\n\n"

                csv_result += f"{table_names[i]}{',' * (max_header - 1)}\n"
                csv_result += csv_string
            elif output == "md":
                md_result += f"# {table_names[i]}\n"
                md_result += df.to_markdown() + "\n"

        return csv_result if output == "csv" else md_result


def get_hashed_file_name(filename: str, content: bytes) -> str:
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


def get_file_content(s3: S3FileSystem, file_path: str) -> str:
    with s3.open(file_path, mode="r") as f:
        content = f.read()
        if isinstance(content, bytes):
            content = content.decode()
    return content


def handle_result_type(
    result_type: str, results: dict[str, str], s3: S3FileSystem, jm: JobMetadata, job_key: str
) -> dict:
    try:
        result = {"job_metadata": jm.__dict__}
        if result_type == ContentType.MARKDOWN.value:
            markdown = get_file_content(s3, results["markdown"])
            result["markdown"] = markdown

        elif result_type == ContentType.HTML.value:
            html = get_file_content(s3, results["html"])
            result["html"] = html

        elif result_type == ContentType.TEXT.value:
            text = get_file_content(s3, results["text"])
            result["text"] = text

        elif result_type == ContentType.TABLE.value:
            html = extract_tables_from_html(s3, results["html"])
            result_html = "<br><br>"
            if html:
                result_html = result_html.join(html)
            result["table"] = result_html

        elif result_type == ContentType.MARKDOWN_TABLE.value:
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

            result["table_md"] = markdown_tbls

        elif result_type == ContentType.IMAGES.value:
            images = results.get("images")

            result["images"] = images
        else:
            try:
                table_queries = syntax_parser(result_type)
            except:
                raise HTTPException(detail="Invalid query syntax", status_code=400)
            with s3.open(results["markdown"], mode="r") as out_file_md:
                markdown = out_file_md.read()
                result[result_type] = (extract_labels(table_queries["tables"], markdown, table_queries["output"]),)

        if len(result) > 1:
            return result

        raise HTTPException(f"Format {result_type} is currently unsupported for {job_key}")

    except Exception as e:
        raise HTTPException(f"Format {result_type} is currently unsupported for {job_key}")
