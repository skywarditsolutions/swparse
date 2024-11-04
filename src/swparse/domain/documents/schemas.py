from uuid import UUID
from swparse.lib.schema import BaseStruct

__all__ = ("Document",)


class Document(BaseStruct):
    id: UUID
    file_name: str
    file_size: int
    job_id: str
    file_path: str
    extracted_file_paths: dict[str, str] | None = None
