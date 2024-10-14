from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, TypeVar

import httpx
import structlog
from advanced_alchemy.extensions.litestar import SQLAlchemyDTO
from litestar import Controller, get, post
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.dto import DTOConfig
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.pagination import OffsetPagination
from litestar.params import Body
from litestar.repository.filters import LimitOffset
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.db.models.document import Document
from swparse.db.models.user import User
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.services import DocumentService
from swparse.domain.swparse.schemas import JobStatus
from swparse.lib.dependencies import provide_limit_offset_pagination

from . import urls

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter


logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
BUCKET = settings.storage.BUCKET

config = DTOConfig(
    exclude={
        "id",
    },
)
WriteDTO = SQLAlchemyDTO[Document]
ReadDTO = SQLAlchemyDTO[Annotated[Document, config]]


def _raise_http_exception(detail: str, status_code: int) -> None:
    raise HTTPException(detail=detail, status_code=status_code)


class DocumentController(Controller):
    tags = ["Documents"]
    dependencies = {
        "doc_service": Provide(provide_document_service),
        "limit_offset": Provide(provide_limit_offset_pagination),
    }
    signature_namespace = {"DocumentService": DocumentService}
    dto = ReadDTO
    return_dto = WriteDTO

    @get(
        operation_id="ListDocuments",
        name="documents:list",
        summary="List Documents",
        description="Retrieve the document of the user_id.",
        path=urls.DOCUMENT_LIST,
    )
    async def list_documents(
        self,
        doc_service: DocumentService,
        limit_offset: LimitOffset,
    ) -> OffsetPagination[Document]:
        """List documents."""
        docs, total = await doc_service.list_and_count(limit_offset)
        return OffsetPagination[Document](
            items=docs,
            total=total,
            limit=limit_offset.limit,
            offset=limit_offset.offset,
        )

    @get(
        operation_id="GetDocument",
        name="documents:get",
        path=urls.DOCUMENT_DETAIL,
        summary="Retrieve the details of a document.",
    )
    async def get_document(
        self,
        doc_service: DocumentService,
        id: Annotated[
            UUID,
            Parameter(
                title="Document ID",
                description="The document to retrieve.",
            ),
        ],
    ) -> Document:
        """Get a Document."""
        db_obj = await doc_service.get(id)
        if not db_obj:
            _raise_http_exception(detail=f"Document {id} is not found", status_code=404)
        return db_obj

    @get(path=urls.LIST_DIR, guards=[requires_active_user])
    async def list_bucket_dirs(self) -> list[str]:
        s3 = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        return s3.ls(f"{BUCKET}")  # type: ignore

    @post(path=urls.DOCUMENT_UPLOAD, guards=[requires_active_user])
    async def upload_document(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        doc_service: DocumentService,
        current_user: User,
    ) -> Document:
        file = await data.read()
        url = "http://localhost:8000/api/parsing/upload"  # URL of the upload_and_parse_que endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                files={"data": file},
                headers={"Content-Type": "multipart/form-data; boundary=0xc0d3kywt"},
            )
        stats = JobStatus(**response.json())
        file_size = len(file)
        return await doc_service.create(
            Document(
                file_name=data.filename,
                file_size=file_size,
                file_path=stats.s3_url,
                user_id=current_user.id,
                job_id=stats.id,
            ),
        )
