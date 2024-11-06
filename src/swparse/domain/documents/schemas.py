from uuid import UUID
from datetime import datetime

from swparse.lib.schema import CamelizedBaseStruct

__all__ = ("Document",)


class Document(CamelizedBaseStruct):
    id: UUID
    file_name: str
    file_size: int
    job_id: str
    file_path: str
    extracted_file_paths: dict[str, str]
    created_at: datetime
    updated_at: datetime
