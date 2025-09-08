"""Add workspace support for multi-tenant architecture

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workspaces table
    op.create_table('workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slack_team_id', sa.String(length=20), nullable=False),
        sa.Column('team_name', sa.String(length=100), nullable=False),
        sa.Column('team_domain', sa.String(length=100), nullable=True),
        sa.Column('bot_token', sa.String(length=200), nullable=False),
        sa.Column('bot_user_id', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('installed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workspaces_id'), 'workspaces', ['id'], unique=False)
    op.create_index(op.f('ix_workspaces_slack_team_id'), 'workspaces', ['slack_team_id'], unique=True)

    # Add workspace_id to users table
    op.add_column('users', sa.Column('workspace_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'users', 'workspaces', ['workspace_id'], ['id'])
    
    # Drop the old unique constraint on slack_user_id
    op.drop_index('ix_users_slack_user_id', table_name='users')
    
    # Create new composite unique constraint for slack_user_id + workspace_id
    op.create_index(op.f('ix_users_slack_user_id'), 'users', ['slack_user_id'], unique=False)
    op.create_unique_constraint('uix_user_workspace', 'users', ['slack_user_id', 'workspace_id'])


def downgrade() -> None:
    # Remove composite unique constraint
    op.drop_constraint('uix_user_workspace', 'users', type_='unique')
    op.drop_index(op.f('ix_users_slack_user_id'), table_name='users')
    
    # Restore old unique constraint
    op.create_index('ix_users_slack_user_id', 'users', ['slack_user_id'], unique=True)
    
    # Remove workspace_id column and foreign key
    op.drop_constraint(None, 'users', type_='foreignkey')
    op.drop_column('users', 'workspace_id')
    
    # Drop workspaces table
    op.drop_index(op.f('ix_workspaces_slack_team_id'), table_name='workspaces')
    op.drop_index(op.f('ix_workspaces_id'), table_name='workspaces')
    op.drop_table('workspaces')