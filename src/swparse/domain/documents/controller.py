from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, TypeVar

import structlog
from litestar import Controller, get
from litestar.di import Provide
from litestar.exceptions import HTTPException

from swparse.domain.documents.dependencies import provide_document_service
from swparse.domain.documents.schemas import Document
from swparse.domain.documents.services import DocumentService

from .urls import DOCUMENT_DETAIL, DOCUMENT_LIST

if TYPE_CHECKING:
    from uuid import UUID

    from advanced_alchemy.filters import FilterTypes
    from advanced_alchemy.service import OffsetPagination
    from litestar.params import Dependency, Parameter


logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])


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
        path=DOCUMENT_LIST,
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
        path=DOCUMENT_DETAIL,
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
