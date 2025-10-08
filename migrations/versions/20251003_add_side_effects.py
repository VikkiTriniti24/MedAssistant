"""add side effects table

Revision ID: 20251003_add_side_effects
Revises: 20251003_add_medication_schedule
Create Date: 2025-10-03 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_add_side_effects"
down_revision = "20251003_add_medication_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "side_effects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drug_id", sa.Integer(), sa.ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("severity IN ('mild','moderate','severe')", name="ck_side_effects_severity"),
    )

    op.create_index("ix_side_effects_drug", "side_effects", ["drug_id"])
    op.create_index("ix_side_effects_category", "side_effects", ["category"])


def downgrade() -> None:
    op.drop_index("ix_side_effects_category", table_name="side_effects")
    op.drop_index("ix_side_effects_drug", table_name="side_effects")
    op.drop_table("side_effects")
