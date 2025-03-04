from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
from typing import TYPE_CHECKING, Annotated, Literal, TypeVar

import pandas as pd
import structlog
from litestar import Controller, get, post
from litestar.di import Provide
from litestar.exceptions import HTTPException
from litestar.pagination import OffsetPagination
from litestar.repository.filters import CollectionFilter, LimitOffset
from litestar.response import File

from saq import Job, Queue

from swparse.config.app import settings
from swparse.db.models import ContentType, User
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.schemas import Document, ExtractAdvancedTablesBody
from swparse.domain.documents.services import DocumentService
from swparse.domain.extractions.dependencies import provide_extraction_serivice
from swparse.domain.extractions.services import ExtractionService
from swparse.domain.swparse.schemas import JobStatus, Status
from swparse.domain.swparse.utils import (
    change_file_ext,
    extract_tables_from_html,
    get_file_name,
    parse_table_query,
    save_file,
    read_file
)

from . import urls

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter

SWPARSE_URL = os.environ.get("APP_URL")
logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

queue = Queue.from_url(settings.worker.REDIS_HOST, name="swparse")

SWPARSE_API_KEY =settings.app.PARSER_API_KEY
MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
BUCKET = settings.storage.BUCKET


class DocumentController(Controller):
    tags = ["Documents"]
    dependencies = {
        "doc_service": Provide(provide_document_service),
        "extraction_service": Provide(provide_extraction_serivice),
    }
    signature_namespace = {
        "DocumentService": DocumentService,
        "ExtractionService": ExtractionService,
    }

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
        filters = [
            CollectionFilter("user_id", values=[current_user.id]),
            limit_offset,
        ]
        docs, total = await doc_service.list_and_count(
            *filters,
            order_by=[("updated_at", True)],
        )

        return doc_service.to_schema(docs, total=total, filters=filters, schema_type=Document)

    @get(
        operation_id="GetDocument",
        name="documents:get",
        path=urls.DOCUMENT_DETAIL,
    )
    async def get_document(
        self,
        doc_service: DocumentService,
        extraction_service: ExtractionService,
        id: Annotated[
            UUID,
            Parameter(
                title="Document ID",
                description="The document to retrieve.",
            ),
        ],
        current_user: User,
    ) -> Document:
        """Get a Document."""
        document = await doc_service.get_one_or_none(
            CollectionFilter("id", [id]),
            CollectionFilter("user_id", [current_user.id]),
        )
        if not document:
            raise HTTPException(detail=f"Document {id} is not found", status_code=404)

        extraction = await extraction_service.get_one_or_none(CollectionFilter("document_id", [document.id]))
        if extraction:
            await extraction_service.delete(extraction.id)

        return doc_service.to_schema(document, schema_type=Document)

    @get(path=urls.DOCUMENT_CONTENT, guards=[requires_active_user])
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
        current_user: User,
    ) -> File:
        document = await doc_service.get_one_or_none(
            CollectionFilter("id", [id]),
            CollectionFilter("user_id", [current_user.id]),
        )

        if not document:
            raise HTTPException(detail=f"Document {id} is not found", status_code=404)

        s3_url = document.file_path
        try:
            content: bytes = await read_file(s3_url)
            mime_type, _ = mimetypes.guess_type(s3_url)
            extension = s3_url.split(".")[-1]

            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                return File(
                    content_disposition_type="attachment",
                    path=tmp_file.name,
                    filename=document.file_name,
                    media_type=mime_type,
                )

        except Exception as e:
            raise HTTPException(f"Failed to read document: {e!s}", status_code=500)

    @get(path=urls.EXTRACTED_CONTENT, guards=[requires_active_user])
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
        current_user: User,
        result_type: str = "markdown",
        image_key: str | None = None,
    ) -> str | None:
        document = await doc_service.get_one_or_none(
            CollectionFilter("id", [id]),
            CollectionFilter("user_id", [current_user.id]),
        )

        if not document:
            raise HTTPException(detail=f"Document {id} is not found", status_code=404)

        extracted_file_paths = document.extracted_file_paths

 
        if result_type not in extracted_file_paths:

            if result_type not in (ContentType.TABLE.value, ContentType.MARKDOWN_TABLE.value):
                return None
            table_file_path = extracted_file_paths.get(ContentType.TABLE.value)

            if table_file_path is None:
                html_file_path = extracted_file_paths.get(ContentType.HTML.value)
                if html_file_path is None:
                    raise HTTPException("HTML file hasn't extracted", status_code=404)

                html_tables = await extract_tables_from_html(html_file_path)
                if html_tables is None:
                    # the file doesn't has any tables
                    return ""
                result_html = "<br><br>".join(html_tables)
                file_name = await get_file_name(html_file_path)
                html_file_name = await change_file_ext(file_name, "html")
                tbl_file_path = await save_file(html_file_name, result_html)
                extracted_file_paths[ContentType.TABLE.value] = tbl_file_path

            if result_type == ContentType.MARKDOWN_TABLE.value:
                
                html_content = await read_file(table_file_path)
                dfs = pd.read_html(html_content)
                
                markdown_tbls = ""
                for i, df in enumerate(dfs):
                    markdown_tbls += f"## Table {i + 1}\n\n"
                    markdown_tbls += df.to_markdown()
                    markdown_tbls += "\n\n"

                file_name = await get_file_name(table_file_path)
                md_tbl_file_name = await change_file_ext(file_name, "html")
                md_tbl_file_path = await save_file(md_tbl_file_name, markdown_tbls)
                extracted_file_paths[ContentType.MARKDOWN_TABLE.value] = md_tbl_file_path

            await doc_service.update(item_id=document.id, data={"extracted_file_paths": extracted_file_paths})

        extracted_file_path = extracted_file_paths[result_type]

        if result_type == ContentType.IMAGES.value:
            if not image_key:
                raise HTTPException(detail="image_key is required", status_code=400)
         
            image_json_str = await read_file(extracted_file_path)

            images = json.loads(image_json_str)
            image_path = images.get(image_key.lower())
            if image_path:
                content = await read_file(image_path)
                b64_bytes = base64.b64encode(content)
                return b64_bytes.decode("ascii")
            else:
                raise HTTPException("Image not found", status_code=404)
       
        content: bytes =  await read_file(extracted_file_path)

        return content.decode(encoding="utf-8", errors="ignore")

    @post(path=urls.EXTRACT_ADVANCED_TABLES)
    async def extract_advanced_tables(
        self,
        doc_service: DocumentService,
        document_id: Annotated[
            UUID,
            Parameter(
                title="Document ID",
                description="The document to retrieve.",
            ),
        ],
        data: ExtractAdvancedTablesBody,
        current_user: User,
    ) -> JobStatus:
        document = await doc_service.get_one_or_none(
            CollectionFilter("id", [document_id]),
            CollectionFilter("user_id", [current_user.id]),
        )
        if not document:
            raise HTTPException(detail="Document not found", status_code=404)

        try:
            result = parse_table_query(data.query)
        except:
            raise HTTPException(detail="Invalid query", status_code=400)
        
        md_path = document.extracted_file_paths["markdown"]
        markdown_content = await read_file(md_path)

        job = await queue.enqueue(
            Job(
                "extract_advanced_tables",
                kwargs={
                    "table_query": result["tables"],
                    "markdown": markdown_content,
                },
                timeout=0,
            )
        )

        return JobStatus(id=job.id, status=Status[job.status])

    @get(path=urls.CHECK_ADVANCED_TABLES)
    async def check_advanced_table_extraction(
        self,
        doc_service: DocumentService,
        document_id: Annotated[
            UUID,
            Parameter(
                title="Document ID",
                description="The document to retrieve.",
            ),
        ],
        job_id: str,
        current_user: User,
    ) -> dict[str, str]:
        # TODO: store in db
        document = await doc_service.get_one_or_none(
            CollectionFilter("id", [document_id]),
            CollectionFilter("user_id", [current_user.id]),
        )
        if not document:
            raise HTTPException(detail="Document not found", status_code=404)

        job_key = queue.job_key_from_id(job_id)
        job = await queue.job(job_key)

        if not job:
            raise HTTPException(detail="Job not found", status_code=404)

        if job.status == "complete":
            return job.result
        elif job.status in ["failed", "aborted"]:
            raise HTTPException(detail="Job Error", status_code=500)

        return {}
