"""add password reset tokens table

Revision ID: add_password_reset
Revises: add_audit_rate_limit
Create Date: 2025-10-02 17:45:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_password_reset'
down_revision = 'add_audit_rate_limit'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index('ix_password_reset_token', 'password_reset_tokens', ['token'])
    op.create_index('ix_password_reset_user_created', 'password_reset_tokens', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_password_reset_user_created', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_token', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
