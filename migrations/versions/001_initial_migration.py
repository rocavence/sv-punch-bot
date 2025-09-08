"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slack_user_id', sa.String(length=50), nullable=False),
        sa.Column('slack_username', sa.String(length=100), nullable=True),
        sa.Column('slack_display_name', sa.String(length=100), nullable=True),
        sa.Column('slack_real_name', sa.String(length=100), nullable=True),
        sa.Column('slack_email', sa.String(length=120), nullable=True),
        sa.Column('slack_avatar_url', sa.String(length=500), nullable=True),
        sa.Column('internal_real_name', sa.String(length=100), nullable=False),
        sa.Column('department', sa.String(length=50), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=True, default='user'),
        sa.Column('standard_hours', sa.Integer(), nullable=True, default=8),
        sa.Column('timezone', sa.String(length=50), nullable=True, default='Asia/Taipei'),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('slack_data_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_slack_user_id'), 'users', ['slack_user_id'], unique=True)

    # Create attendance_records table
    op.create_table('attendance_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_auto', sa.Boolean(), nullable=True, default=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attendance_records_id'), 'attendance_records', ['id'], unique=False)

    # Create leave_records table
    op.create_table('leave_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('leave_type', sa.String(length=50), nullable=True, default='vacation'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, default='approved'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leave_records_id'), 'leave_records', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leave_records_id'), table_name='leave_records')
    op.drop_table('leave_records')
    op.drop_index(op.f('ix_attendance_records_id'), table_name='attendance_records')
    op.drop_table('attendance_records')
    op.drop_index(op.f('ix_users_slack_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')