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
from logging import getLogger
from operator import attrgetter
from snakemd import Document as SnakeMdDocument
from snakemd.elements import MDList
from itertools import islice
from lark import Lark, Transformer

import html_text
import mistletoe
from gliner import GLiNER
from nltk import tokenize, download

logger = getLogger(__name__)
BUCKET = settings.storage.BUCKET
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD

s3 = S3FileSystem(
    # asynchronous=True,
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
        self.fields = set()
        self.tables = set()

    def start(self, items: dict):
        return items

    def instruction(self, items: dict[str, str]):
        return {"mode": items[-1], "table_name": items[0], "labels": items[1:-1]}

    def mode(self, items: dict):
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

    def table_ident(self, items: dict):
        table_name = items[0].value
        if table_name in self.tables:
            raise Exception(f"Duplicate table name: {table_name}")
        self.tables.add(table_name)
        return items[0].value

    def value(self, items: dict[str, str]):
        name = items[0].replace(" ", "_").lower()
        if len(items) == 1:
            return {"name": name, "type": "string"}
        return {"name": name, "type": items[1]}

    def field(self, items: dict):
        field_name = items[0].value
        if field_name in self.fields:
            raise Exception(f"Duplicate field name: {field_name}")
        self.fields.add(field_name)
        return items[0].value

    def type(self, items: dict[str, str]):
        return items[0].value


def syntax_parser(extraction_query: str) -> list[dict]:
    lang = """start: instruction+
        instruction: table_ident value+ mode ";"?
        table_ident: FIELD_NAME "="
        value: field type?
        field: FIELD_NAME ","?
        mode: ("-"MODE)?
        MODE: /by( |_)?sentence|by( |_)?line|ln|sent/i
        FIELD_NAME: /[a-zA-Z0-9_]+((_| )[a-zA-Z0-9_]+)*/
        type: ":" DATATYPES ","?
        DATATYPES: DATATYPE"[]"?
        DATATYPE: "str" | "string" | "text" | "int" | "integer" | "number" | "float" | "date" | "bool"
        %import common.WS
        %ignore WS
        """
    lang_parser = Lark(lang)
    tree = lang_parser.parse(extraction_query)
    return TreeToJson().transform(tree)


def extract_labels(table_queries: list[dict], markdownText: str) -> list[dict]:
    download("punkt_tab")
    model = GLiNER.from_pretrained("gliner-community/gliner_large-v2.5")

    text = html_text.extract_text(mistletoe.markdown(markdownText))
    sent_tokens = tokenize.sent_tokenize(text)
    ln_tokens = tokenize.line_tokenize(text)

    print(ln_tokens)

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

    return results
