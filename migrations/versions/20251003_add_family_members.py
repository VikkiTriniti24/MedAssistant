"""add family members table

Revision ID: 20251003_add_family_members
Revises: 20251003_add_emergency_contacts
Create Date: 2025-10-03 01:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_add_family_members"
down_revision = "20251003_add_emergency_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("relationship", sa.String(length=64), nullable=False),
        sa.Column("birthdate", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("share_preferences", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_index("ix_family_members_profile", "family_members", ["profile_id"])
    op.create_index("ix_family_profile_relationship", "family_members", ["profile_id", "relationship"])


def downgrade() -> None:
    op.drop_index("ix_family_profile_relationship", table_name="family_members")
    op.drop_index("ix_family_members_profile", table_name="family_members")
    op.drop_table("family_members")
