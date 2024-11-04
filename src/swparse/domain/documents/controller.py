from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
from typing import TYPE_CHECKING, Annotated, Literal, TypeVar

import httpx
import pandas as pd
import structlog
from litestar import Controller, get, post
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.pagination import OffsetPagination
from litestar.params import Body
from litestar.repository.filters import CollectionFilter, LimitOffset
from litestar.response import File
from s3fs import S3FileSystem

from swparse.config.app import settings
from swparse.db.models import ContentType, User
from swparse.db.models.document import Document as DocumentModel
from swparse.domain.accounts.guards import requires_active_user
from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.schemas import Document
from swparse.domain.documents.services import DocumentService
from swparse.domain.swparse.schemas import JobStatus
from swparse.domain.swparse.utils import change_file_ext, extract_tables_from_html, get_file_name, save_file_s3

from . import urls

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter


logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])

MINIO_ROOT_USER = settings.storage.ROOT_USER
MINIO_ROOT_PASSWORD = settings.storage.ROOT_PASSWORD
BUCKET = settings.storage.BUCKET


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
        self,
        doc_service: DocumentService,
        limit_offset: LimitOffset,
        current_user: User,
    ) -> OffsetPagination[Document]:
        """List documents."""
        user_id = current_user.id
        filters = [
            CollectionFilter("user_id", values=[user_id]),
            limit_offset,
        ]
        docs, total = await doc_service.list_and_count(
            *filters,
            order_by=[("updated_at", True)],
        )

        return doc_service.to_schema(docs,  total=total, filters=filters, schema_type=Document)

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

        if db_obj.extracted_file_paths is None:
            try:
                if await doc_service.check_job_status(db_obj.job_id):
                    extracted_file_paths = await doc_service.get_extracted_file_paths(db_obj.job_id)
                    db_obj = await doc_service.update(item_id=db_obj.id, data={"extracted_file_paths": extracted_file_paths})

            except Exception as e:
                logger.error(f"Failed to retrieve the extracted file {e}")
                _raise_http_exception(detail=f"Failed to retrieve the extracted file {e}", status_code=404)

        return doc_service.to_schema(db_obj, schema_type=Document)

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
        content = await data.read()
        url = f"{os.environ.get('APP_URL')}/api/parsing/upload"  # URL of the upload_and_parse_que endpoint
        api_key = os.environ.get("PARSER_API_KEY")
        api_key_header = os.environ.get("PARSER_API_HEADER")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    files={"data": (data.filename, data.file, data.content_type)},
                    headers={
                        "Content-Type": "multipart/form-data; boundary=0xc0d3kywt;",
                        f"{api_key_header}": f"{api_key}",
                    },
                )
            except NotAuthorizedException as err:
                raise NotAuthorizedException(detail=err.detail, status_code=403)
            except Exception as err:
                raise HTTPException(detail="Document upload failed", status_code=500)
        stats = JobStatus(**(response.json()))
        file_size = len(content)
        document= await doc_service.create(
            DocumentModel(
                file_name=data.filename,
                file_size=file_size,
                file_path=stats.s3_url,
                user_id=current_user.id,
                job_id=stats.id,
            ),
        )

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
    ) -> File | None:
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
        return None

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
        result_type: str = "markdown",
        image_key: str | None = None,
    ) -> str | None:
        db_obj = await doc_service.get(id)
        if not db_obj:
            _raise_http_exception(detail=f"Document {id} is not found", status_code=404)

        if db_obj.extracted_file_paths is None:
            if not await doc_service.check_job_status(db_obj.job_id):
                _raise_http_exception("Uploaded document has not extracted yet.", status_code=400)

            extracted_file_paths = await doc_service.get_extracted_file_paths(db_obj.job_id)
            db_obj = await doc_service.update(item_id=db_obj.id, data={"extracted_file_paths": extracted_file_paths})


        s3fs = S3FileSystem(
            endpoint_url=settings.storage.ENDPOINT_URL,
            key=MINIO_ROOT_USER,
            secret=MINIO_ROOT_PASSWORD,
            use_ssl=False,
        )
        if result_type not in extracted_file_paths:

            # advanced extraction content type
            if result_type not in (ContentType.TABLE.value, ContentType.MARKDOWN_TABLE.value):
                # Extracted file type does not exit
                return None
            # Extracting table from the existing HTML file path
            table_file_path = extracted_file_paths.get(ContentType.TABLE.value)

            if table_file_path is None:
                html_file_path = extracted_file_paths.get(ContentType.HTML.value)
                if html_file_path is None:
                    _raise_http_exception("HTML file hasn't extracted", status_code=404)

                html_tables = extract_tables_from_html(s3fs, html_file_path)
                if html_tables is None:
                    # the file doesn't has any tables
                    return ""
                result_html = "<br><br>".join(html_tables)
                file_name = get_file_name(html_file_path)
                html_file_name = change_file_ext(file_name, "html")
                tbl_file_path = save_file_s3(s3fs, html_file_name, result_html)
                extracted_file_paths[ContentType.TABLE.value] = tbl_file_path

            if result_type == ContentType.MARKDOWN_TABLE.value:
                with s3fs.open(table_file_path, "r") as f:
                    html_content = f.read()

                dfs = pd.read_html(html_content)
                markdown_tbls = ""
                for i, df in enumerate(dfs):
                    markdown_tbls += f"## Table {i + 1}\n\n"
                    markdown_tbls += df.to_markdown()
                    markdown_tbls += "\n\n"

                file_name = get_file_name(table_file_path)
                md_tbl_file_name = change_file_ext(file_name, "html")
                md_tbl_file_path = save_file_s3(s3fs, md_tbl_file_name, markdown_tbls)
                extracted_file_paths[ContentType.MARKDOWN_TABLE.value] = md_tbl_file_path

            await doc_service.update(item_id=db_obj.id, data={"extracted_file_paths": extracted_file_paths})

        extracted_file_path = extracted_file_paths[result_type]

        if result_type == ContentType.IMAGES.value:
            if not image_key:
                _raise_http_exception("image_key is required", status_code=400)
            images = json.loads(extracted_file_path)
            image_path = images.get(image_key)
            if image_path:
                with s3fs.open(image_path, "rb") as f:
                    b64_bytes = base64.b64encode(f.read())
                    return b64_bytes.decode("ascii")
            else:
                _raise_http_exception("Image not found", status_code=404)

        with s3fs.open(extracted_file_path, "rb") as f:
            content: bytes = f.read()

        return content.decode(encoding="utf-8", errors="ignore")
