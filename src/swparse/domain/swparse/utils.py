import hashlib
import io
import json
import math
import os
import re
from datetime import UTC, datetime
from itertools import islice
from logging import getLogger
from operator import attrgetter
from typing import IO, Any, TYPE_CHECKING, List
from uuid import uuid4

import html_text
import mistletoe
import pandas as pd
from gliner import GLiNER
from lark import Lark, Token, Transformer
from litestar.exceptions import HTTPException
from lxml import html
from markdown_it import MarkdownIt
from mdit_plain.renderer import RendererPlain
from nltk import download, tokenize
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
from swparse.domain.swparse.schemas import JobMetadata

if TYPE_CHECKING:
    from PIL.Image import Image

logger = getLogger(__name__)
BUCKET = settings.storage.BUCKET
JOB_FOLDER = settings.storage.JOB_FOLDER

 
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

def save_img_s3(s3fs: S3FileSystem, image_name:str, image:"Image") -> str:
    image_name = image_name.lower()
    buffered = io.BytesIO()
    image.save(buffered, format=image_name.split(".")[-1])
    img_b = buffered.getvalue()
    return save_file_s3(s3fs, image_name, img_b)


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


def parse_table_query(extraction_query: str) -> list[dict]:
    lang = """start: instruction+ output
        instruction: table_ident value+ mode ";"
        table_ident: FIELD_NAME "="
        value: field type?
        field: FIELD_NAME ","?
        mode: ("-"MODE)?
        output: (("as "|"AS ")OUTPUT)?
        OUTPUT: /csv|md|json|html/i
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


def extract_tables_gliner(table_queries: list[dict], markdownText: str, output: str | None = None) -> Any:
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

            if len(extracted_labels) < (math.floor(len(labels) * 0.8) if len(labels) > 1 else 1):
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

    data_frames = []
    table_names = []
    max_header = 0
    for table in results:
        rows = []
        for row in table["rows"]:
            processed_row = {col: ", ".join(value) if isinstance(value, list) else value for col, value in row.items()}
            rows.append(processed_row)

        if max_header < len(table["headers"]):
            max_header = len(table["headers"])
        df = pd.DataFrame(rows, columns=table["headers"])

        data_frames.append(df.fillna(""))
        table_names.append(table["table_name"])

    json_result = json.dumps(results)
    csv_result = ""
    md_result = ""

    for i, df in enumerate(data_frames):
        # MARKDOWN
        md_result += f"# {table_names[i]}\n"
        md_result += df.to_markdown(index=False) + "\n"

        # CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_string = csv_buffer.getvalue()

        if i != 0:
            csv_result += f"\n============={',' * (max_header - 1)}\n\n"

        csv_result += f"{table_names[i]}{',' * (max_header - 1)}\n"
        csv_result += csv_string

    # HTML
    html_result = mistletoe.markdown(md_result)

    if output == "json":
        return json_result
    elif output == "csv":
        return csv_result
    elif output == "md":
        return md_result
    elif output == "html":
        return html_result

    if output is None:
        return {
            "csv": csv_result,
            "md": md_result,
            "html": html_result,
            "json": json_result,
        }


def get_hashed_file_name(filename: str, content: bytes) -> str:
    file_ext = filename.split(".")[-1]
    check_sum = hashlib.md5(content).hexdigest()
    return f"{check_sum}.{file_ext}"


def get_job_metadata(s3fs: S3FileSystem, job_id: str) -> dict[str, dict[str, str]]:
    job_file_path = f"{BUCKET}/{JOB_FOLDER}/{job_id}.json"
    content = {}
    if s3fs.exists(job_file_path):
        with s3fs.open(job_file_path, mode="r") as f:
            content = json.loads(f.read())
    return content


def save_job_metadata(s3fs: S3FileSystem, job_id: str, metadata: dict[str, str]) -> dict[str, dict[str, str]]:
    job_file_path = f"{BUCKET}/{JOB_FOLDER}/{job_id}.json"
    job_folder_path = f"{BUCKET}/{JOB_FOLDER}/"

    existing_job_metadata: dict[str, dict] = {"metadata": {}}
    if not s3fs.exists(job_folder_path):
        s3fs.mkdir(job_folder_path)

    if not s3fs.exists(job_file_path):
        existing_job_metadata["metadata"].update({"created_at": datetime.now(UTC).isoformat()})
    else:
        existing_job_metadata = get_job_metadata(s3fs, job_id)

    existing_job_metadata["metadata"].update(metadata)

    try:
        with s3fs.open(job_file_path, mode="w") as f:
            f.write(json.dumps(existing_job_metadata, indent=4))
        return existing_job_metadata
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Save job metadata error: {err}")


def get_file_content(s3fs: S3FileSystem, file_path: str) -> str:
    with s3fs.open(file_path, mode="r") as f:
        content = f.read()
        if isinstance(content, bytes):
            content = content.decode()
    return content


def handle_result_type(
    result_type: str, results: dict[str, str], s3fs: S3FileSystem, jm: JobMetadata, job_key: str
) -> dict:
    if results.get("result_type"):
        result_type_check = results["result_type"]
    else:
        result_type_check = result_type
    try:
        result = {"job_metadata": jm.__dict__}
        if result_type_check == ContentType.MARKDOWN.value:
            markdown = get_file_content(s3fs, results["markdown"])
            result[result_type] = markdown

        elif result_type_check == ContentType.HTML.value:
            html = get_file_content(s3fs, results["html"])
            result[result_type] = html

        elif result_type_check == ContentType.TEXT.value:
            text = get_file_content(s3fs, results["text"])
            result[result_type] = text

        elif result_type_check == ContentType.TABLE.value:
            html = extract_tables_from_html(s3fs, results["html"])
            result_html = "<br><br>"
            if html:
                result_html = result_html.join(html)
            result[result_type] = result_html

        elif result_type_check == ContentType.JSON.value:
            json_str = get_file_content(s3fs, results["json"])
            json_pages = json.loads(json_str)
            logger.info("Pages")
            logger.info(json_pages)
            result = {
                'pages':json_pages,
                'job_metadata': jm.__dict__, 
            }

        elif result_type_check == ContentType.MARKDOWN_TABLE.value:
            table_file_path = results.get("table")
            if table_file_path:
                with s3fs.open(results["table"], mode="r") as out_file_html:
                    result_html = out_file_html.read()
            else:
                html = extract_tables_from_html(s3fs, results["html"])
                result_html = "<br><br>".join(html)

            dfs = pd.read_html(result_html)
            markdown_tbls = ""
            for i, df in enumerate(dfs):
                markdown_tbls += f"## Table {i + 1}\n\n"
                markdown_tbls += df.to_markdown()
                markdown_tbls += "\n\n"

            result[result_type] = markdown_tbls

        elif result_type_check == ContentType.IMAGES.value:
            with s3fs.open(results["images"], mode="r") as f:
                json_image_meta = f.read()

            result[result_type] = json.loads(json_image_meta)
        else:
            with s3fs.open(results[result_type_check], mode="r") as tables_file:
                tables_content = tables_file.read()
                result[result_type] = tables_content

        if result:
            return result

        raise HTTPException(f"Format {result_type_check} is currently unsupported for {job_key}")

    except Exception as e:
        raise HTTPException(f"Format {result_type_check} is currently unsupported for {job_key}")


def md_to_text(md: str) -> str:
    parser = MarkdownIt(renderer_cls=RendererPlain)
    return parser.render(md)

class MdAnalyser:
    def __init__(self, markdown_content: str):
        self.markdown_content = markdown_content
        self.components = []
        self.lines = markdown_content.splitlines()
        
        # Compile patterns once for efficiency
        self.patterns = {
            "heading": re.compile(r"^(#{1,6})\s*(.+)$"),
            "table_row": re.compile(r"^\|.*\|$"),
            "paragraph": re.compile(r"^(?!\!\[.*\]\(.*\))[^\|#\s].+$"),
            "table_separator": re.compile(r"^\|[-|]*\|$"),
        }

    def extract_components(self) -> List[dict]:
        """Extracts components from the markdown content."""
        current_table = []
        
        for line in self.lines:
            if not line.strip():
                continue  # Skip empty lines
            
            # Process different patterns
            if self.patterns["heading"].match(line):
                self._flush_table(current_table)
                self.add_heading(line)
            elif self.patterns["table_row"].match(line):
                if not self.patterns["table_separator"].match(line):
                    current_table.append(line)
            elif self.patterns["paragraph"].match(line):
                self._flush_table(current_table)
                self.add_paragraph(line)

        # Add any remaining table
        self._flush_table(current_table)

        return self.components

    def _flush_table(self, current_table: List[str]):
        """Adds the current table to components if not empty."""
        if current_table:
            self.add_table(current_table)
            current_table.clear()

    def add_table(self, current_table: List[str]):
        """Processes and adds a table component."""
        rows = [
            [cell.strip() for cell in re.findall(r"\|([^|]+)", row)]
            for row in current_table
        ]
        self.components.append({
            "type": "table",
            "md": "\n".join(current_table),
            "rows": rows,
            "bBox": self._get_bbox(),
        })

    def add_heading(self, line: str):
        """Processes and adds a heading component."""
        match = self.patterns["heading"].match(line)
        level = len(match.group(1))
        text = match.group(2).strip()
        self.components.append({
            "type": "heading",
            "level": level,
            "md": line,
            "value": text,
            "bBox": self._get_bbox()
        })
 
    def add_paragraph(self, line: str):
        """Processes and adds a paragraph component."""
        self.components.append({
            "type": "paragraph",
            "md": line,
            "value": self.md_to_text(line),
            "bBox": self._get_bbox()
        })

    @staticmethod
    def md_to_text(md: str) -> str:
        """Converts Markdown to plain text (basic implementation)."""
        return re.sub(r"(\*\*|__|`|~~)", "", md).strip()

    @staticmethod
    def _get_bbox() -> dict:
        """Returns a default bounding box structure."""
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}



def extract_md_components(markdown_content: str)->list[dict[str, Any]]:
    analyser = MdAnalyser(markdown_content)
    return analyser.extract_components()


def format_timestamp(timestamp:float) ->str:
    value = datetime.fromtimestamp(timestamp)
    return value.strftime('%S:') + f"{int(value.strftime('%f')) // 1000}"
 