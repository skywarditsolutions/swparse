from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from swparse.db.models import Document


class DocumentRepository(SQLAlchemyAsyncRepository[Document]):
    """Document SQLAlchemy Repository."""

    model_type = Document
