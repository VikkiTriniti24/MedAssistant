"""add email verification

Revision ID: add_email_verification
Revises: add_password_reset
Create Date: 2025-10-02 18:15:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_email_verification'
down_revision = 'add_password_reset'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('users', 'email_verified', server_default=None)
    op.alter_column('users', 'is_active', server_default=None)

    op.create_table(
        'email_verification_tokens',
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
    op.create_index('ix_email_verification_tokens_token', 'email_verification_tokens', ['token'])
    op.create_index('ix_email_verification_user_created', 'email_verification_tokens', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_email_verification_user_created', table_name='email_verification_tokens')
    op.drop_index('ix_email_verification_tokens_token', table_name='email_verification_tokens')
    op.drop_table('email_verification_tokens')

    with op.batch_alter_table('users') as batch:
        batch.drop_column('is_active')
        batch.drop_column('email_verified')
