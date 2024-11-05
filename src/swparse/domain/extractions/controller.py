from __future__ import annotations

import mimetypes
import os
from typing import Annotated
from uuid import UUID

import httpx
import structlog
from litestar import Controller, delete, get, post
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.pagination import OffsetPagination
from litestar.params import Body
from litestar.repository.filters import CollectionFilter, LimitOffset
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.db.models.document import Document as DocumentModel
from swparse.db.models.extraction import Extraction as ExtractionModel
from swparse.db.models.extraction import ExtractionStatus
from swparse.db.models.user import User
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.services import DocumentService
from swparse.domain.swparse.schemas import JobStatus, Status

from .dependencies import provide_extraction_serivice
from .schemas import Extraction
from .services import ExtractionService

logger = structlog.get_logger()

SWPARSE_URL = f"{os.environ.get('APP_URL')}"
SWPARSE_API_KEY = os.environ.get("PARSER_API_KEY")
SWPARSE_API_HEADER = os.environ.get("PARSER_API_HEADER")
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
BUCKET = settings.storage.BUCKET

class ExtractionController(Controller):
    tags = ["Extractions"]
    dependencies = {
        "extraction_service": Provide(provide_extraction_serivice),
        "document_service": Provide(provide_document_service),
    }
    signature_namespace = {
        "ExtractionService": ExtractionService,
        "DocumentSerivce": DocumentService,
    }
    guards = [requires_active_user]
    dto = None
    return_dto = None
    path = "/api/extractions"

    @get(
        operation_id="ListExtractions",
        name="extractions:list",
        description="List all extractions of a user",
        path="",
    )
    async def list_extractions(
        self,
        extraction_service: ExtractionService,
        current_user: User,
        limit_offset: LimitOffset,
    ) -> OffsetPagination[Extraction]:
        filters = [
            CollectionFilter("user_id", [current_user.id]),
            limit_offset,
        ]
        results, count = await extraction_service.list_and_count(*filters)
        return extraction_service.to_schema(data=results, total=count, schema_type=Extraction, filters=filters)

    @post(
        operation_id="CreateExtraction",
        name="extractions:create",
        description="Create an extraction",
        path="",
    )
    async def create_extraction(
        self,
        extraction_service: ExtractionService,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        current_user: User,
    ) -> Extraction:
        content = await data.read()
        job = await extraction_service.create_job(data)

        extraction = await extraction_service.create(
            ExtractionModel(
                file_name=data.filename,
                file_size=len(content),
                file_path=job.s3_url,
                user_id=current_user.id,
                job_id=job.id,
            )
        )
        return extraction_service.to_schema(data=extraction, schema_type=Extraction)

    @get(
        operation_id="CheckExtraction",
        name="extraction:status",
        description="Check the status of an extraction",
        path="/{extraction_id:uuid}",
    )
    async def check_extraction_status(
        self,
        extraction_id: UUID,
        current_user: User,
        extraction_service: ExtractionService,
        document_service: DocumentService,
    ) -> Extraction:
        extraction = await extraction_service.get_one_or_none(
            CollectionFilter("id", [extraction_id]),
            CollectionFilter("user_id", [current_user.id]),
        )
        if not extraction:
            raise HTTPException(detail="Extraction not found", status_code=404)

        if extraction.status in [ExtractionStatus.FAILED, ExtractionStatus.COMPLETE]:
            raise HTTPException(detail="Unsupported by state", status_code=409)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{SWPARSE_URL}/api/parsing/job/{extraction.job_id}",
                    headers={
                        f"{SWPARSE_API_HEADER}": f"{SWPARSE_API_KEY}",
                    },
                )
            except NotAuthorizedException as err:
                raise NotAuthorizedException(detail=err.detail, status_code=403)
            except Exception as err:
                extraction.status = ExtractionStatus.FAILED
                extraction = await extraction_service.update(extraction)
                return extraction_service.to_schema(extraction, schema_type=Extraction)

        job = JobStatus(**(response.json()))

        updated = False

        if job.status == Status.complete:
            extraction.status = ExtractionStatus.COMPLETE
            extracted_file_paths = await extraction_service.get_extracted_file_paths(extraction.job_id)
            document = await document_service.create(
                DocumentModel(
                    file_name=extraction.file_name,
                    file_size=extraction.file_size,
                    file_path=extraction.file_path,
                    user_id=current_user.id,
                    job_id=extraction.job_id,
                    extracted_file_paths=extracted_file_paths,
                )
            )
            extraction.document_id = document.id
            updated = True

        elif job.status == Status.failed:
            extraction.status = ExtractionStatus.FAILED
            updated = True

        if updated:
            extraction = await extraction_service.update(extraction)

        return extraction_service.to_schema(extraction, schema_type=Extraction)

    # TODO
    @post(
        operation_id="RetryExtraction",
        name="extraction:retry",
        description="Retry a failed extraction",
        path="/{extraction_id:uuid}",
    )
    async def retry_extraction(
        self,
        extraction_id: UUID,
        extraction_service: ExtractionService,
        document_service: DocumentService,
        current_user: User,
    ) -> Extraction:
        extraction = await extraction_service.get_one_or_none(
            CollectionFilter("id", [extraction_id]),
            CollectionFilter("user_id", [current_user.id]),
        )
        if not extraction:
            raise HTTPException(detail="Extraction not found", status_code=404)
        if extraction.status != ExtractionStatus.FAILED:
            raise HTTPException(detail="Unsupported by state", status_code=409)

        s3fs = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )

        with s3fs.open(extraction.file_path, "rb") as f:
            content: bytes = f.read()
        content_type, _ = mimetypes.guess_type(url=extraction.file_path) 
        old_file = UploadFile(
            filename=extraction.file_name,
            file_data=content,
            content_type=content_type
            )
        await extraction_service.create_job(old_file)
        extraction.status = ExtractionStatus.PENDING

        return extraction_service.to_schema(extraction, schema_type=Extraction)

    @delete(
        operation_id="DeleteExtraction",
        name="extraction:delete",
        description="Delete an extraction",
        path="/{extraction_id:uuid}",
    )
    async def delete_extraction(
        self,
        extraction_id: UUID,
        current_user: User,
        extraction_service: ExtractionService,
    ) -> None:
        extraction = await extraction_service.get_one_or_none(
            CollectionFilter("id", [extraction_id]),
            CollectionFilter("user_id", [current_user.id]),
        )
        if not extraction:
            raise HTTPException(detail="Extraction not found", status_code=404)

        await extraction_service.delete(extraction.id)
