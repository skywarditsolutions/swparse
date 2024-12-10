# type: ignore
"""Updted the status field of api_key to enum

Revision ID: 6edf860d5793
Revises: ce4f4d09873f
Create Date: 2024-12-10 08:03:59.605740+00:00

"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from advanced_alchemy.types import EncryptedString, EncryptedText, GUID, ORA_JSONB, DateTimeUTC
from sqlalchemy import Text  
from sqlalchemy.dialects.postgresql import ENUM

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["downgrade", "upgrade", "schema_upgrades", "schema_downgrades", "data_upgrades", "data_downgrades"]

sa.GUID = GUID
sa.DateTimeUTC = DateTimeUTC
sa.ORA_JSONB = ORA_JSONB
sa.EncryptedString = EncryptedString
sa.EncryptedText = EncryptedText

# revision identifiers, used by Alembic.
revision = '6edf860d5793'
down_revision = 'ce4f4d09873f'
branch_labels = None
depends_on = None

status_enum = ENUM('ACTIVE', 'REVOKED', 'EXPIRED', name='apikeystatus', create_type=False)

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
    """Schema upgrade migrations go here."""
    # Create the ENUM type
    status_enum.create(op.get_bind(), checkfirst=True)
 
    op.alter_column(
        'api_keys',   
        'status',   
        existing_type=sa.VARCHAR(),  
        type_=status_enum,  
        postgresql_using="status::apikeystatus"  
    )

def schema_downgrades() -> None:
    """Schema downgrade migrations go here."""
 
    op.alter_column(
        'api_keys',
        'status',
        existing_type=status_enum,
        type_=sa.VARCHAR(),
        postgresql_using="status::TEXT"
    )

 
    status_enum.drop(op.get_bind(), checkfirst=True)


def data_upgrades() -> None:
    """Add any optional data upgrade migrations here."""
    op.execute("UPDATE api_keys SET status='ACTIVE' WHERE status='active'")
    op.execute("UPDATE api_keys SET status='REVOKED' WHERE status='revoked'")
    op.execute("UPDATE api_keys SET status='EXPIRED' WHERE status='expired'")

def data_downgrades() -> None:
    """Add any optional data downgrade migrations here."""
    op.execute("UPDATE api_keys SET status='active' WHERE status='ACTIVE'")
    op.execute("UPDATE api_keys SET status='revoked' WHERE status='REVOKED'")
    op.execute("UPDATE api_keys SET status='expired' WHERE status='EXPIRED'")
