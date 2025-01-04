from __future__ import annotations
import os
from typing import Any, Optional, Literal
import httpx

from advanced_alchemy.service import (
    SQLAlchemyAsyncRepositoryService,
)
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar_saq import Queue
from litestar.datastructures import UploadFile

from swparse.db.models import Extraction
from swparse.domain.swparse.schemas import JobStatus
from swparse.config.app import settings

from .repositories import ExtractionRepository

SWPARSE_URL = f"{os.environ.get('APP_URL')}"
SWPARSE_API_KEY = os.environ.get("PARSER_API_KEY")

queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")


class ExtractionService(SQLAlchemyAsyncRepositoryService[Extraction]):
    """Handles database operations for extractions."""

    repository_type = ExtractionRepository

    def __init__(self, **repo_kwargs: Any) -> None:
        self.repository: ExtractionRepository = self.repository_type(**repo_kwargs)
        self.model_type = self.repository.model_type

    async def create_job(self, data: UploadFile, sheet_index: Optional[list[str|int]] = None, force_ocr:bool = False) -> JobStatus:
        form_data = {}
        if force_ocr:
            form_data = {
                "force_ocr": force_ocr
            }
        if sheet_index and len(sheet_index) > 0 :            
            form_data = {
                "sheet_index": sheet_index
            }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{SWPARSE_URL}/api/parsing/upload",
                    files={"file": (data.filename, data.file, data.content_type), },
                    data = form_data,
                    headers={
                        "Content-Type": "multipart/form-data; boundary=0xc0d3kywt;",
                        "Authorization": f"Bearer {SWPARSE_API_KEY}",
                    },
                )
                response.raise_for_status()
            except NotAuthorizedException as err:
                raise NotAuthorizedException(detail=err.detail, status_code=403)
            except Exception as err:
                raise HTTPException(detail="Document upload failed", status_code=500)

        return JobStatus(**(response.json()))

    async def get_extracted_file_paths(self, job_id: str) -> dict[str, str]:
        job_key = queue.job_key_from_id(job_id=job_id)
        job = await queue.job(job_key=job_key)
        if not job:
            raise HTTPException(detail=f"Job {job_id} is not found", status_code=404)
        return job.result
