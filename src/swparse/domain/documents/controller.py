from __future__ import annotations

import base64
import mimetypes
import tempfile
from typing import TYPE_CHECKING, Annotated, Literal, TypeVar
import os
import httpx
import structlog
from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar import Controller, get, post
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import MediaType, RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.pagination import OffsetPagination
from litestar.params import Body
from litestar.repository.filters import CollectionFilter, LimitOffset
from litestar.response import File
from s3fs import S3FileSystem

from typing import Optional
from swparse.config.app import settings
from swparse.db.models import User
from swparse.db.models.document import Document
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.services import DocumentService
from swparse.domain.swparse.schemas import JobStatus
import json
from . import urls

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter


logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
BUCKET = settings.storage.BUCKET

config = SQLAlchemyDTOConfig(
    exclude={"id", "created_at", "updated_at"},
)
WriteDTO = SQLAlchemyDTO[Annotated[Document, config]]
ReadDTO = SQLAlchemyDTO[
    Annotated[
        Document,
        SQLAlchemyDTOConfig(
            exclude={"user_id"},
        ),
    ]
]


def _raise_http_exception(detail: str, status_code: int) -> None:
    raise HTTPException(detail=detail, status_code=status_code)


class DocumentController(Controller):
    tags = ["Documents"]
    dependencies = {
        "doc_service": Provide(provide_document_service),
    }
    signature_namespace = {"DocumentService": DocumentService}
    return_dto = ReadDTO

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
        current_user: User,
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
        logger.error("db_obj.extracted_file_paths")
        logger.error(db_obj.extracted_file_paths)
        logger.error(type(db_obj.extracted_file_paths))
        
        if db_obj.extracted_file_paths is None:
            try:
                if await doc_service.check_job_status(db_obj.job_id):
                    extracted_file_paths = await doc_service.get_extracted_file_paths(db_obj.job_id)
                    await doc_service.update(item_id=db_obj.id, data={"extracted_file_paths": extracted_file_paths})
                    db_obj = await doc_service.get(id)
            except Exception as e:
                logger.error(f"Failed to retrieve the extracted file {e}")
                _raise_http_exception(detail=f"Failed to retrieve the extracted file {e}", status_code=404)
        extracted_file_paths =  db_obj.extracted_file_paths
        extracted_file_paths = base64.b64decode(extracted_file_paths).decode('utf-8')
        db_obj.extracted_file_paths = json.loads(extracted_file_paths)

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

    @post(path=urls.DOCUMENT_UPLOAD, guards=[requires_active_user], return_dto=ReadDTO)
    async def upload_document(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        doc_service: DocumentService,
        current_user: User,
    ) -> Document:
        content = await data.read()
        url = f"{os.environ.get('APP_URL')}/api/parsing/upload"  # URL of the upload_and_parse_que endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                files={"data": (data.filename, data.file, data.content_type)},
                headers={"Content-Type": "multipart/form-data; boundary=0xc0d3kywt"},
            )
        stats = JobStatus(**(response.json()))
        file_size = len(content)
        return await doc_service.create(
            Document(
                file_name=data.filename,
                file_size=file_size,
                file_path=stats.s3_url,
                user_id=current_user.id,
                job_id=stats.id,
                # extracted_file_paths=None,
            ),
        )

    @get(path=urls.DOCUMENT_CONTENT, guards=[requires_active_user], return_dto=WriteDTO)
    async def get_document_content(
        self,
        doc_service: DocumentService,
        id: Annotated[
            UUID,
            Parameter(
                title="Document ID",
                description="The document to retrieve.",
            ),
        ],
    ) -> File | str:
        db_obj = await doc_service.get(id)
        if not db_obj:
            _raise_http_exception(detail=f"Document {id} is not found", status_code=404)
        s3 = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        s3_url = db_obj.file_path
        try:
            with s3.open(s3_url, "rb") as f:
                content: bytes = f.read()
            mime_type, _ = mimetypes.guess_type(s3_url)
            extension = s3_url.split(".")[-1]

            if mime_type and mime_type.startswith(MediaType.TEXT.value):
                logger.error("plain")
                return content.decode("utf-8", "ignore")

            if mime_type and mime_type.startswith("image/"):
                logger.error("image")
                return base64.b64encode(content).decode("utf-8")

            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                return File(
                    content_disposition_type="attachment",
                    path=tmp_file.name,
                    filename=db_obj.file_name,
                    media_type=mime_type,
                )

        except Exception as e:
            _raise_http_exception(f"Failed to read document: {e!s}", status_code=500)
            return ""

    @get(path=urls.EXTRACTED_CONTENT, guards=[requires_active_user], return_dto=WriteDTO)
    async def get_extracted_content(
        self,
        doc_service: DocumentService,
        id: Annotated[
            UUID, 
            Parameter(
                title="Document ID",
                description="The document to retrieve.",
            ),
        ],
        result_type:Optional[str]="markdown",
    ) -> str:
        db_obj = await doc_service.get(id)
        if not db_obj:
            _raise_http_exception(detail=f"Document {id} is not found", status_code=404)
 
        
        if db_obj.extracted_file_paths is None and not await doc_service.check_job_status(db_obj.job_id):
            _raise_http_exception("Uploaded document is not extracted yet.", status_code=400)

        if db_obj.extracted_file_paths is None and await doc_service.check_job_status(db_obj.job_id):
            extracted_file_paths = await doc_service.get_extracted_file_paths(db_obj.job_id)
            await doc_service.update(item_id=db_obj.id, data={"extracted_file_paths": extracted_file_paths})
            db_obj = await doc_service.get(id)
 
        extracted_file_paths =  db_obj.extracted_file_paths
        extracted_file_paths = json.loads( base64.b64decode(extracted_file_paths).decode('utf-8'))
        
        if result_type not in extracted_file_paths:
            _raise_http_exception("Extracted file does not exit.", status_code=400)
        extracted_file_path = extracted_file_paths[result_type]
        s3 = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        with s3.open(extracted_file_path, "rb") as f:
            content: bytes = f.read()
  
        return content.decode(encoding="utf-8", errors="ignore")
    

    @get(path=urls.EXTRACTED_CONTENT_PRESIGNED_URL, guards=[requires_active_user])
    async def get_extracted_file_presigned_url(self, doc_service: DocumentService, doc_id: Annotated[UUID, Parameter(title="Document ID", description="The document to retrieve.")], result_type: str = "markdown") -> str | None:
        doc_obj = await doc_service.get(doc_id)
        if not doc_obj:
            _raise_http_exception(detail=f"Document {id} is not found", status_code=404)

        if doc_obj.extracted_file_paths is None and not await doc_service.check_job_status(doc_obj.job_id):
            _raise_http_exception("Uploaded document is not extracted yet.", status_code=400)

        if doc_obj.extracted_file_paths is None and await doc_service.check_job_status(doc_obj.job_id):
            extracted_file_paths = await doc_service.get_extracted_file_paths(doc_obj.job_id)
            await doc_service.update(item_id=doc_obj.id, data={"extracted_file_paths": extracted_file_paths})
            doc_obj = await doc_service.get(id)
        
        extracted_file_paths: dict = doc_obj.extracted_file_paths
        if result_type not in extracted_file_paths:
            _raise_http_exception("Extracted file does not exit.", status_code=400)
        extracted_file_path = extracted_file_paths[result_type]
        return await doc_service.get_presigned_url(extracted_file_path)
