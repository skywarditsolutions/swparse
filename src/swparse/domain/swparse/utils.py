import io
import os
from uuid import uuid4

from xls2xlsx import XLS2XLSX
from s3fs import S3FileSystem

from swparse.config.app import settings
BUCKET = settings.storage.BUCKET

def convert_xls_to_xlsx_bytes(content: bytes) -> bytes:

    x2x = XLS2XLSX(io.BytesIO(content))
    workbook = x2x.to_xlsx()

    with io.BytesIO() as buffer:
        workbook.save(buffer)
        buffer.seek(0)
        return buffer.read()

def save_file_s3(s3fs: S3FileSystem, file_name:str, content:bytes|str ) -> str:
    new_uuid = uuid4()
    s3_url = f"{BUCKET}/{new_uuid}_{file_name}"
    if isinstance(content, str):
        content = content.encode(encoding="utf-8", errors="ignore")
    with s3fs.open(s3_url, mode="wb") as f:
        f.write(content)
        return s3_url

def get_file_name(s3_url:str) ->str:
    return os.path.basename(s3_url).split('/')[-1]
   
def change_file_ext(file_name:str, extension:str) ->str:
    file_path = file_name.split(".")
    file_path[-1]=extension
    
    return ".".join(file_path)