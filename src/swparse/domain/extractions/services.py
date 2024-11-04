from __future__ import annotations
import os
from typing import Any

from advanced_alchemy.service import (
    SQLAlchemyAsyncRepositoryService,
)
import httpx
from litestar.datastructures import UploadFile
from swparse.db.models import Extraction
from swparse.domain.swparse.schemas import JobStatus
from litestar.exceptions import HTTPException, NotAuthorizedException

from .repositories import ExtractionRepository

SWPARSE_URL = f"{os.environ.get('APP_URL')}"
SWPARSE_API_KEY = os.environ.get("PARSER_API_KEY")
SWPARSE_API_HEADER = os.environ.get("PARSER_API_HEADER")


class ExtractionService(SQLAlchemyAsyncRepositoryService[Extraction]):
    """Handles database operations for extractions."""

    repository_type = ExtractionRepository

    def __init__(self, **repo_kwargs: Any) -> None:
        self.repository: ExtractionRepository = self.repository_type(**repo_kwargs)
        self.model_type = self.repository.model_type

    async def create_job(self, data: UploadFile) -> JobStatus:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{SWPARSE_URL}/api/parsing/upload",
                    files={"data": (data.filename, data.file, data.content_type)},
                    headers={
                        "Content-Type": "multipart/form-data; boundary=0xc0d3kywt;",
                        f"{SWPARSE_API_HEADER}": f"{SWPARSE_API_KEY}",
                    },
                )
            except NotAuthorizedException as err:
                raise NotAuthorizedException(detail=err.detail, status_code=403)
            except Exception as err:
                raise HTTPException(detail="Document upload failed", status_code=500)

        return JobStatus(**(response.json()))
