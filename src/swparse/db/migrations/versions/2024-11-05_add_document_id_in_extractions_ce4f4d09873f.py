# type: ignore
"""add document_id in extractions

Revision ID: ce4f4d09873f
Revises: d73e67ade15d
Create Date: 2024-11-05 06:57:42.095789+00:00

"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from advanced_alchemy.types import EncryptedString, EncryptedText, GUID, ORA_JSONB, DateTimeUTC
from sqlalchemy import Text  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["downgrade", "upgrade", "schema_upgrades", "schema_downgrades", "data_upgrades", "data_downgrades"]

sa.GUID = GUID
sa.DateTimeUTC = DateTimeUTC
sa.ORA_JSONB = ORA_JSONB
sa.EncryptedString = EncryptedString
sa.EncryptedText = EncryptedText

# revision identifiers, used by Alembic.
revision = "ce4f4d09873f"
down_revision = "d73e67ade15d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        with op.get_context().autocommit_block():
            schema_upgrades()
            data_upgrades()


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        with op.get_context().autocommit_block():
            data_downgrades()
            schema_downgrades()


def schema_upgrades() -> None:
    """schema upgrade migrations go here."""
    with op.batch_alter_table("extraction", schema=None) as batch_op:
        batch_op.add_column(sa.Column("document_id", sa.GUID(length=16), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_extraction_document_id_documents"), "documents", ["document_id"], ["id"], ondelete="cascade"
        )


def schema_downgrades() -> None:
    """schema downgrade migrations go here."""
    with op.batch_alter_table("extraction", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_extraction_document_id_documents"), type_="foreignkey")
        batch_op.drop_column("document_id")


def data_upgrades() -> None:
    """Add any optional data upgrade migrations here!"""


def data_downgrades() -> None:
    """Add any optional data downgrade migrations here!"""
