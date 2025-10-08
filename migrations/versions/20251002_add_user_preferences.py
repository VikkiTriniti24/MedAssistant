"""add user preferences

Revision ID: add_user_preferences
Revises: add_email_verification
Create Date: 2025-10-02 19:10:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_preferences'
down_revision = 'add_email_verification'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('language', sa.String(length=16), nullable=False, server_default='en'),
        sa.Column('notify_email', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_push', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notify_sms', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_check_constraint(
        'ck_user_pref_language',
        'user_preferences',
        "language IN ('en','de','es','fr','it')"
    )


def downgrade():
    op.drop_constraint('ck_user_pref_language', 'user_preferences', type_='check')
    op.drop_table('user_preferences')
