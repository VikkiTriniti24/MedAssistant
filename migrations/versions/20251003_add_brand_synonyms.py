"""add brand synonyms column

Revision ID: 20251003_add_brand_synonyms
Revises: 20251003_add_side_effects
Create Date: 2025-10-03 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_add_brand_synonyms"
down_revision = "20251003_add_side_effects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drugs", sa.Column("brand_synonyms", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("drugs", "brand_synonyms")
