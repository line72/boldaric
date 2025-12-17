"""add_category_to_stations

Revision ID: 62f112c1aff4
Revises: [generated_revision_id]
Create Date: 2025-12-17 09:45:00.986673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62f112c1aff4'
down_revision: Union[str, None] = '[generated_revision_id]'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the category enumeration type
    category_enum = sa.Enum('default', 'mood', 'genre', 'old', name='station_category')
    category_enum.create(op.get_bind())
    
    # Add category column to stations table with default value 'default'
    op.add_column(
        "stations",
        sa.Column(
            "category", 
            sa.Enum('default', 'mood', 'genre', 'old', name='station_category'), 
            nullable=False, 
            default='default',
            server_default='default'
        ),
    )


def downgrade() -> None:
    # Remove the category column
    op.drop_column("stations", "category")
    
    # Drop the enumeration type
    sa.Enum(name='station_category').drop(op.get_bind())
