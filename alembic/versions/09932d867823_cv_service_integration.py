"""cv_service_integration

Revision ID: 09932d867823
Revises: ccea8191d3dd
Create Date: 2026-10-31 03:07:04.232660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09932d867823'
down_revision: Union[str, Sequence[str], None] = 'ccea8191d3dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with CV microservice integration columns and cv_events table."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cv_job_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('source_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('camera_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('required_equipment', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('cv_status', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_jobs_cv_job_id'), ['cv_job_id'], unique=True)

    op.create_table(
        'cv_events',
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=True),
        sa.Column('cv_job_id', sa.String(length=100), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('outcome', sa.String(length=50), server_default='accepted', nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('event_id'),
    )
    with op.batch_alter_table('cv_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cv_events_cv_job_id'), ['cv_job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cv_events_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cv_events_type'), ['type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cv_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cv_events_type'))
        batch_op.drop_index(batch_op.f('ix_cv_events_job_id'))
        batch_op.drop_index(batch_op.f('ix_cv_events_cv_job_id'))

    op.drop_table('cv_events')

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_jobs_cv_job_id'))
        batch_op.drop_column('finished_at')
        batch_op.drop_column('cv_status')
        batch_op.drop_column('required_equipment')
        batch_op.drop_column('camera_name')
        batch_op.drop_column('source_type')
        batch_op.drop_column('cv_job_id')
