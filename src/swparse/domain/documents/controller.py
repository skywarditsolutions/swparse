from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, TypeVar

import structlog
import httpx
import nest_asyncio
from litestar import Controller, get, post
from litestar.di import Provide
from litestar.exceptions import HTTPException
from litestar.datastructures import UploadFile
from litestar.params import Body
from litestar.enums import RequestEncodingType
from litestar.datastructures import UploadFile
from litestar.connection import request

from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.schemas import Document
from swparse.domain.documents.services import DocumentService
from swparse.domain.accounts.guards import requires_active_user, current_user_from_token
from swparse.domain.swparse.schemas import JobStatus, JobResult
from s3fs import S3FileSystem
from swparse.config.app import settings
from swparse.domain.swparse.controllers import ParserController
from llama_parse import LlamaParse
from swparse.db.models.user import User

from . import urls

if TYPE_CHECKING:
    from uuid import UUID
    from litestar.connection import Request
    from swparse.domain.swparse.controllers import ParserController
    from advanced_alchemy.filters import FilterTypes
    from advanced_alchemy.service import OffsetPagination
    from litestar.params import Dependency, Parameter

nest_asyncio.apply()
logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
BUCKET = settings.storage.BUCKET


def _raise_http_exception(detail: str, status_code: int) -> None:
    raise HTTPException(detail=detail, status_code=status_code)


class DocumentController(Controller):
    tags = ["Documents"]
    dependencies = {"doc_service": Provide(provide_document_service)}
    signature_namespace = {"DocumentService": DocumentService}
    dto = None
    return_dto = None

    @get(
        operation_id="ListDocuments",
        name="documents:list",
        summary="List Documents",
        description="Retrieve the document of the user_id.",
        path=urls.DOCUMENT_LIST,
    )
    async def list_documents(
        self, doc_service: DocumentService, filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)]
    ) -> OffsetPagination[Document]:
        """List documents."""
        results, total = await doc_service.list_and_count(*filters)
        return doc_service.to_schema(data=results, total=total, schema_type=Document, filters=filters)

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
        if db_obj is None:
            _raise_http_exception(detail=f"Document {id} is not found", status_code=404)
        return doc_service.to_schema(db_obj, schema_type=Document)

    @get(path=urls.LIST_DIR, guards=[requires_active_user])
    async def list_bucket_dirs(self) -> list[str]:
        s3 = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        return s3.ls(f"{BUCKET}")

    @post(path=urls.DOCUMENT_UPLOAD, guards=[requires_active_user])
    async def upload_document(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        doc_service: DocumentService,
        current_user: User,
    ) -> None:
        try:
            pass
            # file = await data.read()
            # url = "http://localhost:8000/api/parsing/upload"  # URL of the upload_and_parse_que endpoint
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         url,
            #         files={"data": file},
            #         headers={"Content-Type": "multipart/form-data; boundary=0xc0d3kywt"},
            #     )
            # job_status = response.json()
            # file_size = len(file)
            # document_obj = await documents_service.create(Document(
            #     file_name=data.filename,
            #     file_size=len(file),
            #     file_path=f"{BUCKET}/"
            # ))
            # logger.error(f"{file_size}")
            # logger.error(current_user.id)
        except Exception as e:
            logger.error("error")
            logger.error(e)


