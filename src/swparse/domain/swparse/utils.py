import io
import os
from uuid import uuid4

from lxml import html
from s3fs import S3FileSystem
from xls2xlsx import XLS2XLSX

# from pptx2md import outputter, parser
# from pptx import Presentation
from swparse.config.app import settings
import re

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


# class CustomizedMdOutputter(outputter.md_outputter):
#     def __init__(self, s3_url: str):
#         self.ofile = s3.open(s3_url, "w")
#         self.esc_re1 = re.compile(r'([\\\*`!_\{\}\[\]\(\)#\+-\.])')
#         self.esc_re2 = re.compile(r'(<[^>]+>)')


def convert_pptx_to_md(input_url: str, output_url: str):
    ...
    # try:
    #     with s3.open(input_url, "rb") as f:
    #         pptx_content = Presentation(f)
    #     output_obj = CustomizedMdOutputter(output_url)
    #     parser.parse(pptx_content, output_obj)
    # except Exception as e:
    #     raise Exception(f"Error converting PPTX to Markdown: {e}")
