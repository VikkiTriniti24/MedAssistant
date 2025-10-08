"""add audit and rate limit tables

Revision ID: add_audit_rate_limit
Revises: 
Create Date: 2025-10-02 17:05:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_audit_rate_limit'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rate_limit_hits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_rate_limit_hits_key', 'rate_limit_hits', ['key'])
    op.create_index('ix_rate_limit_hits_key_created', 'rate_limit_hits', ['key', 'created_at'])

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('method', sa.String(length=16), nullable=False),
        sa.Column('path', sa.String(length=255), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('remote_addr', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_audit_logs_path', 'audit_logs', ['path'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade():
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_path', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('ix_rate_limit_hits_key_created', table_name='rate_limit_hits')
    op.drop_index('ix_rate_limit_hits_key', table_name='rate_limit_hits')
    op.drop_table('rate_limit_hits')
