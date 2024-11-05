# type: ignore
"""make extracted_file_paths non nullable

Revision ID: d73e67ade15d
Revises: d3ec098c01e1
Create Date: 2024-11-05 06:20:24.743211+00:00

"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING
import base64

import sqlalchemy as sa
from alembic import op
from advanced_alchemy.types import EncryptedString, EncryptedText, GUID, ORA_JSONB, DateTimeUTC
from sqlalchemy import Text  # noqa: F401
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["downgrade", "upgrade", "schema_upgrades", "schema_downgrades", "data_upgrades", "data_downgrades"]

sa.GUID = GUID
sa.DateTimeUTC = DateTimeUTC
sa.ORA_JSONB = ORA_JSONB
sa.EncryptedString = EncryptedString
sa.EncryptedText = EncryptedText

# revision identifiers, used by Alembic.
revision = "d73e67ade15d"
down_revision = "d3ec098c01e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        with op.get_context().autocommit_block():
            data_upgrades()
            schema_upgrades()


def downgrade() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        with op.get_context().autocommit_block():
            schema_downgrades()
            data_downgrades()


def schema_upgrades() -> None:
    """schema upgrade migrations go here."""
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.alter_column(
            "extracted_file_paths", existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=False
        )


def schema_downgrades() -> None:
    """schema downgrade migrations go here."""
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.alter_column(
            "extracted_file_paths", existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True
        )


def data_upgrades() -> None:
    """Add any optional data upgrade migrations here!"""
    op.execute(
        "UPDATE documents SET extracted_file_paths = to_jsonb(encode(convert_to('{}'::text, 'UTF8'), 'base64')::text) WHERE extracted_file_paths IS NULL"
    )


def data_downgrades() -> None:
    """Add any optional data downgrade migrations here!"""
