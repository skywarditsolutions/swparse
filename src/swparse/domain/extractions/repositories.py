from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from swparse.db.models import Extraction


class ExtractionRepository(SQLAlchemyAsyncRepository[Extraction]):
    """Extraction SQLAlchemy Repository."""

    model_type = Extraction
