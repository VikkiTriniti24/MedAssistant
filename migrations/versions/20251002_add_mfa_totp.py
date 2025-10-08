"""add mfa totp

Revision ID: add_mfa_totp
Revises: add_user_preferences
Create Date: 2025-10-02 19:25:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_mfa_totp'
down_revision = 'add_user_preferences'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'mfa_totp_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('secret', sa.String(length=64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_mfa_totp_user', 'mfa_totp_configs', ['user_id'])


def downgrade():
    op.drop_index('ix_mfa_totp_user', table_name='mfa_totp_configs')
    op.drop_table('mfa_totp_configs')
