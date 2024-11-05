from __future__ import annotations

import httpx
import os
from typing import TYPE_CHECKING, Any
from swparse.config.app import settings

from advanced_alchemy.repository import Empty, EmptyType, ErrorMessages
from advanced_alchemy.service import (
    ModelDictT,
    SQLAlchemyAsyncRepositoryService,
)
from litestar_saq import Queue
from swparse.db.models import Document
from swparse.domain.swparse.schemas import JobStatus, Status

from .repositories import DocumentRepository

if TYPE_CHECKING:
    from collections.abc import Iterable

    from advanced_alchemy.repository import LoadSpec
    from sqlalchemy.orm import InstrumentedAttribute


queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD


class DocumentService(SQLAlchemyAsyncRepositoryService[Document]):
    """Handles database operations for users."""

    repository_type = DocumentRepository

    def __init__(self, **repo_kwargs: Any) -> None:
        self.repository: DocumentRepository = self.repository_type(**repo_kwargs)
        self.model_type = self.repository.model_type

    async def create(
        self,
        data: ModelDictT[Document],
        *,
        auto_commit: bool | None = None,
        auto_expunge: bool | None = None,
        auto_refresh: bool | None = None,
        error_messages: ErrorMessages | None | EmptyType = Empty,
    ) -> Document:
        """Create a new Document."""
        return await super().create(
            data=data,
            auto_commit=auto_commit,
            auto_expunge=auto_expunge,
            auto_refresh=auto_refresh,
            error_messages=error_messages,
        )

    async def update(
        self,
        data: ModelDictT[Document],
        item_id: Any | None = None,
        *,
        id_attribute: str | InstrumentedAttribute[Any] | None = None,
        attribute_names: Iterable[str] | None = None,
        with_for_update: bool | None = None,
        auto_commit: bool | None = None,
        auto_expunge: bool | None = None,
        auto_refresh: bool | None = None,
        error_messages: ErrorMessages | None | EmptyType = Empty,
        load: LoadSpec | None = None,
        execution_options: dict[str, Any] | None = None,
    ) -> Document:

        return await super().update(
            data=data,
            item_id=item_id,
            attribute_names=attribute_names,
            with_for_update=with_for_update,
            auto_commit=auto_commit,
            auto_expunge=auto_expunge,
            auto_refresh=auto_refresh,
            id_attribute=id_attribute,
            error_messages=error_messages,
            load=load,
            execution_options=execution_options,
        )

    async def to_model(self, data: ModelDictT[Document], operation: str | None = None) -> Document:
        return await super().to_model(data, operation)

    async def check_job_status(self, job_id: str) -> bool:
        url = f"{os.environ.get('APP_URL')}/api/parsing/job/{job_id}"
        api_key = os.environ.get("PARSER_API_KEY")
        api_key_header = os.environ.get("PARSER_API_HEADER")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Content-Type": "multipart/form-data; boundary=0xc0d3kywt;",
                    f"{api_key_header}": f"{api_key}",
                },
            )
        job_status = JobStatus(**(response.json()))
        return job_status.status == Status.complete
