from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, TypeVar

import structlog
from litestar import Controller, get
from litestar.di import Provide
from litestar.exceptions import HTTPException

from swparse.domain.extractions.dependencies import provide_extraction_service
from swparse.domain.extractions.schemas import Extraction
from swparse.domain.extractions.services import ExtractionService

from .urls import EXTRACTION_DETAIL, EXTRACTION_LIST

if TYPE_CHECKING:
    from uuid import UUID

    from advanced_alchemy.filters import FilterTypes
    from advanced_alchemy.service import OffsetPagination
    from litestar.params import Dependency, Parameter


logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])


def _raise_http_exception(detail: str, status_code: int) -> None:
    raise HTTPException(detail=detail, status_code=status_code)


class ExtractionController(Controller):
    tags = ["extractions"]
    dependencies = {"extraction_service": Provide(provide_extraction_service)}
    signature_namespace = {"extractionService": ExtractionService}
    dto = None
    return_dto = None

    @get(
        operation_id="ListExtractions",
        name="extractions:list",
        summary="List extractions",
        description="Retrieve the extraction of the user_id.",
        path=EXTRACTION_LIST,
    )
    async def list_extractions(
        self,
        extraction_service: ExtractionService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[Extraction]:
        """List extractions."""
        results, total = await extraction_service.list_and_count(*filters)
        return extraction_service.to_schema(data=results, total=total, schema_type=Extraction, filters=filters)

    @get(
        operation_id="GetExtraction",
        name="extractions:get",
        path=EXTRACTION_DETAIL,
        summary="Retrieve the details of a extraction.",
    )
    async def get_extraction(
        self,
        extraction_service: ExtractionService,
        id: Annotated[
            UUID,
            Parameter(
                title="extraction ID",
                description="The extraction to retrieve.",
            ),
        ],
    ) -> Extraction:
        """Get a extraction."""
        db_obj = await extraction_service.get(id)
        if db_obj is None:
            _raise_http_exception(detail=f"Extraction id {id} not found", status_code=404)
        return extraction_service.to_schema(db_obj, schema_type=Extraction)
