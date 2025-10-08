"""add emergency contacts table

Revision ID: 20251003_add_emergency_contacts
Revises: 20251003_add_brand_synonyms
Create Date: 2025-10-03 01:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_add_emergency_contacts"
down_revision = "20251003_add_brand_synonyms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emergency_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("relationship", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_index("ix_emergency_contacts_profile", "emergency_contacts", ["profile_id"])
    op.create_index("ix_emergency_profile_primary", "emergency_contacts", ["profile_id", "is_primary"])


def downgrade() -> None:
    op.drop_index("ix_emergency_profile_primary", table_name="emergency_contacts")
    op.drop_index("ix_emergency_contacts_profile", table_name="emergency_contacts")
    op.drop_table("emergency_contacts")
