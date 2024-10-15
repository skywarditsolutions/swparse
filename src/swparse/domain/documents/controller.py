from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, TypeVar
from uuid import uuid4

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
from litestar.repository.filters import CollectionFilter, LimitOffset
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.db.models import User
from swparse.db.models.document import Document
from swparse.db.models.file_types import FileTypes
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.services import DocumentService
from swparse.domain.swparse.schemas import JobStatus

# from swparse.lib.dependencies import provide_limit_offset_pagination
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
    }
    signature_namespace = {"DocumentService": DocumentService}

    @get(
        operation_id="ListDocuments",
        name="documents:list",
        summary="List Documents",
        description="Retrieve the document of the user_id.",
        path=urls.DOCUMENT_LIST,
    )
    async def list_documents(
        self, doc_service: DocumentService, limit_offset: LimitOffset, current_user: User
    ) -> OffsetPagination[Document]:
        """List documents."""
        user_id = current_user.id
        docs, total = await doc_service.list_and_count(
            CollectionFilter("user_id", values=[user_id]),
            order_by=[("updated_at", True)],
        )
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

    @post(path=urls.DOCUMENT_UPLOAD, guards=[requires_active_user], return_dto=WriteDTO)
    async def upload_document(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        doc_service: DocumentService,
        current_user: User,
    ) -> Document:
        content = await data.read()
        url = "http://localhost:8000/api/parsing/upload"  # URL of the upload_and_parse_que endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                files={"data": content},
                headers={"Content-Type": "multipart/form-data; boundary=0xc0d3kywt"},
            )
        stats = JobStatus(**response.json())
        file_size = len(content)
        return await doc_service.create(
            Document(
                file_name=data.filename,
                file_size=file_size,
                file_path=stats.s3_url,
                user_id=current_user.id,
                job_id=stats.id,
                file_type=FileTypes.MARKDOWN,
                extracted_file_path="",
            ),
        )

    # @post(path=urls.DOCUMENT_DETAIL, guards=[requires_active_user], return_dto=WriteDTO)
    # async def update_document(
    #     self,
    #     doc_service: DocumentService,
    #     current_user: User,
    #     id: Annotated[
    #         UUID,
    #         Parameter(
    #             title="Document ID",
    #             description="The document to retrieve.",
    #         ),
    #     ],
    # ) -> Document:
    #     user_id = current_user.id

    #     default_file_type = FileTypes.MARKDOWN.value

    #     new_uuid = uuid4()
    #     file_extension = {"markdown": "md", "csv": "csv", "text": "txt"}
    #     s3_url = f"{BUCKET}/{new_uuid}.{file_extension[default_file_type]}"
    #     # TODO
    #     # get document by id
    #     document = None
    #     new_extraction = {
    #         "extracted_file_url": s3_url,
    #         "user_id": user_id,
    #         "document_id": id,
    #         "file_type": default_file_type,
    #     }
    #     url = f"http://localhost:8000/api/job/{document.job_id}/result/{default_file_type}"
    #     try:
    #         async with httpx.AsyncClient() as client:
    #             response = await client.get(url)

    #             res: JobResult = response.json()

    #         s3 = S3FileSystem(
    #             # asynchronous=True,
    #             endpoint_url=settings.storage.ENDPOINT_URL,
    #             key=MINIO_ROOT_USER,
    #             secret=MINIO_ROOT_PASSWORD,
    #         )
    #         with s3.open(s3_url, "wb") as f:
    #             f.write(res.markdown)

    #     except Exception as e:
    #         logger.error(f"Error creating extraction: {e}")
    #         raise HTTPException(status_code=500, detail="Markdown retriever failed")

    #     if document is None:
    #         raise HTTPException(status_code=400, detail="Extraction creation failed")
    #     return document
