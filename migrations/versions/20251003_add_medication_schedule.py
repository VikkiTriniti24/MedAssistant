"""add medication schedules table

Revision ID: 20251003_add_medication_schedule
Revises: add_mfa_totp
Create Date: 2025-10-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251003_add_medication_schedule"
down_revision = "add_mfa_totp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medication_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_medication_id", sa.Integer(), sa.ForeignKey("profile_medications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("schedule_data", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("remind_via_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remind_via_push", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remind_via_sms", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "(end_date IS NULL) OR (start_date IS NULL) OR (start_date <= end_date)",
            name="ck_med_schedule_dates",
        ),
        sa.UniqueConstraint("profile_medication_id", name="ux_med_schedules_medication"),
    )

    op.create_index(
        "ix_med_schedules_medication",
        "medication_schedules",
        ["profile_medication_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_med_schedules_medication", table_name="medication_schedules")
    op.drop_table("medication_schedules")
